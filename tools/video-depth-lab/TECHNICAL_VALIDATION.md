# 视频深度技术验证报告

验证时间：2026-09-06
硬件：NVIDIA GeForce RTX 4070 Ti SUPER 16GB
运行时：Python 3.12.7、PyTorch 2.6.0+cu126、CUDA 12.6、FFmpeg 8.1.1

## 部署结果

| 模型 | 上游 revision | 权重 | SHA-256 | 状态 |
| --- | --- | ---: | --- | --- |
| GemDepth-VDA | `652865b0ed20e727784a6b77314da1dca2f14e36` | 2,844,171,337 bytes | `F7C3FB7791862CC82684DDB1804480FB0314FDDBA4CF0E3B706553D98292FCAD` | 严格加载通过 |
| Video Depth Anything Base | `4f5ae23172ba60fd7bc11ef671cca678842c7072` | 458,247,082 bytes | `775E578E8F9431EC0496514AA466BD0A1F67C28D0F518267809F35A43C04329B` | 严格加载通过 |

依赖使用清华 PyPI 镜像，仅补装 `easydict==1.13`；CUDA PyTorch、OpenCV、NumPy、Pillow、ImageIO、Einops 等复用本机现有环境。下载过程未设置代理，WinHTTP 保持直连。

## 统一短片验证

输入为 VDA 官方 `davis_rollercoaster.mp4`：960×540、24 FPS。两组测试均采样 8 帧、6 FPS，输出最长边 320，便于只比较模型链路而不把编解码成本放大。

| 配置 | 模型输入 | 端到端耗时 | CUDA peak allocated | CUDA peak reserved | 输出 |
| --- | ---: | ---: | ---: | ---: | --- |
| GemDepth-VDA 8-frame / FP16 autocast / Relative | 392 | 9.857s | 7,184,961,024 bytes（约 6.69GiB） | 8,621,391,872 bytes（约 8.03GiB） | 320×180、6 FPS、8 帧、H.264/yuv420p |
| VDA Base / FP16 autocast / Relative | 322 | 4.934s | 3,502,958,080 bytes（约 3.26GiB） | 4,525,654,016 bytes（约 4.21GiB） | 320×180、6 FPS、8 帧、H.264/yuv420p |

两条链路均完成：FFmpeg 解码 → 官方 checkpoint 严格加载 → CUDA 推理 → 全视频统一 Relative Depth 百分位归一化 → H.264 灰度深度视频编码。首帧视觉检查中，两者均恢复过山车轨道、支架与远近层次；GemDepth 输出的中低灰层次更连续，VDA Base 的背景压黑更明显。本结果只证明工程可用性与肉眼差异，不替代带真值数据集的精度评测。

## 8-frame 与 Windows attention 结论

- GemDepth 官方默认 32-frame 配置标称约需 44GB 显存；本工具使用官方 README 给出的 8-frame / overlap 4 / keyframes `[0,3,6,7]` / interpolation 2 降档。
- GemDepth 上游强制 `SDPBackend.FLASH_ATTENTION`，而 Windows 官方 PyTorch wheel 未提供该 kernel。适配层不改权重，允许 PyTorch SDPA 自动选择可用 backend，并同时覆盖两种模块导入名。
- GemDepth 上游在 eval 路径仍会生成随机 pose mask；统一 worker 固定 NumPy/PyTorch/CUDA seed 为 0，使同输入、同配置的对比可复现。
- 固定 seed 后对同一 8 帧输入连续运行两次，归一化 FP16 深度数组 `array_equal=True`、最大绝对差 `0.0`。
- 392 输入尺寸下 GemDepth 峰值 reserved 约 8.03GiB，在本机 16GB 显卡上具有可用余量。
- VDA Base 仍保持官方 32-frame 内部窗口。518 输入尺寸压力测试持续占用约 15.5GiB/16GiB、GPU 100%，超过 4 分钟仍未完成首个窗口，已人工安全终止。因此 Windows 无 FlashAttention 环境默认改为 322，518 只作为显存压力档保留。

## 参数验证

七项参数与既有深度图调参器保持一致：`farPoint`、`nearPoint`、`midtone`、`contrast`、`brightness`、`smooth`、`invert`。

- 参数运算始终从 `depth-relative-normalized.npz` 重算，不重复运行模型，也不累积多次有损处理。
- `farPoint/nearPoint` 控制 Relative Depth 黑白端点；`midtone` 使用 gamma 曲线；`contrast/brightness` 使用线性变换；`smooth` 使用逐帧 Gaussian；`invert` 交换近亮远暗。
- 使用 `farPoint=5 / nearPoint=95 / midtone=10 / contrast=125 / brightness=2 / smooth=3` 完成真实后处理，成功生成第二份 H.264 参数视频。
- Python 覆盖值域、归一化、反转与模型注册；JavaScript 覆盖模型项、参数边界和版本化配置往返。

## 完整 1080p 提取复核

根据用户复核，界面已把“模型推理尺寸”和“输出分辨率”拆开。模型推理尺寸仍为 14 的倍数，只影响内部计算；输出新增原始分辨率、720p、1080p、1440p 和 4K 档。

- 默认改为原始 FPS、全部帧、原始分辨率。
- 原始 FPS 不再经过 FFmpeg `fps` 滤镜；全部帧不再传递 `-frames:v`，因此不会由工具主动抽帧或截断。
- 新增 6/12/15/24/25/30/48/50/60/90/120 FPS 完整选项，以及常用限定帧数选项。
- 输入视频载入时探测宽高、FPS、时长和帧数；增加显式“更换视频”和“移除视频”。
- 使用 1920×1080、30 FPS、8 帧视频真实复核：GemDepth-VDA 与 VDA Base 输出均为 1920×1080、30 FPS、8 帧、H.264/yuv420p，且元数据 `completeExtraction/sourceFpsPreserved/sourceResolutionPreserved` 均为 `true`。

## 软件验证

- Tauri 2 完整提取优化版 `v0.2.0` release 成功构建，成品 `SHIYIN-Video-Depth-Lab.exe` 为 3,499,520 bytes，SHA-256 `4DA28165F40A08D391A5D99B4E8501500DB8861F5BD8FA9FC278CB6022798310`。
- release 进程启动后正常响应并显示主窗口标题。
- 975×920 浏览器视口视觉 QA：`body.scrollWidth/Height` 与 viewport 完全一致，无横向或纵向溢出；四区布局、模型下拉、预设、七项参数和右下操作区均完整显示。
- 模型下拉从 GemDepth-VDA 切换到 VDA Base 后，输入尺寸从 392 自动变为 322，模型说明更新为 `32-frame · overlap 10 · FP16`，证明不是静态文案。
- 浏览器 console warning/error 为 0。纯浏览器预览中 `invoke is not a function` 被应用作为“非 Tauri 环境”状态正常捕获；Tauri release 使用真实 `window.__TAURI__`。

## 结论

两模型已达到本地技术验证和参数验证目标。当前推荐默认档为：

- 质量/几何一致性优先：GemDepth-VDA 8-frame，输入 392。
- 速度/显存优先：VDA Base FP16 Relative，输入 322。

下一阶段若用于正式长视频，应增加分段落盘、任务恢复和更完整的时间一致性指标；本工具当前定位为短片模型与参数对比验证台。
