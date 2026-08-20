# 版本必须以 GitHub Release 为基线

SHIYIN-AI 的 CI 发布工作流会从 GitHub 最新 Release 解析下一版本，并只在 CI 临时工作区注入版本号，不会回写源码 `VERSION`。本地构建不能简单执行 `VERSION + 1`；必须先读取公开 Release 最新标签，再把目标版本统一注入 `VERSION`、Tauri、npm、发布说明和安装器。
