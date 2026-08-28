from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
ECOMMERCE_JS = (ROOT / "static" / "js" / "canvas-ecommerce-nodes.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_ecommerce_nodes_are_removed_from_the_create_menu():
    assert 'data-ecommerce-menu-host' not in HTML
    assert "menuAdd('ecom-model')" not in HTML
    assert "menuAdd('ecom-product')" not in HTML
    assert "menuAdd('ecom-scene')" not in HTML
    assert "menuAdd('ecom-compose')" not in HTML
    assert "menuAdd('ecom-video')" not in HTML
    assert 'ecommerceMenuHost' not in CANVAS_JS
    assert 'ecommerceSubmenu' not in CANVAS_JS
    assert "menuCreateEcommerceWorkflow" not in HTML
    assert "menuCreateEcommerceWorkflow" not in CANVAS_JS


def test_ecommerce_node_implementations_remain_for_existing_canvas_data():
    expected = {
        "ecom-model": "电商模特",
        "ecom-product": "电商产品",
        "ecom-scene": "电商场景",
        "ecom-compose": "A+ 图合成",
        "ecom-video": "电商视频",
    }
    for node_type, label in expected.items():
        assert f"'{node_type}'" in ECOMMERCE_JS
    assert all(label not in HTML for label in expected.values())


def test_ecommerce_nodes_can_still_be_created_individually():
    for node_type in ("ecom-model", "ecom-product", "ecom-scene", "ecom-compose", "ecom-video"):
        assert f"'{node_type}'" in ECOMMERCE_JS

    assert "function createEcommerceWorkflow(point)" not in CANVAS_JS
    assert "function addEcommerceNode(type, point)" in CANVAS_JS
    assert "if(window.CanvasEcommerceNodes?.isType?.(type)) return addEcommerceNode(type, point);" in CANVAS_JS


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


def test_all_ecommerce_nodes_expose_stable_input_roles():
    expected_roles = {
        "ecom-model": "model-reference",
        "ecom-product": "product-reference",
        "ecom-scene": "scene-reference",
        "ecom-video": "video-input",
    }
    for node_type, role in expected_roles.items():
        assert f"'{node_type}':[" in ECOMMERCE_JS
        assert f"role:'{role}'" in ECOMMERCE_JS
    assert "role:'ecom-model'" in ECOMMERCE_JS
    assert "role:'ecom-product'" in ECOMMERCE_JS
    assert "role:'ecom-scene'" in ECOMMERCE_JS


def test_ecommerce_upload_accepts_extension_when_browser_mime_is_empty_and_surfaces_backend_detail():
    assert "IMAGE_NAME_PATTERN.test(name)" in ECOMMERCE_JS
    assert "data?.detail || data?.message" in ECOMMERCE_JS
    assert "图片上传失败（${response.status}）" in ECOMMERCE_JS


def test_ecommerce_media_refs_can_merge_connected_inputs_without_duplicate_urls():
    assert "function mediaRefs(node, options={})" in ECOMMERCE_JS
    assert "const extraItems = Array.isArray(options.extraItems) ? options.extraItems : [];" in ECOMMERCE_JS
    assert "candidate.url === item.url" in ECOMMERCE_JS


def test_ecommerce_workflow_group_contract_is_removed():
    for marker in (
        "normalizeGroupExposedPorts",
        "groupInputPort",
        "groupInputPorts",
        "groupOutputNodes",
        "groupInputEntries",
        "groupWorkflowNodes",
        "groupRuntimeContext",
        "runGroupNode",
        "exposedWorkflow",
        "exposedInputs",
        "exposedOutputs",
        "data-group-run",
        "group-workflow-run",
    ):
        assert marker not in CANVAS_JS
        assert marker not in CANVAS_CSS


def test_canvas_keeps_ecommerce_ports_on_independent_nodes_and_plain_groups():
    assert "const rolePorts = filmPorts.length ? filmPorts : ecommercePorts;" in CANVAS_JS
    assert "data-input-role=\"${escapeAttr(port.id || port.role)}\"" in CANVAS_JS
    assert "function addGroupNode(point)" in CANVAS_JS
    assert "function groupImageItems(group)" in CANVAS_JS


def test_ecommerce_media_sources_use_direct_connections_after_group_removal():
    assert "function mediaRefsFromNode(node, context={})" in CANVAS_JS
    assert "return groupImageItems(node).map(item => ({...item, __index:undefined}));" in CANVAS_JS
    assert "visitedNodes instanceof Set" in CANVAS_JS
    assert "function generatorSources(gen){" in CANVAS_JS
    assert "inputEntriesByNode" not in CANVAS_JS


def test_cascade_runtime_keeps_ecommerce_nodes_but_not_workflow_groups():
    assert "if(node.type === 'ecom-video') return runVideoNode(node.id, runOpts);" in CANVAS_JS
    assert "if(node.type === 'ecom-compose') return runEcommerceComposeNode(node.id, runOpts);" in CANVAS_JS
    assert "'ecom-compose','ecom-video','group'" not in CANVAS_JS
