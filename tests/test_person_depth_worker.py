from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path

import pytest

from person_depth_worker.worker import install_birefnet_inference_compat, validate_trusted_birefnet_code


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_trusted_birefnet_code_accepts_exact_files(tmp_path: Path):
    files = {
        "BiRefNet_config.py": b"trusted config code",
        "birefnet.py": b"trusted model code",
        "config.json": b'{' + b'"auto_map":{}' + b'}',
    }
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)

    validate_trusted_birefnet_code(
        tmp_path,
        {name: digest(content) for name, content in files.items()},
    )


@pytest.mark.parametrize("mode", ["missing", "tampered"])
def test_trusted_birefnet_code_rejects_missing_or_tampered_files(tmp_path: Path, mode: str):
    expected = {"birefnet.py": digest(b"trusted")}
    if mode == "tampered":
        (tmp_path / "birefnet.py").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="缺失|SHA-256 不匹配"):
        validate_trusted_birefnet_code(tmp_path, expected)


def test_candidate_builder_keeps_noncommercial_release_disabled():
    root = Path(__file__).resolve().parents[1]
    builder = (root / "tools" / "build-person-depth-component.ps1").read_text(encoding="utf-8")
    manifest = (root / "canvas_core" / "person_depth_manifest.json").read_text(encoding="utf-8")
    assert "[switch]$AllowNonCommercialModel" in builder
    assert "[switch]$Resume" in builder
    assert "[switch]$KeepBuildDirectories" in builder
    assert "if (-not $AllowNonCommercialModel)" in builder
    assert 'release_status = "candidate"' in builder
    assert "enabled = $false" in builder
    assert 'domestic_url = ""' in builder and 'official_url = ""' in builder
    assert "$Resume -and (Test-Path -LiteralPath $workerExe -PathType Leaf)" in builder
    assert "$file.Target | Select-Object -First 1" in builder
    assert "[pscustomobject][ordered]" in builder
    assert "$Resume -and $runtimeArchiveExists -and $modelsArchiveExists" in builder
    assert "Refusing to clean a path outside the candidate output root" in builder
    assert '"enabled": false' in manifest


def test_birefnet_inference_compat_replaces_training_only_kornia_import():
    previous_package = sys.modules.pop("kornia", None)
    previous_filters = sys.modules.pop("kornia.filters", None)
    try:
        install_birefnet_inference_compat()
        filters = importlib.import_module("kornia.filters")
        with pytest.raises(RuntimeError, match="仅支持推理"):
            filters.laplacian(None, kernel_size=5)
    finally:
        sys.modules.pop("kornia.filters", None)
        sys.modules.pop("kornia", None)
        if previous_package is not None:
            sys.modules["kornia"] = previous_package
        if previous_filters is not None:
            sys.modules["kornia.filters"] = previous_filters


def test_release_smoke_uses_component_manager_download_install_and_worker_smoke():
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "smoke-person-depth-component.py").read_text(encoding="utf-8")
    assert "ThreadingHTTPServer" in source
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in source
    assert 'sys.stdout.reconfigure(encoding="utf-8")' in source
    assert "PersonDepthComponentManager" in source
    assert 'manifest["enabled"] = True' in source
    assert "manager.ensure_now()" in source
    assert "manager.verify_installed(run_smoke=False)" in source


def test_worker_spec_collects_only_required_model_families():
    root = Path(__file__).resolve().parents[1]
    source = (root / "person-depth-worker.spec").read_text(encoding="utf-8")
    assert 'collect_submodules("transformers.models.depth_anything")' in source
    assert 'collect_submodules("transformers.models.dinov2")' in source
    assert '"timm.layers"' in source
    assert '"torchvision.ops.deform_conv"' in source
    assert "collect_all" not in source
    for excluded in ("datasets", "librosa", "torchcodec", "pydub", "kornia", "boto3", "yt_dlp", "bitsandbytes"):
        assert f'"{excluded}"' in source
