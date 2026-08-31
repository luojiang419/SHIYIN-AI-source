# 桌面 WebView 旧导航恢复修复

状态：已完成
当前阶段：4/4
最后更新：2026-08-31

## 当前状态

1.0.381 的源码和安装包均已移除 bootstrap URL 中的一次性 token；问题根因是安装包使用共享 WebView2 配置目录，旧版本会话恢复可能重新展示包含已消费 token 的旧 bootstrap 页面。现已改为按版本隔离目录并发布 1.0.382。

## 下一步

1. 已将桌面 WebView2 数据目录恢复为按 `CARGO_PKG_VERSION` 隔离。
2. 已更新版本并构建/运行桌面 bootstrap 与安装包 smoke。
3. 已更新本文档并提交。

## 当前 TODO

- [x] 按版本隔离 WebView2 配置目录
- [x] 版本递增并完成静态检查与专项测试
- [x] 完成打包运行 smoke
- [x] 更新文档并提交推送

## 最近验证状态

- 静态检查：`python -m py_compile canvas_core/auth.py main.py`、`git diff --check`、版本同步检查通过
- 单元测试：`tests/test_desktop_bootstrap.py tests/test_security.py` 共 5 项通过
- 编译：Tauri release、安装包构建通过
- 运行测试：桌面运行 smoke 通过；desktop bootstrap smoke 状态 `[303, 303, 303, 303, 303]`
- 安装包：`dist/installer/SHIYIN-AI-Setup-1.0.382.exe`，SHA-256 `0D4A0CC09D97D681B13461285427A9C225CC432577E97C34471920C355E7271A`
- 最近 Git commit：`ae5d7cd fix: isolate desktop webview sessions by version`

---

## 任务目标

避免升级或异常退出后 WebView2 恢复旧的带 token bootstrap 页面，确保桌面窗口每次启动都进入当前版本的无 token bootstrap 并建立可用管理员会话。

## 技术方案

`src-tauri/src/lib.rs` 中使用 `data/cache/webview2/<版本>` 作为 `WebviewWindowBuilder` 的 `data_directory`。已有旧版本目录清理逻辑可继续回收历史数字版本目录；共享目录不主动删除，以免影响用户数据。

## 验收标准

- 桌面启动 URL 不含 token。
- 每个版本使用独立 WebView2 数据目录，不恢复旧版本 bootstrap 页面。
- desktop 模式 bootstrap 无 token、错误 token、重复导航均返回 303。
- source 模式错误 token 和非 loopback 来源仍拒绝。
- 安装包 smoke、相关测试和构建通过。

## 文件 / 模块清单

- 修改：`src-tauri/src/lib.rs`
- 修改：`VERSION`、同步版本文件
- 修改：本文档

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
