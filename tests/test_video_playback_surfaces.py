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
    assert "function workMediaType(item)" in WORKS
    assert "item?.original_name" in WORKS
    assert "item?.filename" in WORKS
    assert "const isVideo = workMediaType(item) === 'video'" in WORKS
    assert "el.worksPreviewImage.hidden=isVideo" in WORKS
    assert "if(raw.startsWith('/assets/') || raw.startsWith('/output/'))" in WORKS
    assert "video-playback-directory-fix" in (ROOT / "static/works.html").read_text(encoding="utf-8")
    assert ".works-preview-frame > [hidden] { display:none !important; }" in (ROOT / "static/css/works.css").read_text(encoding="utf-8")


def test_asset_manager_video_surfaces_use_stream_proxy_and_muted_autoplay():
    assert "function assetMediaPlaybackUrl(url, name='video.mp4')" in ASSETS
    assert "/api/download-output?inline=1&url=" in ASSETS
    assert "assetMediaPlaybackUrl(item.url, item.name)" in ASSETS
    assert "assetMediaPlaybackUrl(url, item.name)" in ASSETS
    assert 'controls autoplay muted playsinline' in ASSETS
    assert "if(raw.startsWith('/assets/') || raw.startsWith('/output/'))" in ASSETS
    assert "data-canvas-asset-reveal" in ASSETS
    assert "item?.original_name" in ASSETS
    assert "item?.filename" in ASSETS
    assert "/api/canvas-assets/${encodeURIComponent" in ASSETS
    assert "video-playback-directory-fix" in (ROOT / "static/asset-manager.html").read_text(encoding="utf-8")
