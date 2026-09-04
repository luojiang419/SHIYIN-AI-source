from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
LOOKBOOK_JS = (ROOT / "static/js/canvas-lookbook-node.js").read_text(encoding="utf-8")
SPECIAL_CSS = (ROOT / "static/css/canvas-special-nodes.css").read_text(encoding="utf-8")
MULTI_VIEW_CSS = (ROOT / "static/css/canvas-multi-view-overrides.css").read_text(encoding="utf-8")


def test_image_toolbar_exposes_multi_view_action_and_creates_node():
    assert "{key:'multi-view', icon:'panels-top-left', label:'创建三视图'" in SMART_JS
    assert "function createMultiViewNode" in SMART_JS
    assert "createMultiViewNode(null, node)" in SMART_JS
    assert "sourceNode ? smartSettingsForNode(sourceNode) : settings" in SMART_JS


def test_multi_view_has_all_role_ports_and_optional_multi_inputs():
    for role, label in [
        ("model-front", "模特正面"),
        ("model-side", "模特侧面"),
        ("model-back", "模特背面"),
        ("product-upper-front", "上装正面"),
        ("product-upper-side", "上装侧面"),
        ("product-upper-back", "上装背面"),
        ("product-lower-front", "下装正面"),
        ("product-lower-side", "下装侧面"),
        ("product-lower-back", "下装背面"),
        ("front-detail", "正面细节"),
        ("back-detail", "背面细节"),
        ("accessory", "配饰"),
    ]:
        assert role in SMART_JS
        assert label in SMART_JS
    assert "MULTI_VIEW_MULTI_INPUT_ROLES" in SMART_JS
    assert "front-detail', 'back-detail', 'accessory" in SMART_JS


def test_multi_view_generates_board_detail_and_three_vertical_assets():
    assert "multi-view-board.png" in SMART_JS
    assert "multi-view-detail.png" in SMART_JS
    assert "`multi-view-${view}.png`" in SMART_JS
    assert "Promise.all([taskFor('front', 'board', 0), taskFor('detail', 'detail', 1), taskFor('front', 'view', 2), taskFor('side', 'view', 3), taskFor('back', 'view', 4)])" in SMART_JS
    assert "outputKind === 'board' ? '16:9' : outputKind === 'detail' ? '3:4' : '9:16'" in SMART_JS
    assert "customRatio:ratio" in SMART_JS
    assert "smartMultiViewSettingsForNode(node)" in SMART_JS
    assert "submitted.providerId" in SMART_JS


def test_multi_view_shows_five_loading_slots_and_updates_in_grid_order():
    for source in (SMART_JS, CANVAS_JS):
        assert "length:5" in source
        assert "multiViewOutputs" in source
    assert "正在生成…" in SMART_JS
    assert "out._pending = Array.from({length:5" in CANVAS_JS
    assert "index === 1 ? {w:3,h:4}" in CANVAS_JS
    assert "outputLayout = {...node.multiViewOutputLayout}" in CANVAS_JS
    assert "type:'grid-split'" in CANVAS_JS
    assert ".output-node .output-grid.grid-layout" in MULTI_VIEW_CSS


def test_multi_view_output_reuses_standard_thumbnail_grid_and_auto_height():
    assert "function isMultiViewOutputNode(node)" in CANVAS_JS
    assert "function normalizedMultiViewOutputWidth(node)" in CANVAS_JS
    assert "el.classList.remove('sized')" in CANVAS_JS
    assert "el.style.height = '';" in CANVAS_JS
    assert "out.w = normalizedMultiViewOutputWidth(out);" in CANVAS_JS
    assert "delete out.h;" in CANVAS_JS
    assert "if(node?.type === 'multiView') return null;" in CANVAS_JS
    assert "out.w = Math.max(Number(out.w || 0), 700);" not in CANVAS_JS
    assert "out.h = Math.max(Number(out.h || 0), 620);" not in CANVAS_JS


def test_multi_view_is_available_from_create_menu_and_has_visual_styles():
    assert 'data-create-type="multi-view"' in SMART_HTML
    assert ".multi-view-input-list" in SPECIAL_CSS
    assert ".multi-view-output-grid" in SPECIAL_CSS
    for setting in [
        "data-multi-view-provider",
        "data-multi-view-model",
        "data-multi-view-resolution",
        "data-multi-view-quality",
    ]:
        assert setting in SMART_JS


def test_classic_canvas_image_toolbar_exposes_create_three_views_action():
    assert "{id:'multi-view', label:langIsEn() ? 'Create three views' : '创建三视图'" in CANVAS_JS
    assert "type === 'multiView' || type === 'multi-view'" in CANVAS_JS
    assert "const inputRole = type === 'multi-view' ? 'model-front' : ''" in CANVAS_JS


def test_classic_canvas_multi_view_node_has_all_ports_and_five_asset_generation():
    assert "const CLASSIC_MULTI_VIEW_INPUT_SLOTS" in CANVAS_JS
    for role in [
        "model-front", "model-side", "model-back",
        "product-upper-front", "product-upper-side", "product-upper-back",
        "product-lower-front", "product-lower-side", "product-lower-back",
        "front-detail", "back-detail", "accessory",
    ]:
        assert role in CANVAS_JS
    assert "Promise.all([taskFor('front', 'board', 0), taskFor('detail', 'detail', 1), taskFor('front', 'view', 2), taskFor('side', 'view', 3), taskFor('back', 'view', 4)])" in CANVAS_JS
    assert "classicMultiViewPrompt(view, refs, outputKind, viewRefs)" in CANVAS_JS
    assert "multi-view-detail.png" in CANVAS_JS
    assert "data-multi-view-run" in CANVAS_JS
    assert ".classic-multi-view-output-grid" in SPECIAL_CSS
    for setting in [
        "data-multi-view-provider",
        "data-multi-view-model",
        "data-multi-view-resolution",
        "data-multi-view-quality",
    ]:
        assert setting in CANVAS_JS
    assert "sanitizeClassicMultiViewSettings(node)" in CANVAS_JS


def test_classic_canvas_multi_view_is_available_from_toolbar_and_create_menu():
    assert "menuAdd('multiView')" in CANVAS_HTML


def test_multi_view_ports_have_explicit_labels_and_grouped_layout_overrides():
    assert 'aria-label="${escapeAttr(`输入端口：${label}`)}"' in SMART_JS
    assert 'aria-label="${escapeAttr(`输入端口：${label}`)}"' in CANVAS_JS
    assert 'data-input-role="${escapeAttr(role)}"' in SMART_JS
    assert 'data-input-role="${escapeAttr(role)}"' in CANVAS_JS
    assert ".multi-view-input-group" in MULTI_VIEW_CSS
    assert ".classic-multi-view-input-group" in MULTI_VIEW_CSS
    assert ".smart-special-node.smart-multi-view-node .multi-view-port::before" in MULTI_VIEW_CSS
    assert ".multi-view-run-row" in MULTI_VIEW_CSS


def test_both_canvas_pages_load_multi_view_layout_overrides():
    assert 'canvas-multi-view-overrides.css?v=2026.08.21.multi-view-five-assets.2' in SMART_HTML
    assert 'canvas-multi-view-overrides.css?v=2026.08.21.multi-view-five-assets.2' in CANVAS_HTML
    assert 'canvas.js?v=2026.08.21.bulk-import-grid.1' in CANVAS_HTML
    assert "location.replace(target)" in SMART_HTML
    assert "'/static/canvas.html'" in SMART_HTML


def test_classic_multi_view_keeps_results_only_in_output_node_and_locks_controls_visible():
    body_start = CANVAS_JS.index("function classicMultiViewBodyHtml")
    body_end = CANVAS_JS.index("function sanitizeClassicMultiViewSettings", body_start)
    body = CANVAS_JS[body_start:body_end]
    assert "classic-multi-view-output-grid" not in body
    assert "5 张资产已在右侧输出节点中生成" in body
    assert ".multiView-node.sized .classic-multi-view-run-row" in MULTI_VIEW_CSS
    assert ".multiView-node.sized .classic-multi-view-input-list" in MULTI_VIEW_CSS
    assert "resizeNode.node.type === 'multiView' ? (min.h || 780)" in CANVAS_JS
    assert "node.specialType === 'multi-view' ? 780" in SMART_JS


def test_multi_view_uses_single_column_rows_for_port_alignment():
    assert "inputSlots.map(([role, label, kind], index)" in SMART_JS
    assert "inputSlots.map(([role, label, kind], index)" in CANVAS_JS
    assert "smartMultiViewInputSlots(node).map(([role, label], index)" in SMART_JS
    assert "classicMultiViewInputSlots(node).map(([role, label], index)" in CANVAS_JS
    assert "style=\"--multi-view-port-index:${index};--multi-view-port-top:${74 + index * 44}px\"" in SMART_JS
    assert "style=\"--multi-view-port-index:${index};--multi-view-port-top:${125 + index * 44}px\"" in CANVAS_JS
    assert ".multi-view-input-list,.classic-multi-view-input-list{display:flex;flex-direction:column" in MULTI_VIEW_CSS
    assert ".smart-special-node.smart-multi-view-node .multi-view-port{top:var(--multi-view-port-top" in MULTI_VIEW_CSS
    assert ".multiView-node .classic-multi-view-port{top:var(--multi-view-port-top" in MULTI_VIEW_CSS


def test_lookbook_input_ports_are_scoped_to_lookbook_nodes():
    assert "inputPorts:type=>type===TYPE ? INPUT_PORTS.map" in LOOKBOOK_JS
    assert "size:type=>type===TYPE ? ({w:430,h:0}) : null" in LOOKBOOK_JS


def test_multi_view_port_labels_are_not_duplicated_and_align_to_rows():
    assert ".smart-special-node.smart-multi-view-node .multi-view-port::before" in MULTI_VIEW_CSS
    assert "content:none!important;display:none!important" in MULTI_VIEW_CSS
    assert "function alignClassicMultiViewPorts" in CANVAS_JS
    assert "classic-multi-view-slot[data-input-role]" in CANVAS_JS
    assert "--multi-view-port-top" in CANVAS_JS


def test_multi_view_product_slots_are_split_by_garment_and_angle():
    assert "<span>12 个输入 · 5 张输出</span>" in SMART_JS
    assert "<span>12 个输入 · 5 张输出</span>" in CANVAS_JS
    assert "role.startsWith('product-upper-') ? '上装'" in SMART_JS
    assert "role.startsWith('product-lower-') ? '下装'" in SMART_JS
    assert "role.startsWith('product-upper-') ? '上装'" in CANVAS_JS
    assert "role.startsWith('product-lower-') ? '下装'" in CANVAS_JS
    assert "['product-front', ['product-upper-front', 'product-lower-front']]" in SMART_JS
    assert "['product-side', ['product-upper-side', 'product-lower-side']]" in CANVAS_JS


def test_multi_view_expands_missing_angles_and_maps_reference_semantics():
    for source in (SMART_JS, CANVAS_JS):
        assert "productAny:Object.values(products).find(Boolean) || null" in source
        assert "请至少连接一张模特或产品图片" in source
        assert "参考图对应关系（必须严格遵守，按提交顺序）" in source
        assert "reference_id:role" in source
        assert "上装参考仅用于上装" in source
        assert "下装参考仅用于下装" in source
        assert "缺失部位与缺失角度根据已提供图片自然延展" in source
    assert "请连接产品正面、产品侧面和产品背面" not in SMART_JS
    assert "请连接产品正面、产品侧面和产品背面" not in CANVAS_JS


def test_multi_view_board_contains_only_three_views_and_detail_is_separate():
    for source, prompt_function, next_function in [
        (SMART_JS, "function multiViewPromptFor", "async function generateSmartMultiView"),
        (CANVAS_JS, "function classicMultiViewPrompt", "function classicMultiViewGridForIndex"),
    ]:
        prompt_body = source[source.index(prompt_function):source.index(next_function, source.index(prompt_function))]
        assert "if(outputKind === 'board')" in prompt_body
        assert "正面全身、标准侧面全身、背面全身三幅照片" in prompt_body
        assert "if(outputKind === 'detail')" in prompt_body
        assert "竖向三列四行的专业写实细节摄影板" in prompt_body
        assert "面料织纹、剪裁车线、腰头、口袋、鞋子、包袋与配饰" in prompt_body
        assert "右上展示头部多角度" not in prompt_body
        assert "右下展示上装" not in prompt_body
        assert "生成一张16:9" not in prompt_body
        assert "单张9:16" not in prompt_body

    assert "['纯三视图横板', '独立细节图', '正面视图', '侧面视图', '背面视图']" in SMART_JS
    assert "1×16:9 + 1×3:4 + 3×9:16" in SMART_JS
    assert "1×16:9 + 1×3:4 + 3×9:16" in CANVAS_JS
    assert ".multi-view-output-item:nth-child(2) img{aspect-ratio:3/4}" in MULTI_VIEW_CSS


def test_multi_view_height_migration_leaves_room_for_twelve_rows_and_parameters():
    assert "x:baseX, y:baseY, w:700, h:780" in SMART_JS
    assert "x:p.x, y:p.y, w:700, h:780" in CANVAS_JS
    assert "[560, 680, 720].includes(savedHeight)" in SMART_JS
    assert "Number(node.h) < 780" in CANVAS_JS
