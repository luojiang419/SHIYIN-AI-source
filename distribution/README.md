# SHIYIN 独立分发中心

后续默认热更新，只有用户明确要求时才编译全量安装包。

- 开发运行：`python -m distribution.launcher`。
- 编译独立控制面板：`powershell -ExecutionPolicy Bypass -File tools/build-distribution-center.ps1`。
- 默认构建与发布：`python tools/build-hot-update.py --publish --notes "本次更新说明"`。仅变动时重编桌面宿主和 backend，未生成安装器。
- 仅前端改动：增加 `--web-only`；涉及 Python、Rust 变化时禁止此选项。
- 管理：`127.0.0.1:3013`，必须使用本机 token；局域网下载：本机 IPv4 `:3011`；UDP 发现：`:3012`。
- 本机数据：`D:\SHIYIN-Distribution`。不要删除 signing-key；换密钥必须重新迁移客户端公钥。

控制面板“选择目录”可导入包含 `manifest.json/files` 的热更新快照；模型选择已有 `data/system/components/person-depth` 或 `video-depth` 根目录，服务会复制当前 installation 并计算哈希。全量包仅导入已存在的 EXE。

关闭控制面板不终止服务。需要暂停局域网下载时点击“停止服务”。服务启动时是否自动分发在设置中控制；Windows 登录自启动由部署脚本创建的 Startup 快捷方式负责。

客户端已删除分发服务器生命周期，设置页仅保留下载源。更新清单公钥固定在客户端，陌生签名被拒绝。旧的未签名热更新接口返回 409，以免旧更新器静默安装新快照；旧客户端首次需用迁移工具更新桌面宿主。
