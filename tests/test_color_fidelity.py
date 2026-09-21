import numpy as np

from canvas_core.color_fidelity import (
    calibrate_lightness_preview,
    crop_rgb,
    feathered_roi_blend,
    inspect_color_fidelity,
    smart_color_match_auto,
    smart_color_match_preview,
)


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


def test_auto_match_selects_a_valid_strategy_and_improves_palette_overlap():
    reference = np.full((64, 64, 3), [145, 101, 73], dtype=np.uint8)
    generated = np.full((64, 64, 3), [87, 59, 42], dtype=np.uint8)
    matched, selected = smart_color_match_auto(reference, generated)
    assert selected["strategy"] in {"affine", "quantile"}
    assert inspect_color_fidelity(reference, matched).palette_overlap > inspect_color_fidelity(reference, generated).palette_overlap


def test_feathered_roi_blend_keeps_the_roi_edge_continuous():
    source = np.full((48, 48, 3), [30, 30, 30], dtype=np.uint8)
    fitted = np.full((24, 24, 3), [220, 100, 50], dtype=np.uint8)
    blended = feathered_roi_blend(source, fitted, (12, 12, 24, 24), feather=6)
    assert np.array_equal(blended[24, 24], fitted[12, 12])
    edge_change = np.abs(blended[12, 12].astype(int) - source[12, 12].astype(int)).sum()
    inner_change = np.abs(blended[15, 15].astype(int) - source[15, 15].astype(int)).sum()
    assert 0 < edge_change < inner_change
