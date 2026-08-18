import re
import unittest
from pathlib import Path


INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"
RUNTIME_SYNC = Path(__file__).resolve().parent.parent / "static" / "js" / "runtime-sync.js"
TAURI_CONFIG = Path(__file__).resolve().parent.parent / "src-tauri" / "tauri.conf.json"
TAURI_HOST = Path(__file__).resolve().parent.parent / "src-tauri" / "src" / "lib.rs"
APP_SETTINGS_HTML = Path(__file__).resolve().parent.parent / "static" / "app-settings.html"
APP_SETTINGS_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "app-settings.js"


class ShellDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX.read_text(encoding="utf-8")

    def test_author_and_social_block_is_removed(self):
        for marker in ("wuli大雄", "author-box", "author-content-wrap", "social-icon-lite"):
            self.assertNotIn(marker, self.source)

    def test_ecommerce_is_default_and_online_generation_page_is_removed(self):
        self.assertIn("const DEFAULT_PAGE_ID = 'ecommerce';", self.source)
        self.assertRegex(self.source, r'id="frame-ecommerce"[^>]*class="active"')
        self.assertNotIn('frame-online', self.source)
        self.assertNotIn('nav.online', self.source)
        self.assertFalse((INDEX.parent / "online.html").exists())
        self.assertNotIn('id="frame-zimage"', self.source)

    def test_sidebar_uses_persisted_manual_state_only(self):
        self.assertIn("studio_sidebar_manual_mode_v1", self.source)
        self.assertIn(".sidebar:not(.is-pinned):hover", self.source)
        self.assertNotIn("is-collapsing", self.source)
        self.assertRegex(
            self.source,
            re.compile(r"function restoreSidebarPinned\(\).*?SIDEBAR_PINNED_KEY\) !== '0'", re.S),
        )

    def test_shell_matches_spatial_sidebar_and_stage_geometry(self):
        self.assertIn("width: 174px;", self.source)
        self.assertIn("margin: 16px 42px 26px 16px;", self.source)
        self.assertIn("border-radius: 30px;", self.source)
        self.assertIn("content: \"SHIYIN AI\";", self.source)
        self.assertIn("--accent: #3a3a39;", self.source)

    def test_collapsed_sidebar_controls_fit_and_dark_hover_is_item_scoped(self):
        rules = re.findall(r"([^{}]+)\{([^{}]*)\}", self.source)

        def declared_widths(selector):
            widths = []
            for selectors, declarations in rules:
                if selector not in selectors:
                    continue
                widths.extend(
                    int(value)
                    for value in re.findall(r"(?:^|;)\s*width\s*:\s*(\d+)px", declarations)
                )
            return widths

        for selector in (
            ".sidebar:not(.is-pinned):hover .nav-item",
            ".sidebar:not(.is-pinned):hover .side-pill",
            ".sidebar:not(.is-pinned):hover .project-version-badge",
        ):
            widths = declared_widths(selector)
            self.assertTrue(widths, selector)
            self.assertLessEqual(max(widths), 80, f"{selector} exceeds the collapsed sidebar")

        collapsed_side_pill_rules = [
            declarations
            for selectors, declarations in rules
            if ".sidebar:not(.is-pinned):hover .side-pill" in selectors
        ]
        self.assertTrue(collapsed_side_pill_rules)
        for declarations in collapsed_side_pill_rules:
            self.assertNotRegex(
                declarations,
                r"(?:^|;)\s*background(?:-color)?\s*:",
                "ancestor hover must not repaint every collapsed settings button",
            )
        self.assertRegex(
            self.source,
            re.compile(r"\.side-pill:hover\s*\{[^}]*background\s*:", re.S),
        )
        self.assertRegex(
            self.source,
            re.compile(r"html\.theme-dark \.side-pill:hover[^{}]*\{[^}]*background\s*:", re.S),
        )

    def test_collapsed_sidebar_hides_nav_labels_without_requiring_hover(self):
        self.assertRegex(
            self.source,
            re.compile(
                r"\.sidebar:not\(\.is-pinned\) \.nav-text\s*\{"
                r"[^}]*display\s*:\s*none"
                r"[^}]*opacity\s*:\s*0",
                re.S,
            ),
        )

    def test_formal_product_name_contains_runtime_version(self):
        tauri_config = TAURI_CONFIG.read_text(encoding="utf-8")
        tauri_host = TAURI_HOST.read_text(encoding="utf-8")
        self.assertIn('"productName": "SHIYIN AI"', tauri_config)
        self.assertIn('SHIYIN AI V', self.source)
        self.assertIn('id="product-identity"', self.source)
        self.assertIn('concat!("SHIYIN AI V", env!("CARGO_PKG_VERSION"))', tauri_host)

    def test_windows_shell_reuses_stable_webview_profile_and_prunes_legacy_caches(self):
        tauri_host = TAURI_HOST.read_text(encoding="utf-8")
        self.assertRegex(
            tauri_host,
            re.compile(
                r'let webview_root = data_root\.join\("cache"\)\.join\("webview2"\);\s*'
                r'let webview_data_root = webview_root\.join\("shared"\);',
                re.S,
            ),
        )
        self.assertNotIn('join("webview2").join(env!("CARGO_PKG_VERSION"))', tauri_host)
        self.assertIn("schedule_legacy_webview_profile_cleanup", tauri_host)
        self.assertIn("is_legacy_webview_version_dir", tauri_host)
        self.assertIn("Duration::from_secs(20)", tauri_host)

    def test_runtime_sync_conflict_retry_does_not_replay_stale_preferences(self):
        runtime_source = RUNTIME_SYNC.read_text(encoding="utf-8")
        self.assertIn("冲突阶段不广播旧偏好", runtime_source)
        self.assertRegex(
            runtime_source,
            re.compile(r"if\(response\.status === 409\).*?const merged = \{\.\.\.state\.values, \.\.\.values\};\s+return writePreferences\(merged, state\.revision, false\);", re.S),
        )
        self.assertNotRegex(
            runtime_source,
            re.compile(r"if\(response\.status === 409\).*?applyValues\(state\.values\).*?const merged", re.S),
        )
        self.assertIn("readyPromise", runtime_source)
        self.assertIn("function ready()", runtime_source)

    def test_software_settings_exposes_persistent_close_behavior(self):
        tauri_host = TAURI_HOST.read_text(encoding="utf-8")
        settings_html = APP_SETTINGS_HTML.read_text(encoding="utf-8")
        settings_js = APP_SETTINGS_JS.read_text(encoding="utf-8")
        self.assertIn("'app-settings'", self.source)
        self.assertIn('id="frame-app-settings"', self.source)
        self.assertIn('value="minimize_to_tray"', settings_html)
        self.assertIn('value="exit"', settings_html)
        self.assertIn('id="generatedOutputDir"', settings_html)
        self.assertIn('id="chooseGeneratedOutput"', settings_html)
        self.assertIn("generated_output_dir", settings_js)
        self.assertIn("select-generated-output-directory", settings_js)
        self.assertIn("'/api/app-settings'", settings_js)
        self.assertIn('id="storageMaintenanceTitle"', settings_html)
        self.assertIn('id="previewOrphanMedia"', settings_html)
        self.assertIn('id="cleanupOrphanMedia"', settings_html)
        self.assertIn("/api/storage/media/reconcile", settings_js)
        self.assertIn("/api/storage/media/cleanup-orphans", settings_js)
        self.assertIn("dry_run:true", settings_js)
        self.assertIn("close_behavior", tauri_host)
        self.assertIn('WindowEvent::CloseRequested', tauri_host)
        self.assertIn('CLOSE_BEHAVIOR_ASK: &str = "ask_on_close"', tauri_host)
        self.assertIn('CLOSE_ACTION_MINIMIZE_LABEL: &str = "最小化到托盘"', tauri_host)
        self.assertIn('CLOSE_ACTION_EXIT_LABEL: &str = "退出软件"', tauri_host)
        self.assertIn("MessageButtons::OkCancelCustom", tauri_host)
        self.assertNotIn("MessageButtons::YesNo", tauri_host)
        self.assertIn("write_close_behavior(&state.data_root, &close_behavior)", tauri_host)
        self.assertIn("close_behavior == CLOSE_BEHAVIOR_EXIT", tauri_host)

    def test_windows_shell_allows_frontend_html5_file_drop(self):
        tauri_host = TAURI_HOST.read_text(encoding="utf-8")
        self.assertRegex(
            tauri_host,
            re.compile(
                r'WebviewWindowBuilder::new\(app,\s*"main".*?\.disable_drag_drop_handler\(\)',
                re.S,
            ),
        )

    def test_windows_shell_uses_native_save_dialog_for_webview_downloads(self):
        tauri_host = TAURI_HOST.read_text(encoding="utf-8")
        self.assertIn("DownloadEvent::Requested", tauri_host)
        self.assertIn("FileDialog::new()", tauri_host)
        self.assertIn(".save_file()", tauri_host)
        self.assertIn(".on_download(native_download_handler)", tauri_host)


if __name__ == "__main__":
    unittest.main()
