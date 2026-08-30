from __future__ import annotations

import threading
from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

from .depth_models import DEPTH_MODEL_NAME, DepthModelManager

DEPTH_INPUT_SIZE = (256, 256)


class DepthUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DepthResult:
    image_gray: np.ndarray
    width: int
    height: int


class DepthInference:
    def __init__(self, model_manager: DepthModelManager) -> None:
        self.model_manager = model_manager
        self._session_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._session: ort.InferenceSession | None = None

    def _ensure_session(self) -> ort.InferenceSession:
        with self._session_lock:
            if self._session is not None:
                return self._session
            if not self.model_manager.status().get("ready") and not self.model_manager.verify_installed():
                raise DepthUnavailableError("深度模型尚未下载完成")
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            try:
                self._session = ort.InferenceSession(
                    str(self.model_manager.model_path(DEPTH_MODEL_NAME)),
                    sess_options=options,
                    providers=["CPUExecutionProvider"],
                )
            except Exception as exc:  # noqa: BLE001
                raise DepthUnavailableError(f"深度模型加载失败：{exc}") from exc
            return self._session

    def render(self, image_rgb: np.ndarray) -> DepthResult:
        if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or not image_rgb.size:
            raise ValueError("输入必须是非空 RGB 图片")
        session = self._ensure_session()
        height, width = image_rgb.shape[:2]
        resized = cv2.resize(image_rgb, DEPTH_INPUT_SIZE, interpolation=cv2.INTER_AREA)
        # MiDaS Small ONNX expects BGR with ImageNet normalization.
        bgr = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR).astype(np.float32) / 255.0
        normalized = (bgr - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None], dtype=np.float32)
        with self._inference_lock:
            output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
        depth = np.asarray(output, dtype=np.float32).squeeze()
        if depth.ndim != 2 or not np.isfinite(depth).any():
            raise DepthUnavailableError("深度模型输出为空")
        depth = np.nan_to_num(depth, copy=False)
        depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_CUBIC)
        low, high = float(np.percentile(depth, 1)), float(np.percentile(depth, 99))
        if high <= low:
            low, high = float(depth.min()), float(depth.max())
        if high <= low:
            gray = np.full((height, width), 127, dtype=np.uint8)
        else:
            gray = np.clip((depth - low) / (high - low), 0.0, 1.0)
            gray = np.round(gray * 255.0).astype(np.uint8)
        return DepthResult(image_gray=gray, width=width, height=height)
