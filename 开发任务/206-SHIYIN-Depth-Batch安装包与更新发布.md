# SHIYIN-Depth-Batch 安装包与更新发布

状态：1.0.2 安装包和魔塔签名更新已发布，更新发现与下载链路验证通过。
下一步：用户安装 1.0.2 后点击检查更新，现场确认独立更新器关闭、替换和重启的界面体验。
TODO：
- [x] 取消便携包构建入口，提供 Windows 安装器
- [x] 接入签名增量更新与独立更新进程
- [x] 分发中心按产品隔离深度批量工具更新
- [x] 创建并接入魔塔 `SHIYIN-Depth-Batch` 仓库
- [x] 编译、安装包检查和缓存上限检查
最近验证：1.0.2 Rust `cargo check`、魔塔回退联网测试及批量界面 Node 5 项通过；Inno Setup 构建通过。公开目录签名、107,476,054 字节更新包 SHA-256 和 ZIP 内 13 个文件逐项校验通过。
branch/commit：`feat/video-depth-batch-delivery` / 待提交
阻塞：无。

[CODEX_LONG_TASK_CONTINUE_V3]

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
