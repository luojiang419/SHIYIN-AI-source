"""隔离数据目录，复用安装版已配置模型验证完整时尚广告生产链路。

会调用已配置的视觉模型及图片 API；不修改安装版数据，凭据仅在内存使用。
"""
import argparse
import asyncio
import contextlib
import io
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
        phase("preparation")
        snapshot, meta = await main.prepare_lookbook_creation(snapshot)
        write(out / "plan.json", {"options": snapshot["options"], "count": snapshot["count"], "inputs": snapshot["inputs"],
                                  "size": snapshot["size"], "aspect_ratio": snapshot["aspect_ratio"], "quality": snapshot["quality"], "meta": meta})
        if meta.get("failed_stage"):
            report.update(status="failed", failed_stage=meta["failed_stage"])
            phase("preparation-failed", meta.get("lookbook_storyboard") or meta.get("brief_parse"))
            return
        prompts = main.lookbook_generation_prompts(snapshot)
        for i, prompt in enumerate(prompts, 1):
            (out / f"generation-prompt-{i}.txt").write_text(prompt, encoding="utf-8")
        phase("generation", {"prompt_chars": [len(p) for p in prompts], "model": args.image_model})
        route = {"provider_id": "shiying", "model": args.image_model}
        batch = await main.execute_lookbook_story_batch(snapshot, route)
        files = []
        for index, url in enumerate(batch["images"], 1):
            source = Path(main.output_file_from_url(url))
            target = out / f"fashion-editorial-{index}{source.suffix}"
            shutil.copy2(source, target)
            files.append(str(target))
        phase("quality", {"files": files})
        quality = await main.analyze_lookbook_outputs(snapshot, batch["images"])
        report.update(status="generated", files=files, quality=quality,
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
