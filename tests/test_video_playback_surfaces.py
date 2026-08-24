from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
WORKS = (ROOT / "static/js/works.js").read_text(encoding="utf-8")
ASSETS = (ROOT / "static/js/asset-manager.js").read_text(encoding="utf-8")


def test_canvas_asset_index_canonicalizes_loopback_media_urls_before_returning_them():
    body = MAIN[MAIN.index("def extract_canvas_assets"):MAIN.index("CANVAS_ASSETS_INDEX_LOCK")]
    assert "canonical_local_media_origin_url(url)" in body


def test_works_video_surfaces_use_stream_proxy_for_remote_urls():
    assert "function mediaPlaybackUrl(url, name='video.mp4')" in WORKS
    assert "/api/download-output?inline=1&url=" in WORKS
    assert "mediaPlaybackUrl(item.url, item.name)" in WORKS
    assert "mediaPlaybackUrl(work.url, work.name)" in WORKS


def test_asset_manager_video_surfaces_use_stream_proxy_and_muted_autoplay():
    assert "function assetMediaPlaybackUrl(url, name='video.mp4')" in ASSETS
    assert "/api/download-output?inline=1&url=" in ASSETS
    assert "assetMediaPlaybackUrl(item.url, item.name)" in ASSETS
    assert "assetMediaPlaybackUrl(url, item.name)" in ASSETS
    assert 'controls autoplay muted playsinline' in ASSETS
