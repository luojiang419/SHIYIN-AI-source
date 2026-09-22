# SHIYIN-Depth-Batch 安装包与更新发布

状态：1.0.1 安装包已上传魔塔；应用内更新验收待导入分发中心快照。
下一步：通过分发中心面板导入 `dist/depth-batch-hot-update/20260922093930` 并发布，然后在已安装 1.0.0 客户端点击检查更新。
TODO：
- [x] 取消便携包构建入口，提供 Windows 安装器
- [x] 接入签名增量更新与独立更新进程
- [x] 分发中心按产品隔离深度批量工具更新
- [x] 创建并接入魔塔 `SHIYIN-Depth-Batch` 仓库
- [x] 编译、安装包检查和缓存上限检查
最近验证：1.0.1 Rust `cargo check` 通过；批量界面 Node 测试 5/5 通过；Inno Setup 安装器构建通过；魔塔文件 HEAD 返回 200 且 ETag 与本地 SHA-256 一致。
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

- 安装包：`dist/installer/SHIYIN-Depth-Batch-Setup-1.0.1.exe`，107,221,739 字节，SHA-256 `784f859d8aa26bd78aa6be5bbae52bc90969630550c1602ba43e1d56db6f8b96`。
- 魔塔路径：`releases/1.0.1/SHIYIN-Depth-Batch-Setup-1.0.1.exe`，公开 HEAD 校验返回同一 ETag。
- 应用内更新快照：`dist/depth-batch-hot-update/20260922093930`，更新包 SHA-256 `eb8efb2362c9fab481700577d57f4b9e6ee1a649983be6e7f34527ff30c2e964`。
