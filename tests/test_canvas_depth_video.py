import io
import json
from pathlib import Path

import canvas_core.video_depth as video_depth
from canvas_core.video_depth import VideoDepthTaskService


ROOT = Path(__file__).resolve().parents[1]


def test_depth_video_frontend_contract():
    shared = (ROOT / "static/js/canvas-special-nodes.js").read_text(encoding="utf-8")
    styles = (ROOT / "static/css/canvas-special-nodes.css").read_text(encoding="utf-8")
    classic = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
    smart = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
    classic_html = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
    smart_html = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")

    assert "depthVideoBodyHtml" in shared
    assert "bindDepthVideo" in shared
    assert 'accept="video/*,.mkv,.avi"' in shared
    assert 'data-depth-video-play="input"' not in shared  # generated through the shared player helper
    assert 'data-depth-video-play="${slot}"' in shared
    assert "object-fit:contain" in styles
    assert "aspect-ratio:16/9" in styles
    assert "depth-video-preview-grid" in styles
    assert 'data-special-action="compare-depth-video"' in shared
    assert 'data-special-action="import-depth-video-runtime"' not in shared
    assert 'data-depth-video-seek="${slot}"' in shared
    assert "function openDepthVideoCompare(node)" in shared
    assert "depth-video-compare-wipe" in styles
    assert "type:'depthVideo'" in classic
    assert "specialType:'depth-video'" in smart
    assert "getInputVideo:classicSpecialInputVideo" in classic
    assert "getInputVideo:smartSpecialInputVideo" in smart
    assert "['panorama','dwpose','depthMap','depthVideo','angle'].includes(node.type)" in classic
    assert "node.type === 'depthVideo' ? 'video' : 'image'" in classic
    assert "menuAdd('depthVideo')" in classic_html
    assert 'data-create-type="depth-video"' in smart_html


def test_depth_video_api_contract():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/video-depth/upload")' in main_source
    assert '@app.post("/api/video-depth/tasks", status_code=202)' in main_source
    assert '@app.get("/api/video-depth/tasks/{task_id}")' in main_source
    assert "2 * 1024 * 1024 * 1024" in main_source


def test_service_runs_validated_full_video_profile(tmp_path, monkeypatch):
    service = VideoDepthTaskService(tmp_path)
    service.worker.parent.mkdir(parents=True)
    service.worker.write_text("# worker", encoding="utf-8")
    service.python.parent.mkdir(parents=True)
    service.python.write_text("", encoding="utf-8")
    service.deployment.parent.mkdir(parents=True, exist_ok=True)
    service.deployment.write_text(json.dumps({"models": [{"key": "vda_base_fp16_relative", "ready": True}]}), encoding="utf-8")
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    output_root = tmp_path / "outputs"
    captured = {}

    class FakeProcess:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            output_dir = Path(command[command.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / "depth-preview.mp4"
            output.write_bytes(b"depth-video")
            result = {"outputVideoPath": str(output), "input": {"processedWidth": 1080, "processedHeight": 1920, "processedFps": 30, "processedFrames": 90}}
            self.stdout = io.StringIO('\n'.join([
                json.dumps({"type": "progress", "percent": 48, "message": "推理中"}),
                json.dumps({"type": "result", "result": result}),
            ]) + '\n')
            self.stderr = io.StringIO("")

        def wait(self):
            return 0

    monkeypatch.setattr(video_depth.subprocess, "Popen", FakeProcess)
    task_id = "task"
    service._tasks[task_id] = {"id": task_id}
    service._run(task_id, source, output_root / task_id, lambda path: "/assets/output/" + Path(path).name)
    task = service.get(task_id)

    assert task["status"] == "done"
    assert task["progress"] == 100
    assert (task["width"], task["height"], task["fps"], task["frameCount"]) == (1080, 1920, 30.0, 90)
    command = captured["command"]
    assert command[command.index("--model") + 1] == "vda_base_fp16_relative"
    assert command[command.index("--input-size") + 1] == "322"
    assert command[command.index("--target-fps") + 1] == "-1"
    assert command[command.index("--max-frames") + 1] == "-1"
    assert command[command.index("--max-resolution") + 1] == "-1"


def test_video_depth_service_closes_persistent_worker(tmp_path):
    service = VideoDepthTaskService(tmp_path)

    class FakeInput:
        def __init__(self):
            self.content = b""

        def write(self, content):
            self.content += content

        def flush(self):
            pass

    class FakeProcess:
        def __init__(self):
            self.stdin = FakeInput()
            self.killed = False

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    process = FakeProcess()
    service._worker_process = process
    service.close()

    assert json.loads(process.stdin.content.decode("utf-8"))["op"] == "shutdown"
    assert service._worker_process is None
