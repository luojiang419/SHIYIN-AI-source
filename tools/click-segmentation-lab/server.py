from __future__ import annotations

import base64
import io
import os
import secrets
import sys
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from segmenter import SegmentationSession, SamSegmenter, decode_image, mask_png, refine_alpha, rgba_png


class Point(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    label: int = Field(ge=0, le=1)


class SegmentRequest(BaseModel):
    session_id: str
    points: list[Point] = Field(min_length=1, max_length=64)
    threshold: float = Field(default=0.5, ge=0.05, le=0.95)
    feather: float = Field(default=1.5, ge=0, le=16)
    edge_shift: int = Field(default=0, ge=-20, le=20)


app = FastAPI(title="SHIYIN 点击抠图技术验证")
engine = SamSegmenter()
sessions: dict[str, tuple[float, SegmentationSession]] = {}
sessions_lock = threading.RLock()


def get_session(session_id: str) -> SegmentationSession:
    with sessions_lock:
        item = sessions.get(session_id)
        if item is None:
            raise HTTPException(404, "图片会话不存在，请重新导入")
        sessions[session_id] = (time.time(), item[1])
        return item[1]


def cleanup_sessions() -> None:
    cutoff = time.time() - 3600
    with sessions_lock:
        expired = [key for key, (used_at, _) in sessions.items() if used_at < cutoff]
        for key in expired:
            sessions.pop(key, None)


def encode_preview(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def build_alpha(request: SegmentRequest) -> tuple[SegmentationSession, np.ndarray]:
    session = get_session(request.session_id)
    points = [point.model_dump() for point in request.points]
    try:
        mask = engine.segment(session, points)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"分割失败：{exc}") from exc
    positive = [(round(point.x), round(point.y)) for point in request.points if point.label == 1]
    alpha = refine_alpha(mask, request.threshold, request.feather, positive, request.edge_shift)
    return session, alpha


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/app.js")
def script() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "app.js", media_type="text/javascript")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "styles.css", media_type="text/css")


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "model": engine.model_id, "loaded": engine._model is not None}


@app.post("/api/images")
async def upload_image(image: UploadFile = File(...)) -> dict[str, int | str]:
    cleanup_sessions()
    payload = await image.read()
    try:
        decoded = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    session_id = secrets.token_urlsafe(24)
    with sessions_lock:
        sessions[session_id] = (time.time(), SegmentationSession(decoded))
    width, height = decoded.size
    preview = decoded.copy()
    buffer = io.BytesIO()
    preview.thumbnail((1600, 1200))
    preview.save(buffer, "JPEG", quality=92)
    return {"session_id": session_id, "width": width, "height": height, "preview": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}


@app.post("/api/segment")
def segment(request: SegmentRequest) -> dict[str, str]:
    _, alpha = build_alpha(request)
    return {"mask": encode_preview(mask_png(alpha))}


@app.post("/api/export/{kind}")
def export(kind: str, request: SegmentRequest) -> Response:
    session, alpha = build_alpha(request)
    if kind == "cutout":
        payload, filename = rgba_png(session.image, alpha), "shiyin-cutout.png"
    elif kind == "mask":
        payload, filename = mask_png(alpha), "shiyin-mask.png"
    else:
        raise HTTPException(404, "不支持的导出类型")
    return Response(payload, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("SHIYIN_SEGMENT_PORT", "8791")))
