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


def _axis_profile(image: Image.Image, axis: str) -> tuple[list[float], list[float], int]:
    """Return separator support and uniformity at each sampled axis position.

    A separator is expected to run through most of the perpendicular axis.
    Sampling a bounded image keeps large uploads cheap and, unlike a simple
    average or gradient, does not mistake a colorful image edge for a grid
    line.
    """

    width, height = image.size
    length = width if axis == "x" else height
    cross_length = height if axis == "x" else width
    max_length = 2400
    scale = min(1.0, max_length / max(length, cross_length))
    sample_width = max(32, round(width * scale))
    sample_height = max(32, round(height * scale))
    sampled = image.resize((sample_width, sample_height), Image.Resampling.BILINEAR) if scale < 1.0 else image
    pixels = sampled.load()
    sampled_length = sample_width if axis == "x" else sample_height
    sampled_cross_length = sample_height if axis == "x" else sample_width
    cross_step = max(1, sampled_cross_length // 320)
    support: list[float] = []
    uniformity: list[float] = []

    for position in range(sampled_length):
        values = [
            int(pixels[position, cross] if axis == "x" else pixels[cross, position])
            for cross in range(0, sampled_cross_length, cross_step)
        ]
        count = max(1, len(values))
        average = sum(values) / count
        variance = max(0.0, sum(value * value for value in values) / count - average * average)
        deviation = math.sqrt(variance)
        # Use support across the full perpendicular axis. Small image details
        # therefore cannot win merely because their local contrast is strong.
        white_support = sum(value >= 224 for value in values) / count
        black_support = sum(value <= 40 for value in values) / count
        support.append(max(white_support, black_support))
        uniformity.append(max(0.0, min(1.0, 1.0 - deviation / 82.0)))

    return support, uniformity, sampled_length


def _detect_axis(image: Image.Image, axis: str) -> tuple[float, ...]:
    support, uniformity, length = _axis_profile(image, axis)
    if length < 3:
        return ()

    scores = [support[index] * uniformity[index] for index in range(length)]
    clusters: list[tuple[int, int]] = []
    start = -1
    for position, score in enumerate(scores):
        if score >= 0.58:
            if start == -1:
                start = position
        elif start != -1:
            clusters.append((start, position - 1))
            start = -1
    if start != -1:
        clusters.append((start, length - 1))

    # Ignore borders and merge only candidates that are closer than a normal
    # separator band. The position is weighted by separator confidence so
    # antialiased lines resolve to their visual center.
    min_gap = max(12, round(length * 0.025))
    candidates: list[tuple[int, float]] = []
    for cluster_start, cluster_end in clusters:
        if cluster_start == 0 or cluster_end == length - 1:
            continue
        total = sum(scores[cluster_start : cluster_end + 1])
        if total <= 0:
            continue
        center = round(
            sum(index * scores[index] for index in range(cluster_start, cluster_end + 1)) / total
        )
        candidates.append((center, max(scores[cluster_start : cluster_end + 1])))

    positions: list[tuple[int, float]] = []
    for center, score in candidates:
        if positions and center - positions[-1][0] < min_gap:
            if score > positions[-1][1]:
                positions[-1] = (center, score)
            continue
        positions.append((center, score))
    return tuple(round(center / length, 6) for center, _ in positions)


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
