import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ChatUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "gpt-chat.html").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static" / "js" / "i18n" / "studio.js").read_text(encoding="utf-8")

    def test_agent_uses_executing_label_and_progress_steps(self):
        self.assertIn('"chat.agentWorking": { zh: "正在执行", en: "Executing" }', self.i18n)
        self.assertIn("function startAgentProgressBubble(assistantBubble, hasReferences)", self.html)
        self.assertIn("正在读取本轮消息和参考图…", self.html)
        self.assertIn("const stopAgentProgress = mode === 'agent'", self.html)

    def test_all_message_bubbles_have_context_delete_and_image_menu_stops_bubbling(self):
        self.assertIn("showMessageContextMenu(event.clientX, event.clientY, msg)", self.html)
        self.assertIn("function deleteChatMessage(msg)", self.html)
        self.assertIn("data-context-action=\"delete-message\"", self.html)
        self.assertIn("event.stopPropagation();\n                        showImageContextMenu", self.html)


if __name__ == "__main__":
    unittest.main()
