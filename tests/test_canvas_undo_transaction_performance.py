import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasUndoTransactionContractTests(unittest.TestCase):
    def test_history_entries_are_snapshot_or_transaction_records(self):
        for source in (CANVAS_JS, SMART_CANVAS_JS):
            self.assertRegex(source, re.compile(r"kind\s*:\s*['\"]snapshot['\"]"))
            self.assertRegex(source, re.compile(r"kind\s*:\s*['\"]transaction['\"]"))
            for field in (
                "createdNodes",
                "deletedNodes",
                "replacedNodes",
                "createdConnections",
                "deletedConnections",
                "selectionBefore",
                "selectionAfter",
            ):
                self.assertIn(field, source)

    def test_classic_history_has_total_byte_budget_and_accounting(self):
        self.assertRegex(CANVAS_JS, re.compile(r"CLASSIC_UNDO_BYTE_LIMIT\s*=\s*\d+"))
        self.assertIn("let undoStackBytes = 0", CANVAS_JS)
        self.assertIn("let redoStackBytes = 0", CANVAS_JS)
        self.assertIn("appendClassicHistoryEntry", CANVAS_JS)
        self.assertRegex(CANVAS_JS, re.compile(r"undoStackBytes\s*[+-]=\s*bytes"))
        self.assertRegex(CANVAS_JS, re.compile(r"redoStackBytes\s*[+-]=\s*bytes"))

    def test_smart_transaction_entries_share_existing_16_mib_limit(self):
        self.assertIn("UNDO_BYTE_LIMIT = 16 * 1024 * 1024", SMART_CANVAS_JS)
        self.assertIn("appendSmartHistoryEntry", SMART_CANVAS_JS)
        self.assertIn("transaction", SMART_CANVAS_JS)
        self.assertIn("undoStackBytes", SMART_CANVAS_JS)
        self.assertIn("redoStackBytes", SMART_CANVAS_JS)

    def test_switching_canvases_clears_history_and_byte_ledgers(self):
        self.assertIn("function clearClassicHistory()", CANVAS_JS)
        self.assertIn("clearClassicHistory();", CANVAS_JS)
        self.assertIn("function clearSmartHistory()", SMART_CANVAS_JS)
        self.assertIn("clearSmartHistory();", SMART_CANVAS_JS)

    def test_classic_structural_paths_use_transaction_boundary(self):
        paths = (
            ("function menuAdd", "function menuCreateFilmWorkflow"),
            ("function pasteNodes", "function selectedWorkflowPayload"),
            ("function addQuickActionNode", "function runMediaQuickAction"),
            ("function createLinkedNode", "function createNodeByType"),
        )
        for start, end in paths:
            section = body(CANVAS_JS, start, end)
            self.assertIn("beginClassicHistoryTransaction", section, start)
            self.assertIn("commitClassicHistoryTransaction", section, start)
            self.assertNotIn("pushUndo()", section, start)

    def test_smart_paste_is_one_transaction_without_full_snapshot(self):
        section = body(SMART_CANVAS_JS, "function pasteNodes", "const SMART_CANVAS_ASSET_INBOX_KEY")
        self.assertIn("beginSmartHistoryTransaction", section)
        self.assertIn("commitSmartHistoryTransaction", section)
        self.assertNotIn("pushUndo()", section)
        self.assertNotIn("snapshotForUndo()", section)

    def test_secondary_structural_creation_and_asset_paste_use_transactions(self):
        classic_workflow = body(CANVAS_JS, "function createFilmWorkflow", "function addH3VideoNode")
        classic_shortcut = body(CANVAS_JS, "function runClassicCanvasShortcutAction", "function syncClassicHeldShortcutActions")
        smart_assets = body(SMART_CANVAS_JS, "function pasteAssetsFromInbox", "function duplicateForAltDrag")
        self.assertIn("beginClassicHistoryTransaction", classic_workflow)
        self.assertNotIn("pushUndo()", classic_workflow)
        self.assertIn("beginClassicHistoryTransaction", classic_shortcut)
        self.assertNotIn("pushUndo()", classic_shortcut)
        self.assertIn("beginSmartHistoryTransaction", smart_assets)
        self.assertNotIn("pushUndo()", smart_assets)
        self.assertNotIn("snapshotForUndo()", smart_assets)

    def test_workflow_import_is_a_structural_transaction(self):
        classic = body(CANVAS_JS, "function insertWorkflowIntoCanvas", "async function importWorkflowFile")
        smart = body(SMART_CANVAS_JS, "function insertSmartWorkflowIntoCanvas", "async function importSmartWorkflowFile")
        self.assertIn("beginClassicHistoryTransaction", classic)
        self.assertIn("commitClassicHistoryTransaction", classic)
        self.assertNotIn("pushUndo()", classic)
        self.assertIn("beginSmartHistoryTransaction", smart)
        self.assertIn("commitSmartHistoryTransaction", smart)
        self.assertNotIn("pushUndo()", smart)
        self.assertNotIn("snapshotForUndo()", smart)

    def test_smart_menu_creation_uses_one_transaction_context(self):
        section = body(SMART_CANVAS_JS, "function createNodeFromMenu", "shell.addEventListener('mousedown'")
        self.assertIn("beginSmartHistoryTransaction", section)
        self.assertIn("commitSmartHistoryTransaction", section)
        self.assertIn("try", section)
        self.assertIn("finally", section)

    def test_smart_structural_transactions_abort_on_exception(self):
        self.assertIn("function abortSmartHistoryTransaction", SMART_CANVAS_JS)
        for start, end in (
            ("function pasteNodes", "const SMART_CANVAS_ASSET_INBOX_KEY"),
            ("function pasteAssetsFromInbox", "function duplicateForAltDrag"),
            ("function insertSmartWorkflowIntoCanvas", "async function importSmartWorkflowFile"),
        ):
            section = body(SMART_CANVAS_JS, start, end)
            self.assertIn("completed", section, start)
            self.assertIn("abortSmartHistoryTransaction", section, start)
            self.assertIn("finally", section, start)

    def test_transactions_capture_selection_before_and_after(self):
        for source, helper in (
            (CANVAS_JS, "commitClassicHistoryTransaction"),
            (SMART_CANVAS_JS, "commitSmartHistoryTransaction"),
        ):
            self.assertIn("selectionBefore", source)
            self.assertIn("selectionAfter", source)
            section = source[source.index(helper):]
            self.assertRegex(section, re.compile(r"selection(?:Before|After)"))

    def test_undo_and_redo_dispatch_both_entry_kinds(self):
        for source, undo, redo in (
            (CANVAS_JS, "function performUndo", "function performRedo"),
            (SMART_CANVAS_JS, "function performUndo", "function performRedo"),
        ):
            undo_body = body(source, undo, redo)
            redo_body = source[source.index(redo):]
            self.assertIn("transaction", undo_body)
            self.assertIn("transaction", redo_body)
            self.assertRegex(undo_body, re.compile(r"[Ss]napshot"))
            self.assertRegex(redo_body, re.compile(r"[Ss]napshot"))

    def test_cross_type_history_keeps_lifo_pop_order(self):
        for source, undo, redo in (
            (CANVAS_JS, "function performUndo", "function performRedo"),
            (SMART_CANVAS_JS, "function performUndo", "function performRedo"),
        ):
            undo_body = body(source, undo, redo)
            redo_body = source[source.index(redo):]
            self.assertRegex(undo_body, re.compile(r"(?:undoStack|history)\.pop\(\)"))
            self.assertRegex(redo_body, re.compile(r"(?:redoStack|history)\.pop\(\)"))
            self.assertRegex(undo_body, re.compile(r"(?:append(?:Classic|Smart)HistoryEntry\(redoStack|appendRedoSnapshot)"))
            self.assertRegex(redo_body, re.compile(r"(?:append(?:Classic|Smart)HistoryEntry\(undoStack|appendUndoSnapshot)"))


if __name__ == "__main__":
    unittest.main()
