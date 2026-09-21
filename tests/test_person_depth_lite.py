import numpy as np
import pytest
from canvas_core.depth_inference import DepthInference, DepthUnavailableError
from canvas_core.person_depth_lite import MASK_SPEC


def test_person_segmentation_model_has_pinned_modelscope_mirror():
    assert MASK_SPEC.domestic_url.startswith(
        "https://modelscope.cn/models/jiangjiang419/shiyin-depth-lite-models/resolve/"
    )
    assert "/image-depth/human_segmentation_pphumanseg_2023mar.onnx" in MASK_SPEC.domestic_url
    assert "/resolve/master/" not in MASK_SPEC.domestic_url


def test_person_normalization_ignores_background(monkeypatch):
    depth = np.full((20, 20), 10000, dtype=np.float32)
    depth[5:15, 5:15] = np.arange(100).reshape(10, 10)
    class Session:
        def get_inputs(self):
            return [type('Input', (), {'name': 'input'})()]
        def run(self, *_args):
            return [depth[None]]
    engine = DepthInference(None)
    monkeypatch.setattr(engine, '_ensure_session', lambda: Session())
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[5:15, 5:15] = 1
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    person = engine.render(rgb, mask=mask).image_gray
    assert np.all(person[mask == 0] == 0)
    assert person[mask > 0].max() == 255
    assert engine.render(rgb).image_gray[0, 0] == 255
    with pytest.raises(DepthUnavailableError):
        engine.render(rgb, mask=np.zeros_like(mask))
