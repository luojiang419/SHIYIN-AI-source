import numpy as np
import pytest
from canvas_core.depth_inference import DepthInference, DepthUnavailableError


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
