from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True)
class GridDetection:
    horizontal: tuple[float, ...]
    vertical: tuple[float, ...]
    confidence: float

    @property
    def rows(self) -> int:
        return len(self.horizontal) + 1

    @property
    def cols(self) -> int:
        return len(self.vertical) + 1

    def as_dict(self) -> dict:
        return {
            "horizontal": list(self.horizontal),
            "vertical": list(self.vertical),
            "rows": self.rows,
            "cols": self.cols,
            "confidence": round(self.confidence, 4),
        }


def _detect_axis(image: Image.Image, axis: str) -> tuple[float, ...]:
    width, height = image.size
    pixels = image.load()
    length = width if axis == "x" else height
    cross_length = height if axis == "x" else width
    step = max(1, cross_length // 640)
    averages = [0.0] * length
    scores = [0.0] * length

    for position in range(length):
        values = [
            int(pixels[position, cross] if axis == "x" else pixels[cross, position])
            for cross in range(0, cross_length, step)
        ]
        average = sum(values) / max(1, len(values))
        variance = max(0.0, sum(value * value for value in values) / max(1, len(values)) - average * average)
        deviation = math.sqrt(variance)
        whiteness = max(0.0, min(1.0, (average - 232.0) / 23.0)) if average > 232 else 0.0
        darkness = max(0.0, min(1.0, (32.0 - average) / 32.0)) if average < 32 else 0.0
        uniformity = max(0.0, min(1.0, 1.0 - deviation / 70.0))
        averages[position] = average
        scores[position] = max(whiteness, darkness) * uniformity

    for position in range(1, length - 1):
        gradient = min(1.0, abs(averages[position - 1] - averages[position + 1]) / 255.0)
        scores[position] = max(scores[position], gradient * 0.8)

    clusters: list[tuple[int, int]] = []
    start = -1
    for position in range(1, length - 1):
        if scores[position] >= 0.56:
            if start == -1:
                start = position
        elif start != -1:
            clusters.append((start, position - 1))
            start = -1
    if start != -1:
        clusters.append((start, length - 2))

    min_gap = max(24, round(length * 0.035))
    positions = [0]
    for cluster_start, cluster_end in clusters:
        center = round((cluster_start + cluster_end) / 2)
        if center - positions[-1] >= min_gap and length - center >= min_gap:
            positions.append(center)
    positions.append(length)
    return tuple(round(position / length, 6) for position in positions[1:-1])


def detect_grid(image: Image.Image) -> GridDetection:
    """Port of storyboard's proven grid separator detector.

    Each axis is detected independently so portrait strips, uneven grids and
    one-dimensional collages remain editable instead of being forced into a
    regular row/column preset.
    """

    gray = ImageOps.grayscale(ImageOps.exif_transpose(image))
    width, height = gray.size
    if width < 32 or height < 32:
        return GridDetection((), (), 0.0)
    vertical = _detect_axis(gray, "x")
    horizontal = _detect_axis(gray, "y")
    separator_count = len(vertical) + len(horizontal)
    confidence = min(0.95, 0.5 + separator_count * 0.07) if separator_count else 0.0
    return GridDetection(horizontal, vertical, confidence)
