# LinkFox 异步请求回传修复与安装包

状态：已完成
当前阶段：4/4
最后更新：2026-09-07

## 当前状态

105 已完成 SD2.0 5 秒真实调用。正确网关为 tool-gateway.linkfox.com，Authorization 原始 Key，模型 SEED；创建返回 taskId，查询返回 PROCESSING/SUCCESS/FAILED 与 resultList/errorMsg。当前 UI 整体阻塞到生成下载结束，中途只有计时。
本任务已复用既有 canvas-video-tasks 持久化机制，为 LinkFox 接入独立提交/查询/落盘，UI 展示上游任务号、状态和失败原因。1.0.418 安装器已编译，冻结程序真实 SD2.0 5 秒视频生成、回传和完整解码通过。
保留工作区其他任务未提交改动，主要共享文件原始副本位于 .codex-artifacts/linkfox-async/baseline。

## 下一步

当前任务已完成。交付 dist/installer/SHIYIN-AI-Setup-1.0.418.exe 与相邻 .sha256 文件；未执行安装或发布 Release。用户当前应用保持运行，安装新版后启用新流程。

## TODO

- [x] 异步后端与有界错误处理
- [x] 前端真实状态与结果回传
- [x] 相关回归和真实 SD2.0 验证
- [x] 版本同步、安装器编译与冻结后端冒烟检查
- [x] 独立提交与 push：227d015，feat/film-workflow-canvas

## 验收标准

创建接口返回真实上游 taskId；保存请求与返回而无 Key；任务查询终态正确；失败不会无限计时；成功文件可解码；重复 task_id 不重新提交；重启后只续查。所有 LinkFox UI 入口走同一机制。1.0.418 安装器、SHA-256 与打包后端验证通过。

## 最近验证

100 项 Python 定向回归通过，覆盖既有 H3/可灵持久化机制、LinkFox 提交/查询/失败/超时/重复请求/重启恢复/下载失败重试/专用节点无需LLM。Node 异步交互测试通过，覆盖响应丢失仅查询、成功回传与失败状态。Chrome headless 真实点击普通视频和影视节点、taskId 展示、跨模型转换保留实际词均通过。
1.0.418 已同步版本，PyInstaller 及 Tauri 编译成功（Tauri 1m38s）。首次完整桌面 smoke 被现有已打开的用户应用 PID46948 拦截，未关闭用户应用。最终包复用桌面程序重建后端，改用隔离的冻结后端验证，不把完整桌面 smoke 标记通过。最终构建日志 .build/build-installer-1.0.418-verified.log。
冻结后端模拟网关检查通过：专用节点仅 LinkFox Key、空提示词可提交；本地图上传、SEED 枚举、taskId 返回、重复请求只有一次上游提交、下载并回传均通过。
冻结后端真实调用：2.28 秒返回 taskId=2096856107412135936，重复本地 ID 返回同一任务；328.63 秒取得 succeeded，已下载 1,531,788 字节视频，完整解码121帧/24fps，1280×720，时长5.0417秒。证据位于 .codex-artifacts/linkfox-async/real/submitted.json、latest.json、verified.json、seedance2-5s.mp4。
安装器验证通过：92,576,881 bytes；SHA-256=0d40aa33b624d2d492dabf906b3f970f15c4cc1230b86bf8061f3e0db0d7a1d4；签名状态NotSigned。三个画布脚本与源码仅存在预期版本戳差异。
独立暂存后端函数与实际测试工作树逐项一致，JS语法与git diff --check通过。只提交本任务差异，保留既有未提交改动；没有提交Key或构建产物。

## 文件与技术方案

canvas_core/linkfox_video.py：原生异步网关协议；main.py：接入 canvas-video-tasks。
static/js/canvas-linkfox-video.js 与两种画布：共用提交、状态显示、恢复与返回逻辑。
新增针对真实响应形态的测试，扩展打包后端 smoke。沿用 tools/build-installer.ps1 和项目版本同步脚本，不发布 Release、不执行安装。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

阅读本文件与105任务文档、检查 Git 和构建日志，从下一步继续；已有 taskId 只查询，不重复提交。
