import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_camera_reference_manifest_is_cc0_and_contains_angle_buckets():
    manifest_path = ROOT / 'static/assets/camera-reference/manifest.json'
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert data['source']['license'] == 'CC0'
    assert len(data['references']) >= 6
    assert any(item['id'] == 'front' for item in data['references'])
    assert any(item['id'] == 'back' for item in data['references'])
    for item in data['references']:
        assert item['url'].startswith('/static/assets/camera-reference/')


def test_angle_panel_exposes_right_side_reference_preview_and_hides_depth_action():
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    css = (ROOT / 'static/css/canvas-special-nodes.css').read_text(encoding='utf-8')
    assert 'data-angle-reference-preview' in shared
    assert 'data-angle-reference-image' in shared
    assert 'data-angle-reference-label' in shared
    assert 'Image 2' in shared
    assert 'generate-angle-depth' not in shared
    assert '.angle-reference-preview' in css


def test_angle_generation_uses_static_reference_as_image_2():
    classic = (ROOT / 'static/js/canvas.js').read_text(encoding='utf-8')
    smart = (ROOT / 'static/js/smart-canvas.js').read_text(encoding='utf-8')
    assert "node.angleGeometryMode === 'director3d' && node.angleDirectorCaptureUrl" in classic
    assert "node.angleGeometryMode === 'director3d' && node.angleDirectorCaptureUrl" in smart
    assert "reference_images:[{url:source.url" in classic
    assert "const refs = [{...source, kind:'image'}, ...(geometry ?" in smart


def test_legacy_depth_mode_is_normalized_to_static_3d_reference_mode():
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    assert "node.angleGeometryMode = node.angleGeometryMode === 'none' ? 'none' : 'director3d';" in shared
