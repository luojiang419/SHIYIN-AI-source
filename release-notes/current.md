# SHIYIN AI v1.0.106

- 更新链路正式收敛为 Windows EXE 安装器，客户端不再选择、下载或执行 ZIP 更新包。
- 移除旧 ZIP 更新器、便携 ZIP 构建/发布分支和相关 CI 烟测，后续 GitHub Release 仅发布 `SHIYIN-AI-Setup-{版本}.exe` 及 SHA-256 校验文件。
- 修复更新过程中 PowerShell、tasklist 等辅助进程创建蓝色命令行窗口一闪而过的问题，更新器及其子进程统一隐藏控制台窗口。
- 保留独立更新器、UAC 静默安装、用户数据保留和 EXE 更新端到端验收链路。
- 本版本用于验证 EXE 更新过程中不再出现命令行窗口闪现。
