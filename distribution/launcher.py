"""独立控制面板入口；--service 模式在关闭面板后继续提供下载。"""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from distribution.service import DEFAULT_DATA


def main():
    if '--service' in sys.argv:
        sys.argv.remove('--service')
        from distribution.service import main as service_main
        return service_main()
    token_path = DEFAULT_DATA / 'admin-token'
    def ready():
        if not token_path.exists(): return False
        try:
            req = urllib.request.Request('http://127.0.0.1:3013/api/status', headers={'Authorization':'Bearer '+token_path.read_text('ascii')})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=1) as r: return r.status==200
        except Exception: return False
    if not ready():
        cmd = [sys.executable, '--service'] if getattr(sys,'frozen',False) else [sys.executable,'-m','distribution.launcher','--service']
        subprocess.Popen(cmd,cwd=Path(__file__).resolve().parents[1],creationflags=0x08000008 if os.name=='nt' else 0,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if ready(): break
            time.sleep(.2)
        else: raise RuntimeError('分发服务未启动，请检查 3013 端口和数据目录权限')
    import webview
    class API:
        def choose_source(self,kind):
            paths=window.create_file_dialog(webview.FileDialog.OPEN if kind=='full' else webview.FileDialog.FOLDER)
            return paths[0] if paths else ''
    window=webview.create_window('SHIYIN 分发中心', 'http://127.0.0.1:3013/#'+token_path.read_text('ascii'),js_api=API(),width=1200,height=800,min_size=(820,600))
    webview.start()


if __name__ == '__main__': main()
