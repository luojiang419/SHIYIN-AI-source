from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
ECOMMERCE_JS = (ROOT / "static" / "js" / "canvas-ecommerce-nodes.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_ecommerce_nodes_live_in_a_second_level_context_menu():
    host = HTML.index('class="menu-submenu-host" data-ecommerce-menu-host')
    submenu = HTML.index('class="create-submenu"', host)
    workflow = HTML.index("menuCreateEcommerceWorkflow()", submenu)
    output_button = HTML.index("menuAdd('output')")
    menu_end = HTML.index('<div id="linkCreateMenu"')

    assert output_button < host < submenu < workflow < menu_end
    assert ".create-submenu.submenu-open" in CANVAS_CSS
    assert ".create-submenu { position:fixed" in CANVAS_CSS
    assert "function positionEcommerceSubmenu()" in CANVAS_JS


def test_second_level_menu_contains_the_five_migrated_nodes_and_combo_action():
    expected = {
        "ecom-model": "电商模特",
        "ecom-product": "电商产品",
        "ecom-scene": "电商场景",
        "ecom-compose": "A+ 图合成",
        "ecom-video": "电商视频",
    }
    for node_type, label in expected.items():
        assert f"menuAdd('{node_type}')" in HTML
        assert label in HTML
        assert f"'{node_type}'" in ECOMMERCE_JS
    assert "创建电商工作流" in HTML


def test_combo_creator_builds_and_connects_the_complete_ecommerce_pipeline():
    for node_type in ("ecom-model", "ecom-product", "ecom-scene", "ecom-compose", "ecom-video"):
        assert f"addEcommerceNode('{node_type}'" in CANVAS_JS

    for role in ("ecom-model", "ecom-product", "ecom-scene"):
        assert f"inputRole:'{role}'" in CANVAS_JS
    assert "from:compose.id,to:video.id" in CANVAS_JS
    assert "function menuCreateEcommerceWorkflow()" in CANVAS_JS


def test_compose_node_reuses_the_existing_ecommerce_task_backend():
    assert "fetch('/api/ecommerce/tasks'" not in ECOMMERCE_JS
    assert "cascadeFetch('/api/ecommerce/tasks'" in CANVAS_JS
    assert "operation:'universal'" in CANVAS_JS
    assert "waitEcommerceTask" in CANVAS_JS
    assert "prompt_policy:'free'" in CANVAS_JS


def test_product_reference_mapping_uses_primary_product_and_detail_evidence():
    assert "reference_type:index === 0 ? node.ecomProductRole : 'detail'" in ECOMMERCE_JS
    assert "detail_target_id:index === 0 ? '' : primaryId" in ECOMMERCE_JS
    assert "slice(0,14)" in CANVAS_JS


def test_ecommerce_video_reuses_canvas_video_execution_and_recovery_path():
    assert "if(node.type === 'ecom-video') body.appendChild(renderVideoBody(node));" in CANVAS_JS
    assert "if(node.type === 'ecom-video') return runVideoNode(node.id, runOpts);" in CANVAS_JS
    assert "['video','ecom-video'].includes(node.type)" in CANVAS_JS
    assert "'ecom-compose','ecom-video'" in CANVAS_JS
