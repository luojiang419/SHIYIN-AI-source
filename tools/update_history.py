"""永久版本日志：构建暂存到包内，构建成功后追加回源码；不依赖可删除的发布包。"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))


def read_history(path):
    path = Path(path)
    if not path.exists():
        return {"history": []}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("history"), list):
        raise ValueError("版本历史格式无效，拒绝覆盖已有记录")
    return data


def record_id(entry):
    return entry.get("id") or f"release:{entry['version']}"


def merge_history(data, records):
    entries = {record_id(entry): dict(entry) for entry in data["history"]}
    for record in records:
        key = record_id(record)
        old = entries.get(key, {})
        merged = {**old, **record}
        items, seen = [], set()
        for item in old.get("items", []) + record.get("items", []):
            text = item if isinstance(item, str) else item.get("text", "")
            if text and text not in seen:
                items.append(item); seen.add(text)
        merged["items"] = items
        if old.get("record_status") == "published":
            merged["record_status"] = "published"
        entries[key] = merged
    # 所有生产记录使用 ISO 时间；时间戳相同时保留稳定顺序。
    return {**data, "history": sorted(entries.values(), key=lambda e: e.get("updated_at", ""), reverse=True)}


def write_history(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")
        temporary = out.name
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def make_record(kind, version, notes, *, baseline="", min_version="", updated_at="", status="built"):
    if kind not in ("baseline", "hot", "web", "hot-updater", "hot-bootstrap"):
        raise ValueError("不支持的日志类型")
    if kind == "baseline":
        if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not re.fullmatch(r"\d{14}", baseline):
            raise ValueError("全量基线需版本号和14位内置基线序号")
        identity = f"baseline:{version}:{baseline}"
    else:
        if not re.fullmatch(r"\d{14}", version):
            raise ValueError("热更新需14位序号")
        identity = f"hot:{version}"
    stamp = baseline if kind == "baseline" else version
    when = updated_at or datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=TZ).isoformat()
    items = [{"type": "update", "text": line.strip()} for line in notes.splitlines() if line.strip()]
    if kind == "baseline":
        items.insert(0, {"type": "baseline", "text": f"全量安装基线切换至 {version}，内置更新基线 {baseline}；历史更新日志持续保留。"})
    return {"id": identity, "version": version, "kind": kind, "updated_at": when,
            "record_status": status, "baseline": baseline, "min_desktop_version": min_version, "items": items}


def stage_record(root, target, record):
    data = merge_history(read_history(Path(root) / "static/update-history.json"), [record])
    write_history(target, data)


def commit_record(root, record):
    path = Path(root) / "static/update-history.json"
    write_history(path, merge_history(read_history(path), [record]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--commit-stage", type=Path)
    args = parser.parse_args()
    if args.commit_stage:
        staged = read_history(args.commit_stage)
        path = args.root / "static/update-history.json"
        write_history(path, merge_history(read_history(path), staged["history"]))
        return
    if not args.stage:
        parser.error("需要 --stage 或 --commit-stage")
    version = (args.root / "VERSION").read_text("utf-8-sig").strip()
    baseline = (args.root / "src-tauri/distribution-baseline.txt").read_text("utf-8-sig").strip()
    notes_path = args.root / "release-notes/current.md"
    text = notes_path.read_text("utf-8-sig") if notes_path.exists() else ""
    text = text.split("## 历史版本记录", 1)[0]
    notes = "\n".join(line[2:].strip() for line in text.splitlines() if line.startswith("- "))
    stage_record(args.root, args.stage, make_record("baseline", version, notes, baseline=baseline))


if __name__ == "__main__":
    main()
