import colorsys
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
UNIFIED_CSS = STATIC / "css" / "studio-unified.css"
THEME_CSS = STATIC / "css" / "theme.css"
ECOMMERCE_CSS = STATIC / "css" / "ecommerce.css"
IMAGE_PREVIEW_JS = STATIC / "js" / "image-preview.js"
CANVAS_UI_FILES = (
    UNIFIED_CSS,
    STATIC / "css" / "canvas.css",
    STATIC / "css" / "canvas-list.css",
    STATIC / "css" / "smart-canvas.css",
    STATIC / "js" / "canvas.js",
    STATIC / "js" / "canvas-list.js",
    STATIC / "js" / "smart-canvas.js",
    STATIC / "canvas.html",
    STATIC / "canvas-list.html",
    STATIC / "smart-canvas.html",
)
COLOR_LITERAL = re.compile(
    r"#([0-9a-fA-F]{6})\b|"
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})",
)


class UnifiedThemeTests(unittest.TestCase):
    def test_workspace_pages_load_unified_theme_after_page_styles(self):
        pages = (
            "gpt-chat.html",
            "asset-manager.html",
            "canvas-list.html",
            "canvas.html",
            "smart-canvas.html",
            "works.html",
            "api-settings.html",
            "app-settings.html",
        )
        for page in pages:
            source = (STATIC / page).read_text(encoding="utf-8")
            self.assertIn("/static/css/studio-unified.css", source, page)
            self.assertLess(source.rfind("<link"), source.rfind("</head>"), page)
            self.assertLess(source.rfind("/static/css/studio-unified.css"), source.rfind("</head>"), page)

    def test_shell_cache_busts_pages_that_receive_unified_theme(self):
        source = (STATIC / "index.html").read_text(encoding="utf-8")
        for frame_id in (
            "frame-gpt-chat",
            "frame-asset-manager",
            "frame-works",
            "frame-api-settings",
            "frame-app-settings",
        ):
            self.assertRegex(
                source,
                rf'id="{frame_id}"[^>]+ivory-surfaces\.1',
                frame_id,
            )
        self.assertRegex(source, r'id="frame-canvas"[^>]+canvas-neutral-no-blue\.1')
        for frame_id in ("frame-ecommerce", "frame-free-creation"):
            self.assertRegex(
                source,
                rf'id="{frame_id}"[^>]+universal-plan-banner-removed\.1',
                frame_id,
            )

    def test_infinite_canvas_dark_surface_is_neutral_and_cache_busted(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "Infinite canvas dark final pass",
            "html.studio-theme-dark body #shell.shell",
            "body.theme-dark #shell.shell > .board",
            "--page:var(--studio-bg)",
            "--grid:var(--studio-grid)",
            "background-color:var(--studio-bg) !important",
            "background-image:radial-gradient(var(--studio-grid) 1px, transparent 1px) !important",
        ):
            self.assertIn(marker, source)
        for page in ("smart-canvas.html", "canvas-list.html", "canvas.html"):
            page_source = (STATIC / page).read_text(encoding="utf-8")
            self.assertRegex(
                page_source,
                r"studio-unified\.css\?v=2026\.08\.14\.blender-neutral\.1",
                page,
            )

    def test_canvas_pages_do_not_load_legacy_blue_theme_and_bust_page_css(self):
        page_styles = {
            "canvas.html": "canvas.css",
            "canvas-list.html": "canvas-list.css",
            "smart-canvas.html": "smart-canvas.css",
        }
        for page, stylesheet in page_styles.items():
            source = (STATIC / page).read_text(encoding="utf-8")
            self.assertNotIn('/static/css/theme.css', source, page)
            self.assertRegex(
                source,
                rf"{re.escape(stylesheet)}\?v=2026\.08\.14\.canvas-neutral-no-blue\.1",
                page,
            )

    def test_canvas_ui_has_no_blue_or_cyan_color_literals(self):
        residues = []
        for path in CANVAS_UI_FILES:
            source = path.read_text(encoding="utf-8")
            for match in COLOR_LITERAL.finditer(source):
                if match.group(1):
                    value = match.group(1)
                    red, green, blue = (
                        int(value[offset:offset + 2], 16)
                        for offset in (0, 2, 4)
                    )
                else:
                    red, green, blue = (int(match.group(index)) for index in (2, 3, 4))
                hue, saturation, _ = colorsys.rgb_to_hsv(
                    red / 255,
                    green / 255,
                    blue / 255,
                )
                hue *= 360
                if 165 <= hue < 250 and saturation >= 0.01:
                    line = source.count("\n", 0, match.start()) + 1
                    residues.append(f"{path.relative_to(ROOT)}:{line} {match.group(0)}")
        self.assertEqual([], residues, "画布仍存在蓝色/青色色相：\n" + "\n".join(residues))

    def test_infinite_canvas_nodes_use_theme_tokens_for_inner_surfaces(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "无限画布节点内部区域",
            "#shell .prompt-node textarea",
            "#shell .llm-input-area",
            "#shell .llm-output",
            "#shell .blank-image",
            "#shell .output-grid img",
            "#shell .gen-btn",
            "background:var(--studio-control) !important",
            "background:var(--studio-accent) !important",
        ):
            self.assertIn(marker, source)

    def test_infinite_canvas_dark_nodes_and_log_panel_have_final_neutral_pass(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "星夜黑无限画布蓝灰残留收口",
            "#shell .gen-settings",
            "#shell .loop-count-row",
            "#shell .setting-input",
            "#shell .mode-tabs button.active",
            ".log-panel",
            ".log-list",
            ".log-item",
            "background-image:none !important",
            "background:var(--studio-panel) !important",
            "background:var(--studio-control) !important",
            "background:var(--studio-panel-raised) !important",
        ):
            self.assertIn(marker, source)

    def test_dark_canvas_pages_have_full_neutral_closure_layer(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "星夜黑暗色画布全量收口",
            "html.studio-theme-dark body .canvas-item",
            "html.studio-theme-dark body .canvas-meta-pop",
            "html.studio-theme-dark body .canvas-owner-input",
            "html.studio-theme-dark body .selection-hub",
            "html.studio-theme-dark body .hub-port",
            "html.studio-theme-dark body .comfy-settings",
            "html.studio-theme-dark body .llm-chat-pane",
            "html.studio-theme-dark body .image-edit-stage",
            "html.studio-theme-dark body .loop-smart-prompt-index",
            "html.studio-theme-dark body .composer-template-btn",
            "html.studio-theme-dark body .jimeng-pending-spinner i",
            ".canvas-owner-chip",
            ".canvas-kind-chip",
            ".ws-card-kind.smart",
            "background:var(--studio-control) !important",
            "background:var(--studio-panel-raised) !important",
        ):
            self.assertIn(marker, source)
        # 暗色画布页面必须引用最新收口版本号，不能回退到旧缓存
        for page in ("canvas.html", "canvas-list.html", "smart-canvas.html"):
            page_source = (STATIC / page).read_text(encoding="utf-8")
            self.assertRegex(
                page_source,
                r"studio-unified\.css\?v=2026\.08\.14\.blender-neutral\.1",
                page,
            )

    def test_gpt_chat_no_longer_declares_legacy_blue_dark_theme(self):
        source = (STATIC / "gpt-chat.html").read_text(encoding="utf-8").lower()
        for color in ("#0f141d", "#171d29", "#111722", "#2a3444", "#d8dee9"):
            self.assertNotIn(color, source)

    def test_unified_theme_uses_ecommerce_tokens_and_scopes_gpt_overrides(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for token in ("#f6eee4", "#faf2e7", "#9a6636", "#1a1a1a", "#3a3a39"):
            self.assertIn(token, source)
        self.assertIn(".chat-shell .topbar", source)
        self.assertNotRegex(source, re.compile(r"(?m)^\.topbar\s*\{"))

    def test_unified_theme_has_final_dark_pass_over_legacy_blue_gray_rules(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        legacy = THEME_CSS.read_text(encoding="utf-8")
        for token in ("#0f141d", "#111722", "#171d29", "#2a3444", "#334155", "#d8dee9"):
            self.assertIn(token, legacy)
            self.assertNotIn(token, source)
        self.assertIn("Final pass: make this file the last visual contract", source)
        self.assertIn("html.studio-theme-dark body .chat-shell .topbar", source)
        self.assertIn("html.studio-theme-dark body .chat-shell .composer", source)
        self.assertIn("html.studio-theme-dark body .asset-search-wrap", source)
        self.assertIn("html.studio-theme-dark body .works-search", source)
        self.assertIn("html.studio-theme-dark body .ws-project-row.active", source)
        for marker in (
            ".output-preview",
            ".studio-preview-frame",
            ".image-edit-stage.preview-mode",
            ".panorama-stage",
            "background:color-mix(in srgb,var(--studio-panel) 96%,transparent)",
            ".output-preview img",
            "html.studio-theme-dark body .output-preview",
            "html.studio-theme-dark body .shell .output-preview img",
            ".preview-stage img",
            "background:var(--studio-bg)",
        ):
            self.assertIn(marker, source)

    def test_shared_image_preview_uses_theme_tokens(self):
        source = IMAGE_PREVIEW_JS.read_text(encoding="utf-8")
        self.assertIn("var(--studio-panel", source)
        self.assertIn("var(--studio-border", source)
        self.assertIn("var(--studio-shadow-raised", source)
        self.assertIn("html.studio-theme-dark .studio-preview-frame", source)
        self.assertNotIn("#020617", source)

    def test_api_recommendation_styles_are_neutralized_by_unified_theme(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "--api-dark-primary:var(--studio-accent)",
            "body.studio-theme-dark .api-link-btn",
            ".api-link-btn::after",
            "display:none !important",
            ".recommend-guide-arrow",
            ".onboarding-rh-row-arrow",
            ".recommend-tag.recommend-free-tag",
            ".recommend-tag.recommend-perk-tag",
            ".provider-onboarding-card .onboarding-save-btn",
        ):
            self.assertIn(marker, source)

    def test_no_explicit_blue_backgrounds_remain_in_static_surfaces(self):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in STATIC.rglob("*")
            if path.suffix.lower() in {".css", ".html", ".js"}
        )
        blue_background = re.compile(
            r"background(?:-color)?\s*:[^;]*(?:"
            r"#2563eb|#3b82f6|#60a5fa|#bfdbfe|#dbeafe|#eff6ff|"
            r"rgba\(\s*(?:37\s*,\s*99\s*,\s*235|"
            r"59\s*,\s*130\s*,\s*246|96\s*,\s*165\s*,\s*250|"
            r"147\s*,\s*197\s*,\s*253))",
            re.IGNORECASE,
        )
        self.assertIsNone(blue_background.search(sources))

    def test_light_theme_has_final_pass_over_pure_white_surfaces(self):
        source = UNIFIED_CSS.read_text(encoding="utf-8")
        for marker in (
            "Light final pass: keep light mode on the warm SHIYIN theme",
            "象牙白主题全站纯白色块收口",
            "body:not(.studio-theme-dark):not(.theme-dark) .bg-white",
            "--api-light-panel:var(--studio-panel)",
            ".canvas-item",
            ".prompt-node-text",
            ".rh-config-card",
            ".works-compare-handle::before",
            ".provider-onboarding-card",
            ".asset-kind-badge",
            ".ref-chip button",
            ".crop-canvas.outpaint-mode",
            "background:var(--studio-panel) !important",
            "background:var(--studio-control) !important",
        ):
            self.assertIn(marker, source)

    def test_shell_ivory_theme_overrides_inline_white_modal_surfaces(self):
        source = (STATIC / "index.html").read_text(encoding="utf-8")
        for marker in (
            "not(.studio-theme-pure-white):not(.theme-pure-white) .shiying-key-input",
            "not(.studio-theme-pure-white):not(.theme-pure-white) .theme-picker-panel",
            "not(.studio-theme-pure-white):not(.theme-pure-white) .update-source-badge",
            "background:#f7efe5",
            "background:#faf2e7",
        ):
            self.assertIn(marker, source)

    def test_ecommerce_light_theme_has_own_final_pass(self):
        source = ECOMMERCE_CSS.read_text(encoding="utf-8")
        for marker in (
            "浅色品牌收口：电商页不加载 studio-unified.css",
            "象牙白纯白色块收口",
            "html:not(.studio-theme-dark):not(.theme-dark) .ec-page.is-universal .ec-control-panel",
            "background:transparent !important",
            "html:not(.studio-theme-dark):not(.theme-dark) .ec-result-panel",
            "html:not(.studio-theme-dark):not(.theme-dark) .ec-universal-dock .ec-universal-reference",
            "not(.studio-theme-pure-white):not(.theme-pure-white) .ec-studio-reference-option",
            "not(.studio-theme-pure-white):not(.theme-pure-white) .ec-compare-handle::before",
            "background:linear-gradient(180deg,var(--ec-control),color-mix(in srgb,var(--ec-control-hover) 58%,var(--ec-control))) !important",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
