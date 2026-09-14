"""桌面外观与当前用户登录启动；不改变系统主题。"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'SHIYINDistributionCenter'


def legacy_startup():
    return Path(os.environ.get('APPDATA', str(Path.home()))) / 'Microsoft/Windows/Start Menu/Programs/Startup/SHIYIN 分发服务.lnk'


def legacy_startups():
    path = legacy_startup()
    # 兼容旧版无BOM脚本在Windows PowerShell中生成的乱码快捷方式。
    return (path, path.with_name('SHIYIN 鍒嗗彂鏈嶅姟.lnk'))


def startup_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_NAME)
            if value:
                return True
    except FileNotFoundError:
        pass
    return any(path.exists() for path in legacy_startups())


def startup_command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable, '--startup']
    else:
        python = Path(sys.executable).with_name('pythonw.exe')
        args = [str(python if python.exists() else sys.executable), str(Path(__file__).with_name('entry.py')), '--startup']
    return subprocess.list2cmdline(args)


def set_startup(enabled):
    if os.name != 'nt':
        if enabled:
            raise ValueError('当前平台暂不支持开机启动设置')
        return
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
    # 迁移旧的服务专用快捷方式，避免关闭自启动后它仍在生效。
    for old in legacy_startups():
        if old.exists():
            old.replace(old.with_suffix('.lnk.disabled'))


def system_dark():
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
        except OSError:
            pass
    return False


def resolve_dark(theme):
    return system_dark() if theme == 'system' else theme == 'dark'


def apply_titlebar(hwnd, dark):
    if os.name != 'nt':
        return {'supported': False}
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    enabled = ctypes.c_int(bool(dark))
    attribute = 20
    result = dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled))
    if result != 0:
        attribute = 19
        result = dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled))
    actual = ctypes.c_int(-1)
    read_result = dwm.DwmGetWindowAttribute(hwnd, attribute, ctypes.byref(actual), ctypes.sizeof(actual))
    return {'supported': result == 0, 'dark': bool(dark), 'applied': actual.value if read_result == 0 else None}
