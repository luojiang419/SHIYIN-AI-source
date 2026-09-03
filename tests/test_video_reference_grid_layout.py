from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_video_reference_list_uses_six_column_wrapping_grid():
    assert ".video-img-list { display:grid; grid-template-columns:repeat(6,minmax(0,1fr));" in CSS
    assert ".video-img-list .video-input-item { width:auto; min-width:0; }" in CSS
    assert ".video-img-list .video-input-thumb { width:100%; height:auto; aspect-ratio:1; }" in CSS
    assert ".video-img-list { display:grid;" in CSS
    assert ".video-img-list { display:flex;" not in CSS
