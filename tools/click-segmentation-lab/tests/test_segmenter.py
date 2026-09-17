from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from segmenter import choose_mask, decode_image, mask_png, refine_alpha, rgba_png


def test_decode_and_export_keep_original_resolution() -> None:
    source = Image.new("RGB", (37, 23), (80, 120, 160))
    encoded = io.BytesIO()
    source.save(encoded, "PNG")
    image = decode_image(encoded.getvalue())
    alpha = np.zeros((23, 37), dtype=np.float32)
    alpha[4:20, 7:31] = 1

    with Image.open(io.BytesIO(rgba_png(image, alpha))) as output:
        assert output.size == source.size
        assert output.mode == "RGBA"
        assert output.getpixel((0, 0))[3] == 0
        assert output.getpixel((10, 10))[3] == 255
    with Image.open(io.BytesIO(mask_png(alpha))) as output_mask:
        assert output_mask.size == source.size
        assert output_mask.mode == "L"


def test_refine_alpha_keeps_component_containing_positive_point() -> None:
    mask = np.zeros((80, 100), dtype=np.float32)
    mask[10:35, 10:35] = 0.9
    mask[40:75, 55:95] = 0.9
    refined = refine_alpha(mask, threshold=0.5, feather=0, positive_points=[(20, 20)])
    assert refined[20, 20] == 1
    assert refined[60, 70] == 0


def test_refine_alpha_softens_only_edge() -> None:
    mask = np.zeros((80, 80), dtype=np.float32)
    mask[20:60, 20:60] = 1
    refined = refine_alpha(mask, threshold=0.5, feather=4, positive_points=[(40, 40)])
    assert refined[40, 40] > 0.99
    assert refined[0, 0] == 0
    assert 0 < refined[19, 40] < 1


def test_choose_mask_rejects_full_frame_candidate() -> None:
    masks = np.zeros((3, 100, 100), dtype=np.float32)
    masks[0] = 1
    masks[1, 30:70, 30:70] = 1
    masks[2, 45:55, 45:55] = 1
    scores = np.array([0.99, 0.91, 0.7], dtype=np.float32)
    point = [{"x": 50, "y": 50, "label": 1}]
    assert choose_mask(masks, scores, point) == 1


def test_choose_mask_strongly_respects_negative_point() -> None:
    masks = np.full((2, 100, 100), 0.05, dtype=np.float32)
    masks[0, 20:80, 20:80] = 0.95
    masks[1, 20:60, 20:60] = 0.88
    scores = np.array([0.98, 0.82], dtype=np.float32)
    points = [{"x": 35, "y": 35, "label": 1}, {"x": 70, "y": 70, "label": 0}]
    assert choose_mask(masks, scores, points) == 1


def test_edge_shift_expands_and_contracts_original_pixel_boundary():
    mask = np.zeros((80, 80), dtype=np.float32)
    mask[20:60, 20:60] = 1
    base = refine_alpha(mask, 0.5, 0, [(40, 40)])
    expanded = refine_alpha(mask, 0.5, 0, [(40, 40)], 3)
    contracted = refine_alpha(mask, 0.5, 0, [(40, 40)], -3)
    assert expanded.sum() > base.sum() > contracted.sum()
    assert expanded[18, 40] == 1 and base[18, 40] == 0
    assert contracted[21, 40] == 0 and base[21, 40] == 1
    assert expanded.shape == contracted.shape == mask.shape
