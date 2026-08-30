from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_parent_director_session_exposes_current_capture_request_and_cleanup():
    source = (ROOT / 'static/js/director-3d.js').read_text(encoding='utf-8')
    assert 'const sessions = new Map()' in source
    assert 'storyai:director-capture-response' in source
    assert "post('storyai:director-capture-request'" in source
    assert '导演台当前机位截图超时' in source
    assert 'pending.forEach(item => item.reject' in source
    assert 'async function capture(node, options={}, payload={})' in source


def test_director_bundle_handles_parent_capture_request():
    bundle = next((ROOT / 'static/director/assets').glob('*.js')).read_text(encoding='utf-8')
    assert 'storyai:director-capture-request' in bundle
    assert 'storyai:director-capture-response' in bundle
    assert 'preset:"current"' in bundle
    assert 'requestId:s' in bundle


def test_angle_nodes_auto_capture_and_keep_recent_fallback():
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    classic = (ROOT / 'static/js/canvas.js').read_text(encoding='utf-8')
    smart = (ROOT / 'static/js/smart-canvas.js').read_text(encoding='utf-8')
    css = (ROOT / 'static/css/canvas-special-nodes.css').read_text(encoding='utf-8')
    assert 'capture-angle-director' in shared
    assert 'options.captureDirectorReference(node)' in shared
    assert '已回退到最近截图' in shared
    assert 'function classicCaptureDirectorReference' in classic
    assert 'function smartCaptureDirectorReference' in smart
    assert 'captureDirectorReference:classicCaptureDirectorReference' in classic
    assert 'captureDirectorReference:smartCaptureDirectorReference' in smart
    assert '.angle-geometry-actions' in css


def test_director_bundle_cache_bust_is_updated():
    html = (ROOT / 'static/director/index.html').read_text(encoding='utf-8')
    assert '1.0.376.director-auto-camera.1' in html
