from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/css/canvas-film-nodes.css").read_text(encoding="utf-8")
CLASSIC_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")


def test_classic_film_ports_share_the_input_row_baseline():
    assert "top:calc(104px + var(--film-port-index) * 36px)" in CSS
    assert ".film-storyboard-node .film-role-port" in CSS
    assert ".film-video-node .film-role-port" in CSS


def test_both_canvas_pages_bust_the_film_port_alignment_cache():
    token = "canvas-film-nodes.css?v=2026.09.04.film-video-layout.1&feature=video-prompt-scroll.1&feature=film-port-alignment.1"
    assert token in CLASSIC_HTML
    assert token in SMART_HTML
