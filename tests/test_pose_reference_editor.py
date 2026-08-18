from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class PoseReferenceEditorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor = (STATIC / "js" / "pose-reference-editor.js").read_text(encoding="utf-8")
        cls.shared = (STATIC / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
        cls.classic = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.styles = (STATIC / "css" / "pose-reference-editor.css").read_text(encoding="utf-8")

    def test_pages_load_editor_before_shared_node_adapter(self):
        for name in ("canvas.html", "smart-canvas.html"):
            page = (STATIC / name).read_text(encoding="utf-8")
            self.assertIn("/static/css/pose-reference-editor.css", page)
            self.assertIn("/static/js/pose-reference-editor.js", page)
            self.assertLess(page.index("pose-reference-editor.js"), page.index("canvas-special-nodes.js"))

    def test_editor_contains_pose_controls_and_webgl_cleanup(self):
        required = (
            "const BONES = [",
            "const PRESETS = [",
            "mirrorRotations",
            "data-pose-axis=",
            "data-pose-setting=\"aspect\"",
            "new THREE.WebGLRenderer",
            "new THREE.Raycaster",
            "renderer.domElement.toBlob",
            "renderer.forceContextLoss",
            "window.PoseReferenceEditor",
        )
        for marker in required:
            self.assertIn(marker, self.editor)
        bones_section = self.editor.split("const PRESETS = [", 1)[0]
        presets_section = self.editor.split("const PRESETS = [", 1)[1].split("function clamp", 1)[0]
        self.assertGreaterEqual(bones_section.count("{name:"), 22)
        self.assertGreaterEqual(presets_section.count("{id:"), 25)

    def test_editor_css_is_modal_and_node_scoped(self):
        for marker in (
            ".pose-ref-editor-overlay",
            ".pose-ref-editor-layout",
            ".pose-ref-stage-shell",
            ".pose-reference-special",
            "body.pose-ref-editor-open",
        ):
            self.assertIn(marker, self.styles)

    def test_empty_pose_node_keeps_editor_button_above_placeholder(self):
        self.assertIn(".pose-reference-preview>.pose-reference-edit{z-index:3}", self.styles)
        for name in ("canvas.html", "smart-canvas.html"):
            page = (STATIC / name).read_text(encoding="utf-8")
            self.assertIn("pose-reference-editor.css?v=2026.08.18.pose-reference.4", page)

    def test_editor_resolves_all_workspace_themes_and_updates_live(self):
        for marker in (
            "const RESOLVED_THEMES = ['light','dark','pure-white']",
            "function resolveTheme(value)",
            "requested === 'system'",
            "window.StudioTheme?.get?.()",
            "overlay.dataset.theme = theme",
            "editor.dataset.theme = theme",
            "window.addEventListener('studio-theme-change', onThemeChange)",
            "window.removeEventListener('studio-theme-change', onThemeChange)",
        ):
            self.assertIn(marker, self.editor)
        self.assertIn("theme:window.StudioTheme?.get?.()", self.shared)

    def test_editor_and_node_colors_use_unified_neutral_tokens(self):
        for marker in (
            '.pose-ref-editor-overlay[data-theme="light"]',
            '.pose-ref-editor-overlay[data-theme="dark"]',
            '.pose-ref-editor-overlay[data-theme="pure-white"]',
            '--pr-bg:var(--studio-bg',
            '--pr-accent:var(--studio-accent',
            '--pr-success:var(--studio-success',
            'var(--strong,var(--studio-accent',
        ):
            self.assertIn(marker, self.styles)
        forbidden = (
            '#7c6df2', '#a06cf2', '#6860df', '#9a62e4',
            'rgba(124,109,242', 'rgba(117,94,237', '#11131f',
        )
        for color in forbidden:
            self.assertNotIn(color, self.styles.lower())

    def test_shared_adapter_persists_and_uploads_export(self):
        for marker in (
            "function poseReferenceBodyHtml(node)",
            "function bindPoseReference(root, node, options={})",
            "node.poseEditorState = state",
            "const file = await uploadBlob(blob",
            "setOutputItem(node, file, options)",
            "bindPoseReference",
        ):
            self.assertIn(marker, self.shared)

    def test_classic_canvas_exposes_output_only_pose_node(self):
        for marker in (
            "function addPoseReferenceNode(point)",
            "type:'poseReference'",
            "api.bindPoseReference?.(el, node, options)",
            "poseReferenceBodyHtml?.(node)",
            "'3D 姿势参考'",
            "if(from.type === 'poseReference')",
        ):
            self.assertIn(marker, self.classic)
        can_input_line = next(line for line in self.classic.splitlines() if "const canInput =" in line)
        can_output_line = next(line for line in self.classic.splitlines() if "const canOutput =" in line)
        self.assertNotIn("poseReference", can_input_line)
        self.assertIn("poseReference", can_output_line)

    def test_smart_canvas_exposes_output_only_pose_node(self):
        for marker in (
            "function createPoseReferenceNode(point)",
            "specialType:'pose-reference'",
            "api.bindPoseReference?.(el, node, options)",
            "poseReferenceBodyHtml?.(node)",
            "node.specialType === 'pose-reference' ? ''",
            "return createPoseReferenceNode(p)",
        ):
            self.assertIn(marker, self.smart)


if __name__ == "__main__":
    unittest.main()
