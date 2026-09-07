"""使用现有加密配置，隔离执行视频提示词 C/A/B 真实对照；不会生成最终视频。"""
from __future__ import annotations

import argparse
import asyncio
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
    runtime = ROOT / ".codex-artifacts" / "video-prompt-benchmark" / uuid.uuid4().hex
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ.update(CANVAS_DATA_DIR=str(runtime / "data"), CANVAS_PORTABLE_ROOT=str(runtime),
                      CANVAS_APP_ROOT=str(ROOT), CANVAS_DWPOSE_AUTO_DOWNLOAD="0",
                      CANVAS_DEPTH_AUTO_DOWNLOAD="0", CANVAS_RUNTIME_MODE="desktop",
                      CANVAS_DESKTOP_TOKEN=uuid.uuid4().hex)
    installed = Path(args.installed_data).resolve()
    with sqlite3.connect((installed / "database/canvas.db").as_uri() + "?mode=ro", uri=True) as db:
        providers = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM providers ORDER BY sort_order,id")]
        provider = next(p for p in providers if p.get("id") == args.provider)
        model = args.model or provider["chat_models"][0]
        canvas = json.loads(db.execute("SELECT payload_json FROM canvases WHERE id=?", (args.canvas,)).fetchone()[0])
        node = next(n for n in canvas["nodes"] if n["id"] == args.node)
        by_id = {n["id"]: n for n in canvas["nodes"]}
        images = [by_id[c["from"]]["url"] for c in canvas["connections"]
                  if c.get("to") == node["id"] and by_id.get(c.get("from"), {}).get("type") == "image"]
        secret_name = "API_PROVIDER_" + args.provider.upper().replace("-", "_") + "_KEY"
        row = db.execute("SELECT encrypted_value FROM secret_values WHERE key=?", (secret_name,)).fetchone()
        if row is None:
            raise RuntimeError("未找到已保存的目标平台密钥")
        from canvas_core.secrets import DpapiProtector
        secret = DpapiProtector().unprotect(row[0])
        os.environ[secret_name] = secret
    import main as app
    normalized = app.normalize_provider(provider)
    app.load_api_providers = lambda: [normalized]
    transport = app.resolve_chat_transport(args.provider, model, "")
    assert transport["protocol"] == "responses", "本次实验要求原生 Responses"
    assert images and len(images) <= 20
    input_root = Path(os.fspath(app.OUTPUT_INPUT_DIR))
    input_root.mkdir(parents=True, exist_ok=True)
    refs = []
    for i, url in enumerate(images, 1):
        assert url.startswith("/assets/input/")
        source = installed / "media/input" / Path(url).name
        target = input_root / source.name
        target.write_bytes(source.read_bytes())
        refs.append({"index": i, "url": url, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})

    manifest = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "provider": args.provider,
                "model": model, "protocol": transport["protocol"], "source_sha256": hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest(),
                "source_version": (ROOT / "VERSION").read_text().strip(), "references": refs,
                "runtime": str(runtime), "canvas_id": args.canvas, "node_id": args.node,
                "case_timeout_s": args.timeout, "baseline_prompt": node.get("prompt", ""),
                "variant_B_scope": "no-search + low reasoning + text-only compression; full rules retained; no cache or rule pruning"}
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("provider", "model", "source_sha256", "references", "baseline_prompt"):
            if previous[key] != manifest[key]:
                raise ValueError(f"复测配置 {key} 已变化，请使用新的输出目录")
        write_json(out / f"run-manifest-{runtime.name}.json", manifest)
    else:
        write_json(manifest_path, manifest)
    state = {"job": None, "phase": None, "attempt": None}
    original_llm = app.canvas_llm
    original_build = app.build_llm_request_body
    original_auto_system = app._video_auto_parse_system_prompt
    original_stream = app.request_responses_stream_json
    original_event = app.normalize_responses_stream_event
    search_instruction = "请先使用模型可用的联网搜索工具检索优秀的视频提示词、分镜和运镜案例，吸收可迁移的方法后再写结果；不要输出检索过程或来源列表。"

    def emit(event, **data):
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **data}
        with (out / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=True), flush=True)

    def auto_system(*a, **kw):
        text = original_auto_system(*a, **kw)
        if state["job"]["variant"] != "C":
            assert search_instruction in text
            text = text.replace(search_instruction, "本次只依据已提供素材和下方规范直接生成，不执行联网检索。")
        return text

    def build(*a, **kw):
        body = original_build(*a, **kw)
        job, phase = state["job"], state["phase"]
        if job["variant"] == "B":
            body["reasoning"] = {"effort": "low"}
        instructions = body.get("instructions", "")
        input_texts = [p.get("text", "") for m in body.get("input", []) for p in m.get("content", []) if p.get("type") == "input_text"]
        phase["request"] = {"model": body.get("model"), "stream": body.get("stream"),
                            "tools": body.get("tools", []), "reasoning": body.get("reasoning"),
                            "instructions_chars": len(instructions), "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
                            "request_utf8_bytes": len(json.dumps(body, ensure_ascii=False).encode()),
                            "image_parts": sum(p.get("type") == "input_image" for m in body.get("input", []) for p in m.get("content", [])),
                            "mandatory_search_instruction": search_instruction in instructions}
        if job["variant"] in {"A", "B"}:
            assert not body.get("tools")
            assert search_instruction not in instructions
        write_json(out / f"{job['id']}-{phase['index']}-request-text.json", {"instructions": instructions, "input_text": input_texts, **phase["request"]})
        emit("request", job=job["id"], phase=phase["name"], **phase["request"])
        return body

    def event(raw):
        result = original_event(raw)
        attempt = state["attempt"]
        # 同一事件还会被正文/完成文本辅助函数再次 normalize；只计一次原事件。
        if result and attempt is not None and result is not state.get("last_event"):
            state["last_event"] = result
            elapsed = time.perf_counter() - attempt["_start"]
            attempt.setdefault("first_event_s", elapsed)
            typ = result.get("type", "unknown")
            attempt["event_counts"][typ] = attempt["event_counts"].get(typ, 0) + 1
            if "web_search" in typ:
                attempt["search_event_count"] += 1
            if typ == "response.output_text.delta":
                if "first_text_s" not in attempt:
                    attempt["first_text_s"] = elapsed
                    state["job"].setdefault("first_text_s", time.perf_counter() - state["job"]["_start"])
                    emit("first_text", job=state["job"]["id"], phase=state["phase"]["name"], seconds=round(elapsed, 3))
            response = result.get("response")
            if isinstance(response, dict):
                for key in ["id", "model", "status", "reasoning", "usage", "service_tier"]:
                    if key in response:
                        attempt["response_" + key] = response[key]
        return result

    async def stream(client, route, body, on_text_delta=None):
        phase = state["phase"]
        attempt = {"index": len(phase["attempts"]) + 1, "_start": time.perf_counter(), "event_counts": {}, "search_event_count": 0, "event_count_method": "unique_normalized_object"}
        phase["attempts"].append(attempt)
        state["attempt"] = attempt
        try:
            raw = await original_stream(client, route, body, on_text_delta=on_text_delta)
            attempt["search_evidence"] = app.responses_web_search_evidence(raw)
            attempt["response_usage"] = raw.get("usage")
            attempt["response_model"] = raw.get("model") or attempt.get("response_model")
            attempt["response_status"] = raw.get("status") or attempt.get("response_status")
            return raw
        except Exception as exc:
            attempt["error"] = str(getattr(exc, "detail", None) or str(exc)).replace(secret, "[REDACTED]")[:1000]
            attempt["error_type"] = type(exc).__name__
            raise
        finally:
            attempt["elapsed_s"] = time.perf_counter() - attempt.pop("_start")
            state["attempt"] = None

    async def llm(payload, progress_callback=None):
        system = payload.system_prompt
        name = "search" if system.startswith("你是视频提示词研究助手") else "compress" if system.startswith("你是视频提示词压缩器") else "repair" if "现在进入引用修复模式" in system else "vision"
        if name == "compress" and state["job"]["variant"] == "B":
            payload = payload.model_copy(update={"images": [], "image_labels": [], "videos": []})
        phase = {"index": len(state["job"]["phases"]) + 1, "name": name, "attempts": [],
                 "start_offset_s": time.perf_counter() - state["job"]["_start"]}
        state["job"]["phases"].append(phase)
        state["phase"] = phase
        started = time.perf_counter()
        try:
            result = await original_llm(payload, progress_callback=progress_callback)
            phase["text"] = result.get("text", "")
            phase["web_search"] = result.get("web_search")
            phase["used_images"] = result.get("used_images")
            phase["status"] = "succeeded"
            return result
        except Exception as exc:
            phase["status"] = "failed"
            phase["error"] = str(getattr(exc, "detail", None) or str(exc)).replace(secret, "[REDACTED]")[:1000]
            raise
        finally:
            phase["elapsed_s"] = time.perf_counter() - started
            emit("phase_end", job=state["job"]["id"], phase=name, seconds=round(phase["elapsed_s"], 3), status=phase.get("status", "cancelled"))

    app._video_auto_parse_system_prompt = auto_system
    app.build_llm_request_body = build
    app.normalize_responses_stream_event = event
    app.request_responses_stream_json = stream
    app.canvas_llm = llm
    cases = {
        "single-auto": ("auto-parse", images[:1], "", "kling-cli", "kling-video-v3_0_omni", 5),
        "multi-auto": ("auto-parse", images, "", "minimax-h3", "MiniMax H3", 15),
        "multi-polish": ("polish", images, node.get("prompt", ""), "minimax-h3", "MiniMax H3", 15),
    }
    if "compression-replay" in args.cases.split(","):
        previous = json.loads((out / "multi-auto-A-r2.json").read_text(encoding="utf-8"))
        long_text = next(p["text"] for p in previous["phases"] if p["name"] == "vision")
        assert len(long_text) > app.video_prompt_limit("minimax-h3", "MiniMax H3")
        cases["compression-replay"] = ("compact", images, long_text, "minimax-h3", "MiniMax H3", 15)
    for repetition in range(1, args.repetitions + 1):
        for case in args.cases.split(","):
            variants = args.variants.split(",")
            if repetition % 2 == 0:
                variants.reverse()
            for variant in variants:
                job_id = f"{case}-{variant}-r{repetition}"
                destination = out / f"{job_id}.json"
                if destination.exists():
                    emit("skip_existing", job=job_id)
                    continue
                kind, selected_images, prompt, video_provider, video_model, duration = cases[case]
                job = {"id": job_id, "variant": variant, "case": case, "phases": [], "_start": time.perf_counter(), "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "input_images": len(selected_images)}
                state["job"] = job
                cls = app.CanvasVideoAutoParseRequest if kind == "auto-parse" else app.CanvasPromptPolishRequest
                payload = cls(provider=args.provider, model=model, video_provider=video_provider, video_model=video_model,
                              prompt=prompt, images=selected_images, image_labels=[f"参考素材{i}" for i in range(1, len(selected_images)+1)],
                              web_search=variant == "C", duration=duration, aspect_ratio="16:9", resolution="1080p")
                emit("job_start", job=job_id, images=len(selected_images), web_search=variant == "C")
                if kind == "compact":
                    job["entrypoint"] = "compact_video_prompt_if_needed (real generated overlength text replay)"
                    job["input_chars"] = len(prompt)
                    try:
                        final, compacted, limit = await asyncio.wait_for(app.compact_video_prompt_if_needed(
                            prompt, video_provider=video_provider, video_model=video_model,
                            llm_provider=args.provider, llm_model=model, images=selected_images), timeout=args.timeout)
                        job.update(status="succeeded", final_chars=len(final), within_limit=len(final) <= limit,
                                   result={"text": final, "prompt_compacted": compacted,
                                           "reference_coverage": app.video_prompt_reference_coverage(final, "minimax-h3", len(selected_images))})
                        (out / f"{job_id}.txt").write_text(final, encoding="utf-8")
                    except asyncio.TimeoutError:
                        job.update(status="timeout", error="压缩补充实验超过时间预算")
                    job["total_s"] = time.perf_counter() - job.pop("_start")
                    job["llm_calls"] = len(job["phases"])
                    job["upstream_attempts"] = sum(len(p["attempts"]) for p in job["phases"])
                    write_json(destination, job)
                    emit("job_end", job=job_id, status=job["status"], seconds=round(job["total_s"], 3))
                    continue
                created = app._create_canvas_prompt_task(kind, payload)
                task_id = created["task_id"]
                try:
                    await asyncio.wait_for(app.CANVAS_PROMPT_TASK_RUNNERS[task_id], timeout=args.timeout)
                    view = app.CANVAS_PROMPT_TASKS[task_id]
                    job["status"] = view["status"]
                    job["error"] = str(view.get("error", "")).replace(secret, "[REDACTED]")
                    job["result"] = view.get("result")
                    if job["result"]:
                        text = job["result"].get("text", "")
                        job["final_chars"] = len(text)
                        job["within_limit"] = len(text) <= app.video_prompt_limit(video_provider, video_model)
                        (out / f"{job_id}.txt").write_text(text, encoding="utf-8")
                except asyncio.TimeoutError:
                    job["status"] = "timeout"
                    job["error"] = f"隔离测试总预算 {args.timeout} 秒已用完，本地协程已取消"
                finally:
                    job["total_s"] = time.perf_counter() - job.pop("_start")
                    job["llm_calls"] = len(job["phases"])
                    job["upstream_attempts"] = sum(len(p["attempts"]) for p in job["phases"])
                    # 失败的搜索可能只有 searching 事件而没有最终 evidence，不能计作未搜索。
                    job["completed_response_search_calls"] = sum(a.get("search_evidence", {}).get("call_count", 0) for p in job["phases"] for a in p["attempts"])
                    job["search_started_observed"] = any(a.get("search_event_count", 0) > 0 for p in job["phases"] for a in p["attempts"])
                    write_json(destination, job)
                    emit("job_end", job=job_id, status=job["status"], seconds=round(job["total_s"], 3), calls=job["llm_calls"], completed_response_search_calls=job["completed_response_search_calls"], search_started_observed=job["search_started_observed"])
                    app.CANVAS_PROMPT_TASK_RUNNERS.pop(task_id, None)
                    app.CANVAS_PROMPT_TASKS.pop(task_id, None)
    emit("all_finished")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "输出/分析报告/视频提示词三方案实测-20260907"))
    parser.add_argument("--installed-data", default=r"D:\Program Files\SHIYIN AI\data")
    parser.add_argument("--provider", default="ecommerce-vision")
    parser.add_argument("--model", default="")
    parser.add_argument("--canvas", default="7cb95071d8874f1f864a769e72068b32")
    parser.add_argument("--node", default="vid_c9ed1b4b267d78_1788496316553")
    parser.add_argument("--cases", default="single-auto,multi-auto,multi-polish")
    parser.add_argument("--variants", default="C,A,B")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=480)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
