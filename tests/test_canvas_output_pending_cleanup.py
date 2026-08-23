from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")


def function_body(name: str, next_name: str) -> str:
    start = CANVAS_JS.index(f"function {name}")
    end = CANVAS_JS.index(f"function {next_name}", start)
    return CANVAS_JS[start:end]


def test_opening_canvas_drops_only_non_resumable_output_placeholders():
    prune_body = function_body("pruneCanvasRuntimeCollections(options={})", "renderCanvasIcon")

    assert "const dropOrphanPending = options.dropOrphanPending === true;" in prune_body
    assert "node.type === 'output' && Array.isArray(node._pending)" in prune_body
    assert (
        "pending.filter(item => item?.canvasTaskId || item?.recoverTaskId)"
        in prune_body
    )
    assert CANVAS_JS.count("pruneCanvasRuntimeCollections({dropOrphanPending:true});") == 2
    # 远端增量同步仍使用保守模式，不能误删刚提交、尚未拿到任务 ID 的占位。
    assert "pruneCanvasRuntimeCollections();" in CANVAS_JS


def test_completed_source_prunes_orphan_spinner_without_dropping_active_tasks():
    cleanup_body = function_body(
        "pruneCompletedOrphanOutputPending()", "refreshOutputTimer(skipOrphanPrune=false)"
    )

    assert "if(item?.canvasTaskId || item?.recoverTaskId) return true;" in cleanup_body
    assert "source.running !== true && source.runStatus === 'done'" in cleanup_body
    assert "out._pending = retained;" in cleanup_body


def test_output_refresh_avoids_recursive_orphan_cleanup():
    timer_body = function_body("refreshOutputTimer(skipOrphanPrune=false)", "serializableCanvasNode")
    refresh_body = function_body("refreshOutputNodeContent(node)", "defaultNodeSize")

    assert "pruneCompletedOrphanOutputPending()" in timer_body
    assert "scheduleSave();" in timer_body
    assert "refreshOutputNodeContent(node)" in timer_body
    assert "refreshOutputTimer(true);" in refresh_body
