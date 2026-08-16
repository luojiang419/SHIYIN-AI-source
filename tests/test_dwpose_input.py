import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi import UploadFile
from PIL import Image

from canvas_core.dwpose_input import DWPoseInputTooLarge, fit_dwpose_size, prepare_dwpose_input


class DWPoseInputTests(unittest.TestCase):
    def jpeg(self, size):
        output = io.BytesIO()
        Image.new("RGB", size, "white").save(output, "JPEG", quality=80)
        return output.getvalue()

    def test_phone_resolution_is_scaled_to_bounded_inference_size(self):
        target = fit_dwpose_size(5464, 8192, max_pixels=4_000_000, max_edge=3072)
        self.assertLessEqual(target[0] * target[1], 4_000_000)
        self.assertLessEqual(max(target), 3072)
        self.assertAlmostEqual(target[0] / target[1], 5464 / 8192, places=3)

    def test_prepared_image_is_rgb_and_never_exceeds_inference_budget(self):
        image = prepare_dwpose_input(
            self.jpeg((1200, 1800)),
            decode_max_pixels=3_000_000,
            inference_max_pixels=800_000,
            inference_max_edge=1200,
        )
        self.assertEqual(image.mode, "RGB")
        self.assertLessEqual(image.width * image.height, 800_000)
        self.assertLessEqual(max(image.size), 1200)

    def test_decode_hard_limit_still_rejects_pathological_images(self):
        with self.assertRaises(DWPoseInputTooLarge):
            prepare_dwpose_input(
                self.jpeg((1200, 1800)),
                decode_max_pixels=1_000_000,
                inference_max_pixels=800_000,
                inference_max_edge=1200,
            )

    def test_api_downscales_large_photo_and_reports_real_output_size(self):
        import main

        captured = {}

        def fake_render(image):
            captured["size"] = image.size
            return SimpleNamespace(
                people=1,
                image_rgb=np.zeros((image.height, image.width, 3), dtype=np.uint8),
            )

        upload = UploadFile(file=io.BytesIO(self.jpeg((1200, 1800))), filename="phone-photo.jpg")
        with (
            patch.object(main, "request_identity"),
            patch.object(main.DWPOSE_MODEL_MANAGER, "status", return_value={"ready": True}),
            patch.object(main, "render_dwpose_image", side_effect=fake_render),
            patch.object(main, "DWPOSE_INPUT_MAX_PIXELS", 3_000_000),
            patch.object(main, "DWPOSE_INFERENCE_MAX_PIXELS", 800_000),
            patch.object(main, "DWPOSE_INFERENCE_MAX_EDGE", 1200),
        ):
            response = asyncio.run(main.detect_dwpose(SimpleNamespace(), upload))
        self.assertLessEqual(captured["size"][0] * captured["size"][1], 800_000)
        self.assertEqual(response.headers["X-DWPose-People"], "1")
        self.assertEqual(response.headers["X-DWPose-Width"], str(captured["size"][0]))
        self.assertEqual(response.headers["X-DWPose-Height"], str(captured["size"][1]))


if __name__ == "__main__":
    unittest.main()
