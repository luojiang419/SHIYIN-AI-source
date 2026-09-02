import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class LookbookNodeFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lookbook = (ROOT / "static" / "js" / "canvas-lookbook-node.js").read_text(encoding="utf-8")
        cls.canvas = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")

    def test_validated_builtin_presets_are_available(self):
        styles = self.lookbook[self.lookbook.index("const STYLES = ["):self.lookbook.index("];", self.lookbook.index("const STYLES = ["))]
        self.assertEqual(re.findall(r"\{id:'([^']+)'", styles), ["fw-cream-cyan-film", "levis-adaptive-campaign"])
        self.assertIn("name:'2026 FW 奶油青蓝胶片抓拍'", styles)
        self.assertIn("name:'李维斯广告·环境自适应纪实'", styles)
        self.assertIn("LEVIS_ADAPTIVE_PROMPT", self.lookbook)

    def test_2026_fw_is_the_default_and_removed_builtin_styles_are_migrated(self):
        self.assertIn("id:'fw-cream-cyan-film'", self.lookbook)
        self.assertIn("16mm/35mm film grain", self.lookbook)
        self.assertIn("DEFAULT_STYLE_ID = 'fw-cream-cyan-film'", self.lookbook)
        self.assertIn("const removedBuiltinStyle=", self.lookbook)
        self.assertIn("node.lookbookStyleName=defaultStyle.name", self.lookbook)
        self.assertIn("node.lookbookStylePrompt=defaultStyle.prompt", self.lookbook)
        self.assertIn("node.lookbookPlan=''", self.lookbook)
        self.assertIn("node.lookbookAutoDecision={}", self.lookbook)

    def test_premium_editorial_research_controls_are_submitted(self):
        self.assertIn("联网研究杂志与品牌时尚大片", self.lookbook)
        self.assertNotIn("研究深度", self.lookbook)
        self.assertNotIn("lookbook_timeout_minutes:", self.canvas)
        self.assertNotIn("lookbook_quality_gate:", self.canvas)
        self.assertNotIn("data-lookbook-field=\"lookbookQualityGate\"", self.lookbook)
        self.assertIn("Lookbook 智能体等待超时", self.canvas)
        self.assertIn("taskNode.lookbookAgentStage = String(task.progress_status)", self.canvas)
        self.assertIn("node.lookbookResearchStatus = String(task.lookbook_research.status)", self.canvas)
        self.assertIn("lookbook_auto_decision", self.canvas)
        self.assertIn("node.lookbookAutoDecision = autoDecision", self.canvas)
        self.assertIn("lookbook_context_signature:String(node.lookbookContextSignature || '')", self.canvas)
        self.assertIn("lookbook_research_images:node.lookbookResearchImages || []", self.canvas)
        self.assertIn("lookbook_research_shots:node.lookbookResearchShots || []", self.canvas)

    def test_brief_and_style_changes_clear_derived_research_without_touching_presets(self):
        self.assertIn("function resetDerivedResearch(node)", self.lookbook)
        self.assertIn("if(key==='lookbookPrompt'||key==='lookbookSearch')resetDerivedResearch(node)", self.lookbook)
        self.assertIn("resetDerivedResearch(pickerNode); Object.assign(pickerNode,{lookbookStyleId:style.id", self.lookbook)
        styles = self.lookbook[self.lookbook.index("const STYLES = ["):self.lookbook.index("];", self.lookbook.index("const STYLES = ["))]
        self.assertEqual(re.findall(r"\{id:'([^']+)'", styles), ["fw-cream-cyan-film", "levis-adaptive-campaign"])

    def test_status_is_rendered_after_run_button_and_quality_gate_is_removed(self):
        body = self.lookbook[self.lookbook.index("function bodyHtml"):self.lookbook.index("function bindGenerationChoices")]
        self.assertLess(body.index("data-lookbook-run"), body.index("lookbook-research-status"))
        self.assertNotIn("lookbookQualityScore", body)
        self.assertNotIn("lookbookQualityGate", body)

    def test_lookbook_uses_image_generation_secondary_choice_menus(self):
        self.assertIn("data-lookbook-generation-settings", self.lookbook)
        self.assertIn("data-lookbook-choice=\"provider\"", self.lookbook)
        self.assertIn("data-lookbook-provider-value", self.lookbook)
        self.assertIn("data-lookbook-choice=\"model\"", self.lookbook)
        self.assertIn("data-lookbook-model-value", self.lookbook)
        self.assertIn("function bindGenerationChoices", self.lookbook)
        self.assertIn("node.apiProvider=resolveProvider", self.lookbook)
        self.assertIn("provider_id:String(node.apiProvider || '')", self.canvas)
        self.assertIn("model:String(node.model || '')", self.canvas)
        self.assertIn(".lookbook-generation-settings .image-quick-choice-panel{z-index:120}", self.css)

    def test_lookbook_choice_menus_are_click_only(self):
        start = self.lookbook.index("function bindGenerationChoices")
        end = self.lookbook.index("function bind(root,node,options={})", start)
        bindings = self.lookbook[start:end]
        self.assertNotIn("pointerenter", bindings)
        self.assertNotIn("pointerleave", bindings)
        self.assertIn("trigger?.addEventListener('click'", bindings)
        self.assertIn(".lookbook-generation-settings .image-quick-choice.open .image-quick-choice-panel", self.css)
        self.assertIn(".lookbook-generation-settings .image-quick-choice:not(.open):hover .image-quick-choice-panel", self.css)
        self.assertIn(".lookbook-generation-settings .image-quick-choice:not(.open):focus-within .image-quick-choice-panel", self.css)

    def test_title_provider_only_owns_lookbook_nodes(self):
        self.assertIn("title:type=>type===TYPE ? 'Lookbook 平面广告' : ''", self.lookbook)
        self.assertIn("const title = lookbookTitle || ecommerceTitle || filmTitle", self.canvas)

    def test_style_picker_has_source_attribution_and_selectable_buttons(self):
        self.assertIn('data-lookbook-choose', self.lookbook)
        self.assertIn('data-lookbook-select', self.lookbook)
        self.assertIn('event.preventDefault();event.stopPropagation();choose(', self.lookbook)
        self.assertIn('参考图优先 · 动作/情绪先行 · 真实环境融合 · 系列化输出', self.lookbook)

    def test_lookbook_actions_have_direct_and_delegated_click_fallbacks(self):
        start = self.lookbook.index("function bind(root,node,options={}){")
        end = self.lookbook.index("function mediaRefs", start)
        body = self.lookbook[start:end]
        self.assertIn("const chooseButton=root.querySelector('[data-lookbook-choose]')", body)
        self.assertIn("button.onclick=handleAction", body)
        self.assertIn("root.addEventListener('click',handleAction,true)", body)
        self.assertIn("modal.style.display='flex'", self.lookbook)
        self.assertNotIn("button.onmousedown=handleAction", body)
        self.assertNotIn("button.onpointerup=handleAction", body)
        self.assertNotIn("document.addEventListener('pointerdown', activateAction, true)", self.lookbook)
        self.assertIn("if(event.type !== 'click') return;", body)
        self.assertIn("if(event.type !== 'click') return;", self.lookbook[self.lookbook.index("function activateAction"):self.lookbook.index("function installActionDelegation")])
        self.assertIn("actionBindings.set(button,{node,options})", self.lookbook)
        self.assertIn("modal.showModal()", self.lookbook)
        self.assertIn("event.preventDefault(); event.stopPropagation();", body)

    def test_selection_hub_keeps_panel_inside_board_and_prefers_above_anchor(self):
        self.assertIn("const availableAbove", self.canvas)
        self.assertIn("selectionHub.style.maxHeight", self.canvas)
        self.assertIn("anchorTop - Math.min(hubRect.height, availableAbove) - gap", self.canvas)
        self.assertIn("z-index:1005", self.css)
        self.assertIn("max-height:calc(100% - 24px)", self.css)

    def test_lookbook_input_ports_have_distinct_roles_and_vertical_positions(self):
        self.assertEqual(self.canvas.count("data-input-role=\"${escapeAttr(port.id || port.role)}\""), 2)
        self.assertIn("--canvas-port-top:${(((index + 1) / (inputPorts.length + 1)) * 100).toFixed(3)}%", self.canvas)
        self.assertIn(".lookbook-node .port.in { left:-29px; top:var(--canvas-port-top,50%); }", self.css)
        self.assertIn(".lookbook-node .port.in::before { content:attr(data-role-label);", self.css)
        self.assertIn(".lookbook-node .node-body { padding-left:74px; }", self.css)
        self.assertIn("left:calc(100% + 7px); right:auto", self.css)
        self.assertIn("white-space:nowrap", self.css)
        self.assertIn("aria-label=\"${escapeAttr(`输入端口：${port.label}`)}\"", self.canvas)

    def test_image_quick_settings_cannot_push_generate_button_outside_panel(self):
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))", self.css)
        self.assertIn(".image-quick-model { min-width:0; grid-column:span 2; }", self.css)
        self.assertIn(".image-quick-camera,.image-quick-generate { min-width:0; width:100%;", self.css)
        self.assertIn("overflow-x:hidden", self.css)

    def test_static_cache_keys_are_bumped_for_the_fix(self):
        self.assertIn("canvas-lookbook-node.js?v=2026.09.02.lookbook.26", self.html)
        self.assertIn("canvas.css?v=2026.08.31.selection-hub-layout.1&rev=20260902.1", self.html)
        self.assertIn("canvas.js?v=2026.08.21.bulk-import-grid.1&rev=20260902.7", self.html)
        self.assertIn("feature=lookbook-picker.1", self.html)
        self.assertIn("feature=lookbook-output-node.1", self.html)
        self.assertIn("feature=lookbook-multi-run.1", self.html)
        self.assertIn("feature=picker-dialog-top-layer.1", self.html)
        self.assertIn("feature=premium-editorial-research.1", self.html)
        self.assertIn("feature=lookbook-agent.1", self.html)
        self.assertIn("feature=lookbook-count.1", self.html)
        self.assertIn("feature=yangpeilin-methods.1", self.html)
        self.assertIn("feature=remove-output-hint.1", self.html)
        self.assertIn("feature=lookbook-single-dispatch.1", self.html)
        self.assertIn("feature=fw-reference-film.1", self.html)
        self.assertIn("feature=fw-natural-sun-grain.1", self.html)
        self.assertIn("feature=fw-model-identity.1", self.html)
        self.assertIn("feature=lookbook-reference-type-ownership.1", self.html)
        self.assertIn("feature=lookbook-validated-presets-only.1", self.html)
        self.assertIn("feature=lookbook-research-evidence.1", self.html)
        self.assertIn("feature=levis-adaptive-campaign.2", self.html)

    def test_lookbook_results_are_rendered_in_output_node(self):
        self.assertNotIn("生成结果已发送到右侧输出节点", self.lookbook)
        self.assertNotIn("生成结果将显示在右侧输出节点", self.lookbook)
        self.assertNotIn("ecom-node-result-empty", self.lookbook)
        self.assertNotIn('ecom-node-result-grid">${outputs.map', self.lookbook)
        self.assertIn('data-lookbook-run aria-busy="${node.running?\'true\':\'false\'}"', self.lookbook)

    def test_lookbook_runs_create_independent_pending_tasks(self):
        start = self.canvas.index("async function runLookbookNode")
        end = self.canvas.index("function bindClassicEcommerceNode", start)
        body = self.canvas[start:end]
        self.assertNotIn("node.running && !opts.cascade", body)
        self.assertIn("outputForNode(node,520,true)", body)
        self.assertIn("canvasTaskType:'ecommerce-lookbook'", body)
        self.assertIn("out._pending = [...(out._pending || []),", body)
        self.assertIn("setTimeout(() =>", body)
        self.assertIn("pollEcommerceLookbookTask(taskId,{cascadeTargetId})", body)
        self.assertIn("p.canvasTaskType === 'ecommerce-lookbook'", self.canvas)

    def test_lookbook_connected_inputs_preserve_semantic_reference_types(self):
        self.assertIn("const referenceTypes = {'lookbook-person':'subject'", self.canvas)
        self.assertIn("reference_type:referenceTypes[entry.connection.inputRole] || 'prop'", self.canvas)

    def test_lookbook_generation_uses_node_count_instead_of_legacy_two_default(self):
        start = self.canvas.index("async function runLookbookNode")
        end = self.canvas.index("function bindClassicEcommerceNode", start)
        body = self.canvas[start:end]
        self.assertIn("window.CanvasLookbookNode?.normalize?.(node)", body)
        self.assertIn("Number(node.count || 4)", body)
        self.assertNotIn("Number(node.count || 2)", body)
        self.assertIn("count, parent_task_id:''", body)

    def test_lookbook_submission_uses_stage_aware_polling(self):
        start = self.canvas.index("async function runLookbookNode")
        end = self.canvas.index("function bindClassicEcommerceNode", start)
        body = self.canvas[start:end]
        self.assertIn("const hasBrief = Boolean(String(node.lookbookPrompt || '').trim())", body)
        self.assertIn("已读取人物与场景参考，准备快速生成生活化随拍系列", body)
        self.assertIn("await pollEcommerceLookbookTask(taskId,{cascadeTargetId})", body)

    def test_new_lookbook_defaults_to_four_coordinated_images(self):
        self.assertIn("count:4,generatedOutputs", self.lookbook)


if __name__ == "__main__":
    unittest.main()
