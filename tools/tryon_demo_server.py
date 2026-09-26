"""Serve the real e-commerce page with an isolated local try-on demo workspace.

Run only with CANVAS_DATA_DIR and TRYON_DEMO_SEED_PATH pointing at disposable
demo data. This module does not add a route to the normal application entry.
"""

import json
import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

import main


app = main.app
SEED_PATH = Path(os.environ["TRYON_DEMO_SEED_PATH"]).resolve()
DEMO_ACCOUNT = os.environ["TRYON_DEMO_ACCOUNT"]
DEMO_PASSWORD = os.environ["TRYON_DEMO_PASSWORD"]
# This exception exists only in this isolated wrapper, never in the normal app.
main.PUBLIC_HTTP_PATHS.add("/demo/tryon")


@app.get("/demo/tryon", response_class=HTMLResponse)
def open_tryon_demo(request: Request, step: int = 1):
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=404)
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    identity = main.ACCOUNT_STORE.authenticate(DEMO_ACCOUNT, DEMO_PASSWORD)
    if identity is None or identity.account_id != seed["accountId"]:
        raise HTTPException(status_code=503, detail="隔离演示账号不可用")
    token = str(request.cookies.get(main.ACCOUNT_SESSION_COOKIE) or "")
    current = main.ACCOUNT_STORE.resolve_session(token) if token else None
    if current is None or current.account_id != identity.account_id:
        token = main.ACCOUNT_STORE.create_session(identity)
    snapshot = json.loads(seed["settings"])
    snapshot["operation"] = "try_on"
    snapshot.setdefault("options", {}).setdefault("try_on", {})["guide_step"] = max(0, min(3, step - 1))
    payload = json.dumps(
        {"accountId": seed["accountId"], "settings": json.dumps(snapshot, ensure_ascii=False)},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    response = HTMLResponse(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>正在打开自由换衣演示</title><body>正在打开自由换衣页面…"
        f"<script>const seed={payload};"
        "(async()=>{try{"
        "const response=await fetch('/api/auth/status',{cache:'no-store'});"
        "if(!response.ok)throw new Error('请先登录演示账号');"
        "const identity=(await response.json()).account;"
        "if(identity.account_id!==seed.accountId)throw new Error('请使用自由换衣演示账号登录');"
        "localStorage.setItem('studio_ecommerce_settings_v2',seed.settings);"
        "localStorage.setItem('studio_ecommerce_settings_v2:account:'+seed.accountId,seed.settings);"
        "const base=seed.accountId+':ecommerce';"
        "localStorage.removeItem('shiyin-page-recovery-v1:'+base);"
        "await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve();}};"
        "const timeout=setTimeout(finish,1500);"
        "try{const request=indexedDB.open('shiyin-page-state-v1',1);"
        "request.onsuccess=()=>{const db=request.result;"
        "if(!db.objectStoreNames.contains('pages')){db.close();clearTimeout(timeout);finish();return;}"
        "const tx=db.transaction('pages','readwrite');const cursor=tx.objectStore('pages').openCursor();"
        "cursor.onsuccess=()=>{const item=cursor.result;if(!item)return;"
        "const key=String(item.key);if(key===base||key.startsWith(base+'::recovery:'))item.delete();item.continue();};"
        "tx.oncomplete=tx.onerror=()=>{db.close();clearTimeout(timeout);finish();};};"
        "request.onerror=()=>{clearTimeout(timeout);finish();};"
        "}catch(error){clearTimeout(timeout);finish();}});"
        "location.replace('/static/ecommerce.html');"
        "}catch(error){document.body.textContent=error.message;}})();"
        "</script></body></html>",
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        main.ACCOUNT_SESSION_COOKIE,
        token,
        max_age=main.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response
