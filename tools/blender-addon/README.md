# SHIYIN AI Blender Bridge

## 安装包自动安装（推荐）

1. 安装 SHIYIN AI 时，在“Blender 联动插件”页面选择“安装到检测到的 Blender”。
2. 如果 Blender 正在运行，请先保存工程并关闭所有 Blender 窗口，再继续安装。
3. 安装器会调用 Blender 自带的 Python，将插件安装到当前 Windows 用户的 Blender 插件目录并启用，不需要额外安装 Python 或 VC 运行库。
4. 安装完成后无需配对码：Blender 已运行时，SHIYIN AI 会自动连接；Blender 未运行时，在“3D 导演台”节点点击“启动 / 连接 Blender”即可自动打开并连接。

安装器主体需要管理员权限，但插件安装会切回启动安装器的原始登录用户执行，避免把插件误装到管理员账户。静默安装默认只保留插件包、不修改 Blender；需要自动安装时显式传入 `/INSTALLBLENDERPLUGIN=1`，需要明确跳过时传入 `/NOBLENDERPLUGIN=1`。

## 手动安装与失败恢复

自动安装失败不会回滚 SHIYIN AI 主程序。关闭 Blender 后，可重新运行安装包，或在 SHIYIN AI 的“3D 导演台”节点点击“下载插件”，然后在 Blender 中打开“编辑 → 偏好设置 → 插件 → 从磁盘安装”，选择下载的 ZIP 并启用插件。

安装日志位于 SHIYIN AI 安装目录的 `data\logs`。安装辅助程序采用临时目录、旧版备份和失败回滚，且拒绝写入符号链接或目录联接目标。

插件只监听 `127.0.0.1`，通过当前 Windows 用户本地目录中的随机密钥自动换取短期会话令牌。密钥不会发送到浏览器或保存进画布。插件只接受相机同步、场景状态、静帧渲染和 MP4 动画渲染四类白名单命令，不支持执行任意 Python。
