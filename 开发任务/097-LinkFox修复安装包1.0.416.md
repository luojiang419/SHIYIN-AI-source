# LinkFox 修复安装包 1.0.416

状态：已完成
当前阶段：3/3
最后更新：2026-09-07

## 当前状态

SHIYIN AI 1.0.416 Windows x64 安装器已完成，包含任务 096 的 LinkFox 修复。已通过安装器版本、SHA-256、载荷一致性及真实冻结后端调用本机模拟网关的完整链路验证。构建包含当前工作树内容，其他任务的未提交修改保持原样。

## 下一步

当前任务已完成，交付 `dist/installer/SHIYIN-AI-Setup-1.0.416.exe`。本轮未执行安装或发布 Release。

## TODO

- [x] 版本同步与更新说明
- [x] PyInstaller、Tauri、Inno Setup 构建
- [x] 安装器与隔离打包后端验证
- [x] 文档与任务独立差异整理；提交推送结果见 Git 历史与最终汇报

## 验收标准

- `dist/installer/SHIYIN-AI-Setup-1.0.416.exe` 存在且版本正确。
- 打包后端健康、LinkFox 资源及冻结程序技能分派验证通过；桌面全流程 smoke 若受用户运行实例阻塞，应保留用户进程并记录限制。
- 生成 SHA-256 文件并记录构建日志。

## 最近验证

- 任务 096 已通过 104 项 Python、3 项 JS 及浏览器连线回归。
- 当前分支：`feat/film-workflow-canvas`；功能提交：`405f9a7`，已推送。
- 9 个版本源同步为 1.0.416；PyInstaller 构建约 44 秒，Tauri Release 约 98 秒，Inno Setup 约 44.5 秒。
- 安装器：`dist/installer/SHIYIN-AI-Setup-1.0.416.exe`，92,546,900 bytes，版本正确，NotSigned。
- SHA-256：`a72513ffc7f2be7b7e5757d12cc87c51312c89e10df283c94a8f365d138dc678`；相邻 `.exe.sha256` 已生成。
- `verify-installer-artifact.ps1` 通过，结果 `.build/installer-1.0.416-verification.json`。
- 完整桌面 smoke 被已安装应用运行实例 PID 35736 阻塞，未关闭用户应用。复用已编译结果，以 `-SkipBackend -SkipDesktop -SkipRuntimeSmoke` 完成打包。
- 隔离冻结后端测试通过：健康与登录、LinkFox 已安装/已配置、3 张参考图仅上传 1 次相同素材、SEED 枚举提交、真实技能子进程、120 秒首次轮询、模拟结果字节转存和画布 URL 读取。未调用真实付费 API；测试字节仅验证传输，不代表真实生成的视频效果。
- 打包的三个画布运行时与源码在预期版本戳处理后相同，两份 LinkFox 技能脚本与源码相同；载荷未包含 `.env`。
- 未执行本轮完整桌面单实例/父进程退出 smoke，也未提供实人 DWPose 输入；未将这些项目报告为通过。
- 日志：`.build/build-installer-1.0.416.log`、`.build/build-installer-1.0.416-package.log`、`.build/linkfox-packaged-smoke-1.0.416.log`。

## 构建验证工具

新增 `tools/smoke-linkfox-packaged.py`。启动器日志放在临时数据目录之外，避免被旧数据迁移器移动而触发 Windows 文件占用；只访问本机模拟网关，退出时清理测试进程。

## 范围

本任务交付安装包；未要求执行安装或发布 GitHub Release。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

检查本任务文档、Git、`.build/build-installer-1.0.416.log` 和构建进程，从下一步继续，不重复启动构建。
