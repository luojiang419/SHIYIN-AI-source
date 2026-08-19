import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "app-settings.html").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "static" / "js" / "app-settings.js").read_text(encoding="utf-8")
STYLES = (ROOT / "static" / "css" / "app-settings.css").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


class TopazVideoSettingsTests(unittest.TestCase):
    def test_settings_page_exposes_installation_and_health_controls(self):
        for element_id in (
            "topazInstallDir", "chooseTopazInstall", "resetTopazInstall",
            "checkTopazInstall", "topazReadyState", "topazModelCount",
            "topazVersion", "topazSignature",
        ):
            self.assertIn(f'id="{element_id}"', HTML)
        self.assertIn(".app-settings-topaz-grid", STYLES)

    def test_settings_frontend_saves_and_rechecks_topaz_directory(self):
        self.assertIn("topaz_video_install_dir:selection.path", JAVASCRIPT)
        self.assertIn("topaz_video_install_dir:''", JAVASCRIPT)
        self.assertIn("/api/app-settings/select-topaz-video-directory", JAVASCRIPT)
        self.assertIn("/api/topaz-video/capabilities", JAVASCRIPT)
        self.assertIn("data?.signature_valid", JAVASCRIPT)

    def test_backend_persists_only_valid_install_directories(self):
        self.assertIn("topaz_video_install_dir: Optional[str] = None", MAIN)
        self.assertIn('("ffmpeg.exe", "ffprobe.exe")', MAIN)
        self.assertIn('@app.post("/api/app-settings/select-topaz-video-directory")', MAIN)
        self.assertIn('config.get("topaz_video_install_dir")', MAIN)


if __name__ == "__main__":
    unittest.main()
