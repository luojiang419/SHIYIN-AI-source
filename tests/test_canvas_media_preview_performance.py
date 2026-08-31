import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import main


ROOT = Path(__file__).resolve().parent.parent


class CanvasMediaPreviewPerformanceTests(unittest.TestCase):
    def test_preview_builds_are_keyed_and_shared_for_concurrent_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(b"source")
            webp = Path(directory) / "preview.webp"
            png = Path(directory) / "preview.png"
            calls = []

            def fake_build(path, width, webp_path, png_path):
                calls.append((path, width))
                time.sleep(0.05)
                Path(webp_path).write_bytes(b"preview")
                return webp_path, "image/webp"

            async def run():
                with patch.object(main, "build_media_preview", side_effect=fake_build):
                    return await asyncio.gather(*[
                        main.get_or_build_media_preview(str(source), 512, str(webp), str(png))
                        for _ in range(8)
                    ])

            results = asyncio.run(run())
            self.assertEqual(len(calls), 1)
            self.assertEqual(set(results), {(str(webp), "image/webp")})

    def test_preview_failures_are_negative_cached_for_short_period(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(b"source")
            webp = Path(directory) / "preview.webp"
            png = Path(directory) / "preview.png"
            calls = []

            def fake_build(*args):
                calls.append(args[0])
                raise RuntimeError("bad media")

            async def run():
                with patch.object(main, "build_media_preview", side_effect=fake_build):
                    with self.assertRaisesRegex(RuntimeError, "bad media"):
                        await main.get_or_build_media_preview(str(source), 512, str(webp), str(png))
                    with self.assertRaisesRegex(RuntimeError, "bad media"):
                        await main.get_or_build_media_preview(str(source), 512, str(webp), str(png))

            try:
                asyncio.run(run())
                self.assertEqual(calls, [str(source)])
            finally:
                main.MEDIA_PREVIEW_FAILURES.clear()

    def test_canvas_previews_are_lazy_and_drained_by_viewport_queue(self):
        classic = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
        smart = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
        self.assertIn("function canvasEagerMediaAttrs", classic)
        self.assertIn('loading=\"lazy\" decoding=\"async\"', classic)
        self.assertIn("const CLASSIC_MEDIA_QUEUE_MAX", classic)
        self.assertIn("function scheduleClassicMediaQueue", classic)
        self.assertIn('data-preview-state=\"${immediate ? \'ready\' : \'queued\'}\"', classic)
        self.assertIn("function smartEagerMediaAttrs", smart)
        self.assertIn('loading=\"lazy\" decoding=\"async\"', smart)
        self.assertIn("const SMART_MEDIA_QUEUE_MAX", smart)
        self.assertIn("function scheduleSmartMediaQueue", smart)
        self.assertIn('data-preview-state=\"${immediate ? \'ready\' : \'queued\'}\"', smart)
        self.assertIn(".replace(/\\sloading\\s*=\\s*(['\"])[^'\"]*\\1/ig, '')", classic)
        self.assertIn(".replace(/\\sloading\\s*=\\s*(['\"])[^'\"]*\\1/ig, '')", smart)
        self.assertIn("if(!selected.has(node.id)) return;", classic)
        self.assertIn("&& isNodeSelected(node.id)", smart)


if __name__ == "__main__":
    unittest.main()
