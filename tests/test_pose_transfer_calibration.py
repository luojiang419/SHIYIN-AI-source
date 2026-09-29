import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

import main
from canvas_core.pose_calibration import (
    POSE_CALIBRATION_MAX_REGIONS,
    create_pose_calibration_references,
    normalize_pose_calibration,
    pose_calibration_prompt,
)


def calibration(source_url="/assets/input/source.jpg"):
    return {
        "source_url": source_url,
        "regions": [
            {"id": "seam", "name": "斜向拼缝", "x": 0.2, "y": 0.25, "w": 0.3, "h": 0.25},
            {"id": "hem", "name": "喇叭裤脚", "x": 0.55, "y": 0.65, "w": 0.25, "h": 0.2},
        ],
    }


def test_pose_calibration_is_bound_to_the_exact_source_and_normalized():
    result = normalize_pose_calibration(calibration(), "/assets/input/source.jpg")
    assert result["version"] == 1
    assert result["source_url"] == "/assets/input/source.jpg"
    assert [item["name"] for item in result["regions"]] == ["斜向拼缝", "喇叭裤脚"]
    assert result["regions"][0]["w"] == 0.3

    with pytest.raises(ValueError, match="不匹配"):
        normalize_pose_calibration(calibration(), "/assets/input/replaced.jpg")


def test_pose_calibration_rejects_invalid_or_excessive_regions():
    value = calibration()
    value["regions"][0]["x"] = 0.9
    value["regions"][0]["w"] = 0.2
    with pytest.raises(ValueError, match="超出"):
        normalize_pose_calibration(value, value["source_url"])

    value = calibration()
    value["regions"] = value["regions"] * (POSE_CALIBRATION_MAX_REGIONS + 1)
    with pytest.raises(ValueError, match="最多支持"):
        normalize_pose_calibration(value, value["source_url"])


def test_pose_calibration_creates_lossless_context_crops_and_audit(tmp_path):
    source = tmp_path / "source.jpg"
    output = tmp_path / "output"
    Image.new("RGB", (1000, 800), (44, 78, 112)).save(source, quality=95)
    normalized = normalize_pose_calibration(calibration(), calibration()["source_url"])
    refs, audit = create_pose_calibration_references(
        source,
        normalized,
        output,
        lambda path: "/output/" + Path(path).name,
    )

    assert [item["role"] for item in refs] == ["source_calibration", "source_calibration"]
    assert refs[0]["pixel_selection"] == {"x": 200, "y": 200, "width": 300, "height": 200}
    assert audit["status"] == "succeeded"
    crop_file = output / Path(refs[0]["url"]).name
    assert crop_file.is_file()
    with Image.open(crop_file) as crop:
        assert crop.format == "PNG"
        assert crop.size == (390, 260)


def test_pose_calibration_references_are_inserted_after_whole_source(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output"
    Image.new("RGB", (400, 600), (120, 80, 40)).save(source)
    source_url = "/assets/input/source.png"
    normalized = normalize_pose_calibration(calibration(source_url), source_url)
    snapshot = {"operation": "pose_transfer", "options": {"calibration": normalized}}
    references = [
        {"role": "source", "url": source_url},
        {"role": "control_map", "url": "/output/depth.png"},
    ]
    with (
        patch.object(main, "output_file_from_url", return_value=str(source)),
        patch.object(main, "OUTPUT_OUTPUT_DIR", str(output)),
        patch.object(main, "media_url_from_path", side_effect=lambda path: "/output/" + Path(path).name),
    ):
        prepared, prompt, audit = asyncio.run(
            main.prepare_pose_calibration_evidence(snapshot, references, "BASE PROMPT")
        )

    assert [item["role"] for item in prepared] == [
        "source", "source_calibration", "source_calibration", "control_map"
    ]
    assert "CALIBRATED SOURCE EVIDENCE" in prompt
    assert "Image 2 = 斜向拼缝" in prompt
    assert audit["regions"][0]["selection"]["width"] == 120
    assert "版型轮廓" in main.gemini_reference_role_text(prepared[1], 2)


def test_pose_calibration_frontend_contract_is_loaded():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "ecommerce.html").read_text(encoding="utf-8")
    script = (root / "static" / "js" / "ecommerce-pose-calibration.js").read_text(encoding="utf-8")
    ecommerce = (root / "static" / "js" / "ecommerce.js").read_text(encoding="utf-8")

    assert 'id="poseCalibrationDialog"' in html
    assert 'id="poseCalibrationReview"' in html
    assert "ecommerce-pose-calibration.js" in html
    assert "MAX_REGIONS = 4" in script
    assert "original" not in script.lower() or "source" in script.lower()
    assert "window.PoseTransferCalibration?.cardHtml" in ecommerce
    assert "window.PoseTransferCalibration?.syncResult" in ecommerce


def test_pose_calibration_prompt_maps_real_reference_indices():
    source = {"role": "source"}
    first = {"role": "source_calibration", "calibration_region": {"name": "腰头"}}
    second = {"role": "source_calibration", "calibration_region": {"name": "裤脚"}}
    depth = {"role": "control_map"}
    prompt = pose_calibration_prompt([first, second], [source, first, second, depth])
    assert "Image 2 = 腰头" in prompt
    assert "Image 3 = 裤脚" in prompt
