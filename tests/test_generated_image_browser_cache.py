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
        self.assertEqual(response.headers.get("cache-control"), main.HTML_CACHE_CONTROL)
        self.assertIn("WORKER_VERSION", response.text)
        self.assertIn("shiyin-generated-images-", response.text)
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
            self.assertIn("/static/js/media-cache-client.js?v=", text, name)

    def test_cache_worker_has_bounded_versioned_storage_and_network_fallback(self):
        text = (ROOT / "static" / "media-cache-sw.js").read_text(encoding="utf-8")
        self.assertIn("MAX_ENTRIES = 500", text)
        self.assertIn("MAX_BYTES = 512 * 1024 * 1024", text)
        self.assertIn("CACHE_PREFIX", text)
        self.assertIn("return Response.error()", text)
        self.assertIn("clear-generated-image-cache", text)
        self.assertIn("invalidate-generated-image-cache", text)
        self.assertIn("activate-media-cache-worker", text)
        self.assertIn("needsFreshNetwork", text)
        self.assertIn("cache: 'no-store'", text)
        self.assertIn("content-type", text)
        cache_response = text[text.index("async function cacheResponse"):text.index("async function matchGeneratedImage")]
        self.assertIn("scheduleTrimCache(cache);", cache_response)
        self.assertNotIn("await scheduleTrimCache(cache)", cache_response)

    def test_cache_client_explicitly_activates_waiting_worker(self):
        text = (ROOT / "static" / "js" / "media-cache-client.js").read_text(encoding="utf-8")
        self.assertIn("activate(registration.waiting)", text)
        self.assertIn("if(worker.state === 'installed') activate(worker)", text)
        self.assertIn("registration.addEventListener('updatefound'", text)
        self.assertIn("worker.state === 'installed'", text)

    def test_service_worker_caches_versioned_static_assets_for_second_open(self):
        text = (ROOT / "static" / "media-cache-sw.js").read_text(encoding="utf-8")
        self.assertIn("STATIC_CACHE_PREFIX = 'shiyin-static-assets-'", text)
        self.assertIn("isVersionedStaticAssetRequest", text)
        self.assertIn("STATIC_CACHE_NAME", text)
        self.assertIn("request.destination", text)
        self.assertIn("cache.put(request, response.clone())", text)


if __name__ == "__main__":
    unittest.main()
