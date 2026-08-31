# 桌面安装包 sidecar 版本同步修复

状态：已完成
当前阶段：4/4
最后更新：2026-08-31

## 当前状态

安装 1.0.382 后仍出现黑屏。实际检查发现 Tauri 主程序为 1.0.382，但安装包内 `canvas-backend.exe` 是旧 sidecar：即使传入 `--runtime-mode desktop`，`/api/auth/bootstrap` 仍返回 401，导致 WebView 无法进入页面。现已重新构建 sidecar 并发布 1.0.383。

## 下一步

1. 已重新构建 PyInstaller sidecar，直接验证 desktop bootstrap 返回 303。
2. 已递增版本到 1.0.383 并重新编译 Tauri 和安装包。
3. 已启动 staging 安装包运行 smoke，确认窗口启动、后端和页面数据加载。

## 当前 TODO

- [x] 重新构建 sidecar 并完成独立 bootstrap smoke
- [x] 递增版本并完成安装包构建
- [x] 完成实际启动与页面加载验证
- [x] 更新文档并提交推送

## 验收标准

- 安装包 sidecar 与源码同步，desktop bootstrap 无 token/错误 token/重复导航均返回 303。
- Tauri 启动参数包含 `--runtime-mode desktop`。
- 桌面运行 smoke health=ok、二次启动保护和退出清理通过。
- 安装后窗口显示完整页面，不再黑屏。

## 验证结果

- 重新构建的 sidecar desktop bootstrap smoke：状态 `[303, 303, 303, 303, 303]`。
- 已验证认证首页返回 HTML，`/api/canvases` 返回列表数据。
- Tauri/安装包 smoke：health=ok，启动约 8.4 秒，内存约 223.8 MB，二次启动保护和退出清理通过。
- 安装包：`dist/installer/SHIYIN-AI-Setup-1.0.383.exe`，SHA-256 `4E3B7832D33FCEE7231870FD5498D81631AA9B6623968D93A141D8F75B9AC04D`。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
