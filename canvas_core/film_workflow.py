"""无限画布到 film 的仅本机工作流适配。连线决定脚本来源，不接受任意磁盘路径。"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

PREPARE = "film-prepare-assets"
CONFIRM = "film-confirm-shots"
WORKFLOW_PORTS = tuple(range(3211, 3220))


class FilmWorkflowUnavailable(ValueError):
    """仅连接发现可重试，不能据此重放生成请求。"""


def workflow_context(graph: dict, node_id: str) -> tuple[dict, dict, list[dict]]:
    nodes = {str(n.get("id")): n for n in graph.get("nodes", []) if isinstance(n, dict)}
    edges = graph.get("connections", [])
    node = nodes.get(node_id)
    if not node or node.get("type") not in {PREPARE, CONFIRM, "film-video"}:
        raise ValueError("请选择影视工作流节点")
    current = node
    for expected in ({PREPARE: [], CONFIRM: [PREPARE], "film-video": [CONFIRM, PREPARE]}[node["type"]]):
        sources = [nodes.get(e.get("from"), {}) for e in edges if e.get("to") == current["id"]]
        sources = [n for n in sources if n.get("type") == expected]
        if len(sources) != 1:
            raise ValueError("请按准备资产 → 确认镜头 → 视频生成连接唯一的上游节点")
        current = sources[0]
    roots = [nodes.get(e.get("from"), {}) for e in edges if e.get("to") == current["id"]]
    roots = [n for n in roots if n.get("type") == "group" and not n.get("workflowFunctionGroup")]
    if len(roots) != 1:
        raise ValueError("准备资产需要连接一个图片组；可先将多组图片合并")
    root = roots[0]
    frames, visited = [], set()

    def visit(group):
        if group.get("id") in visited:
            raise ValueError("图片组中存在循环分组")
        visited.add(group.get("id"))
        for item_id in group.get("items", []):
            item = nodes.get(item_id, {})
            if item.get("type") == "group":
                visit(item)
            elif item.get("type") == "image" and item.get("url") and item.get("mediaKind", "image") == "image":
                frames.append(item)
    visit(root)
    if not frames:
        raise ValueError("图片组没有有效图片")
    return current, root, frames


class FilmWorkflowProxy:
    def __init__(self, *, resolve_media: Callable, media_url: Callable, media_root: str, allowed_roots: list[str], port: int | None = None):
        self.resolve_media, self.media_url = resolve_media, media_url
        self.media_root = Path(media_root)
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        self.ports = (port,) if port is not None else WORKFLOW_PORTS
        self.base = f"http://127.0.0.1:{self.ports[0]}"
        self.token = ""
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _discover(self, project_id: str | None) -> dict:
        def probe(port):
            base = f"http://127.0.0.1:{port}"
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(base + "/capabilities", timeout=1) as response:
                    data = json.loads(response.read(64 * 1024))
                if isinstance(data, dict) and data.get("app") == "filmstoryboard":
                    return base, data
            except (OSError, ValueError):
                pass
            return None

        with ThreadPoolExecutor(max_workers=len(self.ports)) as pool:
            found = [value for value in pool.map(probe, self.ports) if value]
        supported = [(base, data) for base, data in found
                     if data.get("workflow_version") == 1 and data.get("project_id") and data.get("token")]
        matching = [(base, data) for base, data in supported if not project_id or data["project_id"] == project_id]
        if not matching:
            if supported:
                raise ValueError("请在 film 中打开此画布对应的源项目，然后点击同步 / 刷新")
            if found:
                raise ValueError("film 版本不支持三步工作流，请更新 film")
            raise FilmWorkflowUnavailable("尚未连接到 film 影视工作流。请运行新版 film 并打开源项目，画布将自动重连；也可点击同步 / 刷新。")
        if not project_id and len({data["project_id"] for _, data in matching}) > 1:
            raise ValueError("检测到多个 film 项目，请仅保留目标项目，或从 film 导出画板以指定源项目")
        self.base, capabilities = matching[0]
        self.token = str(capabilities["token"])
        return capabilities

    def _request(self, path: str, body: dict | None = None):
        request = urllib.request.Request(self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "X-Workflow-Token": self.token})
        try:
            return self.opener.open(request, timeout=120 if body else 15)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("detail", str(exc))
            except (ValueError, AttributeError):
                detail = str(exc)
            raise ValueError(detail) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise FilmWorkflowUnavailable("film 工作流连接中断，请确认 film 源项目仍打开后点击同步 / 刷新") from exc

    def _image(self, url: str) -> str:
        path = self.resolve_media(url)
        if not path:
            raise ValueError("请先将图片导入本地画布再连接工作流")
        resolved = Path(path).resolve()
        if not any(resolved.is_relative_to(root) for root in self.allowed_roots) or not resolved.is_file():
            raise ValueError("工作流图片不在当前账号的媒体目录中")
        if resolved.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("单张图片不能超过 100MB")
        return base64.b64encode(resolved.read_bytes()).decode("ascii")

    def execute(self, payload: dict, graph: dict, canvas_id: str) -> dict:
        node_id = str(payload.get("node_id", ""))
        prepare, group, frames = workflow_context(graph, node_id)
        capabilities = self._discover(group.get("bridgeProjectId") or prepare.get("workflowProjectId"))
        project_id = group.get("bridgeProjectId") or prepare.get("workflowProjectId") or capabilities.get("project_id")
        if project_id != capabilities.get("project_id"):
            raise ValueError("请在 film 中打开此画布对应的源项目")
        action = payload.get("action", "snapshot")
        node_type = next(n["type"] for n in graph["nodes"] if n["id"] == node_id)
        if action == "generate" and node_type != "film-video":
            raise ValueError("请从视频生成节点提交镜头")
        body = {k: v for k, v in payload.items() if k in {"action", "parameters", "selection", "model", "shot_id", "task_id", "request_id", "job_id", "confirmed", "asset_id", "asset_type", "subject_id", "decision", "format", "prompt", "slot", "name", "element_id", "selected"}}
        body.update(project_id=project_id, script_id=prepare.get("workflowScriptId", ""))
        if action == "sync":
            body["source_board_id"] = group.get("bridgeBoardId", "")
            body.update(group_key=str(prepare.get("workflowSourceKey") or f"{canvas_id}:{prepare['id']}:{group['id']}"), name=group.get("title") or group.get("bridgeBoardName") or "画布脚本")
            body["frames"] = [{"id": n.get("bridgeFrameStableId") or n["id"], "source_asset_id": n.get("bridgeSourceAssetId", ""), "name": n.get("name", ""),
                "caption": n.get("bridgeCaption", ""), "data": self._image(n["url"])} for n in frames]
            if sum(len(n["data"]) for n in body["frames"]) > 240 * 1024 * 1024:
                raise ValueError("图片组超过单次工作流传输限制，请拆分图片组")
        if action == "import-asset":
            body["asset"] = {"data": self._image(str(payload.get("asset_url", "")))}
        with self._request("/workflow", body) as response:
            result = json.load(response)
        if not result.get("ok"):
            raise ValueError(result.get("detail") or "film 工作流请求失败")
        result["project_id"] = project_id
        return self._materialize(result)

    def _materialize(self, value: Any):
        if isinstance(value, list):
            return [self._materialize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._materialize(item) for key, item in value.items()}
        if not isinstance(value, str) or not re.fullmatch(r"/media/[a-f0-9]{64}\.(png|jpg|jpeg|webp|gif|bmp|mp4|webm|mov|mp3|wav)", value):
            return value
        self.media_root.mkdir(parents=True, exist_ok=True)
        target = self.media_root / ("film_" + value.rsplit("/", 1)[1])
        if not target.is_file():
            # 写入临时文件再替换，失败时不会留下被当成完整媒体的半文件。
            import tempfile
            fd, temp = tempfile.mkstemp(dir=self.media_root, suffix=".part")
            try:
                with os.fdopen(fd, "wb") as out, self._request(value) as response:
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 2 * 1024 * 1024 * 1024:
                            raise ValueError("film 单个输出超过 2GB")
                        out.write(chunk)
                os.replace(temp, target)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return self.media_url(os.fspath(target))
