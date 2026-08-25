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


def test_canvas_declares_group_exposed_ports_and_maps_group_connections_to_child_roles():
    assert "function normalizeGroupExposedPorts(group)" in CANVAS_JS
    assert "groupInputPortId(node.id, port.role)" in CANVAS_JS
    assert "targetId:node.id" in CANVAS_JS
    assert "targetRole:port.role || ''" in CANVAS_JS
    assert "if(to.type === 'group')" in CANVAS_JS
    assert "const exposed = groupInputPort(to, inputRole)" in CANVAS_JS
    assert "return canConnect(fromId, exposed.targetId, exposed.targetRole || '')" in CANVAS_JS


def test_canvas_renders_role_ports_for_single_input_nodes_and_groups():
    assert "const groupPorts = node.type === 'group' ? groupInputPorts(node) : [];" in CANVAS_JS
    assert "const rolePorts = filmPorts.length ? filmPorts : ecommercePorts.length ? ecommercePorts : groupPorts;" in CANVAS_JS
    assert "data-input-role=\"${escapeAttr(port.id || port.role)}\"" in CANVAS_JS
    assert ".group-node .group-role-port" in CANVAS_CSS


def test_group_runtime_collects_external_inputs_and_runs_internal_ecommerce_topology():
    assert "function groupInputEntries(group, context={})" in CANVAS_JS
    assert "entriesByNode.set(port.targetId, entries)" in CANVAS_JS
    assert "function groupWorkflowNodes(group)" in CANVAS_JS
    assert "['ecom-compose','ecom-video'].includes(node.type)" in CANVAS_JS
    assert "function runGroupNode(groupId, opts={})" in CANVAS_JS
    assert "inputEntriesByNode:groupInputEntries(group, context)" in CANVAS_JS
    assert "await runEcommerceComposeNode(child.id, childOpts)" in CANVAS_JS
    assert "await runVideoNode(child.id, childOpts)" in CANVAS_JS
    assert "嵌套工作流组存在循环引用" in CANVAS_JS


def test_group_outputs_are_recursive_and_injected_inputs_reach_video_nodes():
    assert "function mediaRefsFromNode(node, context={})" in CANVAS_JS
    assert "groupOutputNodes(node)" in CANVAS_JS
    assert "visitedNodes instanceof Set" in CANVAS_JS
    assert "function generatorSources(gen, context={})" in CANVAS_JS
    assert "context.inputEntriesByNode.get(gen.id)" in CANVAS_JS
    assert "type:'groupInput'" in CANVAS_JS
    assert "generatorSources(node, opts)" in CANVAS_JS
    assert "appendOutputImagesWithoutDuplicates(output, groupRefs)" in CANVAS_JS


def test_group_has_a_user_visible_run_control_and_is_supported_by_cascade_runtime():
    assert "data-group-run" in CANVAS_JS
    assert "runGroupNode(node.id)" in CANVAS_JS
    assert "'group'].includes(node.type)" in CANVAS_JS
    assert "if(node.type === 'group') return runGroupNode(node.id, runOpts);" in CANVAS_JS
    assert "'ecom-compose','ecom-video','group'" in CANVAS_JS
    assert ".group-workflow-run" in CANVAS_CSS
