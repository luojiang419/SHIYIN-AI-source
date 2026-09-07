"""只读安装版配置，在隔离目录实测 Lookbook 搜索开关；不生成图片、不改生产数据。"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.json").exists():
        raise ValueError("输出目录已有实验，请指定新目录，避免覆盖证据或重复付费")
    installed = Path(args.installed_data).resolve()
    runtime = ROOT / ".codex-artifacts" / "lookbook-search-benchmark" / uuid.uuid4().hex
    runtime.mkdir(parents=True)
    os.environ.update(CANVAS_DATA_DIR=str(runtime / "data"), CANVAS_PORTABLE_ROOT=str(runtime),
                      CANVAS_APP_ROOT=str(ROOT), CANVAS_DWPOSE_AUTO_DOWNLOAD="0",
                      CANVAS_DEPTH_AUTO_DOWNLOAD="0", CANVAS_RUNTIME_MODE="desktop",
                      CANVAS_DESKTOP_TOKEN=uuid.uuid4().hex)
    with sqlite3.connect((installed / "database/canvas.db").as_uri() + "?mode=ro", uri=True) as db:
        providers = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM providers ORDER BY sort_order,id")]
        provider = next(p for p in providers if p.get("id") == args.provider)
        task = json.loads(db.execute("SELECT payload_json FROM tasks WHERE id=?", (args.task,)).fetchone()[0])
        source_snapshot = task["request"]
        secret_name = "API_PROVIDER_" + args.provider.upper().replace("-", "_") + "_KEY"
        row = db.execute("SELECT encrypted_value FROM secret_values WHERE key=?", (secret_name,)).fetchone()
        if row is None:
            raise RuntimeError("未找到目标平台加密密钥")
        from canvas_core.secrets import DpapiProtector
        os.environ[secret_name] = DpapiProtector().unprotect(row[0])
        nodes = []
        for row in db.execute("SELECT payload_json FROM canvases"):
            c = json.loads(row[0])
            nodes.extend({"canvas_id": c.get("id"), "node_id": n.get("id"),
                          "search": n.get("lookbookSearch"), "style": n.get("lookbookStyleId")}
                         for n in c.get("nodes", []) if n.get("type") == "lookbook")
        recent = []
        for row in db.execute("SELECT payload_json FROM tasks ORDER BY updated_at DESC LIMIT 20"):
            t = json.loads(row[0])
            if (t.get("request", {}).get("options") or {}).get("prompt_policy") == "lookbook":
                recent.append({"id": t.get("id"), "status": t.get("status"), "stage": t.get("agent_stage"),
                               "created_at": t.get("created_at"), "updated_at": t.get("updated_at"),
                               "research_status": (t.get("lookbook_research") or {}).get("status"),
                               "error": t.get("error")})
    import main as app
    app.load_api_providers = lambda: [app.normalize_provider(provider)]
    route = app.configured_ecommerce_vision_route()
    if not route or route["provider_id"] != args.provider:
        raise RuntimeError("当前真实配置无法解析为指定视觉路由")
    transport = app.resolve_chat_transport(args.provider, route["model"], "")
    if transport["protocol"] != "responses" or not app.provider_supports_builtin_web_search(transport["provider"]):
        raise RuntimeError("此实验需要支持真实内置搜索的 Responses 平台")
    # 只保留正式函数所需字段，避免保存 route_candidates 等无关配置。
    snapshot = {k: copy.deepcopy(source_snapshot[k]) for k in
                ("operation", "inputs", "options", "aspect_ratio", "resolution", "size", "quality", "count")}
    for key in app.LOOKBOOK_DERIVED_OPTION_KEYS:
        snapshot["options"].pop(key, None)
    snapshot["options"].pop("lookbook_context_signature", None)
    snapshot["options"]["lookbook_search"] = False
    snapshot["prompt"] = app.build_ecommerce_prompt(snapshot["operation"], snapshot["inputs"], snapshot["options"])
    refs = []
    for ref in snapshot["inputs"]:
        url = ref["url"]
        if not url.startswith("/assets/input/") or Path(url).name != url[len("/assets/input/"):]:
            raise ValueError("本实验仅复用安装版 input 目录中的本地素材")
        source = installed / "media/input" / Path(url).name
        target = Path(os.fspath(app.OUTPUT_INPUT_DIR)) / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        target.write_bytes(content)
        refs.append({"url": url, "sha256": hashlib.sha256(content).hexdigest()})
    report = {"status": "running", "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": route["model"], "provider": args.provider, "protocol": transport["protocol"],
              "source_sha256": hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(),
              "source_task": args.task, "runtime": str(runtime), "references": refs,
              "stage_timeout_s": args.timeout, "saved_nodes": nodes, "recent_tasks": recent,
              "method": "共享一次真实需求理解及参考分析，再交替 OFF/ON、ON/OFF；每组仅改变搜索开关。搜索后运行正式策划和分镜函数。无生图，阶段外部超时为观测截断。",
              "stages": []}
    write_json(out / "input.json", snapshot)
    current = {}
    original_llm = app.canvas_llm
    original_build = app.build_llm_request_body
    original_stream = app.request_responses_stream_json

    def emit(event, **fields):
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields}
        with (out / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=True), flush=True)

    def build(*a, **kw):
        body = original_build(*a, **kw)
        record = {"model": body.get("model"), "tools": body.get("tools", []), "reasoning": body.get("reasoning"),
                  "input_chars": len(json.dumps(body.get("input"), ensure_ascii=False)),
                  "instructions_chars": len(body.get("instructions", ""))}
        current["requests"].append(record)
        if current["stage"] != "search" and body.get("tools"):
            raise AssertionError("非搜索阶段意外携带工具")
        emit("request", case=current["case"], stage=current["stage"], **record)
        return body

    async def stream(*a, **kw):
        attempt = {"index": len(current["attempts"]) + 1}
        current["attempts"].append(attempt)
        started = time.perf_counter()
        try:
            result = await original_stream(*a, **kw)
            attempt["status"] = "succeeded"
            return result
        except BaseException as exc:
            attempt["status"] = type(exc).__name__
            raise
        finally:
            attempt["elapsed_s"] = round(time.perf_counter() - started, 3)

    async def llm(payload, *a, **kw):
        result = await original_llm(payload, *a, **kw)
        index = len(current["outputs"]) + 1
        file = f"{current['case']}-{current['stage']}-{index}.json"
        write_json(out / file, result)
        evidence = result.get("web_search") or {}
        current["outputs"].append({"file": file, "text_chars": len(result.get("text", "")),
                                   "search_used": evidence.get("used", False),
                                   "queries": evidence.get("queries", []),
                                   "source_count": len(evidence.get("sources", []))})
        return result

    app.build_llm_request_body = build
    app.request_responses_stream_json = stream
    app.canvas_llm = llm

    async def stage(case, name, fn, value):
        nonlocal current
        current = {"case": case, "stage": name, "requests": [], "attempts": [], "outputs": []}
        report["stages"].append(current)
        emit("start", case=case, stage=name)
        started = time.perf_counter()
        try:
            result, meta = await asyncio.wait_for(fn(copy.deepcopy(value)), timeout=args.timeout)
            current["meta"] = meta
            current["status"] = (meta or {}).get("status", "none")
        except asyncio.TimeoutError:
            result = value
            current["status"] = "observation_timeout"
        except Exception as exc:
            result = value
            current["status"] = "error"
            current["error_type"] = type(exc).__name__
        current["elapsed_s"] = round(time.perf_counter() - started, 3)
        write_json(out / "results.json", report)
        emit("finish", case=case, stage=name, status=current["status"], seconds=current["elapsed_s"])
        return result, current["status"]

    snapshot, status = await stage("common", "brief", app.enrich_lookbook_brief_settings, snapshot)
    if status != "succeeded":
        raise RuntimeError("真实需求理解未成功，请查看证据，停止付费测试")
    snapshot, status = await stage("common", "reference", app.enrich_lookbook_reference_analysis, snapshot)
    if status != "succeeded":
        raise RuntimeError("真实参考解析未成功，请查看证据，停止付费测试")
    write_json(out / "common-snapshot.json", snapshot)
    for repetition in range(1, args.repetitions + 1):
        for enabled in ([False, True] if repetition % 2 else [True, False]):
            case = f"{'on' if enabled else 'off'}-r{repetition}"
            value = copy.deepcopy(snapshot)
            value["options"]["lookbook_search"] = enabled
            value, search_status = await stage(case, "search", app.enrich_lookbook_search, value)
            if search_status == "observation_timeout":
                # 外部取消不同于正式流程成功降级，不伪造后续完整流水线。
                continue
            value, _ = await stage(case, "plan", app.enrich_lookbook_plan, value)
            value, status = await stage(case, "storyboard", app.enrich_lookbook_storyboard, value)
            if status == "succeeded":
                prompts = app.lookbook_generation_prompts(value)
                write_json(out / f"{case}-compiled.json", {"count": value["count"], "options": value["options"], "prompts": prompts})
            write_json(out / "results.json", report)
    report["status"] = "completed"
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_json(out / "results.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-data", default=r"D:\Program Files\SHIYIN AI\data")
    parser.add_argument("--provider", default="ecommerce-vision")
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--repetitions", type=int, default=2)
    asyncio.run(run(parser.parse_args()))
