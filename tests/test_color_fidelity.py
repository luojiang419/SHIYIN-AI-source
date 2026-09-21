import numpy as np

from canvas_core.color_fidelity import calibrate_lightness_preview, crop_rgb, inspect_color_fidelity, smart_color_match_preview


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


def test_large_lightness_gap_is_not_credible_even_after_normalization():
    reference = np.full((64, 64, 3), [140, 96, 68], dtype=np.uint8)
    generated = np.full((64, 64, 3), [82, 55, 40], dtype=np.uint8)
    report = inspect_color_fidelity(reference, generated)
    assert abs(report.lightness_offset) > 3.5
    assert not report.confidence.startswith('可信')


def test_crop_rejects_out_of_bounds_roi():
    with np.testing.assert_raises(ValueError):
        crop_rgb(np.zeros((20, 20, 3), dtype=np.uint8), (10, 10, 20, 20))


def test_lightness_preview_keeps_chroma_and_reduces_lightness_gap():
    reference = np.full((32, 32, 3), [140, 96, 68], dtype=np.uint8)
    generated = np.full((32, 32, 3), [82, 55, 40], dtype=np.uint8)
    calibrated = calibrate_lightness_preview(reference, generated)
    assert abs(inspect_color_fidelity(reference, calibrated).lightness_offset) < abs(inspect_color_fidelity(reference, generated).lightness_offset)


def test_smart_color_match_moves_all_lab_offsets_toward_reference():
    reference = np.full((32, 32, 3), [140, 96, 68], dtype=np.uint8)
    generated = np.full((32, 32, 3), [82, 55, 40], dtype=np.uint8)
    assert inspect_color_fidelity(reference, smart_color_match_preview(reference, generated)).delta_e00_mean < inspect_color_fidelity(reference, generated).delta_e00_mean


def test_smart_color_match_strength_controls_adjustment_amount():
    reference = np.full((32, 32, 3), [140, 96, 68], dtype=np.uint8)
    generated = np.full((32, 32, 3), [82, 55, 40], dtype=np.uint8)
    before = abs(inspect_color_fidelity(reference, generated).lightness_offset)
    gentle = abs(inspect_color_fidelity(reference, smart_color_match_preview(reference, generated, .2)).lightness_offset)
    strong = abs(inspect_color_fidelity(reference, smart_color_match_preview(reference, generated, .9)).lightness_offset)
    assert before > gentle > strong
