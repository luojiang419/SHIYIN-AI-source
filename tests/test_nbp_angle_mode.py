from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = (ROOT / "static/js/canvas-special-nodes.js").read_text(encoding="utf-8")
CLASSIC = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")


def test_nbp_angle_prompt_uses_signed_camera_semantics():
    assert "node.angleYaw" in SHARED
    assert "left is camera-left" in SHARED
    assert "const side = yaw < 0 ? 'camera-left'" in SHARED
    assert "three-quarter view" in SHARED
    assert "Never flip, mirror or rotate Image 1" in SHARED


def test_legacy_azimuth_is_migrated_and_previous_view_is_second_reference():
    assert "node.angleAzimuth = (node.angleYaw + 360) % 360" in SHARED
    assert "reference_images:[{url:source.url" in CLASSIC
    assert "const previous = node?.outputUrl" in CLASSIC
    assert "const previous = Array.isArray(node?.images)" in SMART
    assert "? await runApiGeneration(prompt, refs, runSettings)" in SMART
