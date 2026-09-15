from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECIAL_JS = (ROOT / "static/js/canvas-special-nodes.js").read_text(encoding="utf-8")
SPECIAL_CSS = (ROOT / "static/css/canvas-special-nodes.css").read_text(encoding="utf-8")
CLASSIC_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
CLASSIC_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_depth_video_has_live_controls_and_export_output_node():
    for marker in (
        "DEFAULT_DEPTH_VIDEO_CONTROLS",
        'data-special-action="open-depth-video-controls"',
        'data-special-action="export-depth-video"',
        "function openDepthVideoControls(node, options)",
        "preview.style.filter = depthVideoCssFilter(node.depthVideoControls)",
        "'/api/video-depth/export'",
        "outputNode.title = '深度视频输出'",
        "node.depthVideoExportNodeId = outputNode.id",
    ):
        assert marker in SPECIAL_JS
    assert ".depth-video-control-modal" in SPECIAL_CSS
    assert '[data-special-action="export-depth-video"]{margin-left:auto}' in SPECIAL_CSS
    assert "out.images = [{...item, kind:item.kind || 'image'}]" in CLASSIC_JS
    assert "output.images = [{...item, kind:item.kind || 'image'}]" in SMART_JS


def test_depth_video_export_renders_a_real_local_mp4():
    for marker in (
        'class VideoDepthExportRequest(BaseModel):',
        '@app.post("/api/video-depth/export")',
        '"-vf", ",".join(filters)',
        '"-c:v", "libx264"',
        'brightness_factor = round(brightness * 100 / gamma) / 100',
        'filters = [f"lut=y=',
        'register_internal_media_object(url, "output", "video", "video-depth-export")',
    ):
        assert marker in MAIN


def test_storyboard_merge_is_only_a_top_level_classic_context_menu_item():
    button = '<button class="menu-btn" type="button" onclick="menuAdd(\'storyboardMerge\')">'
    assert CLASSIC_HTML.count(button) == 1
    top_level_index = CLASSIC_HTML.index(button)
    film_group_index = CLASSIC_HTML.index('data-film-menu-host')
    assert top_level_index < film_group_index


def test_legacy_depth_video_marked_as_image_still_opens_video_lightbox():
    resolver_start = CLASSIC_JS.index("function mediaKindForOutputItem(item)")
    resolver_end = CLASSIC_JS.index("function formatRunDuration", resolver_start)
    resolver = CLASSIC_JS[resolver_start:resolver_end]
    assert resolver.index("if(isVideoUrl(url)) return 'video'") < resolver.index("if(['image','video','audio','text','file'].includes(explicit))")
    lightbox_start = CLASSIC_JS.index("function openOutputLightbox(url, out)")
    lightbox_end = CLASSIC_JS.index("function closeOutputLightbox", lightbox_start)
    lightbox = CLASSIC_JS[lightbox_start:lightbox_end]
    assert "outputLightboxVideo.src = canvasDisplayMediaUrl(url" in lightbox
    assert "if(wrap._outputBound) return" in CLASSIC_JS
    assert "bindOutputWrap(child, node);\n        grid.appendChild(child);" in CLASSIC_JS
    assert "wrap.ondblclick = e =>" in CLASSIC_JS
    assert "img[data-url], video[data-output-video-fallback]" in CLASSIC_JS
    assert "document.addEventListener('dblclick', event =>" in CLASSIC_JS
    assert "document.addEventListener('click', event =>" in CLASSIC_JS
    assert "mediaKindForOutputItem({url}) !== 'video'" in CLASSIC_JS
    assert 'ondblclick="openOutputMediaFromElement(this,event)"' in CLASSIC_JS
    assert "function openOutputMediaFromElement(element, event)" in CLASSIC_JS
    assert ".output-img-wrap img[data-url]" in CLASSIC_JS
