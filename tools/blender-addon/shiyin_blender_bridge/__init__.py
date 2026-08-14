bl_info = {
    "name": "SHIYIN AI Blender Bridge",
    "author": "SHIYIN AI",
    "version": (1, 1, 0),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar > SHIYIN AI",
    "description": "Automatically connect Blender cameras and renders to the SHIYIN AI canvas",
    "category": "3D View",
}

import hmac
import json
import math
import os
import queue
import secrets
import socket
import tempfile
import threading
import time
from pathlib import Path

import bpy


PROTOCOL = "shiyin-blender/2"
MAX_MESSAGE_BYTES = 1024 * 1024
ALLOWED_ACTIONS = {"ping", "authenticate", "scene_state", "set_camera", "render_still", "render_animation"}
EXCHANGE_ROOT = (Path(tempfile.gettempdir()) / "SHIYIN-AI-Blender").resolve()
SECRET_FILE_NAME = "blender-bridge.key"
MIN_SECRET_LENGTH = 48


def _shared_secret_path():
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "SHIYIN AI" / SECRET_FILE_NAME
    return Path.home() / ".shiyin-ai" / SECRET_FILE_NAME


def _load_or_create_shared_secret():
    path = _shared_secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    for _attempt in range(20):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                secret = path.read_text(encoding="ascii").strip()
            except OSError:
                secret = ""
            if len(secret) >= MIN_SECRET_LENGTH:
                return secret
            time.sleep(0.05)
            continue
        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write(secret + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return secret
    raise RuntimeError("SHIYIN AI 自动连接密钥文件无效：%s" % path)


def _safe_float(value, fallback=0.0, minimum=-100000.0, maximum=100000.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    return max(minimum, min(maximum, number))


def _safe_int(value, fallback, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback
    return max(minimum, min(maximum, number))


def _camera_state(scene):
    camera = scene.camera
    if not camera:
        return None
    return {
        "name": camera.name,
        "location": [round(float(value), 5) for value in camera.location],
        "rotation": [round(math.degrees(float(value)), 5) for value in camera.rotation_euler],
        "lens": round(float(camera.data.lens), 3),
    }


def _scene_state():
    scene = bpy.context.scene
    return {
        "blender_version": bpy.app.version_string,
        "scene": scene.name,
        "camera": _camera_state(scene),
        "frame_current": int(scene.frame_current),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "resolution_x": int(scene.render.resolution_x),
        "resolution_y": int(scene.render.resolution_y),
        "engine": str(scene.render.engine),
        "object_count": len(scene.objects),
    }


def _ensure_camera(scene):
    camera = scene.camera
    if camera and camera.type == "CAMERA":
        return camera
    data = bpy.data.cameras.new("SHIYIN Camera")
    camera = bpy.data.objects.new("SHIYIN Camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def _set_camera(payload):
    scene = bpy.context.scene
    camera = _ensure_camera(scene)
    location = payload.get("location") or []
    rotation = payload.get("rotation") or []
    if len(location) == 3:
        camera.location = tuple(_safe_float(value) for value in location)
    if len(rotation) == 3:
        camera.rotation_euler = tuple(math.radians(_safe_float(value, minimum=-3600, maximum=3600)) for value in rotation)
    camera.data.lens = _safe_float(payload.get("lens"), camera.data.lens, 1.0, 300.0)
    scene.frame_set(_safe_int(payload.get("frame"), scene.frame_current, scene.frame_start, scene.frame_end))
    return _scene_state()


def _render_still(payload, request_id):
    scene = bpy.context.scene
    if not scene.camera:
        raise RuntimeError("当前场景没有活动相机")
    EXCHANGE_ROOT.mkdir(parents=True, exist_ok=True)
    target = EXCHANGE_ROOT / ("shiyin_%s.png" % request_id)
    previous_path = scene.render.filepath
    previous_format = scene.render.image_settings.file_format
    try:
        scene.render.filepath = str(target)
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
    finally:
        scene.render.filepath = previous_path
        scene.render.image_settings.file_format = previous_format
    if not target.is_file():
        raise RuntimeError("Blender 没有生成渲染图片")
    return {"kind": "image", "path": str(target), "scene": _scene_state()}


def _render_animation(payload, request_id):
    scene = bpy.context.scene
    if not scene.camera:
        raise RuntimeError("当前场景没有活动相机")
    EXCHANGE_ROOT.mkdir(parents=True, exist_ok=True)
    base = EXCHANGE_ROOT / ("shiyin_%s" % request_id)
    target = base.with_suffix(".mp4")
    previous = {
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "media_type": getattr(scene.render.image_settings, "media_type", None),
        "use_file_extension": scene.render.use_file_extension,
        "frame_current": scene.frame_current,
    }
    requested_start = _safe_int(payload.get("frame_start"), scene.frame_start, -100000, 100000)
    requested_end = _safe_int(payload.get("frame_end"), scene.frame_end, requested_start, 100000)
    previous_start, previous_end = scene.frame_start, scene.frame_end
    try:
        scene.frame_start = requested_start
        scene.frame_end = requested_end
        scene.render.filepath = str(base)
        if hasattr(scene.render.image_settings, "media_type"):
            scene.render.image_settings.media_type = "VIDEO"
        else:
            scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.audio_codec = "AAC"
        scene.render.use_file_extension = True
        bpy.ops.render.render(animation=True)
    finally:
        scene.frame_start, scene.frame_end = previous_start, previous_end
        scene.frame_set(previous["frame_current"])
        scene.render.filepath = previous["filepath"]
        if previous["media_type"] is not None:
            scene.render.image_settings.media_type = previous["media_type"]
        scene.render.image_settings.file_format = previous["file_format"]
        scene.render.image_settings.color_mode = previous["color_mode"]
        scene.render.use_file_extension = previous["use_file_extension"]
    if not target.is_file():
        matches = sorted(EXCHANGE_ROOT.glob(base.name + "*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
        if matches:
            target = matches[0]
    if not target.is_file():
        raise RuntimeError("Blender 没有生成 MP4 动画")
    return {"kind": "video", "path": str(target), "scene": _scene_state()}


class _WorkItem:
    def __init__(self, request):
        self.request = request
        self.event = threading.Event()
        self.response = None


class _BridgeServer:
    def __init__(self):
        self.port = 9876
        self.session_token = ""
        self.shared_secret = ""
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self._socket = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self, port):
        port = _safe_int(port, 9876, 1024, 65535)
        if self.running and self.port == port:
            return
        self.stop()
        self.port = port
        self.shared_secret = _load_or_create_shared_secret()
        self.session_token = ""
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="shiyin-blender-bridge", daemon=True)
        self._thread.start()
        if not bpy.app.timers.is_registered(self._drain):
            bpy.app.timers.register(self._drain, first_interval=0.05, persistent=True)

    def stop(self):
        self._stop.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        self._thread = None
        if bpy.app.timers.is_registered(self._drain):
            bpy.app.timers.unregister(self._drain)

    def _serve(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket = server
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", self.port))
        server.listen(4)
        server.settimeout(0.5)
        while not self._stop.is_set():
            try:
                connection, _address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_connection, args=(connection,), daemon=True).start()

    def _handle_connection(self, connection):
        with connection:
            connection.settimeout(15.0)
            request_id = ""
            try:
                raw = b""
                while b"\n" not in raw and len(raw) <= MAX_MESSAGE_BYTES:
                    chunk = connection.recv(65536)
                    if not chunk:
                        break
                    raw += chunk
                request = json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
                request_id = str(request.get("id") or "")
                response = self._route(request)
            except Exception as exc:
                response = {"id": request_id, "ok": False, "error": str(exc)}
            connection.sendall(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")

    def _route(self, request):
        request_id = str(request.get("id") or "")
        action = str(request.get("action") or "")
        if request.get("protocol") != PROTOCOL or not request_id:
            raise RuntimeError("无效的 SHIYIN 协议请求")
        if action not in ALLOWED_ACTIONS:
            raise RuntimeError("不允许的命令")
        if action == "ping":
            return {"id": request_id, "ok": True, "data": {"addon_version": "1.1.0", "blender_version": bpy.app.version_string}}
        payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
        if action == "authenticate":
            shared_secret = str(payload.get("shared_secret") or "")
            if not self.shared_secret or not hmac.compare_digest(shared_secret, self.shared_secret):
                raise RuntimeError("自动连接认证失败")
            self.session_token = secrets.token_urlsafe(32)
            return {"id": request_id, "ok": True, "data": {"session_token": self.session_token, "scene": _scene_state()}}
        if not self.session_token or not hmac.compare_digest(str(request.get("session_token") or ""), self.session_token):
            raise RuntimeError("session token 无效，请重新自动连接")
        item = _WorkItem(request)
        self._queue.put(item)
        timeout = 7200 if action == "render_animation" else 900
        if not item.event.wait(timeout):
            raise RuntimeError("Blender 命令执行超时")
        return item.response

    def _drain(self):
        if self._stop.is_set():
            return None
        try:
            item = self._queue.get_nowait()
        except queue.Empty:
            return 0.05
        request = item.request
        request_id = str(request.get("id") or "")
        action = str(request.get("action") or "")
        payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
        try:
            if action == "scene_state":
                data = _scene_state()
            elif action == "set_camera":
                data = _set_camera(payload)
            elif action == "render_still":
                data = _render_still(payload, request_id)
            elif action == "render_animation":
                data = _render_animation(payload, request_id)
            else:
                raise RuntimeError("不允许的命令")
            item.response = {"id": request_id, "ok": True, "data": data}
        except Exception as exc:
            item.response = {"id": request_id, "ok": False, "error": str(exc)}
        finally:
            item.event.set()
        return 0.01


_SERVER = _BridgeServer()


class SHIYIN_OT_bridge_toggle(bpy.types.Operator):
    bl_idname = "shiyin.bridge_toggle"
    bl_label = "启动/停止桥接"

    def execute(self, context):
        if _SERVER.running:
            _SERVER.stop()
        else:
            _SERVER.start(9876)
        return {"FINISHED"}


class SHIYIN_PT_bridge_panel(bpy.types.Panel):
    bl_label = "SHIYIN AI 导演台"
    bl_idname = "SHIYIN_PT_bridge_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SHIYIN AI"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("shiyin.bridge_toggle", text="停止服务" if _SERVER.running else "启动服务", icon="PAUSE" if _SERVER.running else "PLAY")
        box = layout.box()
        box.label(text="已启用自动连接" if _SERVER.running else "自动连接服务未启动", icon="LINKED" if _SERVER.running else "UNLINKED")
        box.label(text="仅监听 127.0.0.1:%d" % _SERVER.port)
        box.label(text="支持相机同步、图片和 MP4 渲染")


CLASSES = (SHIYIN_OT_bridge_toggle, SHIYIN_PT_bridge_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    # Add-on enabling runs with Blender's restricted context, where context.scene is unavailable.
    _SERVER.start(9876)


def unregister():
    _SERVER.stop()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
