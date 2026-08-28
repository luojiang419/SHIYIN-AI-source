# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + ["multipart", "PIL", "requests", "httpx"]
)

a = Analysis(
    ["original-backend-entry.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "pandas", "scipy", "matplotlib", "torch", "transformers"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="canvas-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Tauri 会把标准输出重定向到 data/logs，启用控制台子系统可避免 Windows
    # 无窗口引导程序在部分机器上等待隐式控制台句柄。
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="canvas-backend")
