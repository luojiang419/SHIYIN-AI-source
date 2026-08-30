from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_depth_model_manager_uses_verified_depth_anything_v2_spec():
    source = (ROOT / 'canvas_core/depth_models.py').read_text(encoding='utf-8')
    assert 'model_fp16.onnx' in source
    assert '50_392_064' in source
    assert 'sha256' in source
    assert 'verify_installed' in source


def test_depth_inference_is_cpu_only_and_preserves_original_dimensions():
    source = (ROOT / 'canvas_core/depth_inference.py').read_text(encoding='utf-8')
    assert 'CPUExecutionProvider' in source
    assert 'DEPTH_TARGET_SHORT_EDGE = 518' in source
    assert 'return DepthResult(image_gray=gray, width=width, height=height)' in source


def test_depth_routes_and_angle_geometry_reference_contract_exist():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    shared = (ROOT / 'static/js/canvas-special-nodes.js').read_text(encoding='utf-8')
    classic = (ROOT / 'static/js/canvas.js').read_text(encoding='utf-8')
    smart = (ROOT / 'static/js/smart-canvas.js').read_text(encoding='utf-8')
    assert '@app.post("/api/depth/estimate")' in main
    assert '@app.get("/api/depth/status")' in main
    assert "angleGeometryMode" in shared
    assert "generate-angle-depth" in shared
    assert "GEOMETRY REFERENCE" in shared
    assert "node.angleDepthUrl" in classic and "node.angleDirectorCaptureUrl" in classic
    assert "node.angleDepthUrl" in smart and "node.angleDirectorCaptureUrl" in smart


def test_angle_reference_order_keeps_source_before_geometry_before_previous():
    classic = (ROOT / 'static/js/canvas.js').read_text(encoding='utf-8')
    smart = (ROOT / 'static/js/smart-canvas.js').read_text(encoding='utf-8')
    assert "reference_images:[{url:source.url" in classic
    assert "concat(geometry ? [geometry] : []).concat(previous ? [previous] : [])" in classic
    assert "const refs = [{...source, kind:'image'}, ...(geometry ?" in smart
    assert "...(previous ? [{...previous, kind:'image'}] : [])" in smart



def test_depth_inference_normalizes_fake_relative_depth_without_loading_weights(monkeypatch):
    import numpy as np
    from canvas_core.depth_inference import DepthInference

    class Input:
        name = 'pixel_values'

    class FakeSession:
        def get_inputs(self):
            return [Input()]

        def run(self, _outputs, _feeds):
            return [np.linspace(0.0, 1.0, 256 * 256, dtype=np.float32).reshape(1, 256, 256)]

    inference = DepthInference(object())
    monkeypatch.setattr(inference, '_ensure_session', lambda: FakeSession())
    result = inference.render(np.zeros((13, 17, 3), dtype=np.uint8))
    assert result.image_gray.shape == (13, 17)
    assert result.image_gray.dtype == np.uint8
    assert int(result.image_gray.min()) == 0
    assert int(result.image_gray.max()) == 255
