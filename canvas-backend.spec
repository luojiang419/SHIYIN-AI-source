# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from huggingface_hub import snapshot_download
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

# SAM 与后端一起交付；构建时验证权重齐全，不能发布只有前端的抠像入口。
sam_root = Path(os.environ.get("SHIYIN_SAM_MODEL_DIR") or snapshot_download(
    "facebook/sam-vit-base", revision="70c1a07f894ebb5b307fd9eaaee97b9dfc16068f", local_files_only=True,
))
sam_data = []
for name in ("config.json", "preprocessor_config.json", "model.safetensors"):
    source = sam_root / name
    if not source.is_file():
        raise RuntimeError(f"SAM 模型文件缺失：{source}；请准备模型并设置 SHIYIN_SAM_MODEL_DIR")
    # 保留快照中的逻辑文件名；resolve() 会将缓存软链接变成 blob 哈希文件名。
    sam_data.append((str(source.absolute()), "models/sam-vit-base"))


hiddenimports = collect_submodules("uvicorn") + collect_submodules("websockets") + [
    "multipart",
    "cv2",
    "numpy",
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "transformers.models.sam.modeling_sam",
    "transformers.models.sam.processing_sam",
    "transformers.models.sam.image_processing_sam",
    "transformers.models.sam.image_processing_sam_fast",
]

a = Analysis(
    ["backend_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("canvas_core/distribution-public-key.hex", "canvas_core"),
        ("canvas_core/person_depth_manifest.json", "canvas_core"),
        ("canvas_core/video_depth_manifest.json", "canvas_core"),
        ("canvas_core/video_depth_runtime_manifest.json", "canvas_core"),
        ("skills/fashion-editorial-sequence-director", "skills/fashion-editorial-sequence-director"),
        ("skills/linkfox-expert-aigc-videogen-image-to-video", "skills/linkfox-expert-aigc-videogen-image-to-video"),
    ] + sam_data + copy_metadata("torch") + copy_metadata("transformers"),
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
