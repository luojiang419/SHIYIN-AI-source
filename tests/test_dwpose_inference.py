import tempfile
import unittest
from pathlib import Path

import numpy as np

from canvas_core.dwpose_inference import (
    DWPoseInference,
    DWPoseUnavailableError,
    _decode_simcc,
    _nms,
    _render_pose,
)
from canvas_core.dwpose_models import DWPoseModelManager


class DWPoseInferenceTests(unittest.TestCase):
    def test_nms_suppresses_overlapping_lower_score_box(self):
        boxes = np.array([[0, 0, 100, 100], [5, 5, 98, 98], [200, 200, 260, 260]], dtype=np.float32)
        scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
        self.assertEqual(_nms(boxes, scores, 0.45), [0, 2])

    def test_simcc_decode_uses_axis_argmax_and_split_ratio(self):
        simcc_x = np.zeros((1, 2, 8), dtype=np.float32)
        simcc_y = np.zeros((1, 2, 10), dtype=np.float32)
        simcc_x[0, 0, 6], simcc_y[0, 0, 4] = 0.9, 0.8
        simcc_x[0, 1, 2], simcc_y[0, 1, 8] = 0.7, 0.6
        points, scores = _decode_simcc(simcc_x, simcc_y)
        np.testing.assert_array_equal(points, np.array([[[3, 2], [1, 4]]], dtype=np.float32))
        np.testing.assert_allclose(scores, np.array([[0.8, 0.6]], dtype=np.float32))

    def test_renderer_outputs_black_canvas_for_no_people(self):
        result = _render_pose(
            np.empty((0, 134, 2), dtype=np.float32),
            np.empty((0, 134), dtype=np.float32),
            24,
            32,
        )
        self.assertEqual(result.shape, (24, 32, 3))
        self.assertEqual(int(result.sum()), 0)

    def test_missing_models_raise_stable_unavailable_error(self):
        with tempfile.TemporaryDirectory() as root:
            manager = DWPoseModelManager(Path(root) / "models", proxy_provider=lambda: {})
            inference = DWPoseInference(manager)
            with self.assertRaisesRegex(DWPoseUnavailableError, "尚未下载完成"):
                inference.render(np.zeros((32, 32, 3), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
