from __future__ import annotations

"""CPU-only DWPose ONNX inference.

Adapted from IDEA-Research/DWPose's ONNX example (Apache-2.0). The local
adaptation removes Torch, Matplotlib and CUDA requirements and exposes a
thread-safe service suitable for the desktop backend.
"""

import colorsys
import math
import threading
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np
import onnxruntime as ort

from .dwpose_models import DWPoseModelManager


DETECTOR_INPUT_SIZE = (640, 640)
POSE_SCORE_THRESHOLD = 0.3


class DWPoseUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DWPoseResult:
    image_rgb: np.ndarray
    people: int
    keypoints: np.ndarray
    scores: np.ndarray


def _nms(boxes: np.ndarray, scores: np.ndarray, threshold: float) -> list[int]:
    if boxes.size == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        index = int(order[0])
        keep.append(index)
        xx1 = np.maximum(x1[index], x1[order[1:]])
        yy1 = np.maximum(y1[index], y1[order[1:]])
        xx2 = np.minimum(x2[index], x2[order[1:]])
        yy2 = np.minimum(y2[index], y2[order[1:]])
        width = np.maximum(0.0, xx2 - xx1 + 1)
        height = np.maximum(0.0, yy2 - yy1 + 1)
        intersection = width * height
        overlap = intersection / (areas[index] + areas[order[1:]] - intersection)
        order = order[np.where(overlap <= threshold)[0] + 1]
    return keep


def _multiclass_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    *,
    nms_threshold: float,
    score_threshold: float,
) -> np.ndarray | None:
    detections = []
    for class_index in range(scores.shape[1]):
        class_scores = scores[:, class_index]
        mask = class_scores > score_threshold
        if not np.any(mask):
            continue
        valid_scores = class_scores[mask]
        valid_boxes = boxes[mask]
        keep = _nms(valid_boxes, valid_scores, nms_threshold)
        if keep:
            classes = np.full((len(keep), 1), class_index)
            detections.append(np.concatenate([valid_boxes[keep], valid_scores[keep, None], classes], axis=1))
    return np.concatenate(detections, axis=0) if detections else None


def _detector_preprocess(image: np.ndarray) -> tuple[np.ndarray, float]:
    input_height, input_width = DETECTOR_INPUT_SIZE
    padded = np.full((input_height, input_width, 3), 114, dtype=np.uint8)
    ratio = min(input_height / image.shape[0], input_width / image.shape[1])
    resized = cv2.resize(
        image,
        (int(image.shape[1] * ratio), int(image.shape[0] * ratio)),
        interpolation=cv2.INTER_LINEAR,
    )
    padded[: resized.shape[0], : resized.shape[1]] = resized
    return np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32), ratio


def _detector_postprocess(outputs: np.ndarray) -> np.ndarray:
    grids = []
    expanded_strides = []
    for stride in (8, 16, 32):
        height = DETECTOR_INPUT_SIZE[0] // stride
        width = DETECTOR_INPUT_SIZE[1] // stride
        xv, yv = np.meshgrid(np.arange(width), np.arange(height))
        grid = np.stack((xv, yv), axis=2).reshape(1, -1, 2)
        grids.append(grid)
        expanded_strides.append(np.full((*grid.shape[:2], 1), stride))
    grid = np.concatenate(grids, axis=1)
    strides = np.concatenate(expanded_strides, axis=1)
    predictions = outputs.copy()
    predictions[..., :2] = (predictions[..., :2] + grid) * strides
    predictions[..., 2:4] = np.exp(predictions[..., 2:4]) * strides
    return predictions


def _detect_people(session: ort.InferenceSession, image: np.ndarray) -> np.ndarray:
    model_input, ratio = _detector_preprocess(image)
    output = session.run(None, {session.get_inputs()[0].name: model_input[None]})[0]
    predictions = _detector_postprocess(output)[0]
    boxes = predictions[:, :4]
    scores = predictions[:, 4:5] * predictions[:, 5:]
    boxes_xyxy = np.empty_like(boxes)
    boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    boxes_xyxy /= ratio
    detections = _multiclass_nms(boxes_xyxy, scores, nms_threshold=0.45, score_threshold=0.1)
    if detections is None:
        return np.empty((0, 4), dtype=np.float32)
    person_mask = (detections[:, 4] > 0.3) & (detections[:, 5] == 0)
    return detections[person_mask, :4].astype(np.float32)


def _bbox_center_scale(box: np.ndarray, padding: float = 1.25) -> tuple[np.ndarray, np.ndarray]:
    x1, y1, x2, y2 = box
    center = np.array([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np.float32)
    scale = np.array([x2 - x1, y2 - y1], dtype=np.float32) * padding
    return center, scale


def _third_point(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    direction = first - second
    return second + np.array([-direction[1], direction[0]], dtype=np.float32)


def _pose_preprocess(
    image: np.ndarray,
    box: np.ndarray,
    input_size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    center, scale = _bbox_center_scale(box)
    width, height = input_size
    aspect_ratio = width / height
    if scale[0] > scale[1] * aspect_ratio:
        scale[1] = scale[0] / aspect_ratio
    else:
        scale[0] = scale[1] * aspect_ratio
    source_direction = np.array([0.0, scale[0] * -0.5], dtype=np.float32)
    destination_direction = np.array([0.0, width * -0.5], dtype=np.float32)
    source = np.zeros((3, 2), dtype=np.float32)
    destination = np.zeros((3, 2), dtype=np.float32)
    source[0], source[1] = center, center + source_direction
    source[2] = _third_point(source[0], source[1])
    destination[0] = (width * 0.5, height * 0.5)
    destination[1] = destination[0] + destination_direction
    destination[2] = _third_point(destination[0], destination[1])
    matrix = cv2.getAffineTransform(source, destination)
    resized = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_LINEAR)
    normalized = (resized.astype(np.float32) - np.array([123.675, 116.28, 103.53])) / np.array(
        [58.395, 57.12, 57.375]
    )
    return normalized, center, scale


def _decode_simcc(simcc_x: np.ndarray, simcc_y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    instances, keypoint_count, _ = simcc_x.shape
    flat_x = simcc_x.reshape(instances * keypoint_count, -1)
    flat_y = simcc_y.reshape(instances * keypoint_count, -1)
    locations = np.stack((np.argmax(flat_x, axis=1), np.argmax(flat_y, axis=1)), axis=-1).astype(np.float32)
    scores = np.minimum(np.max(flat_x, axis=1), np.max(flat_y, axis=1))
    locations[scores <= 0] = -1
    return locations.reshape(instances, keypoint_count, 2) / 2.0, scores.reshape(instances, keypoint_count)


def _estimate_poses(
    session: ort.InferenceSession,
    boxes: np.ndarray,
    image: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    input_height, input_width = session.get_inputs()[0].shape[2:]
    input_size = (int(input_width), int(input_height))
    all_keypoints = []
    all_scores = []
    input_name = session.get_inputs()[0].name
    output_names = [item.name for item in session.get_outputs()]
    for box in boxes:
        resized, center, scale = _pose_preprocess(image, box, input_size)
        outputs = session.run(output_names, {input_name: resized.transpose(2, 0, 1)[None].astype(np.float32)})
        keypoints, scores = _decode_simcc(outputs[0], outputs[1])
        keypoints = keypoints / np.array(input_size, dtype=np.float32) * scale + center - scale / 2
        all_keypoints.append(keypoints[0])
        all_scores.append(scores[0])
    return np.asarray(all_keypoints), np.asarray(all_scores)


def _to_openpose(keypoints: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    info = np.concatenate((keypoints, scores[..., None]), axis=-1)
    neck = np.mean(info[:, [5, 6]], axis=1)
    neck[:, 2] = ((info[:, 5, 2] > POSE_SCORE_THRESHOLD) & (info[:, 6, 2] > POSE_SCORE_THRESHOLD)).astype(int)
    info = np.insert(info, 17, neck, axis=1)
    mmpose_indices = [17, 6, 8, 10, 7, 9, 12, 14, 16, 13, 15, 2, 1, 4, 3]
    openpose_indices = [1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17]
    info[:, openpose_indices] = info[:, mmpose_indices]
    return info[..., :2], info[..., 2]


_BODY_LIMBS = (
    (2, 3), (2, 6), (3, 4), (4, 5), (6, 7), (7, 8), (2, 9), (9, 10), (10, 11),
    (2, 12), (12, 13), (13, 14), (2, 1), (1, 15), (15, 17), (1, 16), (16, 18),
)
_BODY_COLORS = (
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
    (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85),
)
_HAND_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (0, 9), (9, 10),
    (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16), (0, 17), (17, 18), (18, 19), (19, 20),
)


def _draw_body(canvas: np.ndarray, candidate: np.ndarray, subset: np.ndarray) -> None:
    height, width = canvas.shape[:2]
    for limb_index, limb in enumerate(_BODY_LIMBS):
        for person in subset:
            indices = person[np.array(limb) - 1]
            if -1 in indices:
                continue
            points = candidate[indices.astype(int)]
            xs = points[:, 0] * width
            ys = points[:, 1] * height
            center = (int(np.mean(xs)), int(np.mean(ys)))
            length = float(np.hypot(xs[0] - xs[1], ys[0] - ys[1]))
            angle = int(math.degrees(math.atan2(ys[0] - ys[1], xs[0] - xs[1])))
            polygon = cv2.ellipse2Poly(center, (int(length / 2), 4), angle, 0, 360, 1)
            cv2.fillConvexPoly(canvas, polygon, _BODY_COLORS[limb_index])
    canvas[:] = (canvas * 0.6).astype(np.uint8)
    for keypoint_index in range(18):
        for person in subset:
            index = int(person[keypoint_index])
            if index == -1:
                continue
            x, y = candidate[index, :2]
            cv2.circle(canvas, (int(x * width), int(y * height)), 4, _BODY_COLORS[keypoint_index], -1)


def _draw_hands(canvas: np.ndarray, hands: Sequence[np.ndarray]) -> None:
    height, width = canvas.shape[:2]
    for hand in hands:
        for edge_index, edge in enumerate(_HAND_EDGES):
            x1, y1 = hand[edge[0]]
            x2, y2 = hand[edge[1]]
            if min(x1, y1, x2, y2) <= 0.01:
                continue
            rgb = colorsys.hsv_to_rgb(edge_index / len(_HAND_EDGES), 1.0, 1.0)
            color = tuple(int(channel * 255) for channel in rgb)
            cv2.line(canvas, (int(x1 * width), int(y1 * height)), (int(x2 * width), int(y2 * height)), color, 2)
        for x, y in hand:
            if min(x, y) > 0.01:
                cv2.circle(canvas, (int(x * width), int(y * height)), 4, (0, 0, 255), -1)


def _draw_faces(canvas: np.ndarray, faces: Sequence[np.ndarray]) -> None:
    height, width = canvas.shape[:2]
    for face in faces:
        for x, y in face:
            if min(x, y) > 0.01:
                cv2.circle(canvas, (int(x * width), int(y * height)), 3, (255, 255, 255), -1)


def _render_pose(keypoints: np.ndarray, scores: np.ndarray, height: int, width: int) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    if keypoints.size == 0:
        return canvas
    normalized = keypoints.copy()
    normalized[..., 0] /= float(width)
    normalized[..., 1] /= float(height)
    body = normalized[:, :18].reshape(-1, 2)
    body_scores = scores[:, :18]
    subset = np.full(body_scores.shape, -1, dtype=np.int32)
    for person_index in range(body_scores.shape[0]):
        visible = body_scores[person_index] > POSE_SCORE_THRESHOLD
        subset[person_index, visible] = 18 * person_index + np.flatnonzero(visible)
    normalized[scores < POSE_SCORE_THRESHOLD] = -1
    hands = np.vstack([normalized[:, 92:113], normalized[:, 113:]])
    _draw_body(canvas, body, subset)
    _draw_hands(canvas, hands)
    _draw_faces(canvas, normalized[:, 24:92])
    return canvas


class DWPoseInference:
    def __init__(self, model_manager: DWPoseModelManager) -> None:
        self.model_manager = model_manager
        self._session_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._detector: ort.InferenceSession | None = None
        self._pose: ort.InferenceSession | None = None

    def _ensure_sessions(self) -> tuple[ort.InferenceSession, ort.InferenceSession]:
        with self._session_lock:
            if self._detector is not None and self._pose is not None:
                return self._detector, self._pose
            if not self.model_manager.status().get("ready") and not self.model_manager.verify_installed():
                raise DWPoseUnavailableError("DWPose 模型尚未下载完成")
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            providers = ["CPUExecutionProvider"]
            try:
                detector = ort.InferenceSession(
                    str(self.model_manager.model_path("yolox_l.onnx")), sess_options=options, providers=providers
                )
                pose = ort.InferenceSession(
                    str(self.model_manager.model_path("dw-ll_ucoco_384.onnx")), sess_options=options, providers=providers
                )
            except Exception as exc:  # noqa: BLE001 - 转换为稳定的业务错误
                raise DWPoseUnavailableError(f"DWPose 模型加载失败：{exc}") from exc
            self._detector, self._pose = detector, pose
            return detector, pose

    def render(self, image_rgb: np.ndarray) -> DWPoseResult:
        if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or not image_rgb.size:
            raise ValueError("输入必须是非空 RGB 图片")
        detector, pose = self._ensure_sessions()
        image_bgr = cv2.cvtColor(np.ascontiguousarray(image_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        with self._inference_lock:
            boxes = _detect_people(detector, image_bgr)
            if boxes.size == 0:
                keypoints = np.empty((0, 134, 2), dtype=np.float32)
                scores = np.empty((0, 134), dtype=np.float32)
            else:
                keypoints, scores = _estimate_poses(pose, boxes, image_bgr)
                keypoints, scores = _to_openpose(keypoints, scores)
            output_bgr = _render_pose(keypoints, scores, image_bgr.shape[0], image_bgr.shape[1])
        return DWPoseResult(
            image_rgb=cv2.cvtColor(output_bgr, cv2.COLOR_BGR2RGB),
            people=int(boxes.shape[0]),
            keypoints=keypoints,
            scores=scores,
        )
