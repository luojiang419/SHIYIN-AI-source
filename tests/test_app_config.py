import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from canvas_core.app_config import read_app_config, update_app_settings, update_close_behavior
from canvas_core.generated_output import export_generated_files


class AppConfigTests(unittest.TestCase):
    def test_missing_config_asks_for_close_behavior_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = read_app_config(Path(tmp))
            self.assertEqual(settings["close_behavior"], "ask_on_close")
            self.assertEqual(settings["generated_output_dir"], "")
            self.assertEqual(settings["topaz_video_install_dir"], "")
            self.assertEqual(settings["shortcut_bindings"], {})

    def test_close_behavior_update_preserves_runtime_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            config_path = data_root / "config" / "app.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps({"host": "127.0.0.1", "port": 3456}), encoding="utf-8")
            saved = update_close_behavior(data_root, "exit")
            self.assertEqual(saved["close_behavior"], "exit")
            self.assertEqual(saved["host"], "127.0.0.1")
            self.assertEqual(saved["port"], 3456)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), saved)

    def test_close_behavior_can_be_saved_as_tray_after_first_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = update_close_behavior(Path(tmp), "minimize_to_tray")
            self.assertEqual(saved["close_behavior"], "minimize_to_tray")

    def test_invalid_close_behavior_is_rejected_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            config_path = data_root / "config" / "app.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('{"close_behavior":"exit"}\n', encoding="utf-8")
            before = config_path.read_bytes()
            with self.assertRaises(ValueError):
                update_close_behavior(data_root, "ask")
            self.assertEqual(config_path.read_bytes(), before)

    def test_generated_output_directory_update_preserves_close_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            custom = data_root / "用户图片"
            saved = update_app_settings(data_root, close_behavior="exit", generated_output_dir=str(custom))
            self.assertEqual(saved["close_behavior"], "exit")
            self.assertEqual(saved["generated_output_dir"], str(custom))
            reset = update_app_settings(data_root, generated_output_dir="")
            self.assertEqual(reset["close_behavior"], "exit")
            self.assertEqual(reset["generated_output_dir"], "")

    def test_generated_output_directory_rejects_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                update_app_settings(Path(tmp), generated_output_dir="relative/output")

    def test_shortcut_bindings_are_persisted_and_can_disable_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = update_app_settings(
                Path(tmp),
                shortcut_bindings={"canvas.undo": "Alt+Z", "canvas.toggleAssets": ""},
            )
            self.assertEqual(saved["shortcut_bindings"]["canvas.undo"], "Alt+Z")
            self.assertEqual(saved["shortcut_bindings"]["canvas.toggleAssets"], "")
            self.assertEqual(read_app_config(Path(tmp))["shortcut_bindings"], saved["shortcut_bindings"])

    def test_shortcut_bindings_reject_invalid_action_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "动作标识"):
                update_app_settings(Path(tmp), shortcut_bindings={"bad action": "Ctrl+K"})

    def test_topaz_install_directory_can_be_saved_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            install_dir = data_root / "Topaz Video AI"
            saved = update_app_settings(data_root, topaz_video_install_dir=str(install_dir))
            self.assertEqual(saved["topaz_video_install_dir"], str(install_dir))
            reset = update_app_settings(data_root, topaz_video_install_dir="")
            self.assertEqual(reset["topaz_video_install_dir"], "")

    def test_topaz_install_directory_rejects_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                update_app_settings(Path(tmp), topaz_video_install_dir="relative/topaz")

    def test_generated_files_use_persistent_sequence_and_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_a = root / "a.png"
            source_b = root / "b.webp"
            source_a.write_bytes(b"A")
            source_b.write_bytes(b"B")
            output = root / "output"
            output.mkdir()
            (output / "SHIYIN-000004-20260722.png").write_bytes(b"old")
            exported = export_generated_files(
                [source_a, source_b],
                output,
                generated_at=datetime(2026, 7, 23, 10, 30),
            )
            self.assertEqual([item["name"] for item in exported], [
                "SHIYIN-000005-20260723.png",
                "SHIYIN-000006-20260723.webp",
            ])
            self.assertEqual((output / exported[0]["name"]).read_bytes(), b"A")
            self.assertEqual((output / exported[1]["name"]).read_bytes(), b"B")


if __name__ == "__main__":
    unittest.main()
