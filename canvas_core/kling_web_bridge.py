"""可灵网页填充队列。只保存当前进程内待处理草稿，绝不提交生成。"""
import copy
import secrets
import time
from threading import RLock
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


class WebReference(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    kind: str
    name: str = Field(default="", max_length=200)


class WebDraft(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    references: list[WebReference] = Field(default_factory=list, max_length=10)
    node_id: str = Field(default="", max_length=200)


class WebResult(BaseModel):
    lease: str
    status: str
    message: str = Field(default="", max_length=2000)


class DraftQueue:
    def __init__(self):
        self.items = {}
        self.lock = RLock()

    def clean(self):
        now = time.time()
        for key, item in list(self.items.items()):
            if now - item["created_at"] > 3600:
                del self.items[key]
            elif item["status"] == "filling" and now - item["claimed_at"] > 300:
                item.update(status="failed", message="插件连接中断，请检查网页后重新填充；不会自动重试")

    def create(self, owner, draft):
        with self.lock:
            self.clean()
            if any(x["owner"] == owner and x["status"] in {"queued", "filling"} for x in self.items.values()):
                raise HTTPException(409, "已有草稿等待填充，请先处理或取消")
            if len(self.items) >= 1000:
                raise HTTPException(429, "网页填充队列已满，请稍后重试")
            item = {**draft, "id": secrets.token_urlsafe(18), "owner": owner,
                    "status": "queued", "created_at": time.time(), "message": "等待 Chrome 插件接收"}
            self.items[item["id"]] = item
            return self.public(item)

    @staticmethod
    def public(item):
        return copy.deepcopy({k: v for k, v in item.items() if k not in {"owner", "lease"}})

    def get(self, owner, key):
        self.clean()
        item = self.items.get(key)
        if not item or item["owner"] != owner:
            raise HTTPException(404, "草稿不存在或已过期")
        return item

    def claim(self, owner):
        with self.lock:
            self.clean()
            item = next((x for x in self.items.values() if x["owner"] == owner and x["status"] == "queued"), None)
            if not item:
                return None
            item.update(status="filling", lease=secrets.token_urlsafe(24), claimed_at=time.time())
            return {**self.public(item), "lease": item["lease"]}

    def finish(self, owner, key, result):
        with self.lock:
            item = self.get(owner, key)
            if not secrets.compare_digest(item.get("lease", ""), result.lease) or not result.lease:
                raise HTTPException(409, "草稿接收凭据不匹配")
            if result.status not in {"filled", "failed"}:
                raise HTTPException(422, "仅允许填充成功或失败状态")
            if item["status"] not in {"filling", result.status}:
                raise HTTPException(409, "草稿状态已改变")
            item.update(status=result.status, message=result.message)
            return self.public(item)


def create_router(identity):
    router = APIRouter(prefix="/api/kling-web", tags=["kling-web"])
    queue = DraftQueue()

    @router.post("/drafts")
    async def create(payload: WebDraft, request: Request):
        for ref in payload.references:
            url = urlsplit(ref.url)
            if ref.kind not in {"image", "video"}:
                raise HTTPException(422, "网页填充目前仅支持图片与视频")
            if url.scheme or url.netloc or not url.path.startswith(("/assets/", "/output/", "/input/")):
                raise HTTPException(422, "请先将参考素材导入本地画布，网页填充只读取当前账号的本地素材")
            if ".." in url.path or "\\" in url.path:
                raise HTTPException(422, "素材路径无效")
        return queue.create(identity(request).account_id, payload.model_dump())

    @router.post("/claim")
    async def claim(request: Request):
        return {"draft": queue.claim(identity(request).account_id)}

    @router.get("/drafts/{key}")
    async def status(key: str, request: Request):
        with queue.lock:
            return queue.public(queue.get(identity(request).account_id, key))

    @router.post("/drafts/{key}/result")
    async def result(key: str, payload: WebResult, request: Request):
        return queue.finish(identity(request).account_id, key, payload)

    @router.delete("/drafts/{key}")
    async def cancel(key: str, request: Request):
        with queue.lock:
            item = queue.get(identity(request).account_id, key)
            if item["status"] == "filling":
                raise HTTPException(409, "插件正在填充，请先在浏览器查看结果")
            item.update(status="cancelled", message="已取消")
            return queue.public(item)

    return router
