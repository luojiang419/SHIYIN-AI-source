from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHARED_JS = (ROOT / "static/js/canvas-building-multi-view.js").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/canvas-multi-view-overrides.css").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")


def test_shared_building_mode_defines_six_typed_inputs_and_five_outputs():
    for role, label, kind in [
        ("building-sketch", "线稿图", "image"),
        ("building-front", "建筑正面", "image"),
        ("building-side", "建筑侧视图", "image"),
        ("building-back", "建筑背视图", "image"),
        ("building-top", "建筑顶视图", "image"),
        ("building-prompt", "提示词", "prompt"),
    ]:
        assert f"['{role}','{label}','{kind}']" in SHARED_JS
    for key, label in [
        ("sketch", "线稿图"),
        ("front", "建筑正面"),
        ("side", "建筑侧视图"),
        ("back", "建筑背视图"),
        ("top", "建筑顶视图"),
    ]:
        assert f"['{key}','{label}']" in SHARED_JS


def test_historical_nodes_default_to_person_mode_and_new_nodes_store_mode_state():
    assert "node?.multiViewMode === MODES.BUILDING ? MODES.BUILDING : MODES.PERSON" in SHARED_JS
    assert "multiViewMode:'person'" in CANVAS_JS
    assert "multiViewMode:'person'" in SMART_JS
    assert "buildingStage:'idle'" in CANVAS_JS
    assert "buildingStage:'idle'" in SMART_JS


def test_both_canvases_render_mode_switch_six_ports_and_inline_prompt():
    for source in (CANVAS_JS, SMART_JS):
        assert 'data-multi-view-mode="person"' in source
        assert 'data-multi-view-mode="building"' in source
        assert "人物三视图" in source
        assert "建筑三视图" in source
        assert "data-building-prompt" in source
        assert "6 个输入 · 5 个输出槽" in source
        assert "生成多视图" in source
    assert "classicMultiViewInputSlots(node).map" in CANVAS_JS
    assert "smartMultiViewInputSlots(node).map" in SMART_JS


def test_prompt_ports_only_accept_prompt_sources_and_inactive_connections_are_hidden():
    assert "roleKind(inputRole) === 'prompt'" in CANVAS_JS
    assert "['prompt','promptGroup','llm'].includes(from.type)" in CANVAS_JS
    assert "roleKind(inputRole) === 'prompt'" in SMART_JS
    assert "from.type === 'smart-prompt'" in SMART_JS
    assert "!classicMultiViewInputSlots(target).some" in CANVAS_JS
    assert "!smartMultiViewInputSlots(targetNode).some" in SMART_JS


def test_shared_script_and_building_styles_are_loaded_by_both_canvases():
    script = '<script src="/static/js/canvas-building-multi-view.js?v=2026.08.22.building-mode.3"></script>'
    assert script in CANVAS_HTML
    assert script in SMART_HTML
    # 构建缓存版本会随发布日递增，检查固定资源签名和 rev 参数即可，
    # 避免测试把上一轮发布日期写死后阻断后续模块回归。
    assert 'canvas.js?v=2026.08.21.bulk-import-grid.1&rev=' in CANVAS_HTML
    assert ".multi-view-mode-switch" in CSS
    assert ".building-prompt" in CSS
    assert ".classic-building-prompt" in CSS


def test_shared_building_prompt_builder_has_all_views_and_photographic_consistency_anchors():
    for view in ["front", "side", "back", "top"]:
        assert f"{view}:'" in SHARED_JS
    assert "buildBuildingPrompt(view, plan={}, referenceRoles=[])" in SHARED_JS
    assert "buildBuildingPromptSet(plan={}, referenceRoles=[]" in SHARED_JS
    assert "same exact building" in SHARED_JS
    assert "full-scale physically constructed building photographed on a real location" in SHARED_JS
    assert "true material microtexture" in SHARED_JS
    assert "natural construction tolerances" in SHARED_JS
    assert "professional architectural design board" in SHARED_JS
    assert "front elevation, right-side elevation, rear elevation and roof plan" in SHARED_JS
    assert "only the four line drawings on blank drafting paper" in SHARED_JS
    assert "rule-of-thirds placement for the ground, sky and surrounding breathing room" in SHARED_JS


def test_classic_building_flow_calls_planner_and_preserves_original_view_slots():
    assert "requestClassicBuildingPlan(node, refs, connectedPrompt)" in CANVAS_JS
    assert "'/api/building-multi-view/plan'" in CANVAS_JS
    assert "inline_prompt:String(node.buildingPrompt || '').trim()" in CANVAS_JS
    assert "connected_prompt:String(connectedPrompt || '').trim()" in CANVAS_JS
    assert "const references = CLASSIC_BUILDING_VIEW_KEYS.map" in CANVAS_JS
    assert "buildingSource:'input'" in CANVAS_JS
    assert "if(refs[view]) node.buildingOutputs[index] = classicBuildingReferenceItem" in CANVAS_JS


def test_classic_building_flow_has_two_confirmation_gates_and_regeneration_actions():
    for action, label in [
        ("confirm-sketch", "确认线稿"),
        ("regenerate-sketch", "重新生成"),
        ("confirm-front", "确认正面"),
        ("regenerate-front", "重新生成"),
    ]:
        assert f"action:'{action}', label:'{label}'" in SHARED_JS
    assert "classicBuildingSetStage(node, 'awaiting-sketch-confirmation')" in CANVAS_JS
    assert "classicBuildingSetStage(node, 'awaiting-front-confirmation')" in CANVAS_JS
    assert "data-building-action" in CANVAS_JS
    assert "handleClassicBuildingAction(node.id" in CANVAS_JS
    assert ".building-action-group" in CSS
    assert ".gen-btn.secondary" in CSS


def test_classic_building_only_generates_missing_real_views_concurrently():
    assert "const targets = ['front','side','back','top'].filter" in CANVAS_JS
    assert "if(!targets.length)" in CANVAS_JS
    assert "classicBuildingCompleteRun(node, startedAt)" in CANVAS_JS
    assert "Promise.allSettled(targets.map(view => generateClassicBuildingView" in CANVAS_JS
    assert "成功结果已保留" in CANVAS_JS
    assert "action:'retry-missing'" in SHARED_JS
    missing_guard = CANVAS_JS.index("if(!targets.length)")
    model_guard = CANVAS_JS.index("if(!classicBuildingHasImageModel(node))", missing_guard)
    assert missing_guard < model_guard


def test_classic_building_input_signature_invalidates_stale_confirmations():
    assert "classicBuildingInputSignature(node" in CANVAS_JS
    assert "node.buildingInputSignature !== classicBuildingInputSignature(node)" in CANVAS_JS
    assert "建筑参考图或提示词已变化" in CANVAS_JS
    assert "node.buildingPlan = null" in CANVAS_JS
    prompt_handler = CANVAS_JS[CANVAS_JS.index("const buildingPrompt = el.querySelector"):]
    prompt_handler = prompt_handler[:prompt_handler.index("const multiViewProvider")]
    assert "node.buildingInputSignature = ''" not in prompt_handler


def test_smart_building_flow_calls_planner_and_extracts_connected_prompt():
    assert "async function requestSmartBuildingPlan(node, refs, connectedPrompt)" in SMART_JS
    assert "fetch('/api/building-multi-view/plan'" in SMART_JS
    assert "inline_prompt:String(node.buildingPrompt || '').trim()" in SMART_JS
    assert "connected_prompt:String(connectedPrompt || '').trim()" in SMART_JS
    assert "function smartBuildingConnectedPrompt(node)" in SMART_JS
    assert "inputRole === 'building-prompt'" in SMART_JS
    assert "buildingSource:'input'" in SMART_JS


def test_smart_building_flow_has_two_confirmation_gates_and_output_node():
    for text in [
        "async function handleSmartBuildingAction(node, action)",
        "action === 'confirm-sketch'",
        "action === 'regenerate-sketch'",
        "action === 'confirm-front'",
        "action === 'regenerate-front'",
        "action === 'retry-missing'",
        "smartBuildingSetStage(node, 'awaiting-sketch-confirmation')",
        "smartBuildingSetStage(node, 'awaiting-front-confirmation')",
        "function smartBuildingEnsureOutputNode(node)",
        "buildingOutputNodeId",
        "buildingMultiViewOutput",
    ]:
        assert text in SMART_JS
    assert "data-building-action" in SMART_JS
    assert ".building-multi-view-output .generation-slot-grid" in CSS


def test_smart_building_only_generates_missing_views_concurrently_and_keeps_successes():
    assert "const targets = SMART_BUILDING_REAL_VIEW_KEYS.filter" in SMART_JS
    assert "if(!targets.length)" in SMART_JS
    assert "Promise.allSettled(targets.map(view => generateSmartBuildingView" in SMART_JS
    assert "成功结果已保留" in SMART_JS
    assert "smartBuildingCompleteRun(node, startedAt)" in SMART_JS
    assert "status:item ? 'success' : error ? 'error' : active.has(view) ? 'loading' : 'waiting'" in SMART_JS


def test_smart_building_input_signature_invalidates_stale_confirmations_and_busy_controls():
    assert "function smartBuildingInputSignature(node" in SMART_JS
    assert "smartBuildingAssertInputStable(node)" in SMART_JS
    assert "建筑参考图或提示词在生成过程中发生变化" in SMART_JS
    assert "const buildingControlDisabled = buildingBusy ? 'disabled' : '';" in SMART_JS
    assert "node.buildingPlan = null;" in SMART_JS


def test_smart_building_persists_task_ids_and_resumes_without_resubmitting_api_tasks():
    assert "buildingPendingTasks" in SHARED_JS
    assert "pendingTask = {view, taskId" in SMART_JS
    assert "function resumeSmartBuildingNodePending(node)" in SMART_JS
    assert "resumeSmartBuildingPendingTasks();" in SMART_JS
    assert "pollSmartCanvasTask(task.taskId)" in SMART_JS
    resume_body = SMART_JS[SMART_JS.index("async function resumeSmartBuildingNodePending"):SMART_JS.index("function resumeSmartBuildingPendingTasks", SMART_JS.index("async function resumeSmartBuildingNodePending"))]
    assert "runApiGeneration" not in resume_body
    assert "smartBuildingItemFromResult(result, task.view)" in resume_body


def test_smart_building_retry_never_submits_duplicate_while_task_is_recovering():
    assert "await resumeSmartBuildingNodePending(node);" in SMART_JS
    assert "建筑任务仍在恢复中，请稍后再次点击“重试缺失视图”" in SMART_JS
    assert "stage === BUILDING_STAGES.PARTIAL || stage === BUILDING_STAGES.ERROR" in SHARED_JS
    assert "已有建筑任务正在恢复，请稍后再开始新的规划" in SMART_JS
    assert "node.buildingPendingTasks = [];" in SMART_JS
