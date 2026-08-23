"""Run repeatable FLUX.2 storyboard edit prompt trials without storing API secrets."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("FLUX2_API_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.getenv("FLUX2_API_KEY", ""))
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--round-name", required=True)
    parser.add_argument("--size", default="auto")
    parser.add_argument("--model", default="flux-2-klein-4b")
    parser.add_argument("images", nargs="+")
    return parser.parse_args()


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def response_image(response: dict, client: httpx.Client, base_url: str) -> bytes:
    item = (response.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    url = str(item.get("url") or "")
    if not url:
        raise RuntimeError(f"接口没有返回图片：{json.dumps(response, ensure_ascii=False)[:500]}")
    download_url = urljoin(f"{base_url.rstrip('/')}/", url)
    parsed_download = urlparse(download_url)
    if parsed_download.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}:
        parsed_base = urlparse(base_url)
        download_url = urlunparse(
            parsed_download._replace(scheme=parsed_base.scheme, netloc=parsed_base.netloc)
        )
    download = client.get(download_url, timeout=300)
    download.raise_for_status()
    return download.content


def main() -> int:
    args = parse_args()
    if not args.base_url:
        raise SystemExit("缺少 --base-url 或 FLUX2_API_BASE_URL")
    if not args.api_key:
        raise SystemExit("缺少 --api-key 或 FLUX2_API_KEY")

    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        raise SystemExit("提示词文件为空")

    round_dir = args.output_dir / args.round_name
    round_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    headers = {"Authorization": f"Bearer {args.api_key}"}
    timeout = httpx.Timeout(connect=30, read=1800, write=300, pool=30)

    with httpx.Client(headers=headers, timeout=timeout) as client:
        for name in args.images:
            source = args.input_dir / name
            if not source.is_file():
                raise FileNotFoundError(source)
            source_width, source_height = image_size(source)
            started = time.perf_counter()
            with source.open("rb") as image_file:
                response = client.post(
                    f"{args.base_url.rstrip('/')}/v1/images/edits",
                    data={
                        "model": args.model,
                        "prompt": prompt,
                        "size": args.size,
                        "quality": "standard",
                        "response_format": "url",
                    },
                    files={"image": (source.name, image_file, "image/jpeg")},
                )
            response.raise_for_status()
            payload = response.json()
            result = response_image(payload, client, args.base_url)
            output = round_dir / f"{source.stem}-{args.round_name}.png"
            output.write_bytes(result)
            output_width, output_height = image_size(output)
            records.append(
                {
                    "source": source.name,
                    "output": output.name,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "source_size": [source_width, source_height],
                    "output_size": [output_width, output_height],
                    "source_ratio": round(source_width / source_height, 6),
                    "output_ratio": round(output_width / output_height, 6),
                    "ratio_error_percent": round(
                        abs((output_width / output_height) / (source_width / source_height) - 1) * 100,
                        3,
                    ),
                }
            )
            print(f"{source.name} -> {output.name} ({output_width}x{output_height})")

    report = {
        "round": args.round_name,
        "model": args.model,
        "size": args.size,
        "prompt": prompt,
        "images": records,
    }
    (round_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
