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


class ShortcutActionRegistryTests(unittest.TestCase):
    def test_action_ids_are_unique_and_cover_every_canvas_node_type(self):
        action_ids = re.findall(r"\{id:'([^']+)'", SHORTCUTS)
        self.assertEqual(len(action_ids), len(set(action_ids)))
        self.assertGreaterEqual(len(action_ids), 60)
        for action_id in (
            "create.image", "create.group", "create.prompt", "create.loop", "create.h3Video",
            "create.panorama", "create.poseReference", "create.dwpose", "create.poseReplicate",
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
            "create.image", "create.group", "create.prompt", "create.loop", "create.h3Video",
            "create.panorama", "create.poseReference", "create.dwpose", "create.poseReplicate",
            "create.relight", "create.multiView", "create.batch",
        ):
            self.assertIn(f"'{action_id}'", SMART_JS)


if __name__ == "__main__":
    unittest.main()
