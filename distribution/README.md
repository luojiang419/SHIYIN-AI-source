# SHIYIN 独立分发中心

后续默认热更新，只有用户明确要求时才编译全量安装包。

- 开发运行：`python -m distribution.launcher`。
- 编译独立控制面板：`powershell -ExecutionPolicy Bypass -File tools/build-distribution-center.ps1`。
- 默认构建与发布：`python tools/build-hot-update.py --publish --notes "本次更新说明"`。产物为单个 `.shiyin-update` 签名增量包；仅变动时重编桌面宿主和 backend，不生成安装器。
- 客户端协议迁移：先用 `--bootstrap` 发布单EXE的v2引导，再用 `--updater-only` 发布小型v3更新器修复包，最后按默认命令发布完整v3增量包。三条发布线同时保留并按能力路由。
- 仅修复更新器：`--updater-only` 包含桌面EXE、更新弹窗脚本和HTML缓存版本，不携带backend，也不清理应用目录。
- 仅前端改动：增加 `--web-only`；涉及 Python、Rust 变化时禁止此选项。
- 管理：`127.0.0.1:3013`，必须使用本机 token；局域网下载：本机 IPv4 `:3011`；UDP 发现：`:3012`。
- 本机数据：`D:\SHIYIN-Distribution`。不要删除 signing-key；换密钥必须重新迁移客户端公钥。

控制面板“选择目录”可导入包含 `manifest.json`、`.shiyin-update` 和构建期 `files` 的热更新快照；服务会校验整包 SHA-256、ZIP 内每个条目及签名文件清单后才发布。模型选择已有 `data/system/components/person-depth` 或 `video-depth` 根目录，服务会复制当前 installation 并计算哈希。全量包仅导入已存在的 EXE。

关闭控制面板不终止服务。需要暂停局域网下载时点击“停止服务”。服务启动时是否自动分发在设置中控制，Windows登录自启动可在“外观与后台运行”中开关。

客户端已删除分发服务器生命周期，设置页仅保留下载源。更新清单公钥固定在客户端，陌生签名被拒绝。最老客户端无能力头，只收到单EXE的v2引导；旧v3客户端发送 `package-v3`，只收到更新器修复小包；快速更新器同时发送 `fast-extract-v1`，才收到完整业务增量包。所有v3下载均为一个支持Range续传的 `.shiyin-update`。旧的未签名热更新接口返回409。

## 桌面外观与后台

服务设置可选择跟随系统/深色/浅色，Windows原生标题栏与页面同步。启用“关闭窗口时收至系统托盘”后，可通过托盘恢复；顶部“后台运行”也可直接隐藏。退出控制面板不停止独立下载服务。

“开机自动运行”实际控制当前用户HKCU Run启动项，登录后按“自动运行时隐藏至托盘”选项显示或后台运行。旧Startup快捷方式迁移为disabled备份；重新部署不会重置开关。当前不支持登录前的系统服务启动。
