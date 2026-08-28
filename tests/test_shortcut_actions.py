from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent
SHORTCUTS = (ROOT / "static" / "js" / "shortcut-actions.js").read_text(encoding="utf-8")
SETTINGS = (ROOT / "static" / "app-settings.html").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "static" / "js" / "app-settings.js").read_text(encoding="utf-8")
SETTINGS_CSS = (ROOT / "static" / "css" / "app-settings.css").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CLASSIC_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CLASSIC_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
CANVAS_LIST_JS = (ROOT / "static" / "js" / "canvas-list.js").read_text(encoding="utf-8")


class ShortcutActionRegistryTests(unittest.TestCase):
    def test_action_ids_are_unique_and_cover_every_canvas_node_type(self):
        action_ids = re.findall(r"\{id:'([^']+)'", SHORTCUTS)
        self.assertEqual(len(action_ids), len(set(action_ids)))
        self.assertGreaterEqual(len(action_ids), 60)
        for action_id in (
            "create.image", "create.group", "create.prompt", "create.h3Video",
            "create.panorama", "create.dwpose", "create.poseReplicate",
            "create.relight", "create.multiView", "create.batch",
        ):
            self.assertIn(action_id, action_ids)

    def test_registry_exposes_normalization_conflicts_and_event_resolution(self):
        for symbol in ("canonicalize", "fromEvent", "validate", "conflicts", "findAction", "resolvedBindings"):
            self.assertIn(symbol, SHORTCUTS)

    def test_settings_page_will_load_shared_registry(self):
        self.assertIn('/static/js/shortcut-actions.js', SETTINGS)
        self.assertIn('id="shortcutSearch"', SETTINGS)
        self.assertIn('id="shortcutCategory"', SETTINGS)
        self.assertIn('id="resetAllShortcuts"', SETTINGS)

    def test_settings_ui_supports_record_clear_reset_conflict_and_broadcast(self):
        for symbol in (
            "setShortcutBinding", "data-shortcut-record", "data-shortcut-clear", "data-shortcut-reset",
            "ShortcutActions.conflicts", "shortcut_bindings:shortcutOverrides", "BroadcastChannel",
        ):
            self.assertIn(symbol, SETTINGS_JS)
        self.assertIn(".app-settings-shortcut-row", SETTINGS_CSS)
        self.assertIn(".app-settings-shortcut-binding.recording", SETTINGS_CSS)

    def test_smart_canvas_loads_registry_and_replaces_hardcoded_dispatch(self):
        self.assertIn('/static/js/shortcut-actions.js', SMART_HTML)
        self.assertIn('id="smartShortcutList"', SMART_HTML)
        for symbol in (
            "loadSmartShortcutSettings", "runSmartCanvasShortcutAction", "runSmartEditorShortcutAction",
            "ShortcutActions.findAction", "shortcut-bindings:changed", "performRedo",
        ):
            self.assertIn(symbol, SMART_JS)
        self.assertNotIn("if((e.ctrlKey || e.metaKey) && key === 'g'", SMART_JS)

    def test_every_registered_node_creation_action_is_dispatched(self):
        for action_id in (
            "create.image", "create.group", "create.prompt", "create.h3Video",
            "create.panorama", "create.dwpose", "create.poseReplicate",
            "create.relight", "create.multiView", "create.batch",
        ):
            self.assertIn(f"'{action_id}'", SMART_JS)

    def test_classic_canvas_uses_same_saved_shortcut_registry(self):
        self.assertIn('/static/js/shortcut-actions.js', CLASSIC_HTML)
        self.assertIn('id="classicShortcutList"', CLASSIC_HTML)
        for symbol in (
            "loadClassicShortcutSettings", "applyClassicShortcutOverrides",
            "runClassicCanvasShortcutAction", "runClassicEditorShortcutAction",
            "ShortcutActions.findAction", "shortcut-bindings:changed", "performRedo",
        ):
            self.assertIn(symbol, CLASSIC_JS)

    def test_classic_canvas_no_longer_dispatches_fixed_default_bindings(self):
        self.assertNotIn("if((e.ctrlKey || e.metaKey) && key === 'g'", CLASSIC_JS)
        self.assertNotIn("if(!e.ctrlKey && !e.metaKey && !e.altKey && key === 'z'", CLASSIC_JS)
        self.assertIn("window.addEventListener('keydown', handleClassicShortcutKeyDown)", CLASSIC_JS)

    def test_classic_canvas_dispatches_all_registered_creation_actions(self):
        for action_id in (
            "create.image", "create.group", "create.prompt", "create.h3Video",
            "create.panorama", "create.dwpose", "create.poseReplicate",
            "create.relight", "create.multiView", "create.batch",
        ):
            self.assertIn(f"'{action_id}'", CLASSIC_JS)

    def test_active_canvas_frames_bridge_shortcuts_from_same_origin_shell(self):
        for source, prefix in ((CLASSIC_JS, "Classic"), (SMART_JS, "Smart")):
            parent_window = f"{prefix.lower()}ParentShortcutWindow"
            self.assertIn(f"sync{prefix}ParentShortcutListeners", source)
            self.assertIn(f"detach{prefix}ParentShortcutListeners", source)
            self.assertIn("window.parent.location.origin === location.origin", source)
            self.assertIn(f"host.addEventListener('keydown', handle{prefix}ShortcutKeyDown)", source)
            self.assertIn(f"{parent_window}.removeEventListener('keydown', handle{prefix}ShortcutKeyDown)", source)

    def test_shell_focuses_active_frame_and_forwards_shortcut_updates(self):
        self.assertIn("function focusStudioFrame", INDEX_HTML)
        self.assertIn("iframe.contentWindow?.focus", INDEX_HTML)
        self.assertIn("function forwardShortcutSettingsChange", INDEX_HTML)
        self.assertIn("data.type !== 'shortcut-bindings:changed'", INDEX_HTML)
        self.assertIn("new BroadcastChannel('shiyin-shortcuts')", INDEX_HTML)

    def test_canvas_navigation_uses_shortcut_runtime_cache_revision(self):
        self.assertIn("shortcuts-runtime.2", INDEX_HTML)
        self.assertIn("shortcuts-runtime.2", CANVAS_LIST_JS)
        self.assertIn("shortcuts-runtime.2", SMART_HTML)
        self.assertIn("shortcuts-runtime.2", CLASSIC_HTML)


if __name__ == "__main__":
    unittest.main()
