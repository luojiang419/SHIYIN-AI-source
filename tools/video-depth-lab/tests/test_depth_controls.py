import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.depth_controls import DepthControls, apply_depth_controls, normalize_relative_depth
from worker.models import MODEL_PROFILES, get_profile


class DepthControlTests(unittest.TestCase):
    def test_normalization_is_global_and_bounded(self):
        values = np.array([[[0.0, 1.0]], [[2.0, 100.0]]], dtype=np.float32)
        normalized, metadata = normalize_relative_depth(values)
        self.assertEqual(normalized.shape, values.shape)
        self.assertGreaterEqual(float(normalized.min()), 0.0)
        self.assertLessEqual(float(normalized.max()), 1.0)
        self.assertLess(metadata["p02"], metadata["p98"])

    def test_controls_generate_uint8_and_invert(self):
        values = np.linspace(0, 1, 16, dtype=np.float32).reshape(1, 4, 4)
        normal = apply_depth_controls(values, DepthControls())
        inverted = apply_depth_controls(values, DepthControls(invert=True))
        self.assertEqual(normal.dtype, np.uint8)
        np.testing.assert_array_equal(inverted, 255 - normal)

    def test_rejects_invalid_black_white_points(self):
        with self.assertRaises(ValueError):
            DepthControls(far_point=90, near_point=80).validate()

    def test_model_registry_matches_requested_profiles(self):
        gem = get_profile("gemdepth_vda_8f")
        self.assertEqual((gem.infer_len, gem.overlap, gem.interp_len), (8, 4, 2))
        vda = get_profile("vda_base_fp16_relative")
        self.assertEqual(vda.encoder, "vitb")
        self.assertEqual(vda.depth_type, "Relative Depth")
        self.assertIn("FP16", vda.precision)
        self.assertEqual(set(MODEL_PROFILES), {"gemdepth_vda_8f", "vda_base_fp16_relative"})


if __name__ == "__main__":
    unittest.main()
