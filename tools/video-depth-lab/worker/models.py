from __future__ import annotations

import gc
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class ModelProfile:
    key: str
    label: str
    source_dir: str
    checkpoint: str
    encoder: str
    precision: str
    depth_type: str
    default_input_size: int
    infer_len: int
    overlap: int
    keyframes: tuple[int, ...]
    interp_len: int
    license_notice: str
    source_revision: str
    checkpoint_sha256: str


MODEL_PROFILES = {
    "gemdepth_vda_8f": ModelProfile(
        key="gemdepth_vda_8f",
        label="GemDepth-VDA · 8-frame",
        source_dir="gemdepth",
        checkpoint="gemdepth/gemdepth.pth",
        encoder="vitl",
        precision="FP16 autocast",
        depth_type="Relative Depth",
        default_input_size=392,
        infer_len=8,
        overlap=4,
        keyframes=(0, 3, 6, 7),
        interp_len=2,
        license_notice="GemDepth 仓库/权重标注 MIT；内嵌 RoPE 模块带 CC-BY-NC-SA-4.0 头，商业使用需另行核验。",
        source_revision="652865b0ed20e727784a6b77314da1dca2f14e36",
        checkpoint_sha256="F7C3FB7791862CC82684DDB1804480FB0314FDDBA4CF0E3B706553D98292FCAD",
    ),
    "vda_base_fp16_relative": ModelProfile(
        key="vda_base_fp16_relative",
        label="Video Depth Anything Base · FP16 · Relative",
        source_dir="video-depth-anything",
        checkpoint="video-depth-anything-base/video_depth_anything_vitb.pth",
        encoder="vitb",
        precision="FP16 autocast",
        depth_type="Relative Depth",
        default_input_size=322,
        infer_len=32,
        overlap=10,
        keyframes=(0, 12, 24, 25, 26, 27, 28, 29, 30, 31),
        interp_len=8,
        license_notice="Video Depth Anything Base: CC-BY-NC-4.0，仅限非商业用途。",
        source_revision="4f5ae23172ba60fd7bc11ef671cca678842c7072",
        checkpoint_sha256="775E578E8F9431EC0496514AA466BD0A1F67C28D0F518267809F35A43C04329B",
    ),
}


def get_profile(key: str) -> ModelProfile:
    try:
        return MODEL_PROFILES[key]
    except KeyError as error:
        raise ValueError(f"未知模型：{key}") from error


def model_status(lab_root: Path) -> list[dict[str, object]]:
    rows = []
    for profile in MODEL_PROFILES.values():
        source = lab_root / "runtime" / "sources" / profile.source_dir
        checkpoint = lab_root / "runtime" / "models" / profile.checkpoint
        rows.append(
            {
                "key": profile.key,
                "label": profile.label,
                "ready": source.is_dir() and checkpoint.is_file() and checkpoint.stat().st_size > 1024 * 1024,
                "sourceReady": source.is_dir(),
                "checkpointReady": checkpoint.is_file() and checkpoint.stat().st_size > 1024 * 1024,
                "checkpointBytes": checkpoint.stat().st_size if checkpoint.is_file() else 0,
                "precision": profile.precision,
                "depthType": profile.depth_type,
                "licenseNotice": profile.license_notice,
                "sourceRevision": profile.source_revision,
                "checkpointSha256": profile.checkpoint_sha256,
            }
        )
    return rows


def _clear_conflicting_modules() -> None:
    prefixes = ("model", "vggt", "video_depth_anything", "utils")
    for name in list(sys.modules):
        if name in prefixes or name.startswith(tuple(f"{prefix}." for prefix in prefixes)):
            sys.modules.pop(name, None)


def _install_windows_sdpa_compatibility() -> None:
    """Replace upstream's forced Flash-only calls with PyTorch backend selection.

    Official Windows wheels do not currently ship the FlashAttention kernel used
    by GemDepth's hard-coded context. Calling SDPA without a forced backend lets
    PyTorch select cuDNN or its math fallback while preserving checkpoint math.
    """
    import torch
    import torch.nn.functional as functional

    def vggt_forward(self, x, pos=None):
        batch, tokens, channels = x.shape
        qkv = self.qkv(x).reshape(batch, tokens, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        query, key, value = qkv.unbind(0)
        query, key = self.q_norm(query), self.k_norm(key)
        if self.rope is not None:
            query = self.rope(query, pos)
            key = self.rope(key, pos)
        output = functional.scaled_dot_product_attention(
            query,
            key,
            value,
            dropout_p=self.attn_drop.p if self.training else 0.0,
            scale=self.scale,
        )
        output = output.transpose(1, 2).reshape(batch, tokens, channels)
        return self.proj_drop(self.proj(output))

    for module_name in ("vggt.layers.attention", "model.vggt.layers.attention"):
        try:
            importlib.import_module(module_name).Attention.forward = vggt_forward
        except ModuleNotFoundError:
            continue

    block_attention = importlib.import_module("model.tools.blocks")

    def block_forward(self, x, xpos):
        batch, tokens, channels = x.shape
        qkv = self.qkv(x).reshape(batch, tokens, 3, self.num_heads, channels // self.num_heads).transpose(1, 3)
        query, key, value = [qkv[:, :, index] for index in range(3)]
        if self.rope is not None:
            query = self.rope(query, xpos) if xpos is not None else query
            key = self.rope(key, xpos) if xpos is not None else key
        scale = self.attn_bias_scale if not self.training and self.attn_bias_for_inference_enabled else self.scale
        output = functional.scaled_dot_product_attention(
            query,
            key,
            value,
            attn_mask=self.attn_mask,
            dropout_p=self.dropout_p if self.training else 0.0,
            is_causal=self.is_causal,
            scale=scale,
        )
        output = output.transpose(1, 2).reshape(batch, tokens, channels)
        return self.proj_drop(self.proj(output))

    block_attention.Attention.forward = block_forward
    torch.backends.cuda.enable_math_sdp(True)


def _load_gemdepth(lab_root: Path, profile: ModelProfile, emit: Callable[[int, str], None]):
    import torch

    source = lab_root / "runtime" / "sources" / profile.source_dir
    checkpoint_path = lab_root / "runtime" / "models" / profile.checkpoint
    _clear_conflicting_modules()
    sys.path.insert(0, str(source / "model"))
    sys.path.insert(0, str(source))
    module = importlib.import_module("model.gemdepth")
    module.INFER_LEN = profile.infer_len
    module.OVERLAP = profile.overlap
    module.KEYFRAMES = list(profile.keyframes)
    module.INTERP_LEN = profile.interp_len
    _install_windows_sdpa_compatibility()
    emit(30, "正在构建 GemDepth ViT-L 模型")
    model = module.GemDepth(
        encoder="vitl",
        features=256,
        out_channels=[256, 512, 1024, 1024],
        num_frames=32,
    )
    emit(36, "正在严格加载 GemDepth 官方权重")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
    model.load_state_dict(state_dict, strict=True)
    model = model.to("cuda").eval()
    return model


def _load_vda(lab_root: Path, profile: ModelProfile, emit: Callable[[int, str], None]):
    import torch

    source = lab_root / "runtime" / "sources" / profile.source_dir
    checkpoint_path = lab_root / "runtime" / "models" / profile.checkpoint
    _clear_conflicting_modules()
    sys.path.insert(0, str(source))
    module = importlib.import_module("video_depth_anything.video_depth")
    emit(30, "正在构建 Video Depth Anything Base")
    model = module.VideoDepthAnything(
        encoder="vitb",
        features=128,
        out_channels=[96, 192, 384, 768],
        metric=False,
    )
    emit(36, "正在严格加载 VDA Base Relative 官方权重")
    state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    model = model.to("cuda").eval()
    return model


def infer_depths(
    lab_root: Path,
    model_key: str,
    frames: np.ndarray,
    fps: float,
    input_size: int,
    emit: Callable[[int, str], None],
) -> tuple[np.ndarray, dict[str, int]]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 CUDA；本技术验证要求 NVIDIA GPU")
    # GemDepth upstream applies stochastic pose masks even in eval mode. A fixed
    # seed keeps repeated parameter/model comparisons reproducible.
    np.random.seed(0)
    torch.manual_seed(0)
    torch.cuda.manual_seed_all(0)
    torch.cuda.reset_peak_memory_stats()
    profile = get_profile(model_key)
    status = next(row for row in model_status(lab_root) if row["key"] == model_key)
    if not status["ready"]:
        raise FileNotFoundError(f"{profile.label} 尚未部署完成，请先运行 setup.ps1")

    model = None
    try:
        if model_key == "gemdepth_vda_8f":
            model = _load_gemdepth(lab_root, profile, emit)
        else:
            model = _load_vda(lab_root, profile, emit)
        emit(45, f"正在执行 {profile.label} 推理")
        depths, _ = model.infer_video_depth(
            frames,
            fps,
            input_size=int(input_size),
            device="cuda",
            fp32=False,
        )
        emit(78, "模型推理完成，正在释放显存")
        statistics = {
            "peakAllocatedBytes": int(torch.cuda.max_memory_allocated()),
            "peakReservedBytes": int(torch.cuda.max_memory_reserved()),
        }
        return np.asarray(depths, dtype=np.float32), statistics
    finally:
        if model is not None:
            del model
        gc.collect()
        torch.cuda.empty_cache()
