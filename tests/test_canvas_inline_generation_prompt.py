import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasInlineGenerationPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static" / "js" / "i18n" / "canvas.js").read_text(encoding="utf-8")

    def test_new_image_and_video_nodes_persist_a_direct_prompt(self):
        image_factory = re.search(r"function addGeneratorNode\(point\)\{(?P<body>.*?)\n\}", self.javascript, re.DOTALL)
        video_factory = re.search(r"function addVideoNode\(point\)\{(?P<body>.*?)\n\}", self.javascript, re.DOTALL)
        self.assertIsNotNone(image_factory)
        self.assertIsNotNone(video_factory)
        self.assertIn("prompt:''", image_factory.group("body"))
        self.assertIn("prompt:''", video_factory.group("body"))

    def test_both_generator_bodies_render_and_bind_the_inline_prompt(self):
        self.assertEqual(self.javascript.count("${generatorInlinePromptHtml(node, promptInputs.length)}"), 2)
        self.assertEqual(self.javascript.count("bindGeneratorInlinePrompt(wrap, node);"), 2)
        self.assertIn('class="generator-prompt-input"', self.javascript)
        self.assertIn("node.prompt = input.value", self.javascript)

    def test_direct_prompt_is_combined_before_connected_prompts_for_every_runner(self):
        self.assertIn("function combinedGeneratorPrompt(node, sources=[])", self.javascript)
        self.assertIn("[String(node?.prompt || '').trim(), ...(sources || []).map", self.javascript)
        self.assertEqual(self.javascript.count("const prompt = combinedGeneratorPrompt("), 3)

    def test_prompt_editor_has_layout_and_bilingual_copy(self):
        self.assertIn(".generator-inline-prompt {", self.styles)
        self.assertIn(".generator-prompt-input {", self.styles)
        self.assertIn('"canvas.generatorPromptPlaceholder"', self.i18n)
        self.assertIn('"canvas.connectedPromptCount"', self.i18n)

    def test_image_quick_generate_preserves_source_and_creates_output_node(self):
        run = re.search(
            r"async function runImageNodeQuickGenerate\(nodeId\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(run)
        body = run.group("body")
        self.assertIn("out = outputForNode(node, 460, true)", body)
        self.assertIn("makePendingForRun(pendingId, run, node", body)
        self.assertLess(body.index("out = outputForNode(node, 460, true)"), body.index("fetch('/api/online-image'"))
        self.assertLess(body.index("refreshRunNodes(node, out)"), body.index("fetch('/api/online-image'"))
        self.assertLess(body.index("scheduleSave()"), body.index("fetch('/api/online-image'"))
        self.assertIn("appendOutputImagesWithoutDuplicates(out, outputItems", body)
        self.assertIn("out._pending = (out._pending || []).filter", body)
        self.assertNotIn("node.url = images[0]", body)
        self.assertNotIn("node.generatedOutputs = images", body)

    def test_image_quick_output_connection_survives_sanitization(self):
        can_connect = re.search(
            r"function canConnect\(fromId, toId, inputRole=''\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        sanitize = re.search(
            r"function sanitizeConnections\(\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(can_connect)
        self.assertIsNotNone(sanitize)
        self.assertIn("if(from.type === 'image' && to.type === 'output') return true", can_connect.group("body"))
        self.assertIn("filter(c => canConnect(c.from, c.to, c.inputRole || ''))", sanitize.group("body"))

    def test_image_quick_generate_button_reflects_running_state(self):
        prompt = re.search(
            r"function imageNodeQuickPromptHtml\(node\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(prompt)
        body = prompt.group("body")
        self.assertIn("const running = Boolean(node.running)", body)
        self.assertIn("${running ? 'disabled' : ''}", body)
        self.assertIn("${running ? '生成中' : '生成'}", body)


if __name__ == "__main__":
    unittest.main()
