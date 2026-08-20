from pathlib import Path


def test_canvas_reverse_bridge_uses_film_loopback_and_download_fallback():
    source = (Path(__file__).resolve().parents[1] / "static/js/canvas.js").read_text(
        encoding="utf-8"
    )

    assert "/api/canvas-bridges/shiyin/capabilities" in source
    assert "/api/canvas-bridges/shiyin/receive" in source
    assert "automatic_receive !== true" in source
    assert "Content-Type':'application/zip" in source
    assert "await downloadUrl(data.url" in source
    assert "film 未运行，已保存桥接包" in source
