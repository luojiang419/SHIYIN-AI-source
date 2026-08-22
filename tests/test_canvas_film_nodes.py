from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILM = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
CLASSIC = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CLASSIC_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
FILM_CSS = (ROOT / "static" / "css" / "canvas-film-nodes.css").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_film_domain_module_defines_both_nodes_and_dynamic_role_ports():
    assert "['film-storyboard','film-video']" in FILM
    assert "actorCount = clamp(node.actorCount || 1, 1, 8)" in FILM
    assert "role:`actor-${i}`" in FILM
    assert "role:`outfit-${i}`" in FILM
    assert "role:`prop-${i}`" in FILM
    assert "data-film-action=\"add-actor\"" in FILM


def test_film_video_ports_are_grouped_per_actor_and_support_inherited_count():
    assert "function effectiveActorCount(node)" in FILM
    assert "node?.autoActorCount || 0" in FILM
    actor_group = "{role:`actor-${i}`,label:actorLabel(i,'演员')"
    outfit_group = "{role:`outfit-${i}`,label:`服装${String.fromCharCode(65+i)}`"
    prop_group = "{role:`prop-${i}`,label:`道具${String.fromCharCode(65+i)}`"
    assert FILM.index(actor_group) < FILM.index(outfit_group) < FILM.index(prop_group)
    assert ".map((port,index) => inputSlotHtml" in FILM


def test_film_canvases_trace_storyboard_actor_assets_for_reuse():
    assert "function classicFilmInheritedActorAssets(node)" in CLASSIC
    assert "classicFilmStoryboardAncestors(connection.from)" in CLASSIC
    assert "function smartFilmInheritedActorAssets(node)" in SMART
    assert "smartFilmStoryboardAncestors(connection.from)" in SMART
    assert "autoReuse:true" in CLASSIC
    assert "autoReuse:true" in SMART


def test_film_mapping_has_model_specific_rules_and_at_insertion():
    for marker in ("MODEL_RULES", "jimeng", "kling", "minimax", "<Picture {index}>", "资产映射："):
        assert marker in FILM
    assert "before.match(/@([^\\s@]*)$/)" in FILM
    assert "data-film-mention-index" in FILM
    assert "event.key==='Enter'" in FILM
    assert "ref.roleLabel || ref.name || '参考资产'" in FILM
    assert "fetch('/api/canvas-llm'" in FILM


def test_film_mapping_is_above_prompt_and_uses_semantic_asset_labels():
    body = FILM[FILM.index('function bodyHtml'):]
    assert body.index('data-film-mapping') < body.index('data-film-field="prompt"')
    assert "ref.roleLabel || '参考资产'" in FILM
    assert "scene:'场景',sketch:'线稿分镜'" in FILM


def test_film_video_storyboard_role_only_keeps_latest_connected_reference():
    marker = "const roleRefs = port.role === 'storyboard'"
    assert marker in FILM
    start = FILM.index(marker)
    body = FILM[start:start + 260]
    assert ".slice(-1)" in body
    assert "inputRole:port.role" in body


def test_film_input_status_accepts_a_live_connection_without_a_resolved_url():
    assert "options.connected?.(node, port.role)" in FILM
    assert "connected:(target, role) => connections.some" in CLASSIC
    assert "connected:(target, role) => (canvas?.connections || []).some" in SMART


def test_film_aspect_ratio_aliases_do_not_fall_back_to_square_size():
    assert "'16:9':'wide'" in CLASSIC
    assert "'9:16':'story'" in CLASSIC
    assert "'16:9':'wide'" in SMART
    assert "'9:16':'story'" in SMART
    assert "size:apiImageSize(node.aspectRatio || '16:9',node.resolution || '2k')" in CLASSIC


def test_film_runs_create_pending_outputs_before_waiting_for_results():
    assert "const out=outputForNode(node,560,true)" in CLASSIC
    assert "out._pending=[...(out._pending || []),pending]" in CLASSIC
    assert "pending.canvasTaskId=task.task_id" in CLASSIC
    assert "output=createPendingOutputFromSource(node,1,meta" in SMART
    assert "output.filmSourceNodeId=node.id" in SMART
    assert "finalizePendingNode(output,images,meta,'image')" in SMART
    assert "status:'error'" in SMART


def test_film_runs_allow_parallel_clicks_and_keep_independent_smart_outputs():
    assert "if(!node) return;" in CLASSIC
    assert "classicFilmHasActiveRun(node,out)" in CLASSIC
    assert "if(!node || !window.CanvasFilmNodes) return;" in SMART
    assert "const smartFilmActiveRuns = new Map();" in SMART
    assert "const output=createPendingOutputFromSource(node,1,meta" in SMART
    assert "每次点击都建立独立输出节点" in SMART
    assert "生成中（可继续）" in FILM


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


def test_classic_film_video_defaults_to_kling_video_3_0_omni_and_resolves_real_model():
    assert "const KLING_VIDEO_3_0_OMNI_MODEL = 'kling-v3-omni';" in CLASSIC
    assert "videoApiProviders().find(provider => provider.id === 'kling-cli')" in CLASSIC
    assert "preferredKlingOmniModel" in CLASSIC
    assert "if(providerId === 'kling-cli' && isKlingOmni30Model(node.model))" in CLASSIC
    assert "result.get(\"model\") or payload.model" in MAIN


def test_classic_film_render_passes_image_model_sources_for_storyboard_node():
    compact_classic = " ".join(CLASSIC.split())
    assert "imageProviderOptions:filmNodeImageProviderOptions" in compact_classic
    assert "imageModelOptions:filmNodeImageModelOptions" in compact_classic
    assert "const payload={prompt:built.prompt,provider_id:imageProvider" in CLASSIC


def test_film_connected_input_status_has_a_green_indicator_and_connected_label():
    assert "film-input-status-dot" in FILM
    assert "'<span class=\"film-input-status-dot\" aria-hidden=\"true\"></span>已连接'" in FILM
    assert ".film-input-status-dot" in FILM_CSS
    assert "background:#2fbf71" in FILM_CSS


def test_video_preview_ffmpeg_uses_hidden_windows_process_flags():
    assert "def hidden_subprocess_window_kwargs()" in MAIN
    assert "getattr(subprocess, \"CREATE_NO_WINDOW\", 0x08000000)" in MAIN
    assert "subprocess.run(cmd, capture_output=True, text=True, timeout=60, **hidden_subprocess_window_kwargs())" in MAIN
