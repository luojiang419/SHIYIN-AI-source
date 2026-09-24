# -*- mode: python ; coding: utf-8 -*-

import os
import runpy
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

# 固定运行时保留原依赖；应用层 worker 必须随 backend 同步更新。
runpy.run_path('tools/video-depth-lab/scripts/build-worker-overlays.py', run_name='__main__')

# 点击抠图运行时和 SAM 权重作为按需组件分发，不再进入全量安装器。
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
    datas=[
        ("tools/video-depth-lab/worker-overlays", "canvas_core/video_depth_workers"),
        ("canvas_core/distribution-public-key.hex", "canvas_core"),
        ("canvas_core/person_depth_manifest.json", "canvas_core"),
        ("canvas_core/cutout_runtime_manifest.json", "canvas_core"),
        ("canvas_core/video_depth_manifest.json", "canvas_core"),
        ("canvas_core/video_depth_runtime_manifest.json", "canvas_core"),
        ("skills/fashion-editorial-sequence-director", "skills/fashion-editorial-sequence-director"),
        ("skills/linkfox-expert-aigc-videogen-image-to-video", "skills/linkfox-expert-aigc-videogen-image-to-video"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "onnxruntime.experimental",
        "onnxruntime.transformers",
        "pandas",
        "pyarrow",
        "scipy",
        "matplotlib",
        "numba",
        "tensorflow",
        "tensorboard",
        # SAM 不使用这些可选训练/音频依赖；避免探测到半打包模块后错误导入。
        "sklearn",
        "librosa",
        "torchaudio",
        "torchcodec",
        "av",
        "timm",
        "datasets",
        "bitsandbytes",
        "accelerate",
        "torch",
        "transformers",
        "tokenizers",
        "safetensors",
        "huggingface_hub",
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
    # Tauri 用 CREATE_NO_WINDOW 启动并收集日志；保留标准流供 Uvicorn/Torch 使用。
    console=True,
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
