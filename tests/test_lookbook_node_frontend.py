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

    def test_builtin_visual_skill_set_is_available_without_network(self):
        self.assertIn("VISUAL_SKILLS_IMAGE_URL = 'https://github.com/smixs/visual-skills/tree/main/image'", self.lookbook)
        for style_id in ("fashion-street-editorial", "visual-ecommerce", "visual-fashion-editorial", "visual-poster", "visual-social"):
            self.assertIn(f"id:'{style_id}'", self.lookbook)
        self.assertIn("skill:'image'", self.lookbook)
        self.assertIn("CC BY 4.0", self.lookbook)

    def test_premium_editorial_research_controls_are_submitted(self):
        self.assertIn("name:'时尚街景'", self.lookbook)
        self.assertIn("lookbookResearchDepth", self.lookbook)
        self.assertIn("研究深度", self.lookbook)
        self.assertIn("联网研究杂志与品牌时尚大片", self.lookbook)
        self.assertIn("lookbook_research_depth:node.lookbookResearchDepth || 'deep'", self.canvas)
        self.assertIn("lookbook_timeout_minutes:Math.max(5,Math.min(60,Number(node.lookbookTimeoutMinutes || 30)))", self.canvas)
        self.assertIn("Lookbook 智能体等待超时", self.canvas)
        self.assertIn("taskNode.lookbookAgentStage = String(task.progress_status)", self.canvas)
        self.assertIn("node.lookbookResearchStatus = String(task.lookbook_research.status)", self.canvas)

    def test_title_provider_only_owns_lookbook_nodes(self):
        self.assertIn("title:type=>type===TYPE ? 'Lookbook 平面广告' : ''", self.lookbook)
        self.assertIn("const title = lookbookTitle || ecommerceTitle || filmTitle", self.canvas)

    def test_style_picker_has_source_attribution_and_selectable_buttons(self):
        self.assertIn('data-lookbook-choose', self.lookbook)
        self.assertIn('data-lookbook-select', self.lookbook)
        self.assertIn('event.preventDefault();event.stopPropagation();choose(', self.lookbook)
        self.assertIn('smixs/visual-skills/image', self.lookbook)

    def test_lookbook_actions_have_direct_and_delegated_click_fallbacks(self):
        start = self.lookbook.index("function bind(root,node,options={}){")
        end = self.lookbook.index("function mediaRefs", start)
        body = self.lookbook[start:end]
        self.assertIn("const chooseButton=root.querySelector('[data-lookbook-choose]')", body)
        self.assertIn("button.onclick=handleAction", body)
        self.assertIn("root.addEventListener('click',handleAction,true)", body)
        self.assertIn("button.onpointerup=handleAction", body)
        self.assertIn("modal.style.display='flex'", self.lookbook)
        self.assertIn("document.addEventListener('pointerdown', activateAction, true)", self.lookbook)
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
        self.assertIn("canvas-lookbook-node.js?v=2026.08.31.lookbook.9", self.html)
        self.assertIn("canvas.css?v=2026.08.31.selection-hub-layout.1&rev=20260831.4", self.html)
        self.assertIn("canvas.js?v=2026.08.21.bulk-import-grid.1&rev=20260831.2", self.html)
        self.assertIn("feature=lookbook-picker.1", self.html)
        self.assertIn("feature=lookbook-output-node.1", self.html)
        self.assertIn("feature=lookbook-multi-run.1", self.html)
        self.assertIn("feature=picker-dialog-top-layer.1", self.html)
        self.assertIn("feature=premium-editorial-research.1", self.html)
        self.assertIn("feature=lookbook-agent.1", self.html)

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
        self.assertIn("completeEcommerceLookbookTask(taskId,task)", body)
        self.assertIn("p.canvasTaskType === 'ecommerce-lookbook'", self.canvas)


if __name__ == "__main__":
    unittest.main()
