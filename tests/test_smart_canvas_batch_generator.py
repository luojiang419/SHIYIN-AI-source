from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
JAVASCRIPT = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")
I18N = (ROOT / "static" / "js" / "i18n" / "smart-canvas.js").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    start_index = JAVASCRIPT.index(start)
    return JAVASCRIPT[start_index:JAVASCRIPT.index(end, start_index)]


def test_image_and_group_floating_menus_create_a_connected_batch_node():
    assert JAVASCRIPT.count("{key:'batch', icon:'layers-3', label:'批量处理'") == 2
    assert "function createSmartBatchGeneratorNode(sourceNode=null, point=null)" in JAVASCRIPT
    create_body = section("function createSmartBatchGeneratorNode", "const MULTI_VIEW_INPUT_SLOTS")
    assert "specialType:'batch-generator'" in create_body
    assert "title:'批量处理'" in create_body
    assert "node.specialType === 'batch-generator' ? '批量处理'" in JAVASCRIPT
    assert "connectInputNode(sourceNode.id, node.id)" in create_body
    assert "sourceRect.x + sourceRect.width + 120" in create_body


def test_batch_node_accepts_uncapped_unique_image_inputs():
    body = section("function smartBatchInputRefs(node)", "function smartBatchPrompt(node)")
    assert "inputNodesFor(node)" in body
    assert ".flatMap(input => imagesForNode(input))" in body
    assert "mediaKindForItem(item) === 'image'" in body
    assert "SMART_REFERENCE_IMAGE_MAX" not in body
    assert "seen.add(item.url)" in body


def test_batch_run_creates_stable_output_slots_before_parallel_submission():
    prepare_body = section("function prepareSmartBatchOutput", "async function runSmartBatchGenerator")
    assert "output.generationSlots = refs.map" in prepare_body
    assert "status:'loading'" in prepare_body
    assert "node.batchOutputNodeId" in prepare_body

    run_body = section("async function runSmartBatchGenerator", "function multiViewInputRefs")
    assert "prepareSmartBatchOutput(node, refs, meta)" in run_body
    assert "Promise.allSettled(plans.map" in run_body
    assert "runApiGeneration(prompt, [plan.ref], plan.runSettings)" in run_body
    assert "await resumeSmartPendingNode(output" in run_body


def test_each_batch_item_preserves_source_ratio_and_retry_context():
    settings_body = section("async function smartBatchRunSettingsForRef", "function prepareSmartBatchOutput")
    assert "loadSmartOriginalImageDimensions" in settings_body
    assert "gcdInt" in settings_body
    assert "ratio:'custom'" in settings_body
    assert "count:1" in settings_body

    retry_body = section("async function retrySmartGenerationSlot", "function deleteSmartGenerationSlot")
    assert "previousTask?.runSettings" in retry_body
    assert "previousTask?.prompt" in retry_body
    assert "previousTask?.refs" in retry_body


def test_batch_node_has_dedicated_controls_and_layout():
    assert "function smartBatchBodyHtml(node)" in JAVASCRIPT
    assert 'data-special-action="run-batch"' in JAVASCRIPT
    assert 'data-batch-provider' in JAVASCRIPT
    assert 'data-batch-prompt' in JAVASCRIPT
    assert ".smart-special-node.smart-batch-generator-node" in STYLES
    assert '"smart.batchProcess"' in I18N
