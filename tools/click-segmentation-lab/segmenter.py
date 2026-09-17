from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps


MAX_IMAGE_PIXELS = 60_000_000
DEFAULT_MODEL = "facebook/sam-vit-base"


def decode_image(payload: bytes) -> Image.Image:
    if not payload:
        raise ValueError("图片内容为空")
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(payload)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
    except Exception as exc:
        raise ValueError("无法读取该图片，请使用 JPEG、PNG 或 WebP") from exc
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("图片像素过大，当前上限为 6000 万像素")
    return image


def refine_alpha(mask: np.ndarray, threshold: float, feather: float, positive_points: list[tuple[int, int]]) -> np.ndarray:
    probability = np.clip(mask.astype(np.float32), 0.0, 1.0)
    binary = (probability >= threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count > 1 and positive_points:
        selected = set()
        height, width = binary.shape
        for x, y in positive_points:
            selected.add(int(labels[min(max(y, 0), height - 1), min(max(x, 0), width - 1)]))
        selected.discard(0)
        if selected:
            binary = np.isin(labels, list(selected)).astype(np.uint8)
    if count > 1:
        minimum = max(16, int(binary.size * 0.00002))
        keep = [index for index in range(1, count) if stats[index, cv2.CC_STAT_AREA] >= minimum]
        if keep and not positive_points:
            binary = np.isin(labels, keep).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(binary, contours, -1, 1, thickness=cv2.FILLED)
    radius = max(0.0, float(feather))
    if radius == 0:
        return binary.astype(np.float32)
    sigma = max(0.35, radius / 2.0)
    softened = cv2.GaussianBlur(binary.astype(np.float32), (0, 0), sigmaX=sigma, sigmaY=sigma)
    return np.clip(softened, 0.0, 1.0)


def rgba_png(image: Image.Image, alpha: np.ndarray) -> bytes:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    alpha_u8 = np.round(np.clip(alpha, 0.0, 1.0) * 255).astype(np.uint8)
    output = Image.fromarray(np.dstack((rgb, alpha_u8)), "RGBA")
    buffer = io.BytesIO()
    output.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def mask_png(alpha: np.ndarray) -> bytes:
    output = Image.fromarray(np.round(np.clip(alpha, 0.0, 1.0) * 255).astype(np.uint8), "L")
    buffer = io.BytesIO()
    output.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def choose_mask(masks: np.ndarray, scores: np.ndarray, points: list[dict[str, float | int]]) -> int:
    """Prefer a confident local object over a near-full-frame SAM candidate."""
    height, width = masks.shape[-2:]
    ranked: list[tuple[float, int]] = []
    for index, candidate in enumerate(masks):
        binary = candidate >= 0.5
        area_ratio = float(binary.mean())
        positive_hits = 0
        negative_hits = 0
        for point in points:
            x = min(max(round(float(point["x"])), 0), width - 1)
            y = min(max(round(float(point["y"])), 0), height - 1)
            hit = bool(binary[y, x])
            if int(point["label"]) == 1:
                positive_hits += int(hit)
            else:
                negative_hits += int(hit)
        utility = float(scores[index]) + positive_hits * 0.35 - negative_hits * 0.8
        if area_ratio > 0.9:
            utility -= 2.0 + area_ratio
        ranked.append((utility, index))
    return max(ranked)[1]


@dataclass
class SegmentationSession:
    image: Image.Image
    embedding: object | None = None
    last_mask: np.ndarray | None = None
    last_points: tuple[tuple[int, int, int], ...] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class SamSegmenter:
    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or os.getenv("SHIYIN_SEGMENT_MODEL", DEFAULT_MODEL)
        self._model = None
        self._processor = None
        self._device = None
        self._load_lock = threading.RLock()

    def _load(self) -> None:
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            from transformers import SamModel, SamProcessor

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            dtype = torch.float16 if self._device.type == "cuda" else torch.float32
            self._processor = SamProcessor.from_pretrained(self.model_id)
            self._model = SamModel.from_pretrained(self.model_id, dtype=dtype).to(self._device).eval()

    def prepare(self, session: SegmentationSession) -> None:
        self._load()
        if session.embedding is not None:
            return
        import torch

        inputs = self._processor(images=session.image, return_tensors="pt")
        pixels = inputs["pixel_values"].to(device=self._device, dtype=self._model.dtype)
        with torch.inference_mode():
            session.embedding = self._model.get_image_embeddings(pixels)

    def segment(self, session: SegmentationSession, points: list[dict[str, float | int]]) -> np.ndarray:
        if not points:
            raise ValueError("至少需要一个提示点")
        with session.lock:
            point_key = tuple(
                (round(float(item["x"])), round(float(item["y"])), int(item["label"]))
                for item in points
            )
            if session.last_mask is not None and session.last_points == point_key:
                return session.last_mask
            self.prepare(session)
            import torch

            coordinates = [[[float(item["x"]), float(item["y"])] for item in points]]
            labels = [[int(item["label"]) for item in points]]
            inputs = self._processor(
                images=session.image,
                input_points=coordinates,
                input_labels=labels,
                return_tensors="pt",
            )
            model_inputs = {
                "image_embeddings": session.embedding,
                "input_points": inputs["input_points"].to(self._device),
                "input_labels": inputs["input_labels"].to(self._device),
                "multimask_output": True,
            }
            with torch.inference_mode():
                outputs = self._model(**model_inputs)
            scores = outputs.iou_scores[0, 0].float().cpu().numpy()
            masks = self._processor.image_processor.post_process_masks(
                outputs.pred_masks.cpu(), inputs["original_sizes"], inputs["reshaped_input_sizes"]
            )[0]
            candidates = masks[0].float().cpu().numpy()
            best = choose_mask(candidates, scores, points)
            session.last_mask = candidates[best]
            session.last_points = point_key
            return session.last_mask
