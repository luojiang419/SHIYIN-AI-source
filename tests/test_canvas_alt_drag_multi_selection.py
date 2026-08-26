from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIC_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")


def _body(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_classic_alt_drag_duplicates_the_active_multi_selection_and_selects_all_copies():
    duplicate = _body(CLASSIC_JS, "function duplicateNodesForAltDrag", "function collectClassicClipboardNode")
    drag = _body(CLASSIC_JS, "function startNodeDrag", "function onNodeDrag")

    assert "selected.has(node?.id) && selected.size > 1" in duplicate
    assert "selectedSourceIds.map(id => nodes.find(item => item.id === id))" in duplicate
    assert "isMultiSelection || node.type === 'group' || node.type === 'promptGroup'" in duplicate
    assert "return {primary:copies.find(copy => copy.id === idMap.get(node.id)) || copies[0], copies};" in duplicate
    assert "copies.filter(Boolean).forEach(item => selected.add(item.id));" in drag


def test_smart_alt_drag_keeps_multi_selection_state_for_group_drag():
    duplicate = _body(SMART_JS, "function duplicateForAltDrag", "function shellPoint")
    drag = _body(SMART_JS, "const beginNodeDrag = e =>", "el.querySelectorAll('.node-port')")

    assert "sourceNodes.some(isSmartGroupNode) || ids.length > 1" in duplicate
    assert "copies.forEach(copy => nodeIndex.set(copy.id, copy));" in duplicate
    assert "selectedIds = copies.length > 1 ? copies.map(copy => copy.id) : [];" in duplicate
    assert "let dragIds = selectedIds.includes(node.id) ? selectedIds.slice() : [node.id];" in drag
