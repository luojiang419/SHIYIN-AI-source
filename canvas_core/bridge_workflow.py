"""画板影视流程图。仅显式启用 workflow 的导出创建功能组。"""
from __future__ import annotations

from typing import Any, Callable, Mapping

STEPS = (("film-prepare-assets", "准备资产"), ("film-confirm-shots", "确认镜头"), ("film-video", "视频生成"))


def ensure_workflow(canvas: dict[str, Any], group: dict[str, Any], manifest: Mapping[str, Any], make_id: Callable[[str], str]) -> list[str]:
    config = manifest.get("canvas") or {}
    if config.get("workflow") != "film-production-v1":
        return []
    source = manifest.get("source") or {}
    group["title"] = str((manifest.get("storyboard") or {}).get("board_name") or "画板")
    group["bridgeProjectId"] = str(source.get("project_id") or "")
    nodes, edges = canvas["nodes"], canvas["connections"]
    ids = []
    previous = group["id"]
    for index, (kind, label) in enumerate(STEPS):
        key = f"{group['id']}:{kind}"
        node = next((n for n in nodes if n.get("workflowKey") == key and n.get("type") == kind), None)
        # 重发只创建缺失节点；用户断开的边、编辑参数和位置不能被重新覆盖。
        if node is None:
            x = float(group.get("x", 120)) + float(group.get("w", 600)) + 160 + index * 1060
            y = float(group.get("y", 120))
            node = {"id": make_id("film"), "type": kind, "x": x + 24, "y": y + 64, "w": 520 if kind == "film-video" else 960,
                    "workflowKey": key, "workflowSourceGroupId": group["id"], "workflowProjectId": group["bridgeProjectId"],
                    "workflowBoardId": group.get("bridgeBoardId", ""), "workflowParameters": {}}
            nodes.append(node)
            if kind == "film-video":
                nodes.append({"id": make_id("fg"), "type": "group", "title": label, "x": x, "y": y,
                              "w": 1008, "h": 790, "items": [node["id"]], "workflowFunctionGroup": True,
                              "workflowOwnerId": node["id"]})
            edges.append({"id": make_id("c"), "from": previous, "to": node["id"], "inputRole": "workflow"})
        ids.append(node["id"])
        previous = node["id"]
    group["workflowNodeIds"] = ids
    # 只拆除旧版自动创建的单节点背景；保留用户分组、额外成员与外部连线。
    removable = {n["id"] for n in nodes if n.get("type") == "group" and n.get("workflowFunctionGroup")
                 and n.get("workflowOwnerId") in ids[:2] and n.get("items") == [n.get("workflowOwnerId")]
                 and not any(e.get("from") == n["id"] or e.get("to") == n["id"] for e in edges)
                 and not any(n["id"] in (parent.get("items") or []) for parent in nodes if parent.get("type") == "group")}
    nodes[:] = [n for n in nodes if n.get("id") not in removable]
    return ids
