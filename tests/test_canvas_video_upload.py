import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from canvas_core.video_clip import resolve_video_clip_tools
from canvas_core.video_upload import browser_playback_proxy


class CanvasVideoUploadTests(unittest.TestCase):
    def test_professional_container_gets_playable_proxy(self):
        tools = resolve_video_clip_tools()
        if not tools.ready:
            self.skipTest("FFmpeg/FFprobe unavailable")
        with tempfile.TemporaryDirectory() as directory:
            source = str(Path(directory) / "source.mpg")
            proxy = str(Path(directory) / "playback.mp4")
            subprocess.run([
                tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24",
                "-t", "1", "-c:v", "mpeg2video", "-y", source,
            ], check=True, capture_output=True)
            self.assertTrue(browser_playback_proxy(source, proxy))
            self.assertTrue(os.path.getsize(proxy) > 0)
            video = subprocess.run([
                tools.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", proxy,
            ], capture_output=True, text=True, check=True)
            self.assertEqual(video.stdout.strip(), "h264")
            self.assertTrue(os.path.exists(source))

    def test_large_video_upload_streams_and_keeps_original(self):
        import main
        from fastapi import UploadFile

        class LargeFile:
            filename = "camera.mxf"
            content_type = "video/x-mxf"
            reads = []
            remaining = 99 * 1024 * 1024

            async def read(self, size=-1):
                self.reads.append(size)
                count = min(size, self.remaining)
                self.remaining -= count
                return b"x" * count

        source = LargeFile()
        with tempfile.TemporaryDirectory() as directory:
            def path_for(name, _kind):
                return str(Path(directory) / name)

            with patch.object(main, "output_path_for", side_effect=path_for), \
                 patch.object(main, "output_url_for", side_effect=lambda name, _kind: f"/assets/input/{name}"), \
                 patch.object(main, "register_internal_media_object"), \
                 patch.object(main, "browser_playback_proxy", return_value=False):
                result = asyncio.run(main.upload_ai_reference([source]))
            self.assertEqual(result["files"][0]["kind"], "video")
            self.assertEqual(os.path.getsize(path_for(Path(result["files"][0]["url"]).name, "input")), 99 * 1024 * 1024)
            self.assertTrue(all(size == 1024 * 1024 for size in source.reads))


if __name__ == "__main__":
    unittest.main()
