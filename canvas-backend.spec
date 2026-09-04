# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("uvicorn") + collect_submodules("websockets") + [
    "multipart",
    "cv2",
    "numpy",
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
]

a = Analysis(
    ["backend_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[("canvas_core/person_depth_manifest.json", "canvas_core")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "torch",
        "transformers",
        "onnxruntime.experimental",
        "onnxruntime.transformers",
        "pandas",
        "pyarrow",
        "scipy",
        "matplotlib",
        "numba",
        "tensorflow",
        "tensorboard",
    ],
    noarchive=False,
    optimize=1,
)
cpu_only_excluded_binaries = {
    "onnxruntime_providers_cuda.dll",
    "onnxruntime_providers_tensorrt.dll",
}
a.binaries = [
    item for item in a.binaries if item[0].replace("\\", "/").rsplit("/", 1)[-1].lower() not in cpu_only_excluded_binaries
]
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
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="canvas-backend",
)
