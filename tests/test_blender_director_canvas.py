import unittest
from pathlib import Path


class BlenderDirectorCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.css = (root / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.unified_css = (root / "static" / "css" / "studio-unified.css").read_text(encoding="utf-8")
        cls.main = (root / "main.py").read_text(encoding="utf-8")
        cls.addon = (root / "tools" / "blender-addon" / "shiyin_blender_bridge" / "__init__.py").read_text(encoding="utf-8")
        cls.installer = (root / "tools" / "build-installer.ps1").read_text(encoding="utf-8")

    def test_canvas_exposes_director_node_and_render_controls(self):
        self.assertIn("id:'blenderDirector'", self.javascript)
        self.assertIn("addBlenderDirectorNode()", self.javascript)
        self.assertIn("menuAdd('blenderDirector')", self.html)
        self.assertIn("function renderBlenderDirectorBody(node)", self.javascript)
        self.assertIn("function syncBlenderCamera(nodeId)", self.javascript)
        self.assertIn("function runBlenderDirectorNode(nodeId, kind='image')", self.javascript)
        self.assertIn(".blender-director-body", self.css)

    def test_rendered_images_and_videos_are_downstream_media(self):
        self.assertIn("...['generator','video','rh','blenderDirector','director3d']", self.javascript)
        self.assertIn("'batchGenerator'", self.javascript)
        self.assertIn("mergeGeneratedOutputs(node, [item], true)", self.javascript)
        self.assertIn("appendOutputImagesWithoutDuplicates(out, [item])", self.javascript)

    def test_rendered_video_can_be_dragged_from_output_back_to_canvas(self):
        self.assertIn("pose-replicate.5", self.html)
        self.assertIn("application/x-canvas-output-media", self.javascript)
        self.assertIn("function setCanvasOutputDragData(event, url, kind)", self.javascript)
        self.assertIn("function bindCanvasOutputMediaDrag(element, url, kind)", self.javascript)
        self.assertIn("if(outputWrap) bindCanvasOutputMediaDrag(video", self.javascript)
        self.assertIn("function outputMediaDragPayload(dataTransfer)", self.javascript)
        self.assertIn("function hasOutputMediaDrag(dataTransfer)", self.javascript)
        self.assertIn("const mediaKind = mediaKindForRef({url:mediaUrl})", self.javascript)
        self.assertIn("createMediaCardFromOutput(outputMediaDragPayload(e.dataTransfer)", self.javascript)
        self.assertIn("mediaKind:kind", self.javascript)

    def test_camera_settings_are_collapsed_by_default_and_remember_toggle(self):
        self.assertIn("cameraSettingsExpanded:false", self.javascript)
        self.assertIn("<details class=\"blender-camera-settings\" ${node.cameraSettingsExpanded ? 'open' : ''}>", self.javascript)
        self.assertIn("node.cameraSettingsExpanded = event.currentTarget.open", self.javascript)
        self.assertIn(".blender-camera-settings, .ltx-director-timeline-host", self.javascript)
        self.assertIn(".blender-camera-settings[open] summary::after", self.css)

    def test_backend_has_auto_connect_camera_render_and_addon_routes(self):
        for route in ("/api/blender/addon", "/api/blender/status", "/api/blender/connect", "/api/blender/camera", "/api/blender/render"):
            self.assertIn(route, self.main)
        self.assertNotIn('@app.post("/api/blender/pair")', self.main)
        self.assertIn('register_internal_media_object(url, "output", kind, "blender-render")', self.main)

    def test_addon_is_loopback_only_and_has_no_arbitrary_execution_command(self):
        self.assertIn('server.bind(("127.0.0.1", self.port))', self.addon)
        self.assertIn('ALLOWED_ACTIONS = {"ping", "authenticate", "scene_state", "set_camera", "render_still", "render_animation"}', self.addon)
        self.assertIn('hmac.compare_digest(shared_secret, self.shared_secret)', self.addon)
        self.assertNotIn("exec(", self.addon)
        self.assertNotIn("eval(", self.addon)

    def test_canvas_uses_one_click_auto_connect_without_pairing_code(self):
        self.assertIn("function connectBlenderDirector(nodeId)", self.javascript)
        self.assertIn("/api/blender/connect", self.javascript)
        self.assertIn("启动 / 连接 Blender", self.javascript)
        self.assertIn("if(!node._blenderStatusRequested)", self.javascript)
        self.assertIn("delete copy._blenderStatusRequested", self.javascript)
        self.assertIn("delete copy._blenderState", self.javascript)
        self.assertNotIn("data-blender-pair", self.javascript)
        self.assertNotIn("6 位配对码", self.javascript)
        self.assertNotIn("pairBlenderDirector", self.javascript)
        self.assertNotIn("shared_secret", self.javascript)

    def test_blender_blocks_use_node_dark_gray_background(self):
        self.assertIn(".blender-connection {", self.css)
        self.assertIn("background:var(--card-solid)", self.css)
        self.assertIn(".blender-camera-settings", self.css)
        self.assertNotIn(".blender-camera-settings { overflow:hidden; border:1px solid var(--line); border-radius:11px; background:var(--soft);", self.css)
        self.assertIn("#shell .blender-connection,", self.unified_css)
        self.assertIn("#shell .blender-camera-settings", self.unified_css)
        self.assertIn("background:color-mix(in srgb,var(--studio-panel) 96%,transparent) !important;", self.unified_css)

    def test_addon_panel_reports_auto_connect_without_pairing_code(self):
        self.assertIn("已启用自动连接", self.addon)
        self.assertNotIn("pairing_code", self.addon)
        self.assertNotIn("regenerate_code", self.addon)
        self.assertNotIn("配对码", self.addon)

    def test_installer_packages_blender_addon(self):
        self.assertIn("tools\\blender-addon", self.installer)
        self.assertIn("connectors 'blender'", self.installer)

    def test_addon_register_is_compatible_with_blender_restricted_context(self):
        register_body = self.addon.split("def register():", 1)[1].split("def unregister():", 1)[0]
        self.assertIn("_SERVER.start(9876)", register_body)
        self.assertNotIn("bpy.context.scene", register_body)

    def test_addon_uses_blender_52_video_media_type_with_legacy_fallback(self):
        self.assertIn('hasattr(scene.render.image_settings, "media_type")', self.addon)
        self.assertIn('scene.render.image_settings.media_type = "VIDEO"', self.addon)
        self.assertIn('scene.render.image_settings.file_format = "FFMPEG"', self.addon)


if __name__ == "__main__":
    unittest.main()
