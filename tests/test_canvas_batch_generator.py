from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
JAVASCRIPT = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
I18N = (ROOT / "static" / "js" / "i18n" / "canvas.js").read_text(encoding="utf-8")


def function_body(name: str, next_name: str) -> str:
    start = JAVASCRIPT.index(f"function {name}")
    end = JAVASCRIPT.index(f"function {next_name}", start)
    return JAVASCRIPT[start:end]


def test_batch_generator_is_a_first_class_image_generator_variant():
    assert "function addBatchGeneratorNode(point)" in JAVASCRIPT
    assert "type:'batchGenerator'" in JAVASCRIPT
    assert "['generator','batchGenerator'].includes(node.type)" in JAVASCRIPT
    assert "'batchGenerator-node batch-generator-node generator-node'" in JAVASCRIPT
    assert "node.type === 'generator' || node.type === 'batchGenerator'" in JAVASCRIPT
    assert '"canvas.batchProcess"' in I18N
    assert ".batch-process-hint" in STYLES


def test_batch_toolbar_action_is_available_for_image_and_group_targets():
    assert JAVASCRIPT.count("{id:'batchGenerator', label:tr('canvas.batchProcess'), icon:'layers-3'}") == 2
    body = function_body("runMediaQuickAction(action, target)", "startSelectionLink(e, kind)")
    assert "action === 'batchGenerator' && target?.kind === 'group'" in body
    assert "addQuickActionNode(sourceNode, action)" in body
    assert "addQuickActionNode(image, action)" in body


def test_batch_run_expands_inputs_to_one_reference_per_task_and_submits_concurrently():
    body = function_body("runBatchGenerator(genId, opts={})", "runGeneratorLegacy(genId, opts={})")
    assert "const refs = batchGeneratorImageRefs(gen);" in body
    assert "reference_images:[ref]" in body
    assert "plans.map(plan => plan.pending)" in body
    assert "Promise.allSettled(plans.map(plan => createCanvasImageTask" in body
    assert "Promise.all(accepted.map(plan => pollCanvasImageTask" in body
    assert "batchIndex:index" in body


def test_batch_run_forces_output_node_and_reuses_pending_recovery_pipeline():
    body = function_body("runBatchGenerator(genId, opts={})", "runGeneratorLegacy(genId, opts={})")
    assert "outputForNode(gen, 460, true)" in body
    assert "makePendingForRun" in body
    assert "canvasTaskType:'online-image'" in body
    assert "pending.canvasTaskId = result.value.task_id" in body
    assert "pollCanvasImageTask(plan.taskId" in body
