import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from canvas_core.video_clip import (
    VideoClipError,
    VideoClipTools,
    build_video_clip_command,
    canvas_clip_directory,
    create_video_clip,
    delete_video_clip,
    output_dimensions,
    parse_video_probe,
    validate_clip_range,
)


class VideoClipTests(unittest.TestCase):
    def test_probe_parses_rotation_audio_and_fractional_fps(self):
        result = parse_video_probe(json.dumps({
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                 "avg_frame_rate": "30000/1001", "tags": {"rotate": "90"}},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "10.5", "size": "1234"},
        }))
        self.assertEqual((result["width"], result["height"]), (1080, 1920))
        self.assertAlmostEqual(result["fps"], 29.97, places=2)
        self.assertTrue(result["audio"])

    def test_resolution_caps_landscape_portrait_and_never_upscales(self):
        self.assertEqual(output_dimensions(3840, 2160, "1080p"), (1920, 1080))
        self.assertEqual(output_dimensions(2160, 3840, "1080p"), (1080, 1920))
        self.assertEqual(output_dimensions(1280, 720, "1080p"), (1280, 720))
        self.assertEqual(output_dimensions(2048, 858, "1080p"), (1920, 804))
        self.assertEqual(output_dimensions(1920, 1080, "720p"), (1280, 720))

    def test_range_rejects_invalid_or_out_of_bounds_values(self):
        self.assertEqual(validate_clip_range(1, 3, 10), (1, 3))
        with self.assertRaises(VideoClipError):
            validate_clip_range(3, 1, 10)
        with self.assertRaises(VideoClipError):
            validate_clip_range(1, 11, 10)

    def test_command_reencodes_mp4_with_accurate_post_input_seek(self):
        command = build_video_clip_command(
            VideoClipTools("ffmpeg.exe", "ffprobe.exe"), "source clip.mov", "result.mp4",
            start=1.25, end=4.75, width=1920, height=1080,
        )
        self.assertLess(command.index("-i"), command.index("-ss"))
        self.assertIn("libx264", command)
        self.assertIn("aac", command)
        self.assertIn("scale=1920:1080:flags=lanczos,setsar=1", command)
        self.assertNotIn("shell", command)

    def test_canvas_directory_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(
                canvas_clip_directory(temp_dir, "canvas_123"),
                Path(temp_dir).resolve() / "canvases" / "canvas_123" / "video-clips",
            )
            with self.assertRaises(VideoClipError):
                canvas_clip_directory(temp_dir, "../outside")

    def test_create_is_atomic_and_delete_only_targets_owned_clip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            tools = VideoClipTools("ffmpeg.exe", "ffprobe.exe")

            def runner(command, **_kwargs):
                if command[0] == "ffprobe.exe":
                    return subprocess.CompletedProcess(command, 0, json.dumps({
                        "streams": [{"codec_type": "video", "width": 3840, "height": 2160, "avg_frame_rate": "24/1"}],
                        "format": {"duration": "8"},
                    }), "")
                Path(command[-1]).write_bytes(b"encoded video")
                return subprocess.CompletedProcess(command, 0, "", "")

            result = create_video_clip(
                source, root / "generated", "canvas_1", start=1, end=4,
                tools=tools, runner=runner, clip_id="clip_test",
            )
            output = Path(result["path"])
            self.assertTrue(output.is_file())
            self.assertEqual((result["width"], result["height"]), (1920, 1080))
            self.assertEqual(result["duration"], 3)
            self.assertFalse(any(output.parent.glob("*.partial.mp4")))
            self.assertTrue(delete_video_clip(root / "generated", "canvas_1", "clip_test"))
            self.assertFalse(output.exists())
            with self.assertRaises(VideoClipError):
                delete_video_clip(root / "generated", "canvas_1", "../source")

    def test_backend_exposes_clip_lifecycle_endpoints(self):
        main_source = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/canvas-tools/video-clip/capabilities")', main_source)
        self.assertIn('@app.post("/api/canvas-tools/video-clip/probe")', main_source)
        self.assertIn('@app.post("/api/canvas-tools/video-clip/create")', main_source)
        self.assertIn('@app.post("/api/canvas-tools/video-clip/delete")', main_source)
        self.assertIn("purge_canvas_video_clips", main_source)


if __name__ == "__main__":
    unittest.main()
