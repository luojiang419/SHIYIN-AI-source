"""监测官方 OAuth CLI；授权地址只供本机管理员短时读取，不保存 token/输出。"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs


def authorization_url(line: str) -> str:
    for url in re.findall(r'https://[^\s<>"\x1b]+', line):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        allowed = any(host == domain or host.endswith("." + domain) for domain in ("klingai.com", "kling.ai"))
        query = parse_qs(parsed.query)
        if allowed and all(key in query for key in ("client_id", "state", "redirect_uri", "code_challenge")):
            return url
    return ""


class KlingLoginManager:
    def __init__(self, *, timeout: float = 360):
        self.lock = threading.RLock()
        self.process = None
        self.timeout = timeout
        self.state = {"status": "idle", "authorization_url": "", "error": ""}

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.state)

    def open_browser(self) -> None:
        with self.lock:
            url = self.state.get("authorization_url", "")
            if self.state["status"] != "waiting" or not authorization_url(url):
                raise RuntimeError("授权链接尚未就绪或已失效，请重新登录。")
            if os.name == "nt":
                os.startfile(url)
            elif not webbrowser.open(url):
                raise RuntimeError("无法打开系统浏览器，请复制授权链接到浏览器。")

    def start(self, command: list[str]) -> dict:
        with self.lock:
            if self.state["status"] in {"starting", "waiting"}:
                return dict(self.state)
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0,
            )
            self.state = {"status": "starting", "authorization_url": "", "error": "", "pid": self.process.pid}
            threading.Thread(target=self._watch, args=(self.process,), daemon=True, name="kling-login-watch").start()
            threading.Thread(target=self._read, args=(self.process,), daemon=True, name="kling-login-output").start()
            return dict(self.state)

    def _watch(self, process):
        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            with self.lock:
                if self.process is process and self.state["status"] in {"starting", "waiting"}:
                    self.state.update(status="failed", authorization_url="", error="可灵授权超时，请检查网络后重新登录。")
                    process.kill()

    def _read(self, process):
        browser_failed = False
        failure_kind = ""
        try:
            for raw in iter(process.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace")
                url = authorization_url(line)
                browser_failed = browser_failed or "Could not open browser" in line or "Headless environment" in line
                # 仅归类错误，不向 API 返回可能含 token 的原始日志。
                if "EADDRINUSE" in line:
                    failure_kind = "本机授权回调端口被占用，请关闭其他可灵授权窗口后重试。"
                elif any(marker in line.lower() for marker in ("fetch failed", "enotfound", "econn", "network")):
                    failure_kind = "无法连接可灵授权服务，请检查网络或代理后重试。"
                with self.lock:
                    if self.process is not process or self.state["status"] == "failed":
                        continue
                    if url:
                        self.state.update(status="waiting", authorization_url=url)
                    if browser_failed:
                        self.state["error"] = "浏览器未自动打开，请点击“打开授权页面”。"
            code = process.wait()
            with self.lock:
                if self.process is process and self.state["status"] != "failed":
                    self.state.update(
                        status="succeeded" if code == 0 else "failed", authorization_url="",
                        error="" if code == 0 else failure_kind or f"可灵授权未完成（退出码 {code}），请重新登录。",
                    )
        except (OSError, ValueError):
            with self.lock:
                if self.process is process:
                    self.state.update(status="failed", authorization_url="", error="读取可灵授权状态失败，请重新登录。")
            if process.poll() is None:
                process.kill()
        finally:
            process.stdout.close()


LOGIN_MANAGER = KlingLoginManager()
