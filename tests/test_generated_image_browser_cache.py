import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import main


ROOT = Path(__file__).resolve().parents[1]


class GeneratedImageBrowserCacheTests(unittest.TestCase):
    def test_service_worker_is_exposed_at_root_with_broad_scope(self):
        with TestClient(main.app, client=("127.0.0.1", 50110)) as client:
            response = client.get("/media-cache-sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.headers.get("content-type", ""))
        self.assertEqual(response.headers.get("service-worker-allowed"), "/")
        self.assertIn("shiyin-generated-images-v1", response.text)
        self.assertIn("/api/media-preview", response.text)
        self.assertIn("/output/", response.text)
        self.assertIn("request.destination !== 'image'", response.text)

    def test_image_cache_client_is_registered_on_image_pages(self):
        pages = (
            "index.html",
            "canvas.html",
            "smart-canvas.html",
            "works.html",
            "ecommerce.html",
            "asset-manager.html",
            "gpt-chat.html",
        )
        for name in pages:
            text = (ROOT / "static" / name).read_text(encoding="utf-8")
            self.assertIn("/static/js/media-cache-client.js?v=2026.08.22.generated-image-cache.1", text, name)

    def test_cache_worker_has_bounded_versioned_storage_and_network_fallback(self):
        text = (ROOT / "static" / "media-cache-sw.js").read_text(encoding="utf-8")
        self.assertIn("MAX_ENTRIES = 500", text)
        self.assertIn("MAX_BYTES = 512 * 1024 * 1024", text)
        self.assertIn("CACHE_PREFIX", text)
        self.assertIn("return Response.error()", text)
        self.assertIn("clear-generated-image-cache", text)
        self.assertIn("content-type", text)


if __name__ == "__main__":
    unittest.main()
