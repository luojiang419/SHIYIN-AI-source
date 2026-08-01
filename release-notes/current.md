# SHIYIN AI v1.0.109
- 新增 Grsai API 服务商：支持 `https://grsaiapi.com` 的 nano-banana-2 与 gpt-image-2 图片生成、异步结果查询和模型预设。
- 修复 Grsai 被启动清理逻辑删除、验证阶段误请求 `/v1/models` 以及异步任务 ID 无法解析的问题。
- 修复 API 设置页 Grsai 平台卡片名称为空的问题。
- 更新链路正式收敛为 Windows EXE 安装器，客户端不再选择、下载或执行 ZIP 更新包。
- 移除旧 ZIP 更新器、便携 ZIP 构建/发布分支和相关 CI 烟测，后续 GitHub Release 仅发布 `SHIYIN-AI-Setup-{版本}.exe` 及 SHA-256 校验文件。
- 修复更新过程中 PowerShell、tasklist 等辅助进程创建蓝色命令行窗口一闪而过的问题，更新器及其子进程统一隐藏控制台窗口。
- 保留独立更新器、UAC 静默安装、用户数据保留和 EXE 更新端到端验收链路。
- 更新弹窗新增安装器实时百分比和处理详情，百分比来自 Inno Setup 实际安装进度，不使用阶段递增。
- 修复自动更新后开始菜单快捷方式丢失：安装器固定注册公共开始菜单入口，更新完成后自动校正已有 SHIYIN AI 快捷方式的目标路径。
