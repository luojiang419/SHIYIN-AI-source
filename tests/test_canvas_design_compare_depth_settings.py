from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
SHARED_JS = (ROOT / "static" / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
SETTINGS_HTML = (ROOT / "static" / "app-settings.html").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "static" / "js" / "app-settings.js").read_text(encoding="utf-8")
TUNER_HTML = (ROOT / "static" / "depth-map-tuner.html").read_text(encoding="utf-8")
TUNER_JS = (ROOT / "static" / "js" / "depth-map-tuner.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_canvas_work_mode_switch_is_persistent_and_keeps_public_nodes():
    for marker in (
        'id="canvasWorkModeSwitch"',
        'data-canvas-work-mode="all"',
        'data-canvas-work-mode="design"',
        "const CANVAS_WORK_MODE_KEY = 'canvas_work_mode_v1'",
        "function applyCanvasWorkMode(mode=canvasWorkMode())",
        "CANVAS_VIDEO_ONLY_NODE_TYPES",
        "canvas-work-mode-design",
    ):
        assert marker in CANVAS_HTML + CANVAS_JS + CANVAS_CSS
    for node_type in ("depthMap", "poseReplicate", "multiView", "resultCompare"):
        assert node_type not in CANVAS_JS[CANVAS_JS.index("const CANVAS_VIDEO_ONLY_NODE_TYPES"):CANVAS_JS.index("const CLASSIC_QUICK_TOOLBAR_DEFS")]
        assert f"menuAdd('{node_type}')" in CANVAS_HTML


def test_storyboard_merge_is_named_puzzle_without_breaking_internal_type():
    assert "type:'storyboardMerge'" in CANVAS_JS
    assert "合并分镜" not in CANVAS_HTML
    assert "合并分镜" not in CANVAS_JS
    assert "node.type === 'storyboardMerge' ? '拼图'" in CANVAS_JS


def test_result_compare_node_has_two_ports_inline_compare_and_fullscreen():
    for marker in (
        "function addResultCompareNode(point)",
        "type:'resultCompare'",
        "['compare-source','源文件']",
        "['compare-target','目标文件']",
        "function resultCompareBodyHtml(node)",
        "new window.CompareViewer",
        "data-result-compare-fullscreen",
        "function openCanvasResultCompare(beforeUrl, afterUrl",
        'id="canvasCompareOverlay"',
        ".result-compare-stage.is-portrait",
    ):
        assert marker in CANVAS_HTML + CANVAS_JS + CANVAS_CSS


def test_image_and_pose_replicate_output_compare_shortcuts_are_connected():
    for marker in (
        "{id:'resultCompare', label:'结果对比'",
        "function createResultCompareFromImage(sourceNode)",
        "inputRole:'compare-target'",
        "action === 'resultCompareFullscreen'",
        "sourceNode.poseReplicateSourceId",
        "classicSpecialInputImage(poseNode, 'pose-reference')",
        "{before:'目标图片', after:'生成图片'}",
    ):
        assert marker in CANVAS_JS


def test_depth_mode_settings_and_integrated_tuner_are_available():
    for marker in (
        'id="depthMapMode"',
        'value="person"',
        'value="professional"',
        'id="openDepthMapTuner"',
        "depth_map_mode:mode",
        "studio-open-depth-map-tuner",
    ):
        assert marker in SETTINGS_HTML + SETTINGS_JS
    assert 'id="frame-depth-map-tuner"' in INDEX_HTML
    assert "'depth-map-tuner'" in INDEX_HTML
    assert "保存配置" in TUNER_HTML
    assert "导出参数配置" not in TUNER_HTML
    assert "depth_map_controls:state.controls" in TUNER_JS
    assert "'/api/depth/estimate'" in TUNER_JS
    assert "'/api/person-depth/estimate'" in TUNER_JS


def test_shared_depth_nodes_follow_mode_and_global_controls():
    for marker in (
        "function activeDepthMapMode()",
        "function refreshDepthMapSettings(force=false)",
        "depth-map-settings:changed",
        "depthMapSharedConfigSignature",
        "poseDepthSharedConfigSignature",
        "function estimateConfiguredDepthFile(source, options",
        "professional ? '/api/depth/estimate' : '/api/person-depth/estimate'",
        "function applyPoseDepthGlobalControls(node, options)",
    ):
        assert marker in SHARED_JS
