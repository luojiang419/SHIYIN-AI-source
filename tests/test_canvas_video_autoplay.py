from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_classic_canvas_video_player_does_not_autoplay():
    source = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
    start = source.index("function canvasVideoPlayerHtml")
    end = source.index("function canvasActivateVideoPreview", start)
    player = source[start:end]
    assert " controls autoplay " not in player
    activation = source[end:source.index("function isCanvasPreviewImage", end)]
    assert "video.play?.().catch(() => {});" in activation

    output_start = source.index("function renderOutputMedia")
    output_end = source.index("function outputGridLayout", output_start)
    assert "controls autoplay" not in source[output_start:output_end]


def test_smart_canvas_video_player_does_not_autoplay():
    source = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
    start = source.index("function smartVideoPlayerHtml")
    end = source.index("function smartActivateVideoPreview", start)
    player = source[start:end]
    assert " controls autoplay " not in player
    activation = source[end:source.index("function isSmartPreviewImage", end)]
    assert "video.play?.().catch(() => {});" in activation
