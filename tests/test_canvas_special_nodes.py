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
        cls.classic = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.classic_html = (STATIC / "canvas.html").read_text(encoding="utf-8")
        cls.smart_html = (STATIC / "smart-canvas.html").read_text(encoding="utf-8")

    def test_both_canvas_pages_load_shared_assets_and_offer_released_special_nodes(self):
        for page in (self.classic_html, self.smart_html):
            self.assertIn("/static/css/canvas-special-nodes.css", page)
            self.assertIn("/static/js/canvas-special-nodes.js", page)
            self.assertIn("720°取景器", page)
            self.assertIn("动作提取", page)
            self.assertIn("灯光重塑", page)
            self.assertIn("special-nodes.4", page)

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
            "function bindRelight(root, node, options={})",
        ):
            self.assertIn(marker, self.shared)

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

    def test_paid_image_edits_only_run_from_explicit_buttons_and_keep_one_reference(self):
        self.assertIn("action !== `run-${prefix}`", self.shared)
        self.assertIn("options.generateImageEdit(node, editPrompt(node, prefix), source, prefix)", self.shared)
        self.assertIn("reference_images:[{url:source.url", self.classic)
        self.assertIn("runApiGeneration(prompt, [{...source, kind:'image'}]", self.smart)
        self.assertIn("clearOutputItem(node, options)", self.shared)

    def test_edit_preview_and_source_dimensions_stay_truthful(self):
        self.assertIn("relightOverlay.hidden = Boolean(output?.url)", self.shared)
        self.assertIn("nodeForControls[`${prefix}SourceWidth`] = uploaded.natural_w || 0", self.smart)
        self.assertIn("nodeForControls[`${prefix}SourceHeight`] = uploaded.natural_h || 0", self.smart)
        self.assertIn("w:460, h:660", self.classic)
        self.assertIn("w:460, h:660", self.smart)

    def test_classic_canvas_persists_connects_and_forwards_special_outputs(self):
        for marker in (
            "function addPanoramaNode(point)",
            "function addDWPoseNode(point)",
            "function addRelightNode(point)",
            "function addAngleNode(point)",
            "function bindClassicSpecialNode(el, node)",
            "['panorama','dwpose','relight','angle'].includes(node.type)",
            "function generateClassicSpecialEdit(node, prompt, source, kind)",
            "delete copy.panoramaGenerating",
            "delete copy.specialRunning",
        ):
            self.assertIn(marker, self.classic)
        self.assertRegex(
            self.classic,
            re.compile(r"specialTypes\.includes\(from\.type\).*?CANVAS_GENERATOR_TYPES\.includes\(to\.type\)", re.S),
        )

    def test_smart_canvas_persists_connects_and_forwards_special_outputs(self):
        for marker in (
            "specialType:'panorama'",
            "specialType:'dwpose'",
            "specialType:'relight'",
            "specialType:'angle'",
            "function bindSmartSpecialNode(el, node)",
            "function smartSpecialInputImage(node)",
            "function generateSmartSpecialEdit(node, prompt, source, kind)",
            "node.specialType === 'panorama'",
            "delete node.panoramaGenerating",
            "delete node.specialRunning",
        ):
            self.assertIn(marker, self.smart)
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


if __name__ == "__main__":
    unittest.main()
