import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


class CanvasSpecialNodeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = (STATIC / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
        cls.styles = (STATIC / "css" / "canvas-special-nodes.css").read_text(encoding="utf-8")
        cls.angle_styles = (STATIC / "css" / "canvas-angle-3d.css").read_text(encoding="utf-8")
        cls.pose_replicate_styles = (STATIC / "css" / "pose-replicate-node.css").read_text(encoding="utf-8")
        cls.classic = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.classic_html = (STATIC / "canvas.html").read_text(encoding="utf-8")
        cls.smart_html = (STATIC / "smart-canvas.html").read_text(encoding="utf-8")

    def test_canvas_pages_load_shared_assets_and_offer_current_special_nodes(self):
        for page in (self.classic_html, self.smart_html):
            self.assertIn("/static/css/canvas-special-nodes.css", page)
            self.assertIn("/static/js/canvas-special-nodes.js", page)
            self.assertIn("720°取景器", page)
            self.assertIn("动作提取", page)
            self.assertIn("pose-replicate.6", page)
            self.assertIn("feature=pose-replicate-top-ports.1", page)
            self.assertNotIn("灯光重塑", page)
        self.assertIn("location.replace(target)", self.smart_html)

    def test_angle_node_creation_is_hidden_but_legacy_canvas_data_remains_compatible(self):
        self.assertNotIn('onclick="addAngleNode()"', self.classic_html)
        self.assertNotIn("menuAdd('angle')", self.classic_html)
        self.assertNotIn('data-create-type="angle"', self.smart_html)
        self.assertNotIn("{type:'angle', label:'角度调整'", self.classic)
        self.assertNotIn("if(type === 'angle') return addAngleNode(point)", self.classic)
        self.assertNotIn("if(type === 'angle') addAngleNode(menuPoint)", self.classic)
        self.assertNotIn("if(type === 'angle') return createAngleNode(p)", self.smart)
        self.assertIn("function addAngleNode(point)", self.classic)
        self.assertIn("function createAngleNode(point)", self.smart)
        self.assertIn("if(node.type === 'angle') body.innerHTML", self.classic)
        self.assertIn("if(node.specialType === 'angle') return", self.smart)

    def test_panorama_uses_full_sphere_source_and_perspective_projection(self):
        for marker in (
            "标准 2:1 等距柱状投影",
            "atan(d.x,-d.z)",
            "asin(clamp(d.y",
            "panoramaYaw",
            "panoramaPitch",
            "panoramaFov",
            "panoramaResolution",
        ):
            self.assertIn(marker, self.shared)
        self.assertIn("gl.CLAMP_TO_EDGE", self.shared)
        self.assertNotIn("gl.REPEAT", self.shared)

    def test_panorama_releases_replaced_webgl_contexts_and_restores_lost_context(self):
        for marker in (
            "function disposePanoramaCanvas(canvas)",
            "function disposePanoramasIn(root)",
            "WEBGL_lose_context",
            "webglcontextlost",
            "webglcontextrestored",
            "state.gl?.isContextLost?.()",
        ):
            self.assertIn(marker, self.shared)
        self.assertIn("disposePanoramasIn?.(nodesEl)", self.classic)
        self.assertIn("disposePanoramasIn?.(world)", self.smart)

    def test_smart_canvas_blank_click_does_not_rebuild_live_panorama(self):
        handler = re.search(
            r"shell\.onclick\s*=\s*e\s*=>\s*\{(?P<body>.*?)\n\s*\};",
            self.smart,
            re.S,
        )
        self.assertIsNotNone(handler)
        body = handler.group("body")
        self.assertIn("clearSelection();", body)
        self.assertIn("syncSelectionUi();", body)
        self.assertIn("updateComposer();", body)
        self.assertNotIn("render();", body)

    def test_panorama_exports_view_and_mannequin_as_one_downstream_image(self):
        export_body = re.search(
            r"async function exportReference\(.*?\n\s*return file;\n\s*\}",
            self.shared,
            re.S,
        )
        self.assertIsNotNone(export_body)
        body = export_body.group(0)
        self.assertIn("drawMannequin", body)
        self.assertIn("ctx.drawImage(canvas", body)
        self.assertIn("ctx.drawImage(overlay", body)
        self.assertIn("uploadBlob(blob", body)
        self.assertIn("function setOutputItem", self.shared)

    def test_dwpose_runs_automatically_and_uploads_a_reusable_skeleton(self):
        self.assertIn("runPose(node, options, false)", self.shared)
        self.assertIn("/api/dwpose/detect", self.shared)
        self.assertIn("X-DWPose-People", self.shared)
        self.assertIn("uploadBlob(blob, `dwpose-", self.shared)
        self.assertIn("poseSourceSignature", self.shared)

    def test_dwpose_waits_for_upgrade_model_download_then_retries_automatically(self):
        for marker in (
            "function waitForPoseModel(node, options)",
            "'/api/dwpose/status'",
            "response.status === 503",
            "完成后将自动提取骨架",
            "DWPOSE_MODEL_WAIT_TIMEOUT_MS",
            "const retryForm = new FormData()",
        ):
            self.assertIn(marker, self.shared)

    def test_dwpose_large_input_uses_returned_size_and_failed_input_does_not_retry_forever(self):
        for marker in (
            "X-DWPose-Width",
            "X-DWPose-Height",
            "node.poseFailedSignature = signature",
            "delete node.poseFailedSignature",
            "node.poseFailedSignature !== currentSignature",
        ):
            self.assertIn(marker, self.shared)

    def test_dwpose_export_creates_a_visible_connected_output_node_on_both_canvases(self):
        for marker in (
            'data-special-action="export-pose"',
            "options.createOutputNode(node, item)",
            "node.poseOutputNodeId",
        ):
            self.assertIn(marker, self.shared)
        for source, markers in (
            (self.classic, ("function createClassicPoseOutputNode(sourceNode, item)", "type:'output'", "poseReferenceSourceId:sourceNode.id", "createOutputNode:createClassicPoseOutputNode")),
            (self.smart, ("function createSmartPoseOutputNode(sourceNode, item)", "title:'骨架参考图'", "poseReferenceSourceId:sourceNode.id", "createOutputNode:createSmartPoseOutputNode")),
        ):
            for marker in markers:
                self.assertIn(marker, source)

    def test_pose_replicate_node_is_available_on_both_canvases_with_four_role_ports(self):
        for page in (self.classic_html, self.smart_html):
            self.assertIn("一键复刻", page)
            self.assertIn("/static/css/pose-replicate-node.css?v=2026.09.04.pose-replicate.6", page)
            self.assertIn("/static/js/canvas-special-nodes.js?v=2026.09.04.pose-replicate-top-ports.1", page)
            self.assertIn("feature=pose-replicate-v2.2", page)

        for marker in (
            "function addPoseReplicateNode(point)",
            "type:'poseReplicate'",
            "['pose-reference','动作参考']",
            "['target-image','目标图']",
            "['model-subject','模特主体']",
            "['scene','场景']",
            "poseReplicateBodyHtml(node, {providers:",
        ):
            self.assertIn(marker, self.classic)
        self.assertIn("if(from.type === 'poseReplicate') return to.type === 'output'", self.classic)
        self.assertIn("if(node.type === 'poseReplicate')", self.classic)

        for marker in (
            "function createPoseReplicateNode(point)",
            "specialType:'pose-replicate'",
            "['pose-reference','动作参考']",
            "['target-image','目标图']",
            "['model-subject','模特主体']",
            "['scene','场景']",
            "poseReplicateBodyHtml(node, {providers:",
        ):
            self.assertIn(marker, self.smart)

    def test_pose_replicate_connections_persist_the_selected_input_role(self):
        for marker in (
            "connections.push({id:uid('c'), from:fromId, to:toId, ...(inputRole ? {inputRole} : {})})",
            "portPoint(c.to, 'in', c.inputRole || '')",
            "canConnect(c.from, c.to, c.inputRole || '')",
            "canConnect(conn.from, conn.to, conn.inputRole || '')",
            "from:group.id, to:connection.to, ...(inputRole ? {inputRole} : {})",
        ):
            self.assertIn(marker, self.classic)

        for marker in (
            "const connection = {id:uid('c'), from:fromId, to:toId, kind, ...(inputRole ? {inputRole} : {})}",
            "connectInputNode(fromId, toId, inputRole)",
            "`${c.from}->${c.to}:${c.kind || 'flow'}:${c.inputRole || ''}`",
            ".filter(item => item.to === to.id && (item.kind || 'flow') === 'input')",
            "item.inputRole === 'pose-reference'",
            "item.inputRole === 'target-image'",
        ):
            self.assertIn(marker, self.smart)

        for marker in (
            ".port.in[data-input-role]",
            ".node-port.port-in[data-input-role]",
            ".poseReplicate-node",
            ".pose-replicate-node",
            ".smart-pose-replicate-node",
            ".pose-replicate-input-list",
            ".pose-replicate-input-row",
            "top: calc(69px + var(--pose-port-index) * 36px)",
        ):
            self.assertIn(marker, self.pose_replicate_styles)
        self.assertNotIn("--pose-port-top:${20 + index * 20}%", self.classic)
        self.assertNotIn("--pose-port-top:${20 + index * 20}%", self.smart)
        self.assertIn("poseReplicateInputRow(action, 'pose-reference', '动作参考'", self.shared)
        self.assertIn("poseReplicateInputRow(scene, 'scene', '场景'", self.shared)
        self.assertIn("type:'poseReplicate', x:p.x, y:p.y, w:720, h:820", self.classic)
        self.assertIn("specialType:'pose-replicate'", self.smart)
        self.assertIn("w:720, h:820", self.smart)

    def test_relight_compiles_mature_direction_temperature_and_consistency_controls(self):
        for marker in (
            "RELIGHT_DIRECTIONS",
            "camera-left key light",
            "relightTemperature",
            "relightIntensity",
            "relightSoftness",
            "relightMood",
            "严格保持人物/产品与构图不变",
            "function buildRelightPrompt(node)",
            "relightPreviewStatusText",
            "relight-preview-panel",
            "data-relight-status",
            "data-relight-source-label",
            "data-relight-output-label",
            "function bindRelight(root, node, options={})",
        ):
            self.assertIn(marker, self.shared)

    def test_relight_and_angle_inputs_fall_back_to_node_input_ids_when_connection_cache_is_stale(self):
        for marker in (
            "if(!orderedSources.length && !inputRole && Array.isArray(node?.inputNodeIds))",
        ):
            self.assertIn(marker, self.classic)
        for marker in (
            "const fallbackSource = [...node.inputNodeIds].reverse().map(id => nodes.find(item => item.id === id)).find(Boolean);",
            "if(Array.isArray(node?.inputNodeIds)){",
        ):
            self.assertIn(marker, self.smart)

    def test_angle_control_generates_a_real_novel_view_instead_of_2d_rotation(self):
        for marker in (
            "ANGLE_AZIMUTHS",
            "front-right quarter view",
            "angleElevation",
            "angleDistance",
            "angleLens",
            "angleSubject",
            "Never flip, mirror or rotate Image 1",
            "function buildAnglePrompt(node)",
            "function bindAngle(root, node, options={})",
        ):
            self.assertIn(marker, self.shared)

    def test_angle_prompt_uses_world_coordinates_and_chirality_instead_of_mirror_composition(self):
        for marker in (
            "CAMERA COORDINATE SYSTEM",
            "WORLD COORDINATE LOCK",
            "ANATOMICAL CHIRALITY LOCK",
            "OBJECT CHIRALITY LOCK",
            "SCENE TOPOLOGY LOCK",
            "MIRROR LOCK",
            "Never flip, mirror or rotate Image 1",
            "camera-right +X",
            "Each signed orbit is a new camera ray",
            "function signedAngleAzimuth(value)",
            "function angleOrbitInstruction(value)",
            "function angleParallaxInstruction(value)",
            "Preserve physical content, not Image 1 pixel positions",
            "A source-matching or near-copy view is invalid",
        ):
            self.assertIn(marker, self.shared)

        prompt_body = re.search(
            r"function buildAnglePrompt\(node\).*?\n\s*\}",
            self.shared,
            re.S,
        )
        self.assertIsNotNone(prompt_body)
        self.assertNotIn("窗户向", prompt_body.group(0))
        self.assertNotIn("画面左", prompt_body.group(0))

    def test_angle_preview_keeps_subject_centered_and_draws_camera_trajectory_with_back_occlusion(self):
        for marker in (
            'class="angle-camera-trajectory"',
            'data-angle-trajectory',
            'data-angle-sightline',
            'data-angle-depth',
            "const depth = Math.cos(radians)",
            "marker.classList.toggle('is-behind', behind)",
        ):
            self.assertIn(marker, self.shared)
        self.assertIn(".angle-world-3d{position:absolute;inset:0", self.angle_styles)
        self.assertIn("transform-origin:50% 50%", self.angle_styles)
        self.assertIn(".angle-subject-3d{transform:translate(-50%,-54%)", self.angle_styles)
        self.assertIn(".angle-camera-marker.is-behind{z-index:2", self.angle_styles)

    def test_paid_image_edits_only_run_from_explicit_buttons_and_keep_one_reference(self):
        self.assertIn("action !== `run-${prefix}`", self.shared)
        self.assertIn("options.generateImageEdit(node, editPrompt(node, prefix), source, prefix)", self.shared)
        self.assertIn("reference_images:[{url:source.url", self.classic)
        self.assertIn("runApiGeneration(prompt, [{...source, kind:'image'}]", self.smart)
        self.assertIn("clearOutputItem(node, options)", self.shared)

    def test_edit_nodes_expose_generation_controls_and_forward_them(self):
        for marker in (
            "function normalizeEditGeneration(node)",
            "data-edit-field=\"editResolution\"",
            "data-edit-field=\"editQuality\"",
            "data-edit-field=\"editRatio\"",
            "node.editResolution || '2k'",
            "node.editQuality || 'high'",
            "requestedRatio",
        ):
            self.assertIn(marker, self.shared + self.classic + self.smart)

    def test_special_edit_results_create_downstream_output_nodes(self):
        for marker in (
            "createEditOutputNode:createClassicSpecialOutputNode",
            "function createClassicSpecialOutputNode(sourceNode, item, kind)",
            "createEditOutputNode:createSmartSpecialOutputNode",
            "function createSmartSpecialOutputNode(sourceNode, item, kind)",
            "options.createEditOutputNode",
        ):
            self.assertIn(marker, self.classic + self.smart + self.shared)

    def test_angle_creates_recoverable_pending_output_before_remote_generation(self):
        for source, markers in (
            (self.classic, ("function createClassicSpecialPendingOutputNode", "specialPending:true", "createEditPendingOutputNode:createClassicSpecialPendingOutputNode")),
            (self.smart, ("function createSmartSpecialPendingOutputNode", "specialPending:true", "createEditPendingOutputNode:createSmartSpecialPendingOutputNode")),
        ):
            for marker in markers:
                self.assertIn(marker, source)
        self.assertIn("先创建可恢复的下游占位节点", self.shared)
        self.assertIn("await options.createEditPendingOutputNode(node, prefix)", self.shared)

    def test_angle_forwards_style_lock_and_color_calibration_metadata(self):
        for marker in (
            "STYLE CONSISTENCY LOCK",
            "COLOR MATCH CHECK",
            "operation:kind === 'angle' ? 'angle_change' : 'relight'",
            "style_reference_url:kind === 'angle' ? source.url : ''",
            "runSettings.operation = 'angle_change'",
            "runSettings.style_reference_url = source.url",
            "if(runSettings.style_reference_url) payload.style_reference_url = runSettings.style_reference_url",
        ):
            self.assertIn(marker, self.shared + self.classic + self.smart)

    def test_angle_subject_preview_is_not_rotated_with_camera(self):
        self.assertIn("if(world) world.style.transform = 'none'", self.shared)
        self.assertIn(".angle-world-3d{position:absolute;inset:0", self.angle_styles)
        self.assertIn("transform:none;transform-origin:50% 50%", self.angle_styles)
        self.assertIn(".angle-subject-3d{transform:translate(-50%,-54%) translateZ(32px)", self.angle_styles)

    def test_edit_preview_and_source_dimensions_stay_truthful(self):
        self.assertIn("updateRelightPreview(root, node, options, source)", self.shared)
        self.assertEqual(
            len(re.findall(r"function updateRelightPreview\s*\(", self.shared)),
            1,
            "灯光重塑预览必须只有一个负责同步图片/占位状态的实现",
        )
        self.assertIn("function updateRelightControls(root, node)", self.shared)
        self.assertIn("node.relightSourceUrl = file.url", self.shared)
        self.assertIn("data-relight-preview", self.shared)
        self.assertIn("image.dataset.originalSrc = originalUrl", self.shared)
        self.assertIn("image.dataset.previewFallback", self.shared)
        self.assertIn("nodeForControls[`${prefix}SourceWidth`] = uploaded.natural_w || 0", self.smart)
        self.assertIn("nodeForControls[`${prefix}SourceHeight`] = uploaded.natural_h || 0", self.smart)
        self.assertIn("w:460, h:660", self.classic)
        self.assertIn("w:460, h:660", self.smart)

    def test_classic_canvas_persists_connects_and_forwards_special_outputs(self):
        for marker in (
            "function addPanoramaNode(point)",
            "function addDWPoseNode(point)",
            "function addAngleNode(point)",
            "function bindClassicSpecialNode(el, node)",
            "['panorama','dwpose','director3d','poseReplicate','angle'].includes(node.type)",
            "function generateClassicSpecialEdit(node, prompt, source, kind)",
            "delete copy.panoramaGenerating",
            "delete copy.specialRunning",
            "indexClassicConnectionModel(connection)",
            "scheduleClassicRender();\n    scheduleSave();",
        ):
            self.assertIn(marker, self.classic)
        self.assertNotIn("function addRelightNode(point)", self.classic)
        self.assertRegex(
            self.classic,
            re.compile(r"specialTypes\.includes\(from\.type\).*?CANVAS_GENERATOR_TYPES\.includes\(to\.type\)", re.S),
        )

    def test_smart_canvas_persists_connects_and_forwards_special_outputs(self):
        for marker in (
            "specialType:'panorama'",
            "specialType:'dwpose'",
            "specialType:'angle'",
            "function bindSmartSpecialNode(el, node)",
            "function smartSpecialInputImage(node, inputRole='')",
            "function generateSmartSpecialEdit(node, prompt, source, kind)",
            "node.specialType === 'panorama'",
            "delete node.panoramaGenerating",
            "delete node.specialRunning",
            "function smartSpecialInputImage(node, inputRole='')",
            "if(source?.url) return {...source, kind:'image'}",
            "output.images = [{...item, kind:'image'}];\n    render();\n    scheduleSave();",
        ):
            self.assertIn(marker, self.smart)
        self.assertNotIn("specialType:'relight'", self.smart)
        self.assertIn("images = [item]", self.shared)
        self.assertIn("inputImagesFor(node)", self.smart)

    def test_special_node_controls_follow_canvas_theme_tokens(self):
        for marker in (
            "var(--text",
            "var(--line",
            "var(--card",
            "var(--soft",
            "var(--strong",
            ".smart-special-node",
            ".panorama-node",
            ".dwpose-node",
            ".relight-node",
            ".angle-node",
            ".angle-orbit",
            ".relight-direction-pad",
        ):
            self.assertIn(marker, self.styles)

    def test_pose_replicate_automatically_extracts_a_role_scoped_dwpose_skeleton(self):
        for marker in (
            "DEFAULT_POSE_REPLICATE_PROMPT",
            "function bindPoseReplicate(root, node, options={})",
            "poseReplicateInput(node, options, 'pose-reference')",
            "poseReplicateInput(node, options, 'target-image')",
            "poseInputRole:'pose-reference'",
            "setPoseOutput:(node, file)",
            "runPose(node, poseOptions, false)",
            "node.poseSkeletonUrl = file.url",
            "data-special-action=\"run-pose-replicate\"",
        ):
            self.assertIn(marker, self.shared)

        self.assertIn("function classicSpecialInputImage(node, inputRole='')", self.classic)
        self.assertIn("connection.inputRole === inputRole", self.classic)
        self.assertIn("function smartSpecialInputImage(node, inputRole='')", self.smart)
        self.assertIn("item.inputRole === inputRole", self.smart)

    def test_pose_replicate_cards_support_manual_upload_remove_and_connection_fallback(self):
        body = re.search(
            r"function poseReplicateBodyHtml\(node, options=\{\}\).*?(?=\n\s*const RELIGHT_DIRECTIONS)",
            self.shared,
            re.S,
        )
        self.assertIsNotNone(body)
        body_source = body.group(0)
        self.assertIn("动作参考", body_source)
        self.assertIn("目标图", body_source)
        self.assertIn("模特主体", body_source)
        self.assertIn("场景", body_source)
        self.assertIn("内部控制图", body_source)
        self.assertIn("poseReplicatePrompt", body_source)
        self.assertIn('type="file"', self.shared)
        self.assertIn("data-pose-replicate-upload-role", self.shared)
        self.assertIn("data-pose-replicate-remove-role", self.shared)
        self.assertIn("poseReplicateManualInputs", body_source)
        self.assertIn("请上传或连接动作参考和目标图", body_source)
        self.assertIn("function poseReplicateInput(node, options, role)", self.shared)
        self.assertIn("return poseReplicateManualInput(node, role) || options.getInputImage?.(node, role) || null", self.shared)
        self.assertIn("const fallback = options.getInputImage?.(node, role) || null", self.shared)
        self.assertIn("恢复使用连线输入", self.shared)
        self.assertIn("card.addEventListener('mousedown', event => event.stopPropagation())", self.shared)
        self.assertIn("const button = event.target.closest('[data-pose-replicate-remove-role]')", self.shared)
        self.assertIn("}, true);", self.shared)
        self.assertIn("请点击对应缩略图卡片上传", self.smart)
        self.assertIn(".pose-replicate-inputs .pose-replicate-input-card { height: 118px; min-height: 118px; }", self.pose_replicate_styles)

    def test_pose_replicate_creates_one_recoverable_output_per_click_on_both_canvases(self):
        classic_run = re.search(
            r"async function generateClassicPoseReplicate\(.*?(?=\nfunction createClassicPoseOutputNode)",
            self.classic,
            re.S,
        )
        self.assertIsNotNone(classic_run)
        classic_source = classic_run.group(0)
        self.assertIn("const refs = [inputs.action, inputs.control, inputs.target, inputs.modelSubject, inputs.scene]", classic_source)
        self.assertIn("type:'output'", classic_source)
        self.assertIn("canvasTaskType:'online-image'", classic_source)
        self.assertIn("nodes.push(output)", classic_source)
        self.assertIn("'/api/canvas/pose-replicate-tasks'", classic_source)
        self.assertLess(classic_source.index("nodes.push(output)"), classic_source.index("'/api/canvas/pose-replicate-tasks'"))
        self.assertIn("pollCanvasImageTask(task.task_id)", classic_source)

        smart_run = re.search(
            r"async function generateSmartPoseReplicate\(.*?(?=\nfunction createSmartPoseOutputNode)",
            self.smart,
            re.S,
        )
        self.assertIsNotNone(smart_run)
        smart_source = smart_run.group(0)
        self.assertIn("const refs = [inputs.action, inputs.control, inputs.target, inputs.modelSubject, inputs.scene]", smart_source)
        self.assertIn("createPendingOutputFromSource(node, 1", smart_source)
        self.assertIn("'/api/canvas/pose-replicate-tasks'", smart_source)
        self.assertLess(smart_source.index("createPendingOutputFromSource(node, 1"), smart_source.index("'/api/canvas/pose-replicate-tasks'"))
        self.assertIn("initializeSmartGenerationSlots", smart_source)
        self.assertIn("resumeSmartPendingNode(output", smart_source)

    def test_pose_replicate_button_stays_clickable_while_previous_runs_continue(self):
        for marker in (
            "node.poseReplicateActiveRuns = Math.max(0, Number(node.poseReplicateActiveRuns) || 0) + 1",
            "Promise.resolve(options.generatePoseReplicate",
            "每次点击都会创建一个独立输出节点",
            "个复刻任务正在并发生成",
        ):
            self.assertIn(marker, self.shared)

        run_button = re.search(
            r'<button type="button" class="special-primary" data-special-action="run-pose-replicate"(?P<attrs>.*?)>',
            self.shared,
            re.S,
        )
        self.assertIsNotNone(run_button)
        self.assertIn("ready", run_button.group("attrs"))
        self.assertNotIn("poseReplicateActiveRuns", run_button.group("attrs"))
        self.assertIn("delete copy.poseReplicateActiveRuns", self.classic)
        self.assertIn("delete node.poseReplicateActiveRuns", self.smart)

    def test_pose_replicate_depth_mode_and_component_progress_are_shared(self):
        for marker in (
            "PERSON_DEPTH_ACTIVE_STATES",
            "'/api/person-depth/component/status'",
            "'/api/person-depth/component/install'",
            "'/api/person-depth/estimate'",
            "poseDepthSourceSignature",
            "poseDepthUrl",
            "data-person-depth-state",
            "role=\"progressbar\"",
            "downloaded_bytes",
            "source_label",
            "openPersonDepthDialog(options, false)",
            "data-person-depth-dialog-confirm",
            "SHA-256、原子安装和小图 smoke 验证",
        ):
            self.assertIn(marker, self.shared)

    def test_pose_replicate_new_defaults_and_legacy_mode_are_explicit(self):
        for source in (self.classic, self.smart):
            for marker in (
                "poseReplicateSchemaVersion:2",
                "poseReplicateMode:'depth'",
                "poseReplicateProvider:'shiying'",
                "poseReplicateModel:'gemini-3-pro-image-preview'",
                "poseReplicateRatio:'16:9'",
                "poseReplicateResolution:'2k'",
            ):
                self.assertIn(marker, source)
        self.assertIn("if(!modern)", self.shared)
        self.assertIn("node.poseReplicateMode = 'skeleton'", self.shared)
        self.assertIn("if(field === 'poseReplicateMode') node.poseReplicateSchemaVersion = 2", self.shared)

    def test_pose_replicate_uses_server_compiler_without_generic_second_optimization(self):
        for source, function_name, end_name in (
            (self.classic, "generateClassicPoseReplicate", "createClassicPoseOutputNode"),
            (self.smart, "generateSmartPoseReplicate", "createSmartPoseOutputNode"),
        ):
            body = re.search(
                rf"async function {function_name}\(.*?(?=\nfunction {end_name})",
                source,
                re.S,
            ).group(0)
            self.assertIn("'/api/canvas/pose-replicate-tasks'", body)
            self.assertIn("template_id:'pose-replicate.v2.2'", body)
            self.assertNotIn("auto_optimize_prompt:true", body)


if __name__ == "__main__":
    unittest.main()
