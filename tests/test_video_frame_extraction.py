import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from canvas_core.video_clip import VideoClipTools
from canvas_core.video_frame_extraction import (
    VideoFrameExtractionError,
    VideoFrameExtractionRequest,
    build_video_frame_command,
    extract_video_frames,
    parse_showinfo_timestamps,
    parse_video_probe_payload,
    validate_extraction_options,
)


class VideoFrameExtractionTests(unittest.TestCase):
    def test_strategy_validation_and_command_filters(self):
        options = validate_extraction_options("sceneAndInterval", 1.5, 0.42, 12)
        self.assertEqual(options["max_frames"], 12)
        command = build_video_frame_command(
            VideoClipTools("ffmpeg.exe", "ffprobe.exe"),
            "input.mp4",
            "frame_%06d.png",
            **options,
        )
        self.assertIn("select=eq(n\\,0)+gt(scene\\,0.420000)+gte(t-prev_selected_t\\,1.500000),showinfo", command)
        self.assertIn("-frames:v", command)

    def test_invalid_strategy_is_rejected(self):
        with self.assertRaises(VideoFrameExtractionError):
            validate_extraction_options("unknown")

    def test_probe_payload_includes_display_metadata(self):
        payload = {
            "streams": [{
                "codec_type": "video",
                "width": 1080,
                "height": 1920,
                "duration": "4.5",
                "avg_frame_rate": "30/1",
                "codec_name": "h264",
                "tags": {"rotate": "90"},
            }],
            "format": {"duration": "4.5", "size": "1234"},
        }
        parsed = parse_video_probe_payload(payload)
        self.assertEqual((parsed["width"], parsed["height"]), (1920, 1080))
        self.assertEqual(parsed["duration_ms"], 4500)
        self.assertEqual(parsed["display_size"], "1920×1080")

    def test_showinfo_timestamp_parser(self):
        text = "[Parsed_showinfo] n:   0 pts_time:0.000\n[Parsed_showinfo] n:   1 pts_time:1.250"
        self.assertEqual(parse_showinfo_timestamps(text), [
            {"source_index": 0, "timestamp": 0.0},
            {"source_index": 1, "timestamp": 1.25},
        ])

    def test_extract_frames_returns_ordered_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mp4"
            source.write_bytes(b"video")
            output = root / "frames"

            def fake_runner(command, **kwargs):
                pattern = Path(command[-1])
                pattern.parent.mkdir(parents=True, exist_ok=True)
                (pattern.parent / "frame_000001.png").write_bytes(b"a")
                (pattern.parent / "frame_000002.png").write_bytes(b"bb")
                return SimpleNamespace(returncode=0, stderr="showinfo n: 0 pts_time:0.0\nshowinfo n: 1 pts_time:1.0", stdout="")

            result = extract_video_frames(
                VideoFrameExtractionRequest(source, output, strategy="intervalOnly", interval_seconds=1, max_frames=5),
                tools=VideoClipTools("ffmpeg.exe", "ffprobe.exe"),
                runner=fake_runner,
            )
            self.assertEqual(result["frame_count"], 2)
            self.assertEqual(result["frames"][1]["timestamp_ms"], 1000)


if __name__ == "__main__":
    unittest.main()
