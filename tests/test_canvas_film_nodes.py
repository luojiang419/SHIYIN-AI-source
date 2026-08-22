from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILM = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
CLASSIC = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CLASSIC_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
FILM_CSS = (ROOT / "static" / "css" / "canvas-film-nodes.css").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")


def test_film_domain_module_defines_both_nodes_and_dynamic_role_ports():
    assert "['film-storyboard','film-video']" in FILM
    assert "actorCount = clamp(node.actorCount || 1, 1, 8)" in FILM
    assert "role:`actor-${i}`" in FILM
    assert "role:`outfit-${i}`" in FILM
    assert "role:`prop-${i}`" in FILM
    assert "data-film-action=\"add-actor\"" in FILM


def test_film_mapping_has_model_specific_rules_and_at_insertion():
    for marker in ("MODEL_RULES", "jimeng", "kling", "minimax", "<Picture {index}>", "资产映射："):
        assert marker in FILM
    assert "input.value.lastIndexOf('@')" in FILM
    assert "data-film-mention-index" in FILM
    assert "fetch('/api/canvas-llm'" in FILM


def test_both_canvas_entries_expose_secondary_film_menu_and_shared_module():
    assert "/static/js/canvas-film-nodes.js" in CLASSIC_HTML
    assert "/static/js/canvas-film-nodes.js" in SMART_HTML
    assert "data-film-menu-host" in CLASSIC_HTML
    assert "data-create-type=\"film-storyboard\"" in SMART_HTML
    assert "data-create-type=\"film-video\"" in SMART_HTML
    assert "function addFilmNode(type, point)" in CLASSIC
    assert "function createFilmNode(type, point)" in SMART


def test_both_canvas_runtimes_bind_film_nodes_and_parse_visuals():
    assert "if(window.CanvasFilmNodes?.isType?.(node.type)) bindClassicFilmNode(el,node);" in CLASSIC
    assert "node.specialType === 'film-storyboard' || node.specialType === 'film-video'" in SMART
    assert "runSmartFilmNode(changed)" in SMART
    assert "runFilmNode(changed.id)" in CLASSIC


def test_film_input_slots_match_three_view_layout_and_keep_labels_inside_content():
    for token in ("var(--strong)", "var(--soft)", "var(--line)", "var(--text)", "var(--muted)"):
        assert token in FILM_CSS
    assert "film-input-list" in FILM
    assert "film-input-row" in FILM
    assert "top:calc(125px + var(--film-port-index) * 36px)" in FILM_CSS
    assert "top:calc(74px + var(--film-port-index) * 36px)" in FILM_CSS
    assert "right:100%" not in FILM_CSS
    assert ".film-input-row strong" in FILM_CSS
    assert "grid-template-columns:minmax(0,1fr) minmax(0,1fr)" in FILM_CSS
    assert "rgba(124,58,237" not in FILM_CSS
    assert "rgba(139,92,246" not in FILM_CSS
    assert "rgba(124,58,237" not in SMART_CSS


def test_film_variants_use_their_parent_generation_model_sources():
    assert "imageProviderOptions:filmSmartImageProviderOptions" in SMART
    assert "imageModelOptions:filmSmartImageModelOptions" in SMART
    assert "const imageProvider=filmSmartImageProviderId(node)" in SMART
    assert "if(isKlingVideoNode(node)) ensureKlingCapabilities();" in CLASSIC


def test_film_connected_input_status_has_a_green_indicator_and_connected_label():
    assert "film-input-status-dot" in FILM
    assert "'<span class=\"film-input-status-dot\" aria-hidden=\"true\"></span>已连接'" in FILM
    assert ".film-input-status-dot" in FILM_CSS
    assert "background:#2fbf71" in FILM_CSS
