from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path

import requests
import websockets


class DevTools:
    def __init__(self, socket):
        self.socket = socket
        self.next_id = 1

    async def call(self, method: str, params: dict | None = None) -> dict:
        request_id = self.next_id
        self.next_id += 1
        await self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(await self.socket.recv())
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result") or {}

    async def evaluate(self, expression: str):
        result = await self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")


async def wait_for(devtools: DevTools, predicate: str, timeout: float = 20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if await devtools.evaluate(predicate):
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for: {predicate}")


async def run(args) -> dict:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = output_dir / "chrome-profile-visual"
    if profile.exists():
        shutil.rmtree(profile)
    browser = subprocess.Popen(
        [
            args.chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={args.debug_port}",
            f"--user-data-dir={profile}",
            "--window-size=1600,1000",
            f"http://127.0.0.1:{args.port}/api/auth/bootstrap?token={args.token}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        target = None
        for _ in range(200):
            if browser.poll() is not None:
                raise RuntimeError(f"Chrome exited with code {browser.returncode}")
            try:
                targets = requests.get(f"http://127.0.0.1:{args.debug_port}/json", timeout=.5).json()
                target = next((
                    item for item in targets
                    if item.get("type") == "page" and f"127.0.0.1:{args.port}" in str(item.get("url") or "")
                ), None)
                if target:
                    break
            except Exception:
                pass
            await asyncio.sleep(.1)
        if not target:
            raise TimeoutError("Chrome DevTools target was not available")

        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=16 * 1024 * 1024) as socket:
            devtools = DevTools(socket)
            await devtools.call("Runtime.enable")
            await devtools.call("Page.enable")
            await devtools.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600,
                "height": 1000,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
            await wait_for(devtools, "document.readyState === 'complete' && !!document.getElementById('frame-ecommerce')")
            captures = {}
            for theme in ("light", "dark"):
                await devtools.evaluate(f"""
                    (() => {{
                        localStorage.setItem('studio_theme', '{theme}');
                        localStorage.setItem('canvas_theme', '{theme}');
                        localStorage.setItem('studio_sidebar_pinned', '1');
                        localStorage.setItem('studio_sidebar_manual_mode_v1', '1');
                        localStorage.setItem('studio_active_page', 'ecommerce');
                        localStorage.setItem('studio_ui_scale_mode', '100');
                        location.reload();
                        return true;
                    }})()
                """)
                await wait_for(
                    devtools,
                    "document.readyState === 'complete' && !!document.getElementById('frame-ecommerce')?.contentWindow?.EcommerceStudio?.state?.capabilities",
                )
                await devtools.evaluate("document.querySelector('[onclick*=\"ecommerce\"]')?.click(); true")
                await devtools.evaluate(f"window.StudioTheme?.set?.('{theme}'); window.broadcastTheme?.('{theme}'); true")
                await wait_for(
                    devtools,
                    f"document.documentElement.classList.contains('studio-theme-dark') === {str(theme == 'dark').lower()}",
                )
                await devtools.evaluate("window.StudioTheme?.setScaleMode?.('100'); true")
                await asyncio.sleep(.45)
                geometry = await devtools.evaluate("""
                    (() => {
                        const rect = node => {
                            const value = node?.getBoundingClientRect();
                            return value ? {x:Math.round(value.x),y:Math.round(value.y),width:Math.round(value.width),height:Math.round(value.height)} : null;
                        };
                        const frame = document.getElementById('frame-ecommerce');
                        const doc = frame.contentDocument;
                        return {
                            viewport:{width:innerWidth,height:innerHeight},
                            sidebar:rect(document.getElementById('studioSidebar')),
                            stage:rect(document.querySelector('.stage')),
                            topbar:rect(doc.querySelector('.ec-operation-tabs')),
                            controls:rect(doc.getElementById('controlPanel')),
                            result:rect(doc.querySelector('.ec-result-panel')),
                            dock:rect(doc.getElementById('universalDock')),
                            dark:document.documentElement.classList.contains('studio-theme-dark'),
                        };
                    })()
                """)
                screenshot = await devtools.call("Page.captureScreenshot", {
                    "format": "png",
                    "captureBeyondViewport": False,
                })
                path = output_dir / f"ecommerce-{theme}-1600x1000.png"
                path.write_bytes(base64.b64decode(screenshot["data"]))
                captures[theme] = {"path": str(path), "geometry": geometry}
            return captures
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--debug-port", type=int, default=9341)
    parser.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
