# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
lab_root = project_root / "tools" / "video-depth-lab"
hiddenimports = [
    "cv2", "easydict", "einops", "numpy", "torch", "torch.utils.checkpoint",
    "torchvision", "torchvision.transforms", "tqdm",
]

a = Analysis(
    [str(lab_root / "worker" / "main.py")],
    pathex=[str(lab_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest", "tkinter", "tensorflow", "tensorboard", "jax", "flax",
        "transformers", "onnxruntime", "scipy", "pandas", "pyarrow",
        "matplotlib", "sklearn", "torchaudio", "timm", "datasets",
        "librosa", "soundfile", "kornia", "torchcodec", "pydub", "soxr",
        "boto3", "botocore", "bitsandbytes", "yt_dlp", "sqlalchemy",
        "fastapi", "uvicorn", "websockets", "Crypto", "Cryptodome",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="video-depth-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="video-depth-worker",
)
