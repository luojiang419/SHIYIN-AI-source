"""隔离数据目录，复用安装版已配置模型验证完整时尚广告生产链路。

会调用已配置的视觉模型及图片 API；不修改安装版数据，凭据仅在内存使用。
"""
import argparse
import asyncio
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "report.json").exists():
        raise ValueError("该验证目录已运行，请使用新目录，避免覆盖或重复生图")
    runtime = out / "runtime"
    os.environ.update(CANVAS_DATA_DIR=str(runtime / "data"), CANVAS_PORTABLE_ROOT=str(runtime),
                      CANVAS_APP_ROOT=str(ROOT), CANVAS_DWPOSE_AUTO_DOWNLOAD="0", CANVAS_DEPTH_AUTO_DOWNLOAD="0")
    from canvas_core.secrets import DpapiProtector
    providers = []
    database = args.installed_data.resolve() / "database/canvas.db"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        for provider_id in ("ecommerce-vision", "shiying"):
            row = db.execute("SELECT payload_json FROM providers WHERE id=?", (provider_id,)).fetchone()
            key_name = "API_PROVIDER_" + provider_id.upper().replace("-", "_") + "_KEY"
            key_row = db.execute("SELECT encrypted_value FROM secret_values WHERE key=?", (key_name,)).fetchone()
            if not row or not key_row:
                raise ValueError(f"未配置 {provider_id}")
            providers.append(json.loads(row[0]))
            os.environ[key_name] = DpapiProtector().unprotect(bytes(key_row[0]))
    report = {"status": "running", "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "phases": {}}
    write(out / "report.json", report)

    def phase(name, result=None):
        report["phase"] = name
        if result is not None:
            report["phases"][name] = result
        write(out / "report.json", report)
        print(name, file=sys.__stdout__, flush=True)

    # 防止底层调试日志输出请求配置；只保存白名单诊断数据。
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import main
        main.ADMIN_DATABASE.save_providers(providers)
        original_llm = main.canvas_llm
        director_calls = 0

        async def traced_llm(request):
            nonlocal director_calls
            result = await original_llm(request)
            if "# Fashion Editorial Sequence Director v1.2" in request.system_prompt:
                director_calls += 1
                (out / f"director-response-{director_calls}.txt").write_text(str(result.get("text") or ""), encoding="utf-8")
            return result

        main.canvas_llm = traced_llm
        refs = []
        for index, (source, role) in enumerate(((args.scene, "场景"), (args.person, "人物")), 1):
            target = Path(os.fspath(main.OUTPUT_INPUT_DIR)) / f"fashion-ref-{index}{source.suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            reference_type = "scene" if role == "场景" else "subject"
            refs.append({"url": "/assets/input/" + target.name, "role": reference_type, "reference_type": reference_type, "lookbook_role": role,
                         "label": role, "name": source.name})
        request = main.EcommerceTaskRequest(
            operation="universal", mode="standard", inputs=refs, provider_id="shiying", model=args.image_model,
            count=1, aspect_ratio="3:2", resolution="2k", quality="high",
            options={"prompt_policy": "lookbook", "lookbook_mode": "story-campaign",
                     "lookbook_style": {"id": "fashion-advertising"},
                     "lookbook_layout_selection": {"preset_id": "grid-3x3"}, "lookbook_search": False,
                     "instruction": args.brief},
        )
        phase("snapshot")
        snapshot = main.prepare_ecommerce_request(request)
        if len(snapshot["inputs"]) != len(refs):
            raise ValueError("实测参考图数量不一致，禁止继续生图")
        phase("references-verified", {"count": len(snapshot["inputs"]), "roles": [ref.get("lookbook_role") for ref in snapshot["inputs"]]})
        if args.reuse_analysis:
            old_plan = json.loads(args.reuse_analysis.read_text(encoding="utf-8"))
            old_inputs = old_plan["inputs"]
            if len(old_inputs) != len(snapshot["inputs"]):
                raise ValueError("复用分析的参考数量不同")
            for old, current in zip(old_inputs, snapshot["inputs"]):
                old_path = args.reuse_analysis.parent / "runtime/data/media/input" / Path(old["url"]).name
                current_path = Path(main.output_file_from_url(current["url"]))
                if hashlib.sha256(old_path.read_bytes()).digest() != hashlib.sha256(current_path.read_bytes()).digest():
                    raise ValueError("参考图内容变化，不可复用旧分析")
            snapshot["options"]["lookbook_reference_analysis"] = old_plan["options"]["lookbook_reference_analysis"]
            phase("reference-analysis-reused", {"source": str(args.reuse_analysis), "hashes_verified": True})
        phase("preparation")
        if args.reuse_direction:
            if not args.reuse_analysis or args.reuse_direction.resolve() != args.reuse_analysis.resolve():
                raise ValueError("复用导演方案必须同时校验同一计划的参考图")
            for key in ("lookbook_bible", "lookbook_shot_cards", "lookbook_plan", "lookbook_story_summary"):
                snapshot["options"][key] = old_plan["options"][key]
            snapshot, storyboard_meta = await main.enrich_fashion_director_storyboard(snapshot)
            meta = {"lookbook_storyboard": storyboard_meta, "direction_reused": True}
            if storyboard_meta.get("status") == "failed":
                meta["failed_stage"] = "storyboard"
        else:
            snapshot, meta = await main.prepare_lookbook_creation(snapshot)
        write(out / "plan.json", {"options": snapshot["options"], "count": snapshot["count"], "inputs": snapshot["inputs"],
                                  "size": snapshot["size"], "aspect_ratio": snapshot["aspect_ratio"], "quality": snapshot["quality"], "meta": meta})
        if meta.get("failed_stage"):
            report.update(status="failed", failed_stage=meta["failed_stage"])
            phase("preparation-failed", meta.get("lookbook_storyboard") or meta.get("brief_parse"))
            return
        prompts = main.lookbook_generation_prompts(snapshot)
        if args.product_detail:
            region = json.loads(args.product_detail)
            snapshot["options"]["lookbook_bible"]["product_direction"]["detail_regions"] = [region]
            write(out / "product-detail-region.json", region)
            write(out / "plan.json", {"options": snapshot["options"], "count": snapshot["count"], "inputs": snapshot["inputs"],
                                    "size": snapshot["size"], "aspect_ratio": snapshot["aspect_ratio"], "quality": snapshot["quality"], "meta": meta})
        for i, prompt in enumerate(prompts, 1):
            (out / f"generation-prompt-{i}.txt").write_text(prompt, encoding="utf-8")
        phase("review-existing" if args.review_report else "generation", {"prompt_chars": [len(p) for p in prompts], "model": args.image_model})
        route = {"provider_id": "shiying", "model": args.image_model}
        repaired_quality = None
        if args.review_report:
            if not args.reuse_direction or args.review_report.parent.resolve() != args.reuse_direction.parent.resolve():
                raise ValueError("复检必须使用同一输出的导演方案")
            source_report = json.loads(args.review_report.read_text(encoding="utf-8"))
            source_image = Path(source_report["files"][0])
            target = Path(os.fspath(main.OUTPUT_OUTPUT_DIR)) / ("fashion-review-source" + source_image.suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_image, target)
            batch = {"images": ["/assets/output/" + target.name]}
        elif args.repair_report:
            source_report = json.loads(args.repair_report.read_text(encoding="utf-8"))
            if not args.reuse_direction or args.repair_report.parent.resolve() != args.reuse_direction.parent.resolve():
                raise ValueError("修复必须复用同一输出的导演方案")
            source_image = Path(source_report["files"][0])
            target = Path(os.fspath(main.OUTPUT_OUTPUT_DIR)) / ("fashion-repair-source" + source_image.suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_image, target)
            cached_quality = source_report["quality"]
            if cached_quality.get("status") != "succeeded" or cached_quality.get("passed"):
                raise ValueError("只复用已有明确弱图意见进行修复")
            initial_quality_used = False
            original_analyze = main.analyze_lookbook_outputs

            async def reuse_initial_quality(current_snapshot, images):
                nonlocal initial_quality_used
                if not initial_quality_used:
                    initial_quality_used = True
                    return cached_quality
                return await original_analyze(current_snapshot, images)

            main.analyze_lookbook_outputs = reuse_initial_quality
            snapshot["options"].update(lookbook_quality_gate=True, lookbook_auto_repair=True)
            batch, repaired_quality = await main.improve_lookbook_batch(
                {"images": ["/assets/output/" + target.name]}, snapshot, route)
            main.analyze_lookbook_outputs = original_analyze
        else:
            batch = await main.execute_lookbook_story_batch(snapshot, route)
        files = []
        for index, url in enumerate(batch["images"], 1):
            source = Path(main.output_file_from_url(url))
            target = out / f"fashion-editorial-{index}{source.suffix}"
            shutil.copy2(source, target)
            files.append(str(target))
        phase("quality", {"files": files})
        quality = repaired_quality["final"] if repaired_quality else await main.analyze_lookbook_outputs(snapshot, batch["images"])
        report.update(status="reviewed" if args.review_report else "generated", files=files, quality=quality,
                      repair=repaired_quality,
                      finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        phase("completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--person", type=Path, required=True)
    parser.add_argument("--image-model", default="gemini-3-pro-image-preview")
    parser.add_argument("--brief", required=True)
    parser.add_argument("--reuse-analysis", type=Path)
    parser.add_argument("--reuse-direction", type=Path)
    parser.add_argument("--repair-report", type=Path)
    parser.add_argument("--product-detail", help="可选的已核对商品局部坐标 JSON，用于验证局部参考打包")
    parser.add_argument("--review-report", type=Path, help="只重新视觉验收已有输出，不调用生图")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception as exc:
        import traceback
        error = {"status": "failed", "error_type": type(exc).__name__, "status_code": getattr(exc, "status_code", None),
                 "trace": [{"file": Path(frame.filename).name, "line": frame.lineno} for frame in traceback.extract_tb(exc.__traceback__)]}
        report_file = args.output.resolve() / "report.json"
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            write(report_file, {**report, **error})
        print(json.dumps(error))
        raise SystemExit(1)
