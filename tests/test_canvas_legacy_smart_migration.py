import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "static/js/canvas-legacy-migration.js"
CANVAS_HTML = ROOT / "static/canvas.html"


def run_migration(nodes):
    script = f"""
const migration = require({json.dumps(str(MIGRATION))});
const input = {json.dumps(nodes, ensure_ascii=False)};
process.stdout.write(JSON.stringify(migration.migrate(input)));
"""
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def test_real_legacy_smart_nodes_migrate_to_classic_shapes_without_losing_media():
    result = run_migration([
        {
            "id": "smart-image-1",
            "type": "smart-image",
            "x": 10,
            "y": 20,
            "title": "历史图片",
            "images": [{"url": "/assets/output/a.png", "name": "a.png", "kind": "image", "natural_w": 1200, "natural_h": 800}],
        },
        {
            "id": "smart-image-2",
            "type": "smart-image",
            "x": 100,
            "y": 200,
            "images": [
                {"url": "/assets/output/b.png", "name": "b.png", "kind": "image"},
                {"url": "/assets/output/c.png", "name": "c.png", "kind": "image"},
            ],
        },
        {"id": "smart-prompt-1", "type": "smart-prompt", "text": "电影感夜景"},
        {"id": "smart-loop-1", "type": "smart-loop", "count": 4, "showPrompt": True, "variablePrompt": "第《计数》张"},
        {"id": "smart-group-1", "type": "smart-group", "items": ["smart-prompt-1"], "images": [{"url": "/assets/output/d.png", "name": "d.png"}]},
    ])

    migrated = result["nodes"]
    by_id = {node["id"]: node for node in migrated}
    assert result["changed"] is True
    assert by_id["smart-image-1"]["type"] == "image"
    assert by_id["smart-image-1"]["url"] == "/assets/output/a.png"
    assert by_id["smart-image-1"]["natural_w"] == 1200
    assert by_id["smart-image-2"]["type"] == "group"
    child_ids = by_id["smart-image-2"]["items"]
    assert [by_id[child_id]["url"] for child_id in child_ids] == ["/assets/output/b.png", "/assets/output/c.png"]
    assert by_id["smart-prompt-1"] == {"id": "smart-prompt-1", "type": "prompt", "text": "电影感夜景"}
    assert by_id["smart-loop-1"]["type"] == "loop"
    assert by_id["smart-loop-1"]["count"] == 4
    assert by_id["smart-group-1"]["type"] == "group"
    assert len(by_id["smart-group-1"]["items"]) == 2


def test_migration_is_idempotent_after_classic_save():
    first = run_migration([{"id": "smart-image-1", "type": "smart-image", "images": [{"url": "/output/a.png"}]}])
    second = run_migration(first["nodes"])
    assert second["changed"] is False
    assert second["nodes"] == first["nodes"]


def test_unified_editor_loads_legacy_migration_before_canvas_runtime():
    page = CANVAS_HTML.read_text(encoding="utf-8")
    assert "canvas-legacy-migration.js" in page
    assert page.index("canvas-legacy-migration.js") < page.index("/static/js/canvas.js")


def test_media_service_worker_serves_cached_previews_before_background_refresh():
    worker = (ROOT / "static/media-cache-sw.js").read_text(encoding="utf-8")
    assert "return url.pathname.startsWith('/api/');" in worker
    assert "MEDIA_PREVIEW_REFRESH_INTERVAL" in worker
    assert "mediaPreviewRefreshes" in worker
    assert "matchGeneratedImage" in worker
    assert "new Request(request, {cache: 'no-store'})" in worker
    assert "path === '/api/media-preview'" in worker
    assert "staleWhileRevalidateMediaPreview" in worker
    assert "event.waitUntil(refresh.catch(() => {}))" in worker
