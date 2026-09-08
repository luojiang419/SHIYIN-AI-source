from pathlib import Path


def test_canvas_does_not_offer_reverse_send_to_film():
    source = (Path(__file__).resolve().parents[1] / "static/js/canvas.js").read_text(
        encoding="utf-8"
    )

    assert "send-to-film" not in source
    assert "trySendShiyinBridgeToFilm" not in source
    assert "/api/canvas-bridges/shiyin/receive" not in source
