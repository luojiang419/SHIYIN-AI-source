import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_macos_tauri_config_builds_app_bundle():
    config = json.loads((ROOT / "src-tauri/tauri.macos.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["active"] is True
    assert config["bundle"]["targets"] == ["app"]
    assert config["bundle"]["macOS"]["minimumSystemVersion"] == "12.0"


def test_macos_build_packages_same_web_skills_and_backend():
    script = (ROOT / "tools/build-macos.sh").read_text(encoding="utf-8")
    for contract in (
        "canvas-backend.spec", "cp -R static", "cp -R skills",
        "prepare-kling-runtime.py", "seedance-2.5/SKILL.md",
        "smoke-macos-bundle.py", "codesign --verify", "hdiutil create",
    ):
        assert contract in script


def test_macos_workflow_is_public_artifact_only_and_dual_architecture():
    workflow = (ROOT / ".github/workflows/build-macos.yml").read_text(encoding="utf-8")
    assert "macos-15-intel" in workflow and "macos-15" in workflow
    assert "Apple-Silicon" in workflow and "Intel" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "secrets." not in workflow
    assert "workflow_dispatch:" in workflow


def test_desktop_runtime_has_platform_specific_updater_and_bundle_paths():
    source = (ROOT / "src-tauri/src/lib.rs").read_text(encoding="utf-8")
    mac_updater = (ROOT / "src-tauri/src/updater_macos.rs").read_text(encoding="utf-8")
    assert '#[path = "updater_macos.rs"]' in source
    assert 'join("Resources")' in source
    assert '"Application Support"' in source
    assert '"canvas-backend.exe"' in source and '"canvas-backend"' in source
    assert "macOS 暂不支持应用内自动替换" in mac_updater
