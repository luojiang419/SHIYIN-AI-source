# Hugging Face 模型外置 Worker 发布包需解引用并裁剪可选依赖

## 问题表现

- 将 Hugging Face snapshot 目录直接挂载或复制到组件目录后，`from_pretrained(local_files_only=True)` 报缺少 `config.json` 或权重。
- PyInstaller 使用 `collect_all(transformers)` 时把音频、数据集、下载器和服务端等无关模块打入运行时。
- 冻结后的 worker 可能依次报 `torchcodec` metadata 缺失，或 Kornia TorchScript 无法读取函数源码。

## 触发条件

- Windows Hugging Face 缓存中的 snapshot 文件是指向 `../../blobs` 的相对符号链接。
- 模型通过 Transformers `auto_map` 加载固定 revision 的自定义 Python 代码。
- 构建环境安装了大量 Transformers 可选依赖，PyInstaller 静态分析会看到本任务不使用的分支。

## 根本原因

- snapshot 不是自包含模型目录，相对符号链接离开原缓存层级后会失效。
- `collect_all` 会收集整个包的子模块，不能表达实际推理调用范围。
- Transformers 的可选音频检测会依据冻结模块表判断包存在，但对应 distribution metadata 未必被带入。
- BiRefNet 的 `laplacian` 只用于训练分支，却通过 `kornia.filters` 导入触发了 Kornia 顶层 TorchScript 初始化。

## 无效尝试

- 使用 Junction 把 snapshot 映射到新的组件目录：内部相对符号链接仍然失效。
- 在 Windows PowerShell 5.1 使用 `Copy-Item -FollowSymlink`：该版本不支持此参数。
- 为所有依赖使用 `collect_all`：构建时间和运行时体积显著增加，并引入无关模块故障。
- 仅补 `torchcodec` metadata：会保留本来不需要的音频依赖链。
- 将整个 Kornia 源码加入冻结包：没有解决“推理不应加载训练分支”的职责问题。

## 正确解决方案

1. 枚举 snapshot 文件；遇到 `FileInfo.Target` 时解析真实 blob 路径并复制文件内容，生成自包含模型目录。
2. 固定模型 revision，并把模型 ID、revision、许可证和受信自定义代码 SHA-256 写入候选 manifest。
3. 加载 `trust_remote_code=True` 前逐个校验 BiRefNet 代码和配置哈希，篡改或缺失立即拒绝。
4. PyInstaller 只显式收集 `depth_anything`、`dinov2`、`timm.layers`、`torchvision.models/ops` 等实际模块。
5. 明确排除 `torchcodec`、`librosa`、`pydub`、`datasets`、`yt_dlp`、`bitsandbytes` 等无关生态。
6. 对 BiRefNet 训练期 `kornia.filters.laplacian` 提供只允许推理的最小兼容模块；意外进入训练分支时明确报错。
7. 候选发布物必须保持 `enabled:false`、URL 为空；许可证确认前不得公开发布或回填正式 manifest。

## 验证方法

- 源码 worker 使用锁定模型 revision 完成真实 CUDA smoke。
- 候选包通过本地 HTTP 完整执行下载、大小校验、SHA-256、安全解压、原子激活和 packaged worker smoke。
- 检查 candidate manifest 中两个 ZIP 的真实大小和 SHA-256。
- 检查失败候选和构建 staging 已清理，只保留最终候选包。

## 如何避免

- 不要把 Hugging Face snapshot 当作普通自包含目录。
- 不要在大型 AI 运行时 spec 中默认使用 `collect_all`。
- 自定义模型代码必须同时锁定 revision 和文件哈希。
- 先跑源码 smoke，再冻结；冻结后必须通过完整安装链 smoke，不能只验证 EXE 能启动。
- Windows PowerShell 5.1 使用的 `.ps1` 保持纯 ASCII，避免无 BOM UTF-8 中文导致解析失败。

## 影响模块

- `person_depth_worker/`
- `person-depth-worker.spec`
- `tools/build-person-depth-component.ps1`
- `tools/smoke-person-depth-component.py`
- `canvas_core/person_depth_components.py`
