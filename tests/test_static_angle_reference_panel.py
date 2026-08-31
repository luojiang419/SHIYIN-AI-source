import json
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parents[1]


def test_camera_reference_manifest_contains_generated_horizontal_and_pitch_buckets():
    manifest_path = ROOT / 'static/assets/camera-reference/manifest.json'
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert data['source']['license'] == 'Project-generated asset'
    assert len(data['references']) == 9
    assert {item['id'] for item in data['references']} >= {'front', 'back', 'low', 'elevated', 'high'}
    for item in data['references']:
        assert item['url'].startswith('/static/assets/camera-reference/')
        assert (ROOT / item['url'].lstrip('/')).exists()
    pitch_bands = {item['id']: (item['elevationMin'], item['elevationMax']) for item in data['references'] if item.get('pitchBand')}
    assert pitch_bands['low'] == (-45, -15)
    assert pitch_bands['elevated'] == (16, 45)
    assert pitch_bands['high'] == (46, 60)


def test_angle_panel_exposes_right_side_reference_preview_and_hides_depth_action():
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    css = (ROOT / 'static/css/canvas-special-nodes.css').read_text(encoding='utf-8')
    assert 'data-angle-reference-preview' in shared
    assert 'data-angle-reference-image' in shared
    assert 'data-angle-reference-label' in shared
    assert 'Image 2' in shared
    assert 'generate-angle-depth' not in shared
    assert '.angle-reference-preview' in css
    assert 'min="${ANGLE_ELEVATION_MIN}" max="${ANGLE_ELEVATION_MAX}"' in shared
    assert 'node.angleElevation = clamp' in shared
    assert "if(elevation <= -15) return ANGLE_REFERENCE_CARDS.find(item => item.id === 'low');" in shared
    assert "if(elevation >= 46) return ANGLE_REFERENCE_CARDS.find(item => item.id === 'high');" in shared
    assert "if(elevation >= 16) return ANGLE_REFERENCE_CARDS.find(item => item.id === 'elevated');" in shared


def test_angle_generation_uses_static_reference_as_image_2():
    classic = (ROOT / 'static/js/canvas.js').read_text(encoding='utf-8')
    smart = (ROOT / 'static/js/smart-canvas.js').read_text(encoding='utf-8')
    assert "kind === 'angle' && node.angleGeometryMode === 'director3d'" in classic
    assert "kind === 'angle' && node.angleGeometryMode === 'director3d'" in smart
    assert "window.CanvasSpecialNodes?.angleReferenceForNode?.(node)" in classic
    assert "window.CanvasSpecialNodes?.angleReferenceForNode?.(node)" in smart
    assert "reference_images:[{url:source.url" in classic
    assert "const refs = [{...source, kind:'image'}, ...(geometry ?" in smart


def test_generated_static_reference_is_materialized_for_provider_payloads():
    url = '/static/assets/camera-reference/angle-eye-front.png'
    path = main.output_file_from_url(url)
    assert path
    assert Path(path).resolve() == (ROOT / 'static/assets/camera-reference/angle-eye-front.png').resolve()
    data_url = main.reference_to_data_url({'url': url}, max_size=256)
    assert data_url.startswith('data:image/')
    assert main.media_reference_to_url(url, max_image_size=256).startswith('data:image/')


def test_legacy_depth_mode_is_normalized_to_static_3d_reference_mode():
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    assert "node.angleGeometryMode = node.angleGeometryMode === 'none' ? 'none' : 'director3d';" in shared
