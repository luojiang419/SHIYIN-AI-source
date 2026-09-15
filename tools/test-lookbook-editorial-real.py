"""正式 Lookbook 两阶段→提示词编译→生图→终审实测；安装版只读，凭据不落盘。

python tools/test-lookbook-editorial-real.py --case outdoor
输出已存在时拒绝重跑；另设 --output 可以明确启动新一轮。
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INSTALLED = Path("D:/Program Files/SHIYIN AI/data")
CASES = {
    "studio": "ecommerce_c3e2838f8ce74c39872a25ceb144bcb9",
    "outdoor": "ecommerce_776f753421d946588c7ec34fcf9c0ae7",
}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(app, snapshot, out, report):
    route = app.configured_ecommerce_vision_route()
    report["vision_route"] = route
    report["image_route"] = {"provider_id": "shiying", "model": "gemini-3-pro-image-preview"}
    original_llm = app.canvas_llm
    calls = []

    async def capture(request):
        number = len(calls) + 1
        entry = {"number": number, "model": request.model, "status": "running"}
        calls.append(entry)
        save(out / "calls.json", calls)
        save(out / f"llm-{number}-request.json", {
            "system_prompt": request.system_prompt, "message": request.message,
            "images": request.images, "image_labels": request.image_labels,
            "messages": request.messages, "web_search": request.web_search,
        })
        started = time.monotonic()
        try:
            response = await original_llm(request)
            save(out / f"llm-{number}-response.json", {"text": response.get("text")})
            entry["status"] = "succeeded"
            return response
        finally:
            entry["elapsed_s"] = round(time.monotonic() - started, 2)
            save(out / "calls.json", calls)

    app.canvas_llm = capture
    report["stage"] = "prepare"
    save(out / "results.json", report)
    if report.get("review_image"):
        value, meta = snapshot, {"status": "reused-for-review", "new_planning_calls": 0}
    else:
        value, meta = await asyncio.wait_for(app.prepare_lookbook_creation(snapshot), 900)
    save(out / "prepared.json", {"snapshot": value, "meta": meta})
    if meta.get("failed_stage"):
        raise RuntimeError("preparation_failed: " + json.dumps(meta, ensure_ascii=False))
    prompts = [] if report.get("review_image") else app.lookbook_generation_prompts(value)
    save(out / "prompts.json", prompts)
    report.update(stage="image", prompt_chars=[len(p) for p in prompts])
    save(out / "results.json", report)
    started = time.monotonic()
    if report.get("review_image"):
        reviewed = Path(report["review_image"])
        target = Path(os.fspath(app.OUTPUT_INPUT_DIR)) / ("review-" + uuid.uuid4().hex + reviewed.suffix)
        shutil.copy2(reviewed, target)
        batch = {"images": ["/assets/input/" + target.name]}
    else:
        batch = await asyncio.wait_for(app.execute_lookbook_story_batch(value, report["image_route"]), 900)
    repair_quality = None
    if report.get("repair_image"):
        value["options"].update(lookbook_quality_gate=True, lookbook_auto_repair=True, lookbook_max_retries=1)
        repair_started = time.monotonic()
        batch, repair_quality = await app.improve_lookbook_batch(batch, value, report["image_route"])
        report["repair_elapsed_s"] = round(time.monotonic()-repair_started, 2)
        save(out / "repair.json", repair_quality)
    urls = batch.get("images") or []
    if len(urls) != 1:
        raise RuntimeError("expected_one_generated_grid")
    source = app.output_file_from_url(urls[0])
    image_path = out / ("result" + Path(source).suffix)
    shutil.copy2(source, image_path)
    report.update(stage="quality", image=image_path.name, image_elapsed_s=round(time.monotonic()-started, 2))
    save(out / "results.json", report)
    quality = repair_quality["final"] if repair_quality else await app.analyze_lookbook_outputs(value, urls)
    save(out / "quality.json", quality)
    report.update(status="generated", stage="done", quality=quality)
    save(out / "results.json", report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--output")
    parser.add_argument("--prepared", help="复用已保存的真实解析响应，经正式缓存校验后测试最新编译/生图；不人工改镜头")
    parser.add_argument("--review-image", help="只复核指定的现有测试图片，不再次生成")
    parser.add_argument("--instruction", help="本轮真实测试的用户需求")
    parser.add_argument("--layout", default="grid-3x3", choices=["grid-2x2", "grid-3x3"], help="节点的拼格设置")
    parser.add_argument("--repair", action="store_true", help="对review-image运行正式质量门，最多一次定向修复")
    args = parser.parse_args()
    out = Path(args.output) if args.output else ROOT / "输出/Lookbook摄影多样性-20260915" / args.case
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.json").exists():
        raise RuntimeError("已有实测记录，请指定新输出目录，避免重复付费")
    runtime = ROOT / ".codex-artifacts/lookbook-editorial-real" / uuid.uuid4().hex
    runtime.mkdir(parents=True)
    os.environ.update(CANVAS_DATA_DIR=str(runtime / "data"), CANVAS_PORTABLE_ROOT=str(runtime),
                      CANVAS_APP_ROOT=str(ROOT), CANVAS_DEPTH_AUTO_DOWNLOAD="0", CANVAS_DWPOSE_AUTO_DOWNLOAD="0")
    from canvas_core.secrets import DpapiProtector
    with sqlite3.connect((INSTALLED / "database/canvas.db").as_uri() + "?mode=ro", uri=True) as db:
        providers = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM providers ORDER BY sort_order,id")]
        providers = [p for p in providers if p["id"] in {"ecommerce-vision", "shiying"}]
        for p in providers:
            name = "API_PROVIDER_" + p["id"].upper().replace("-", "_") + "_KEY"
            encrypted = db.execute("SELECT encrypted_value FROM secret_values WHERE key=?", (name,)).fetchone()
            os.environ[name] = DpapiProtector().unprotect(bytes(encrypted[0]))
        task = json.loads(db.execute("SELECT payload_json FROM tasks WHERE id=?", (CASES[args.case],)).fetchone()[0])
    report = {"status": "running", "case": args.case, "source_task": CASES[args.case],
              "method": "正式prepare_lookbook_creation、lookbook_generation_prompts、execute_lookbook_story_batch与analyze_lookbook_outputs；不手改返回提示词、不修图"}
    if args.review_image:
        if not args.prepared:
            raise ValueError("复核图片必须同时指定原始prepared方案")
        report["review_image"] = str(Path(args.review_image).resolve())
        report["method"] = "复用真实已解析方案与已生成原图，仅重新执行正式analyze_lookbook_outputs；不生图、不改镜头、不修图"
        if args.repair:
            report["repair_image"] = True
            report["method"] = "复用真实方案与原图，执行正式improve_lookbook_batch质量门，最多一次API定向修复并复检；不人工修改提示词或图片"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import main as app
            app.ADMIN_DATABASE.save_providers(providers)
            source = task["request"]
            snapshot = {k: copy.deepcopy(source[k]) for k in ("operation", "inputs", "aspect_ratio", "resolution", "size", "quality", "count")}
            snapshot["options"] = {
                "prompt_policy": "lookbook", "lookbook_mode": "story-campaign", "lookbook_search": False,
                "instruction": args.instruction if args.instruction is not None else ("棚拍时尚大片，纯色底，影视光效" if args.case == "studio" else ""),
                "lookbook_style": copy.deepcopy(source["options"]["lookbook_style"]),
                "lookbook_count": 1, "lookbook_cell_aspect_ratio": "16:9",
                "lookbook_layout_selection": {"preset_id": args.layout},
                "lookbook_manual_overrides": {"count": 1, "aspect_ratio": "16:9", "resolution": "2k", "quality": "high"},
            }
            snapshot.update(count=1, aspect_ratio="16:9", resolution="2k", size="2048x1152", quality="high", prompt="")
            if args.prepared:
                prepared_path = Path(args.prepared).resolve()
                snapshot = json.loads(prepared_path.read_text(encoding="utf-8"))["snapshot"]
                report["reused_real_plan"] = str(prepared_path)
            for i, ref in enumerate(snapshot["inputs"], 1):
                source = INSTALLED / "media/input" / Path(ref["url"]).name
                target = Path(os.fspath(app.OUTPUT_INPUT_DIR)) / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                shutil.copy2(source, out / f"reference-{i}{source.suffix}")
            save(out / "input.json", snapshot)
            asyncio.run(run(app, snapshot, out, report))
    except Exception as exc:
        reason = str(exc)
        for p in providers:
            secret = os.environ.get("API_PROVIDER_" + p["id"].upper().replace("-", "_") + "_KEY", "")
            if secret:
                reason = reason.replace(secret, "[redacted]")
        report.update(status="failed", error=reason[:1500])
        save(out / "results.json", report)
    finally:
        for p in providers:
            os.environ.pop("API_PROVIDER_" + p["id"].upper().replace("-", "_") + "_KEY", None)
    print(json.dumps(report, ensure_ascii=True))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
