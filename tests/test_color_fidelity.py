import numpy as np

from canvas_core.color_fidelity import crop_rgb, inspect_color_fidelity


def test_same_color_is_credible():
    image = np.full((64, 64, 3), [112, 82, 54], dtype=np.uint8)
    report = inspect_color_fidelity(image, image.copy())
    assert report.delta_e00_mean == 0
    assert report.confidence.startswith('可信')


def test_different_color_is_not_credible():
    reference = np.full((64, 64, 3), [112, 82, 54], dtype=np.uint8)
    generated = np.full((64, 64, 3), [83, 100, 150], dtype=np.uint8)
    report = inspect_color_fidelity(reference, generated)
    assert report.normalized_delta_e00_mean > 12
    assert report.confidence.startswith('不可信')


def test_crop_rejects_out_of_bounds_roi():
    with np.testing.assert_raises(ValueError):
        crop_rgb(np.zeros((20, 20, 3), dtype=np.uint8), (10, 10, 20, 20))
