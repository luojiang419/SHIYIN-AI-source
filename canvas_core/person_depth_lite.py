"""轻量人物深度：独立下载人体分割权重，复用 CPU 深度推理。"""
from __future__ import annotations

import threading

from .depth_models import DepthModelManager, DepthModelSpec
from .depth_inference import DepthUnavailableError

MASK_NAME = "human_segmentation_pphumanseg_2023mar.onnx"
MASK_SPEC = DepthModelSpec(
    name=MASK_NAME, size=6_163_938,
    sha256="552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24",
    official_url="https://huggingface.co/opencv/human_segmentation_pphumanseg/resolve/e876e63603f6c65c1a22576bfd5fc7c07ecf9eb9/" + MASK_NAME,
)


class PersonDepthLite:
    def __init__(self, depth_manager):
        self.manager = DepthModelManager(depth_manager.model_root / "person-mask", specs=(MASK_SPEC,))
        self._lock = threading.Lock()
        self._net = None

    def mask(self, image_rgb):
        import cv2
        import numpy as np

        with self._lock:
            if self._net is None:
                if not self.manager.ensure_now():
                    raise DepthUnavailableError("人物分割模型下载失败，请重试：" + str(self.manager.status().get("error", "")))
                try:
                    self._net = cv2.dnn.readNet(str(self.manager.model_path(MASK_NAME)))
                    self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                except cv2.error as exc:
                    raise DepthUnavailableError("人物分割模型加载失败") from exc
            rgb = cv2.resize(image_rgb, (192, 192)).astype(np.float32) / 127.5 - 1.0
            self._net.setInput(cv2.dnn.blobFromImage(rgb))
            try:
                prediction = self._net.forward()
            except cv2.error as exc:
                raise DepthUnavailableError("人物分割推理失败") from exc
        if prediction.shape != (1, 2, 192, 192) or not np.isfinite(prediction).all():
            raise DepthUnavailableError("人物分割输出无效")
        # 输出已经是概率，不能再次 softmax。先放大概率，再阈值化。
        probability = cv2.resize(prediction[0, 1], (image_rgb.shape[1], image_rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
        if np.count_nonzero(probability > 0.5) < 16:
            raise DepthUnavailableError("未识别到人物，请使用人物清晰的图片或切换专业模式")
        return np.clip((probability - 0.5) / 0.4, 0.0, 1.0)
