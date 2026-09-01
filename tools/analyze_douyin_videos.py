from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def probe_capture(path: Path) -> tuple[cv2.VideoCapture, dict]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"无法打开视频：{path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frames / fps if fps > 0 else 0.0
    return capture, {
        "fps": round(fps, 4),
        "frame_count": frames,
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
    }


def frame_at(capture: cv2.VideoCapture, seconds: float, fps: float) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(seconds * fps))))
    ok, frame = capture.read()
    return frame if ok else None


def frame_metrics(frame: np.ndarray) -> dict:
    small = cv2.resize(frame, (240, 426), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    brightness = float(np.mean(lab[:, :, 0]) / 255.0)
    contrast = float(np.std(lab[:, :, 0]) / 255.0)
    saturation = float(np.mean(hsv[:, :, 1]) / 255.0)
    highlight_clip = float(np.mean(gray >= 245))
    shadow_clip = float(np.mean(gray <= 10))
    b, g, r = cv2.split(small.astype(np.float32))
    warmth = float(np.mean(r - b) / 255.0)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "saturation": round(saturation, 4),
        "highlight_clip": round(highlight_clip, 4),
        "shadow_clip": round(shadow_clip, 4),
        "warmth": round(warmth, 4),
        "sharpness": round(sharpness, 2),
    }


def dominant_colors(frames: list[np.ndarray], count: int = 6) -> list[str]:
    pixels = []
    for frame in frames:
        thumb = cv2.resize(frame, (80, 142), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB).reshape(-1, 3)
        pixels.append(rgb[::6])
    data = np.concatenate(pixels).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _compactness, labels, centers = cv2.kmeans(data, count, None, criteria, 4, cv2.KMEANS_PP_CENTERS)
    populations = np.bincount(labels.ravel(), minlength=count)
    order = np.argsort(populations)[::-1]
    return ["#" + "".join(f"{int(round(value)):02x}" for value in centers[index]) for index in order]


def histogram(frame: np.ndarray) -> np.ndarray:
    small = cv2.resize(frame, (160, 284), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 16], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten()


def temporal_metrics(capture: cv2.VideoCapture, meta: dict) -> dict:
    duration = float(meta["duration_seconds"])
    fps = float(meta["fps"])
    step = 0.75
    samples = []
    motions = []
    cuts = []
    previous_gray = None
    previous_hist = None
    t = 0.0
    while t < duration:
        frame = frame_at(capture, t, fps)
        if frame is None:
            break
        small = cv2.resize(frame, (120, 214), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hist = histogram(frame)
        if previous_gray is not None:
            diff = float(np.mean(cv2.absdiff(gray, previous_gray)) / 255.0)
            motions.append(diff)
            hist_distance = float(cv2.compareHist(previous_hist, hist, cv2.HISTCMP_BHATTACHARYYA))
            if hist_distance >= 0.47 and diff >= 0.11:
                cuts.append(round(t, 2))
        samples.append(t)
        previous_gray = gray
        previous_hist = hist
        t += step
    average_shot = duration / (len(cuts) + 1) if duration else 0.0
    return {
        "sampling_step_seconds": step,
        "estimated_cut_count": len(cuts),
        "estimated_average_shot_seconds": round(average_shot, 3),
        "estimated_cut_times": cuts[:120],
        "motion_mean": round(float(np.mean(motions)) if motions else 0.0, 4),
        "motion_p90": round(float(np.percentile(motions, 90)) if motions else 0.0, 4),
    }


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def make_contact_sheet(frames: list[np.ndarray], times: list[float], title: str, output: Path) -> None:
    cell_w, cell_h = 300, 534
    margin, gap, header = 18, 10, 72
    canvas = Image.new("RGB", (margin * 2 + cell_w * 4 + gap * 3, header + margin + cell_h * 3 + gap * 2), "#161616")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(22)
    time_font = load_font(18)
    clean_title = " ".join(str(title or "").split())
    draw.text((margin, 16), clean_title[:68], fill="white", font=title_font)
    for index, (frame, seconds) in enumerate(zip(frames, times)):
        row, col = divmod(index, 4)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
        x = margin + col * (cell_w + gap) + (cell_w - image.width) // 2
        y = header + row * (cell_h + gap) + (cell_h - image.height) // 2
        canvas.paste(image, (x, y))
        label = f"{seconds:06.1f}s"
        draw.rounded_rectangle((x + 7, y + 7, x + 88, y + 35), radius=6, fill=(0, 0, 0, 180))
        draw.text((x + 13, y + 8), label, fill="white", font=time_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)


def make_palette(colors: list[str], output: Path) -> None:
    width, height = 720, 120
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = load_font(18)
    cell = width // max(1, len(colors))
    for index, color in enumerate(colors):
        x0 = index * cell
        draw.rectangle((x0, 0, x0 + cell, height), fill=color)
        rgb = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
        luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        draw.text((x0 + 10, 88), color.upper(), fill="black" if luminance > 140 else "white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def analyze_video(item: dict, video_path: Path, sheets_dir: Path, palettes_dir: Path) -> dict:
    capture, meta = probe_capture(video_path)
    duration = float(meta["duration_seconds"])
    fps = float(meta["fps"])
    times = [duration * (index + 0.5) / 12 for index in range(12)]
    frames = [frame_at(capture, seconds, fps) for seconds in times]
    frames = [frame for frame in frames if frame is not None]
    times = times[: len(frames)]
    metrics = [frame_metrics(frame) for frame in frames]
    aggregate = {
        key: round(float(np.mean([entry[key] for entry in metrics])), 4)
        for key in ("brightness", "contrast", "saturation", "highlight_clip", "shadow_clip", "warmth", "sharpness")
    }
    colors = dominant_colors(frames)
    temporal = temporal_metrics(capture, meta)
    capture.release()
    sheet_path = sheets_dir / f"{item['id']}.jpg"
    palette_path = palettes_dir / f"{item['id']}.png"
    make_contact_sheet(frames, times, item.get("title", ""), sheet_path)
    make_palette(colors, palette_path)
    return {
        "id": item["id"],
        "title": item.get("title", ""),
        "file": str(video_path),
        "contact_sheet": str(sheet_path),
        "palette_strip": str(palette_path),
        **meta,
        **temporal,
        "visual_metrics": aggregate,
        "dominant_colors": colors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    sheets_dir = root / "contact-sheets"
    palettes_dir = root / "palettes"
    analyses = []
    failures = []
    for index, item in enumerate(manifest.get("items") or [], 1):
        video_path = Path(item["file"])
        try:
            result = analyze_video(item, video_path, sheets_dir, palettes_dir)
            analyses.append(result)
            print(f"[{index:02d}/{len(manifest['items']):02d}] {item['id']} ok", flush=True)
        except Exception as exc:
            failures.append({"id": item.get("id"), "error": str(exc)})
            print(f"[{index:02d}/{len(manifest['items']):02d}] {item.get('id')} failed: {exc}", flush=True)
    output = {
        "source_manifest": str(root / "manifest.json"),
        "count": len(analyses),
        "failed": failures,
        "items": analyses,
    }
    (root / "analysis-metrics.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
