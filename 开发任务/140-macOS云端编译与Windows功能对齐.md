# macOS 云端编译与 Windows 功能对齐

状态：开发中
当前阶段：3/5，本地实现与静态验证完成
最后更新：2026-09-10 00:05

## 当前状态

源码仓库 `luojiang419/SHIYIN-AI-source` 已经是 Public，GitHub Actions 已启用，无需再次修改可见性。当前 CI 只在 `windows-latest` 构建并发布 Windows EXE；macOS 只有依赖系统 Python 的脚本运行方式，不是与 Windows 对等的原生桌面安装包。

已完成首轮跨平台实现：Rust updater 按平台隔离；桌面宿主可定位 `.app/Contents/Resources`、无扩展名 sidecar 和 Application Support 数据目录；macOS 使用 Keychain + Fernet 保护数据库密钥；Kling 自包含 Node 覆盖 darwin arm64/x64；新增同源 staging、ad-hoc 签名、bundle smoke、DMG/ZIP/哈希/manifest 脚本及双架构 Actions workflow。

Windows 本地 Python 41 项与 Rust 11 项回归已通过，JSON/YAML/Bash 语法正常。下一步需要推送并用真实 macOS runner 验证编译与运行。

## 下一步

1. 隔离提交并推送 macOS 跨平台实现。
2. 触发 `build-macos.yml`，跟踪 Apple Silicon / Intel runner 的真实日志并修复。
3. 下载 Actions artifacts，复核 DMG/ZIP/manifest/SHA-256。
4. 整理并验证需要进入云端构建的当前功能源码，确保与 Windows 1.0.431 实际内容对齐。

## 当前 TODO

- [x] 检查仓库可见性、Actions 权限和当前 Git 状态
- [x] 扫描 tracked 工作树常见 API Key / 私钥模式
- [x] 完成 Rust 桌面宿主 macOS 适配
- [x] 完成 Python backend 与密钥存储 macOS 适配
- [x] 完成 macOS `.app/.dmg` 构建及本地静态测试
- [x] 增加 GitHub Actions 双架构 workflow
- [ ] 验证 GitHub Actions 云端构建
- [ ] 上传并核验 Intel / Apple Silicon 产物
- [ ] 更新任务文档、提交并推送

## 最近验证状态

- GitHub 仓库：`PUBLIC`，Actions enabled，默认 workflow token 为 read
- 凭据扫描：当前 tracked 工作树未匹配常见 API Key / 私钥模式；`.env*`、本地数据和构建产物已忽略
- Windows 基线：`1.0.431` 安装包已完成 PyInstaller/Tauri/Inno/runtime smoke
- 本地 Python：安全、账号、Kling、Mac 构建契约 `41 passed`
- Windows Rust：`cargo test --locked`，11 passed
- 静态检查：macOS JSON/YAML/Bash/Python 编译检查通过
- macOS 编译：等待 GitHub Actions runner
- 最近 Git commit：`b5a7616 docs: 记录1.0.431安装包验证`

---

## 任务目标

在公开源码仓库使用 GitHub 托管 macOS runner 构建可安装的 SHIYIN AI macOS 桌面应用，使其与 Windows 版共享同一套 Web 业务界面、Python API 后端、项目数据和核心生成工作流，并提供 Apple Silicon 与 Intel 架构产物、SHA-256 和可追踪构建记录。

## 当前项目现状

- Windows 使用 Tauri 裸宿主 + PyInstaller sidecar + Inno Setup，安装后无需用户安装 Python。
- macOS 脚本直接运行 `python3 main.py`，依赖用户安装解释器和 requirements。
- `src-tauri/src/updater.rs` 使用 `std::os::windows`、PowerShell、tasklist 和 EXE 安装器。
- `src-tauri/src/lib.rs` 固定读取 `canvas-backend.exe` 和 `python.exe`，数据写在可执行文件旁。
- `canvas_core/secrets.py` 默认使用 Windows DPAPI，macOS 初始化 SecretStore 会失败。
- `canvas_core/kling_runtime.py` 的内置 Node 只支持 Windows x64；macOS 可先使用系统 Node 作为平台等价回退。
- `tauri.conf.json` 当前关闭 bundle，没有 `.app/.dmg` 目标。

## 技术方案

- 用 `cfg(target_os)` 隔离 Windows updater；macOS 暂不执行 EXE 自更新，更新 API 返回平台明确状态，避免编译或运行崩溃。
- 桌面宿主按平台解析 sidecar 文件名和 bundle Resources 根目录；macOS 数据写入用户 Application Support，保持程序包只读。
- macOS backend 使用 PyInstaller `onedir` 产物，随 `.app/Contents/Resources/app/backend` 打包。
- SecretStore 在 Windows 保持 DPAPI；macOS 使用系统 Keychain 派生/保存本机密钥并对数据库值做认证加密，或在能力不可用时提供明确错误，禁止明文落库。
- 新增 macOS 构建脚本，负责 backend、Web/skills、Tauri app bundle、资源布局、签名状态和哈希校验。
- GitHub Actions 使用公开仓库托管 runner 构建 Intel 与 Apple Silicon 两套产物；不依赖私有 API Token，不发布到外部 release 仓库，先上传 Actions artifacts。

## 文件 / 模块清单

预计修改或新增：

- `src-tauri/src/lib.rs`
- `src-tauri/src/updater.rs` 及 macOS updater stub
- `src-tauri/tauri.macos.conf.json`
- `canvas_core/secrets.py`
- `canvas-backend.spec`
- `tools/build-macos.sh`
- `tools/smoke-macos-bundle.py`
- `.github/workflows/build-macos.yml`
- 对应 Rust / Python / workflow 契约测试
- 本任务文档

## 开发阶段

- [x] 阶段 1：仓库、凭据与跨平台差异审计
- [x] 阶段 2：运行时代码跨平台适配
- [x] 阶段 3：macOS 打包脚本与本地静态验证
- [ ] 阶段 4：GitHub Actions 云端构建与修复
- [ ] 阶段 5：真实产物核验与最终交付

## 验收标准

1. 公开仓库 workflow 不使用私有 API，不消耗私有仓库 Actions 额度。
2. Apple Silicon 与 Intel runner 均成功生成 `.app` 压缩包或 `.dmg`，用户无需安装 Python。
3. 应用能启动内置 backend，通过 health/version/bootstrap，并显示与 Windows 同源的主界面。
4. 图片、视频、影视、作品、设置、项目数据等跨平台核心业务代码与 Windows 使用同一源码/staging。
5. Windows updater、路径和 sidecar 行为不回归；Mac 对 Windows 专属能力提供平台等价实现或清晰降级。
6. 每个云端产物包含版本、架构、文件大小和 SHA-256；Actions 日志可追踪。
7. 不提交 `.env`、API Key、本地数据库、用户输出、模型、缓存或构建产物。

## 已完成内容

- 确认仓库已经公开，Actions 权限正常。
- 完成当前 tracked 工作树常见凭据模式扫描。
- 定位 updater、sidecar、数据目录、密钥存储和 Kling runtime 的主要平台阻塞。
- 完成 Rust 平台模块、macOS bundle/data/sidecar 路径与更新降级接口。
- 完成 macOS Keychain 密钥保护和 Kling 双架构内置 Node。
- 完成 macOS app/DMG 构建、冻结后端 smoke 和双架构 Actions workflow。

## 当前关键修改

- 新建本任务文档，建立五阶段交付状态。
- 新增 `updater_macos.rs`、`tauri.macos.conf.json`、`build-macos.sh`、`smoke-macos-bundle.py` 和 `build-macos.yml`。
- 修改桌面宿主、密钥存储和 Kling runtime，使 Windows 与 macOS 使用同一业务后端和静态资源。

## 已知问题

- GitHub 不允许从默认分支尚不存在的新 workflow 执行 `workflow_dispatch`；当前先使用仅 feature branch 的 paths 限定 push 触发，进入默认分支后可直接手动调度。
- 首轮 Actions `34372587813`：Intel 因 `onnxruntime 1.27.0` 无 x64 Mac wheel 在依赖安装失败；Apple Silicon 完成 Python 与 Rust 编译，但一个下载文件名测试使用 Windows 路径导致断言失败。两项根因均已修正，等待下一轮验证。
- 第二轮 Actions `34373137772`：两架构依赖、Python、Rust 和 PyInstaller 均通过；Node 官方 tar 中 `bin/node` 为 112,937,728 bytes，超过原 100MB 单文件解包上限。归档 SHA-256 与固定 member 路径均正确，已将仅 Node 可执行文件的上限调整为 160MB。
- 第三轮 Actions `34374900714`：两架构通过依赖、contracts、PyInstaller、内置 Node、Tauri app bundle 和 ad-hoc codesign；bundle smoke 的 `/api/version` 请求未带桌面 token，被后端正确返回 401。已修复 smoke 鉴权并增加 Cargo 缓存。
- 当前 Windows 版自动更新只识别 EXE，Mac 更新安装需要独立机制。
- macOS 云端产物没有 Apple Developer ID 时只能 ad-hoc/未公证，首次打开会受 Gatekeeper 提示影响。
- Topaz、DWPose GPU、本地 FFmpeg/Kling CLI 等能力需要逐项确认 macOS 依赖，不应以“能编译”冒充完全可用。
- 当前工作区存在其他任务改动，提交与云端构建快照必须精确筛选。

## 后续优化

- 配置 Apple Developer ID、notarization 和 stapling。
- 为 macOS 增加独立更新资产选择与签名校验。
- 将 Kling 独立 Node runtime 扩展到 darwin-arm64 / darwin-x64。

## 开发日志

- 2026-09-09：任务启动；确认仓库已公开，完成 Actions 权限、凭据和首轮平台差异检查。
- 2026-09-10：完成第一版 macOS 运行时与打包链，本地 Python/Rust/静态契约通过，准备触发真实云端构建。
- 2026-09-10：首次 `workflow_dispatch` 因 workflow 尚未进入默认分支被 GitHub 返回 404；改用当前 feature branch 限定 push 触发。
- 2026-09-10：Actions 首轮 `34372587813` 两架构均失败；根据完整日志增加 Intel onnxruntime marker，并修正 Rust 测试的跨平台路径假设。
- 2026-09-10：Actions 第二轮 `34373137772` 两架构均通过到 PyInstaller，确认 Node 可执行文件真实大小后修正安全解包上限。
- 2026-09-10：Actions 第三轮 `34374900714` 两架构完成 `.app` 和签名，仅 bundle smoke 的版本接口因漏传 token 失败；保持后端鉴权并修正测试请求。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：阅读项目规则与本文，检查 Git branch/status，以源码、Actions run 和构建日志为准从“下一步”继续；不要重复修改仓库可见性，不要把本地输出或凭据纳入公开仓库。
