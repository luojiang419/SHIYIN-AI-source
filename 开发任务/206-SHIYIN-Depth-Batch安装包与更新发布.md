# SHIYIN-Depth-Batch 安装包与更新发布

状态：独立更新器退出码 1 的脚本解析错误已修复；Windows PowerShell 实际执行回归、界面测试和 release 编译通过。
下一步：本地演示版已准备；公开渠道仍为原 1.0.3，待演示确认后再发布。
TODO：
- [x] 取消便携包构建入口，提供 Windows 安装器
- [x] 接入签名增量更新与独立更新进程
- [x] 分发中心按产品隔离深度批量工具更新
- [x] 创建并接入魔塔 `SHIYIN-Depth-Batch` 仓库
- [x] 编译、安装包检查和缓存上限检查
最近验证：1.0.3 Rust `cargo check`、魔塔回退联网测试、批量界面 Node 9 项和 Python 7 项通过；Inno Setup 构建通过。公开目录签名、107,476,910 字节更新包 SHA-256 和 ZIP 内 13 个文件逐项校验通过。
branch/commit：`fix/depth-batch-update-script` / 本次修复见 Git 最新提交。
阻塞：无。

[CODEX_LONG_TASK_CONTINUE_V3]

## 2026-09-22 独立更新器退出码 1

- 现场 `%LOCALAPPDATA%/SHIYIN-Depth-Batch/update/apply-depth-batch.ps1` 的 `WriteAllText(..., $_ | Out-String, ...)` 无法解析，PowerShell 在进入 try/catch 前退出，因此没有 apply-error.log。新旧两个脚本入口均改为带括号的管道表达式。
- 生成脚本增加 UTF-8 BOM，支持 Windows PowerShell 5.1 中文路径；独立更新流程规范化 canonicalize 产生的扩展路径。
- 新增执行生产脚本的 Rust 回归：中文/空格/单引号路径复制及版本写入；目标独占锁定时错误日志、退出码和原版本/待更新记录保留。测试通过。批量界面 6 项通过，release 编译通过。
- 修复版宿主：`dist/depth-batch-repair/SHIYIN-Depth-Batch.exe`，SHA-256 `cf669465f742ddc649c3b61d6e594fecb38ad81732020846c19520abac747d23`。本轮未构建安装包、未发布魔搭，保留原版本号。
- 本地真实独立更新器已执行，隔离状态目录 `.build/depth-batch-updater-fix/data/update/installed.json` 已登记 `20260922105810`。演示目录沿用 `.build/depth-batch-ui-demo-20260922`。
- 构建后缓存检查：`.build` 0.699 GiB，`.codex-tmp` 8.353 GiB，均低于 20 GiB。

## 目标

将 `tools/video-depth-lab` 从便携 ZIP 改为 Windows 安装包交付。软件更新复用 SHIYIN 独立局域网分发中心的签名增量包、独立更新进程和控制面板发布方式；更新产品通道与 SHIYIN AI 主软件隔离。魔塔仓库作为外网更新镜像和后续持续发布的远端仓库。

## 交付

- 安装包：`dist/installer/SHIYIN-Depth-Batch-Setup-1.0.0.exe`，SHA-256 为 `964514a843885358d27ed2a99d3255c56a0480165f7e61afa3bf4228a6e7711c`。构建只包含 EXE、worker、按需组件清单和运行时覆盖层，不再生成 ZIP 便携包。
- 客户端更新：检查按钮调用签名清单；下载后对 `.shiyin-update` 和每个文件进行 SHA-256 校验，独立 PowerShell 更新进程等待主程序退出后替换并重启。所有更新文件受产品白名单限制。
- 分发中心：新增 `hot-depth-batch` 资源类型与 `product=depth-batch` 目录接口，面板可直接导入对应快照；更新包地址为 `/hot-depth-batch/packages/<name>`，不与 SHIYIN AI 主软件更新混用。
- 更新快照：`dist/depth-batch-hot-update/20260922093535`，13 个文件，供分发中心导入签名发布。
- 魔塔：已创建并上传说明至 `jiangjiang419/SHIYIN-Depth-Batch`。

缓存检查：`.build` 与 `.codex-tmp` 合计文件大小约 7.4 MiB，低于 20 GiB 上限。

## 1.0.1 发布

- 安装包：`dist/installer/SHIYIN-Depth-Batch-Setup-1.0.1.exe`，107,692,121 字节，SHA-256 `634a66ae6df489b155907b3e743c44fa58c0f4ee4aa077f2ddde5fb5cfda898c`。
- 魔塔路径：`releases/1.0.1/SHIYIN-Depth-Batch-Setup-1.0.1.exe`，公开 HEAD 校验返回同一 ETag。
- 图标采用用户确认的 `generated-images/20260922-depth-batch-icon-v3/image-00004.jpg`，转换为 16 至 256 像素九档 ICO；应用 EXE、窗口、快捷方式、安装器和卸载项统一使用该图标。
- 安装器默认目录改为 `D:\Program Files\SHIYIN-Depth-Batch`，写入该目录时请求管理员权限。
- 应用内更新快照：`dist/depth-batch-hot-update/20260922101611`，包含新图标宿主。

## 1.0.2 魔塔更新验证

- 安装包：`dist/installer/SHIYIN-Depth-Batch-Setup-1.0.2.exe`，SHA-256 `841ee697ae611e608f439205483a2fcce8f8df9e297d671be5575465a7461803`，已发布到魔塔 `releases/1.0.2/`。
- 安装基线序号为 `20260922102509`；公开验证更新序号为 `20260922103240`，确保新安装的 1.0.2 可以立即检查到一次更新。
- 更新器优先使用局域网分发中心，连接失败后读取魔塔 `public/catalog.json`；两种来源共用客户端内置 Ed25519 公钥和相同逐文件 SHA-256 校验。
- 更新成功后写入 `data/update/installed.json` 并清除 `pending.json`，再次检查不会重复提示同一更新。
- 修复独立更新脚本使用 `Copy-Item -LiteralPath` 搭配通配符导致不能复制的问题，改为 `-Path`；更新完成后再启动新程序。
- 魔塔增量包：`updates/20260922103240/SHIYIN-Depth-Batch-Update-20260922103240.shiyin-update`，SHA-256 `1e6bcc582db7f68a754abb67a19a8f3e3aa6c0895e2efb4240177df866d9295e`。

## 1.0.3 更新器修复

- 用户现场的“更新清单无效”来自未包含魔塔回退的新宿主；1.0.3 为更新请求增加 JSON `Accept`、固定 User-Agent、BOM 兼容，以及局域网和魔塔两路的独立诊断信息。
- 更新下载、暂存、设置和状态从受保护的安装目录迁移到 `%LOCALAPPDATA%\SHIYIN-Depth-Batch`，同时兼容读取旧设置。
- 独立更新器在覆盖 `D:\Program Files\SHIYIN-Depth-Batch` 前通过 UAC 请求管理员权限；失败时写入 `apply-error.log` 并显示提示。
- 安装包：`dist/installer/SHIYIN-Depth-Batch-Setup-1.0.3.exe`，107,698,783 字节，SHA-256 `4dd0c6dbf7a7b473aca9f97e4b59395274260416a8d836db20dc0c7b825dcbf7`。
- 安装基线序号为 `20260922105200`；公开验证更新序号为 `20260922105810`。
- 魔塔验证更新包：107,476,910 字节，SHA-256 `4441bb33ef1cda92159ae8d5df8abe5f02f03b7738f850364e522eac903a795b`；公开下载后已验证 Ed25519 签名、整包 SHA-256 和 13 个 ZIP 文件哈希。
