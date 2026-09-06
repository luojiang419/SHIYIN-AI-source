# SHIYIN 视频深度验证台

独立的 Windows/Tauri 2 技术验证工具，用同一段视频对比：

- `GemDepth-VDA · 8-frame`：GemDepth 官方 `gemdepth.pth`（论文中的 VDA backbone 变体），使用官方给出的 16GB 显存降档配置 `INFER_LEN=8 / OVERLAP=4 / KEYFRAMES=[0,3,6,7] / INTERP_LEN=2`，默认输入尺寸 392。
- `Video Depth Anything Base · FP16 · Relative`：官方 ViT-Base Relative Depth 权重，CUDA FP16 autocast。Windows 官方 PyTorch 缺少 FlashAttention 时默认输入尺寸 322；518 作为高压力档保留。

这里的 “GemDepth-VDA · 8-frame” 是 GemDepth 论文/官方代码中的 VDA backbone 变体，使用官方单一公开权重与 8-frame 低显存滑窗配置，并不存在另一份名为“8-frame”的权重。

## 部署

在 PowerShell 中进入本目录后执行：

```powershell
.\setup.ps1
```

脚本会：

1. 优先尝试国内 Git 镜像，失败后直连 GitHub。
2. 创建 `runtime/venv`，复用本机已有 CUDA PyTorch，不重复下载大型 Torch 包。
3. 从清华 PyPI 镜像安装最小补充依赖。
4. 优先从 `hf-mirror.com` 入口下载模型，失败后直连 Hugging Face。
5. 主动移除当前脚本进程的代理环境变量，`curl` 同时使用 `--noproxy '*'`。

本机若没有 CUDA 版 PyTorch，脚本会明确失败，不会偷偷下载数 GB 的替代包。运行 `scripts/diagnose.ps1` 可重新检查部署状态。

## 启动与构建

```powershell
npm run dev
npm test
npm run build
```

release 可执行文件生成在：

`src-tauri/target/release/SHIYIN-Video-Depth-Lab.exe`

## 使用

1. 点击左侧区域或拖入视频。
2. 在底部“模型”下拉项选择要验证的模型。
3. 设置采样 FPS、最大帧数、输出最长边与模型输入尺寸。
4. 点击“开始模型测试”。输出目录包含归一化 Relative Depth、H.264 灰度视频和运行元数据。
5. 调整黑白点、中间层次、对比度、亮度、平滑或反转；界面先给出近似滤镜预览，点击“应用参数”后从原始 Relative Depth 精确重算，不重复运行模型。
6. 可导出当前深度视频和版本化 JSON 参数配置，也可重新导入配置。

统一 worker 将推理随机种子固定为 0。GemDepth 上游即使在 eval 模式仍会使用随机 pose mask，固定 seed 可保证模型与参数对比能够复现。

默认每次只采样 48 帧用于技术验证。GemDepth 默认 392；VDA Base 因内部使用 32-frame 窗口，默认 322。518 档在 Windows 无 FlashAttention 的 PyTorch 上可能占满 16GB 显存并显著变慢，只用于压力验证。

## 输出结构

每次模型测试创建独立时间戳目录：

- `depth-relative-normalized.npz`：全视频统一百分位归一化后的 Relative Depth，FP16 存储。
- `depth-preview.mp4`：默认参数的 H.264 灰度深度视频。
- `depth-preview-adjusted.mp4`：精确应用调参后的深度视频。
- `run-metadata.json`：输入信息、模型、精度、滑窗配置、参数、归一化区间和耗时。

## 许可证

- GemDepth 官方仓库/权重标注 MIT；其内嵌 RoPE 等第三方模块带有 `CC-BY-NC-SA-4.0` 文件头，商业使用前必须单独核验完整依赖链。
- Video Depth Anything Base 为 `CC-BY-NC-4.0`，仅限非商业用途。
- 本工具是技术和参数验证项目，不改变上游许可证。
