import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
from PIL import Image

import main
from canvas_core.component_profiles import RuntimeCapabilities
from canvas_core.depth_model_policy import select_depth_model_tier


def depth_png():
    output = BytesIO()
    Image.new("L", (8, 12), 128).save(output, format="PNG")
    return output.getvalue()


class PoseTransferPreparedDepthTests(unittest.TestCase):
    def test_prepared_depth_replaces_pose_without_running_depth_model_again(self):
        with tempfile.TemporaryDirectory() as directory:
            pose = Path(directory, "pose.jpg")
            pose.write_bytes(b"pose")
            depth = Path(directory, "pose_transfer_depth_prepared.png")
            depth.write_bytes(depth_png())
            paths = {"/pose": str(pose), "/assets/output/pose_transfer_depth_prepared.png": str(depth)}
            with patch.object(main, "output_file_from_url", side_effect=lambda url: paths.get(url)), patch.object(
                main, "render_universal_person_depth", new=AsyncMock()
            ) as estimate:
                refs, prompt, audit = asyncio.run(main.prepare_universal_pose_depth({
                    "operation": "pose_transfer",
                    "inputs": [{"role": "source", "url": "/style"}, {"role": "pose", "url": "/pose"}],
                    "options": {"pose_source": "reference", "pose_depth": {
                        "source_url": "/pose", "url": "/assets/output/pose_transfer_depth_prepared.png", "tier": "quality"
                    }},
                    "prompt": "stale",
                }))
            self.assertEqual([item["role"] for item in refs], ["source", "control_map"])
            self.assertEqual(refs[1]["url"], "/assets/output/pose_transfer_depth_prepared.png")
            self.assertTrue(audit["pre_extracted"])
            self.assertFalse(audit["pose_rgb_submitted"])
            self.assertIn("Image 2 is the ORIGINAL registered person depth", prompt)
            estimate.assert_not_awaited()

    def test_prepared_depth_from_previous_pose_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            pose = Path(directory, "pose.jpg")
            pose.write_bytes(b"pose")
            with patch.object(main, "output_file_from_url", return_value=str(pose)), patch.object(
                main, "render_universal_person_depth", new=AsyncMock()
            ) as estimate:
                with self.assertRaisesRegex(ValueError, "不匹配"):
                    asyncio.run(main.prepare_universal_pose_depth({
                        "operation": "pose_transfer",
                        "inputs": [{"role": "source", "url": "/style"}, {"role": "pose", "url": "/pose"}],
                        "options": {"pose_source": "reference", "pose_depth": {
                            "source_url": "/old-pose", "url": "/assets/output/pose_transfer_depth_old.png"
                        }},
                        "prompt": "stale",
                    }))
            estimate.assert_not_awaited()

    def test_prepare_endpoint_returns_saved_depth_for_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "pose.png")
            source.write_bytes(b"pose")
            with patch.object(main, "request_identity"), patch.object(main, "output_file_from_url", return_value=str(source)), patch.object(
                main, "render_universal_person_depth", new=AsyncMock(return_value=(depth_png(), "quality"))
            ) as estimate, patch.object(main, "OUTPUT_OUTPUT_DIR", directory), patch.object(
                main, "media_url_from_path", side_effect=lambda path: "/assets/output/" + Path(path).name
            ), patch.object(main, "register_internal_media_object") as register:
                result = asyncio.run(main.prepare_ecommerce_pose_depth(None, {"source_url": "/pose"}))
            self.assertEqual(result["source_url"], "/pose")
            self.assertEqual(result["tier"], "quality")
            self.assertEqual(Image.open(Path(directory, Path(result["url"]).name)).mode, "L")
            estimate.assert_awaited_once_with(str(source))
            register.assert_called_once()

    def test_auto_mode_uses_lite_for_low_vram_and_cpu_on_pose_upload(self):
        for capabilities in (
            RuntimeCapabilities("windows", "x86_64", "cuda", gpu_memory_bytes=6 * 1024**3),
            RuntimeCapabilities("windows", "x86_64", "cpu"),
        ):
            with self.subTest(accelerator=capabilities.accelerator):
                with tempfile.TemporaryDirectory() as directory:
                    source = Path(directory, "pose.png")
                    Image.new("RGB", (8, 12), "white").save(source)
                    worker = SimpleNamespace(estimate=Mock())
                    with patch.object(main, "request_identity"), patch.object(
                        main, "read_app_config", return_value={"depth_model_preference": "auto"}
                    ), patch.object(
                        main, "select_depth_model_tier",
                        side_effect=lambda override: select_depth_model_tier(capabilities, override),
                    ), patch.object(main, "output_file_from_url", return_value=str(source)), patch.object(
                        main.DEPTH_MODEL_MANAGER, "public_status", return_value={"ready": True}
                    ), patch.object(main, "PERSON_DEPTH_WORKER", worker), patch.object(
                        main, "prepare_dwpose_input", return_value=object()
                    ), patch.object(
                        main, "render_depth_image",
                        return_value=SimpleNamespace(image_gray=np.full((12, 8), 128, dtype=np.uint8)),
                    ) as lite_estimate, patch.object(main, "OUTPUT_OUTPUT_DIR", directory), patch.object(
                        main, "media_url_from_path", side_effect=lambda path: "/assets/output/" + Path(path).name
                    ), patch.object(main, "register_internal_media_object"):
                        result = asyncio.run(main.prepare_ecommerce_pose_depth(None, {"source_url": "/pose"}))
                    self.assertEqual(result["tier"], "lite")
                    self.assertEqual(Image.open(Path(directory, Path(result["url"]).name)).mode, "L")
                    lite_estimate.assert_called_once()
                    worker.estimate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
