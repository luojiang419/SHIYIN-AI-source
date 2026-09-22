"""独立控制面板：主题同步、系统托盘和可选登录启动。"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

from distribution.service import DEFAULT_DATA, atomic_json
from distribution.desktop_settings import apply_titlebar, resolve_dark, set_startup, startup_enabled


class ServiceWatchdog:
    def __init__(self, failure_threshold=3, restart_interval=15):
        self.failure_threshold = failure_threshold
        self.restart_interval = restart_interval
        self.failures = 0
        self.last_restart = float('-inf')

    def succeeded(self):
        self.failures = 0

    def failed(self, now):
        self.failures += 1
        if self.failures < self.failure_threshold or now - self.last_restart < self.restart_interval:
            return False
        self.last_restart = now
        return True


def launch_service():
    cmd = [sys.executable, '--service'] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'distribution.launcher', '--service']
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return subprocess.Popen(cmd, cwd=Path(__file__).resolve().parents[1],
        env=env, creationflags=0x08000000 if os.name == 'nt' else 0,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe_service(request):
    try:
        return request('health')
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        return request('status')


def wait_for_service(request, process, timeout=60):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            probe_service(request)
            return
        except Exception as exc:
            last_error = exc
        code = process.poll()
        if code is not None:
            raise RuntimeError(f'分发服务进程退出（代码 {code}）。日志：{DEFAULT_DATA / "service-startup.log"}；连接错误：{last_error}')
        time.sleep(.2)
    raise RuntimeError(f'分发服务在 {timeout} 秒内未就绪。日志：{DEFAULT_DATA / "service-startup.log"}；连接错误：{last_error}')


def main():
    if '--sync-startup' in sys.argv:
        path = DEFAULT_DATA / 'settings.json'
        config = json.loads(path.read_text('utf-8')) if path.exists() else {}
        enabled = config.get('launch_at_login', startup_enabled())
        set_startup(enabled)
        config['launch_at_login'] = enabled
        atomic_json(path, config)
        return
    if '--service' in sys.argv:
        sys.argv.remove('--service')
        from distribution.startup import run_service
        return run_service()

    token_path = DEFAULT_DATA / 'admin-token'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path='status', body=None):
        token = token_path.read_text('ascii').strip()
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request('http://127.0.0.1:3013/api/' + path, data=data,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=3) as response:
            return json.load(response)

    def ready():
        try:
            probe_service(request)
            return True
        except Exception:
            return False

    if not ready():
        wait_for_service(request, launch_service())

    guard = socket.socket()
    try:
        guard.bind(('127.0.0.1', 3014))
        guard.listen(1)
    except OSError:
        request('desktop-action', {'action': 'show'})
        guard.close()
        return

    import webview
    import pystray
    from PIL import Image

    config = request()['settings']
    hide_on_start = '--background' in sys.argv or ('--startup' in sys.argv and config.get('start_hidden', True))
    quitting = threading.Event()
    state_path = DEFAULT_DATA / 'control-panel.json'
    tray = None
    theme_status = {}
    hwnd = None
    visible = not hide_on_start

    def record():
        atomic_json(state_path, {'pid': os.getpid(), 'running': not quitting.is_set(), 'visible': visible,
            'theme': config.get('theme', 'system'), 'titlebar': theme_status, 'tray': bool(tray and tray.visible)})

    def restore(*_):
        nonlocal visible
        window.show()
        window.restore()
        visible = True
        record()

    def background(*_):
        nonlocal visible
        if tray is None or not tray.visible:
            return
        window.hide()
        visible = False
        record()

    def exit_panel(*_):
        quitting.set()
        window.destroy()

    def closing():
        if not quitting.is_set() and config.get('background_on_close', True) and tray and tray.visible:
            background()
            return False
        quitting.set()
        return True

    def closed():
        nonlocal visible
        visible = False
        quitting.set()
        if tray:
            tray.stop()
        record()

    class API:
        def choose_source(self, kind):
            paths = window.create_file_dialog(webview.FileDialog.OPEN if kind == 'full' else webview.FileDialog.FOLDER)
            return paths[0] if paths else ''

    window = webview.create_window('SHIYIN 分发中心', 'http://127.0.0.1:3013/#' + token_path.read_text('ascii'),
        js_api=API(), width=1200, height=800, min_size=(820, 600), hidden=hide_on_start,
        background_color='#0d1115' if resolve_dark(config.get('theme', 'system')) else '#f4f7f9')
    window.events.closing += closing
    window.events.closed += closed

    def desktop_loop():
        nonlocal config, tray, theme_status, hwnd
        watchdog = ServiceWatchdog()
        image = Image.open(Path(__file__).parent / 'assets' / 'distribution.png').convert('RGBA')
        tray = pystray.Icon('SHIYINDistributionCenter', image, 'SHIYIN 分发中心', menu=pystray.Menu(
            pystray.MenuItem('打开控制面板', restore, default=True),
            pystray.MenuItem('隐藏到后台', background),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('退出控制面板（分发服务继续运行）', exit_panel)))
        try:
            tray.run_detached()
            sequence = request()['desktop_action']['sequence']
            last_dark = None
            while not quitting.wait(1):
                try:
                    state = request()
                    watchdog.succeeded()
                    config = state['settings']
                    if window.native is not None:
                        hwnd = window.native.Handle.ToInt64()
                        dark = resolve_dark(config.get('theme', 'system'))
                        if dark != last_dark:
                            theme_status = apply_titlebar(hwnd, dark)
                            last_dark = dark
                            record()
                    action = state['desktop_action']
                    if action['sequence'] > sequence:
                        sequence = action['sequence']
                        if action['action'] == 'show': restore()
                        elif action['action'] == 'background': background()
                        elif action['action'] == 'close': window.destroy()
                except Exception as exc:
                    if watchdog.failed(time.monotonic()):
                        try:
                            launch_service()
                        except Exception as restart_exc:
                            exc = RuntimeError(f'{exc}；自动恢复失败：{restart_exc}')
                    atomic_json(DEFAULT_DATA / 'control-panel-error.json', {'error': str(exc), 'time': time.time()})
        except Exception as exc:
            window.show()
            atomic_json(DEFAULT_DATA / 'control-panel-error.json', {'error': str(exc), 'time': time.time()})
        finally:
            if tray:
                tray.stop()

    try:
        webview.start(desktop_loop, icon=str(Path(__file__).parent / 'assets' / 'distribution.ico'))
    finally:
        quitting.set()
        guard.close()


if __name__ == '__main__':
    main()
