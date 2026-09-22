"""账号隔离的可灵网页任务与单次提交许可。"""
import copy
import secrets
import time
import os
import shutil
import subprocess
import asyncio
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field


class WebReference(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    kind: str
    name: str = Field(default="", max_length=200)


class WebSettings(BaseModel):
    duration: int = Field(default=5, ge=3, le=15)
    resolution: Literal['720p', '1080p', '4K'] = '1080p'
    aspect_ratio: Literal['16:9', '9:16', '1:1', 'auto'] = '16:9'
    generate_audio: bool = True


class WebDraft(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    references: list[WebReference] = Field(default_factory=list, max_length=10)
    node_id: str = Field(default="", max_length=200)
    auto_submit: bool = False
    settings: WebSettings = Field(default_factory=WebSettings)


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
            elif item['status'] == 'submitting' and now - item['submit_at'] > 90:
                item.update(status='unknown', message='提交回执中断，请检查可灵历史记录；禁止自动重试')

    def create(self, owner, draft):
        with self.lock:
            self.clean()
            if any(x["owner"] == owner and x["status"] in {"queued", "filling", "submitting"} for x in self.items.values()):
                raise HTTPException(409, "已有草稿等待填充，请先处理或取消")
            if len(self.items) >= 1000:
                raise HTTPException(429, "网页填充队列已满，请稍后重试")
            item = {**draft, "id": secrets.token_urlsafe(18), "owner": owner,
                    "ticket": secrets.token_urlsafe(32),
                    "status": "queued", "created_at": time.time(), "message": "等待 Chrome 插件接收"}
            self.items[item["id"]] = item
            return self.public(item)

    @staticmethod
    def public(item):
        return copy.deepcopy({k: v for k, v in item.items() if k not in {"owner", "lease", "ticket"}})

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
            allowed = {'submitted', 'unknown'} if item['status'] in {'submitting', 'unknown', 'submitted'} else {'filled', 'failed'}
            if result.status not in allowed:
                raise HTTPException(422, "仅允许填充成功或失败状态")
            if item["status"] not in {"filling", 'submitting', 'unknown', result.status}:
                raise HTTPException(409, "草稿状态已改变")
            item.update(status=result.status, message=result.message)
            return self.public(item)

    def permit(self, owner, key, lease):
        with self.lock:
            item = self.get(owner, key)
            if not lease or not secrets.compare_digest(item.get('lease', ''), lease):
                raise HTTPException(409, '提交凭据不匹配')
            if not item.get('auto_submit') or item['status'] != 'filling':
                raise HTTPException(409, '该任务未授权自动提交或已经领取提交许可；不得重试')
            item.update(status='submitting', submit_at=time.time(), message='正在提交可灵；请勿重复生成')
            return {'permitted': True}


def create_router(identity, resolve_media=None):
    router = APIRouter(prefix="/api/kling-web", tags=["kling-web"])
    queue = DraftQueue()
    channels = {}

    def channel_item(request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        channel = channels.get(token)
        if not channel or channel['expires'] < time.time():
            channels.pop(token, None)
            raise HTTPException(401, '后台连接已过期，请从画布重新发送')
        channel['seen'] = time.time()
        return channel

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
        owner = identity(request).account_id
        result = queue.create(owner, payload.model_dump())
        item = queue.get(owner, result['id'])
        return {**result, 'ticket': item['ticket']}

    def ticket_item(request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        with queue.lock:
            queue.clean()
            item = next((x for x in queue.items.values() if token and secrets.compare_digest(x['ticket'], token)), None)
            if not item:
                raise HTTPException(401, '任务连接凭据无效或已过期，请从画布重新发送')
            return item

    router.bridge_account = lambda request: (channel_item(request) if request.url.path.endswith('/transport/poll') else ticket_item(request))['owner']

    @router.post('/transport/channel')
    async def channel_register(request: Request):
        item = ticket_item(request)
        now = time.time()
        for token, channel in list(channels.items()):
            if channel['expires'] < now or channel['owner'] == item['owner']:
                del channels[token]
        token = secrets.token_urlsafe(32)
        channels[token] = {'owner': item['owner'], 'seen': now, 'expires': now + 86400}
        return {'channel': token}

    @router.post('/transport/poll')
    async def channel_poll(request: Request):
        owner = channel_item(request)['owner']
        with queue.lock:
            queue.clean()
            item = next((x for x in queue.items.values() if x['owner'] == owner and x['status'] == 'queued'), None)
            return {'ticket': item['ticket'] if item else None}

    @router.get('/connect', response_class=HTMLResponse)
    async def connect():
        return HTMLResponse('<!doctype html><meta charset="utf-8"><title>拾影 · 可灵任务交接</title><h2>正在交给可灵插件…</h2><p id="status">请保持 Chrome 中的可灵账号已登录。若此页未自动关闭，请在 Chrome 扩展管理中刷新拾影可灵插件至最新版。</p>', headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})

    @router.post('/drafts/{key}/open')
    async def open_chrome(key: str, request: Request):
        if request.client.host not in {'127.0.0.1', '::1', 'testclient'}:
            raise HTTPException(403, '远程 Web 请在当前浏览器打开交接页')
        item = queue.get(identity(request).account_id, key)
        port = request.url.port or 80
        url = f'http://127.0.0.1:{port}/api/kling-web/connect#' + item['ticket']
        candidates = [shutil.which('chrome')]
        for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            candidates.append(str(Path(os.environ.get(base, '')) / 'Google/Chrome/Application/chrome.exe'))
        chrome = next((p for p in candidates if p and Path(p).is_file()), None)
        if not chrome:
            raise HTTPException(409, '未找到 Chrome，请在 Chrome 中打开 Web 画布')
        def launch():
            startup = None
            if os.name == 'nt':
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE，不激活窗口。
            subprocess.Popen([chrome, '--new-window', '--start-minimized', url],
                             startupinfo=startup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        connected = any(c['owner'] == item['owner'] and c['expires'] > time.time() and time.time()-c['seen'] < 75 for c in channels.values())
        if connected:
            async def fallback():
                await asyncio.sleep(40)
                # Chrome 若刚退出，心跳仍可能新鲜；仅尚未领取的任务允许唤起。
                if item['status'] == 'queued' and time.time()-item['created_at'] < 300:
                    launch()
            asyncio.create_task(fallback())
            return {'opened': False, 'background': True}
        launch()
        return {'opened': True, 'background': True}

    @router.post('/transport/claim')
    async def ticket_claim(request: Request):
        with queue.lock:
            item = ticket_item(request)
            if item['status'] != 'queued':
                return {'draft': None}
            return {'draft': queue.claim(item['owner'])}

    @router.post('/transport/result')
    async def ticket_result(payload: WebResult, request: Request):
        item = ticket_item(request)
        return queue.finish(item['owner'], item['id'], payload)

    @router.post('/transport/submit-permit')
    async def ticket_permit(payload: WebResult, request: Request):
        item = ticket_item(request)
        return queue.permit(item['owner'], item['id'], payload.lease)

    @router.get('/transport/media/{index}')
    async def ticket_media(index: int, request: Request):
        item = ticket_item(request)
        if item['status'] != 'filling' or not 0 <= index < len(item['references']):
            raise HTTPException(403, '该素材未授权或任务已经结束')
        path = resolve_media(item['references'][index]['url']) if resolve_media else None
        if not path:
            raise HTTPException(404, '任务素材不存在')
        return FileResponse(path, headers={'Cache-Control':'no-store'})

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

    @router.post('/drafts/{key}/submit-permit')
    async def permit(key: str, payload: WebResult, request: Request):
        return queue.permit(identity(request).account_id, key, payload.lease)

    @router.delete("/drafts/{key}")
    async def cancel(key: str, request: Request):
        with queue.lock:
            item = queue.get(identity(request).account_id, key)
            if item["status"] in {"filling", 'submitting', 'submitted', 'unknown'}:
                raise HTTPException(409, "插件正在填充，请先在浏览器查看结果")
            item.update(status="cancelled", message="已取消")
            return queue.public(item)

    return router
