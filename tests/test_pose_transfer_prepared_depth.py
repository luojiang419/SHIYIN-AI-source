import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image

import main


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


if __name__ == "__main__":
    unittest.main()
