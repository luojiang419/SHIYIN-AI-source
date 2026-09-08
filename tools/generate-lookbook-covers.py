"""用安装版保存的拾影配置生成内置封面；密钥仅在内存使用。"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_installed_shiying(data_dir: Path):
    from canvas_core.secrets import DpapiProtector
    database = data_dir.resolve() / "database" / "canvas.db"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT payload_json FROM providers WHERE id=?", ("shiying",)).fetchone()
        secret = connection.execute("SELECT encrypted_value FROM secret_values WHERE key=?", ("API_PROVIDER_SHIYING_KEY",)).fetchone()
    if not row or not secret:
        raise RuntimeError("安装版未保存 shiying 平台或密钥")
    provider = json.loads(row[0])
    key = DpapiProtector().unprotect(bytes(secret[0]))
    if not provider.get("enabled", True) or not key:
        raise RuntimeError("安装版 shiying 平台未启用或密钥不可用")
    return provider, key


def builtin_styles():
    script = """
const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('static/js/canvas-lookbook-node.js','utf8');
const context={window:{},document:{addEventListener:()=>{}},localStorage:{getItem:()=>null}};
vm.runInNewContext(source.replace('window.CanvasLookbookNode={','window.CanvasLookbookNode={styles,'),context);
process.stdout.write(JSON.stringify(context.window.CanvasLookbookNode.styles()));
"""
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, encoding="utf-8")
    return json.loads(result.stdout)


async def generate(main, destination: Path):
    from canvas_core.lookbook_styles import FASHION_EDITORIAL_STYLE, shiying_cover_route
    route = shiying_cover_route(main.configured_ecommerce_providers())
    styles = builtin_styles()
    scenes = {
        "fw-cream-cyan-film": "A woman in an ivory knit pauses at a pale lemon and turquoise news kiosk in clear afternoon sunshine; intimate tilted candid editorial, luminous cream and cyan, visible fine organic film grain.",
        "levis-adaptive-campaign": "A person wearing indigo denim steps out of an old brick doorway into an overcast wet city street, adjusting a canvas bag with a purposeful off-frame gaze; authentic documentary campaign with scene-motivated light.",
        "standard-advertising": "A woman in a tailored neutral jacket walks through a warm stone urban arcade carrying a sculptural leather bag; balanced neutral contrast, readable shadows and restrained polished fashion composition.",
        "levis-high-key-color": "A confident woman in light blue denim strides in bright open daylight past a clean yellow wall and pale blue architecture, jacket catching a small breeze; airy high-key clean-color fashion campaign.",
        "levis-black-white": "A person in tactile dark denim turns through a doorway mid-laugh; dramatic but readable side light, expressive close fashion photograph in strictly neutral black and white.",
        "fashion-advertising": "An adult woman in sculptural charcoal tailoring strides down a rain-darkened metropolitan stairway; intentional low 24mm viewpoint and asymmetric fashion hero composition, foreground handrail, natural overcast light, living skin, cool silver and charcoal palette with a burgundy accent, physically grounded motion.",
    }
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / "manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    results = {item["id"]: item for item in previous.get("images", [])}
    limit = asyncio.Semaphore(3)

    async def one(style):
        style_id = style["id"]
        target = destination / f"{style_id}.webp"
        if target.exists() and results.get(style_id, {}).get("status") == "succeeded":
            return
        if style_id == FASHION_EDITORIAL_STYLE["id"]:
            style = FASHION_EDITORIAL_STYLE
        async with limit:
            try:
                result = await main.generate_lookbook_skill_cover(main.LookbookSkillCoverRequest(
                    prompt=style["prompt"] + " COVER SUBJECT: " + scenes[style_id] + " FINAL COVER DELIVERY OVERRIDE: one single 3:4 full-bleed fashion photograph only. No grid, contact sheet, text, logos, border or watermarks. Any sequence instructions above describe style only; do not render multiple pictures.",
                    aspect_ratio="3:4", resolution="1k", quality="high",
                ))
                source = main.output_file_from_url(result["image"]["url"])
                if not source:
                    raise RuntimeError("生成图片未落地到媒体目录")
                with Image.open(source) as image:
                    image.convert("RGB").save(target, "WEBP", quality=90)
                    size = list(image.size)
                results[style_id] = {"id": style_id, "name": style["name"], "status": "succeeded", "file": target.name, "size": size, "model": result["model"]}
            except Exception as exc:
                results[style_id] = {"id": style_id, "status": "failed", "error_type": type(exc).__name__, "status_code": getattr(exc, "status_code", None)}
            manifest_path.write_text(json.dumps({"provider_id": route["provider_id"], "credential_source": "installed_application", "aspect_ratio": "3:4", "resolution": "1k", "images": list(results.values())}, ensure_ascii=False, indent=2), encoding="utf-8")

    await asyncio.gather(*(one(style) for style in styles))
    return list(results.values())


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "static" / "img" / "lookbook-covers")
    args = parser.parse_args()
    provider, key = read_installed_shiying(args.installed_data_dir)
    with tempfile.TemporaryDirectory(prefix="lookbook-covers-") as temporary:
        os.environ.update(CANVAS_DATA_DIR=temporary, CANVAS_PORTABLE_ROOT=temporary,
                          CANVAS_DWPOSE_AUTO_DOWNLOAD="0", CANVAS_DEPTH_AUTO_DOWNLOAD="0")
        os.environ["API_PROVIDER_SHIYING_KEY"] = key
        # 屏蔽底层请求调试输出，只交付不含凭据的封面清单。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import main
            main.ADMIN_DATABASE.save_providers([provider])
            results = asyncio.run(generate(main, args.output_dir))
        os.environ.pop("API_PROVIDER_SHIYING_KEY", None)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(item["status"] == "succeeded" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
