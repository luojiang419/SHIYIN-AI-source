import asyncio
import json
from pathlib import Path

import httpx
import pytest

from canvas_core.linkfox_video import LinkFoxVideoError, normalize_request, prepare_image_inputs


def request(**extra):
    return dict(entry="img2video", mode="reference", videoType="seedance2.0",
                videoTime=10, imageList=["/assets/input/a.png"], **extra)


def prepare(tmp_path, data=None, *, failure="", published=""):
    image = tmp_path / "a.png"
    image.write_bytes(b"image fixture")
    calls = []

    def handler(req):
        calls.append(req)
        if req.method == "POST":
            assert req.url.path == "/oss/file/presignedPut"
            assert req.headers["Authorization"] == "fixture-key"
            assert json.loads(req.content) == {"contentType": "image/png", "fileExtension": "png"}
            if failure == "network":
                raise httpx.ConnectError("private-url-must-not-leak", request=req)
            if failure == "auth":
                return httpx.Response(401)
            if failure == "business":
                return httpx.Response(200, json={"errcode": 401, "errmsg": "private response"})
            if failure == "json":
                return httpx.Response(200, content="not json")
            return httpx.Response(200, json={"errcode": 200, "url": "https://oss.example.com/a.png?secret=signature"})
        assert req.method == "PUT"
        assert req.content == b"image fixture"
        assert "Authorization" not in req.headers
        assert req.headers["x-oss-object-acl"] == "public-read"
        return httpx.Response(500 if failure == "put" else 200)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await prepare_image_inputs(data or request(), client=client, api_key="fixture-key",
                gateway="https://tool-gateway.linkfox.com", resolve_path=lambda url: image if url == "/assets/input/a.png" else None,
                public_url=lambda _: published)
            return result, calls
    return asyncio.run(run())


def test_local_image_upload_and_duplicate_fields_share_public_url(tmp_path):
    data = request(imageUrl="/assets/input/a.png")
    result, calls = prepare(tmp_path, data)
    assert len(calls) == 2
    assert result["imageList"] == ["https://oss.example.com/a.png"]
    assert result["imageUrl"] == result["imageList"][0]
    assert normalize_request(result)[1] == "multi"


def test_public_url_and_configured_media_host_skip_upload(tmp_path):
    data = request()
    data["imageList"] = ["https://example.com/a.jpg"]
    assert prepare(tmp_path, data)[1] == []
    result, calls = prepare(tmp_path, published="https://media.example.com/a.png")
    assert calls == []
    assert result["imageList"] == ["https://media.example.com/a.png"]


@pytest.mark.parametrize("failure", ["auth", "business", "json", "put", "network"])
def test_upload_failures_are_actionable_and_do_not_leak_secrets(tmp_path, failure):
    with pytest.raises(LinkFoxVideoError, match="上传") as error:
        prepare(tmp_path, failure=failure)
    assert "secret" not in str(error.value)
    assert "private" not in str(error.value)


def test_missing_local_image_is_not_sent_as_public_url(tmp_path):
    data = request()
    data["imageList"] = ["/assets/input/missing.png"]
    with pytest.raises(LinkFoxVideoError, match="文件不存在"):
        prepare(tmp_path, data)


def test_invalid_count_is_rejected_before_upload(tmp_path):
    data = request()
    data["imageList"] *= 10
    with pytest.raises(LinkFoxVideoError, match="最多支持 9"):
        prepare(tmp_path, data, failure="network")


def test_first_last_list_fallback_and_limit():
    data = request()
    data.update(mode="first_last_frame", imageList=["https://e.com/first.png", "https://e.com/last.png"])
    payload, kind = normalize_request(data)
    assert kind == "single"
    assert payload["imageUrl"].endswith("/first.png")
    assert payload["lastFrameImageUrl"].endswith("/last.png")
    data["lastFrameImageUrl"] = "https://e.com/third.png"
    with pytest.raises(LinkFoxVideoError, match="两张"):
        normalize_request(data)


def test_base64_image_uses_same_upload_protocol(tmp_path):
    data = request()
    data["imageList"] = ["data:image/png;base64,aW1hZ2UgZml4dHVyZQ=="]
    result, calls = prepare(tmp_path, data)
    assert len(calls) == 2
    assert result["imageList"] == ["https://oss.example.com/a.png"]


def test_route_upload_failure_never_starts_generation(monkeypatch):
    import main
    async def fail(*args, **kwargs):
        raise LinkFoxVideoError("LinkFox 图片上传失败")
    monkeypatch.setattr(main, "prepare_linkfox_image_inputs", fail)
    monkeypatch.setattr(main, "linkfox_configured_key", lambda: "fixture-key")
    monkeypatch.setattr(main, "linkfox_tool_gateway", lambda: "https://tool-gateway.linkfox.com")
    monkeypatch.setattr(main, "run_linkfox_video_skill", lambda *a, **k: pytest.fail("must not generate"))
    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.linkfox_video(main.LinkFoxVideoRequest(**request())))
    assert error.value.status_code == 400


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("model,expected", [("seedance2.0", "SEED"), ("seedance2.0fast", "SEED_FAST"), ("可灵Omni", "KLING"), ("HappyHorse", "HAPPY_HORSE")])
def test_skill_receives_api_enum_and_explicit_credentials(tmp_path, monkeypatch, model, expected, frozen):
    from canvas_core import linkfox_video
    from types import SimpleNamespace
    video = tmp_path / "result.mp4"
    video.write_bytes(b"video fixture")
    monkeypatch.setattr(linkfox_video, "_skill_path", lambda *_: tmp_path / "skill.py")
    monkeypatch.setattr(linkfox_video.sys, "frozen", frozen, raising=False)
    def run(command, **options):
        if frozen:
            assert command[1:3] == ["--linkfox-video-skill", "multi"]
        payload = json.loads(command[-1])
        assert payload["videoType"] == expected
        assert payload["imageList"] == ["https://example.com/a.png"]
        assert "entry" not in payload and "mode" not in payload
        assert options["env"]["LINKFOX_AGENT_API_KEY"] == "fixture-key"
        assert options["env"]["LINKFOX_TOOL_GATEWAY"] == "https://tool-gateway.linkfox.com"
        assert options["encoding"] == "utf-8"
        stdout = f"Saved full response: {json.dumps([str(video)])}"
        if frozen:
            Path(options["env"]["LINKFOX_SKILL_RESULT_FILE"]).write_text(json.dumps({"stdout": stdout}), encoding="utf-8")
            stdout = ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    monkeypatch.setattr(linkfox_video.subprocess, "run", run)
    data = request()
    data.update(videoType=model, imageList=["https://example.com/a.png"])
    result = linkfox_video.run_skill(data, project_root=tmp_path, output_dir=tmp_path / "output",
        api_key="fixture-key", gateway="https://tool-gateway.linkfox.com")
    assert Path(result["paths"][0]).read_bytes() == b"video fixture"


def test_sidecar_dispatches_only_bundled_skill_without_starting_server(tmp_path, monkeypatch):
    import backend_entry
    import sys
    script = tmp_path / "skills/linkfox-expert-aigc-videogen-image-to-video/skills/linkfox-aigc-videogen-multi/scripts/aigc_videogen_multi.py"
    script.parent.mkdir(parents=True)
    marker = tmp_path / "called.txt"
    script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('executed')\n", encoding="utf-8")
    monkeypatch.setattr(backend_entry, "ENTRY_DIR", str(tmp_path))
    captured = tmp_path / "result.json"
    monkeypatch.setenv("LINKFOX_SKILL_RESULT_FILE", str(captured))
    monkeypatch.setattr(sys, "argv", ["sidecar.exe", "--linkfox-video-skill", "multi", str(marker)])
    backend_entry.main()
    assert marker.read_text() == "executed"
    assert json.loads(captured.read_text(encoding="utf-8")) == {"stdout": "", "stderr": ""}
    monkeypatch.setattr(sys, "argv", ["sidecar.exe", "--linkfox-video-skill", "../arbitrary.py", "{}"])
    with pytest.raises(SystemExit, match="Invalid"):
        backend_entry.main()
