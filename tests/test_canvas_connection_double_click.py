from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLASSIC_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CLASSIC_INTERACTIONS = (ROOT / "static" / "js" / "canvas-connection-interactions.js").read_text(encoding="utf-8")
SMART_CANVAS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_classic_canvas_loads_double_click_connection_interactions():
    assert "/static/js/canvas-connection-interactions.js?v=2026.09.09.double-click-disconnect.1" in CLASSIC_HTML
    assert "board.addEventListener('dblclick'" in CLASSIC_INTERACTIONS
    assert ".link-hit[data-connection-id]" in CLASSIC_INTERACTIONS
    assert "event.button !== 0" in CLASSIC_INTERACTIONS
    assert "deleteConnection(connectionId, event)" in CLASSIC_INTERACTIONS
    assert "event.stopPropagation()" in CLASSIC_INTERACTIONS


def test_smart_canvas_keeps_existing_double_click_disconnect_behavior():
    assert "world.addEventListener('dblclick'" in SMART_CANVAS
    assert ".conn-hit[data-conn-index]" in SMART_CANVAS
    assert "disconnectConnectionsByIds([hit.dataset.connectionId])" in SMART_CANVAS
    assert "disconnectConnections(hit.dataset.connIndex)" in SMART_CANVAS
