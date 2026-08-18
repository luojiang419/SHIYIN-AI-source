import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class SmartCanvasGenerationSlotContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smart_js = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.smart_css = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static" / "js" / "i18n" / "smart-canvas.js").read_text(encoding="utf-8")

    def test_batch_tasks_create_stable_generation_slots(self):
        self.assertIn("function initializeSmartGenerationSlots(node, tasks", self.smart_js)
        self.assertIn("slotId", self.smart_js)
        self.assertGreaterEqual(self.smart_js.count("initializeSmartGenerationSlots("), 3)

    def test_success_and_failure_update_the_original_slot(self):
        self.assertIn("function markSmartGenerationSlotFailed(node, task, error", self.smart_js)
        finalize_start = self.smart_js.index("function finalizeSmartPendingTask(node, taskId")
        finalize_end = self.smart_js.index("async function resumeSmartPendingNode", finalize_start)
        finalize_body = self.smart_js[finalize_start:finalize_end]
        self.assertIn("slotId", finalize_body)
        self.assertIn("slot.status = 'success'", finalize_body)
        self.assertIn("rebuildSmartGenerationSlotImages(node)", finalize_body)

        rebuild_start = self.smart_js.index("function rebuildSmartGenerationSlotImages(node)")
        rebuild_end = self.smart_js.index("function settleSmartGenerationSlots", rebuild_start)
        self.assertNotIn("cleanHistoryImages(images)", self.smart_js[rebuild_start:rebuild_end])

    def test_failed_slot_has_retry_and_delete_actions(self):
        self.assertIn("data-generation-slot-retry", self.smart_js)
        self.assertIn("data-generation-slot-delete", self.smart_js)
        self.assertIn("async function retrySmartGenerationSlot(nodeId, slotId)", self.smart_js)
        self.assertIn("function deleteSmartGenerationSlot(nodeId, slotId)", self.smart_js)
        self.assertIn(".generation-slot-error", self.smart_css)

    def test_retry_submits_one_image_and_keeps_slot_id(self):
        retry_start = self.smart_js.index("async function retrySmartGenerationSlot(nodeId, slotId)")
        retry_end = self.smart_js.index("function deleteSmartGenerationSlot", retry_start)
        retry_body = self.smart_js[retry_start:retry_end]
        self.assertIn("count:1", retry_body)
        self.assertIn("task.slotId = slotId", retry_body)
        self.assertIn("slot.status = 'loading'", retry_body)

    def test_slot_copy_is_localized(self):
        for key in ("smart.slotGenerating", "smart.slotFailed", "smart.retrySlot", "smart.deleteSlot"):
            self.assertIn(f'"{key}"', self.i18n)


if __name__ == "__main__":
    unittest.main()
