from pathlib import Path

import pytest

from canvas_core.linkfox_video import LinkFoxVideoError, normalize_request


IMG = "https://example.com/product.jpg"


def test_reference_multi_model_routes_to_multi_skill_payload():
    payload, kind = normalize_request({
        "entry": "img2video",
        "mode": "reference",
        "imageList": [IMG, "https://example.com/detail.jpg"],
        "videoType": "seedance2.0",
        "videoTime": 10,
        "resolution": "1080p",
        "aspectRatio": "16:9",
    })
    assert kind == "multi"
    assert payload["imageList"] == [IMG, "https://example.com/detail.jpg"]
    assert payload["videoType"] == "seedance2.0"


def test_hailuo_ui_six_seconds_is_preserved():
    payload, kind = normalize_request({
        "entry": "img2video", "mode": "reference", "imageUrl": IMG,
        "videoType": "海螺2.3", "videoTime": 6, "resolution": "1080p",
    })
    assert kind == "single"
    assert payload["videoTime"] == 6
    assert payload["imageUrl"] == IMG
    assert "imageList" not in payload


def test_kling_first_last_frame_tail_requires_1080p_without_voice():
    with pytest.raises(LinkFoxVideoError):
        normalize_request({
            "entry": "img2video", "mode": "first_last_frame", "imageUrl": IMG,
            "lastFrameImageUrl": "https://example.com/end.jpg", "videoType": "可灵2.6",
            "videoTime": 5, "resolution": "720p", "voice": False,
        })


def test_local_asset_url_is_rejected_before_skill_call():
    with pytest.raises(LinkFoxVideoError, match=r"HTTP\(S\)"):
        normalize_request({
            "entry": "img2video", "imageList": ["/assets/output/local.png"],
            "videoType": "seedance2.0", "videoTime": 5,
        })


def test_skill_files_are_installed_in_project_workspace():
    root = Path(__file__).resolve().parents[1]
    assert (root / "skills" / "e-commerce-find-skills" / "SKILL.md").is_file()
    assert (root / "skills" / "linkfox-expert-aigc-videogen-image-to-video" / "SKILL.md").is_file()


def test_both_canvas_runtimes_expose_linkfox_node_and_run_endpoint():
    root = Path(__file__).resolve().parents[1]
    classic = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
    smart = (root / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
    module = (root / "static" / "js" / "canvas-linkfox-video.js").read_text(encoding="utf-8")
    assert "menuAdd('linkfox-video')" in (root / "static" / "canvas.html").read_text(encoding="utf-8")
    assert 'data-create-type="linkfox-video"' in (root / "static" / "smart-canvas.html").read_text(encoding="utf-8")
    assert "runLinkfoxVideoNode" in classic
    assert "runSmartLinkfoxVideoNode" in smart
    assert "fetch('/api/linkfox-video'" in classic
    assert "fetch('/api/linkfox-video'" in smart
    assert "entry:'img2video'" in module

