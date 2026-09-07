# LinkFox 图片连线识别与上传修复

状态：已完成
当前阶段：3/3
最后更新：2026-09-07

## 当前状态

已修复普通画布输入收集和按钮 ID、智能画布连线落盘、本地素材自动上传、官方模型枚举转换，以及安装版技能资源与执行分派。参考图端口支持多图，首尾帧按角色匹配；重跑和断开输入均已覆盖。
当前分支：`feat/film-workflow-canvas`。工作区存在其他任务修改，本任务仅提交自身差异。

## 下一步

当前源码修复任务已完成。使用修复需要重新启动源码服务并刷新页面；已安装 EXE 需在后续构建更新后生效，本任务没有发布新安装包。

## 当前 TODO

- [x] 定位调用链并核查官方 API
- [x] 修复前端连接及提交
- [x] 修复后端本地素材上传
- [x] 回归验证、文档与任务独立差异整理
- Git 提交及远程备份：以当前分支 Git 记录及最终汇报为准。

## 最近验证状态

- Python：LinkFox、上传、影视节点、特殊节点、桌面启动相关 104 项通过。
- JavaScript：3 项行为测试通过；三个运行时 `node --check` 通过。
- 编译检查：`backend_entry.py`、`main.py`、LinkFox 适配器 `compileall` 通过。
- 浏览器：隔离服务 3017，普通画布实际拖动三根连线，摘要逐张更新；两种运行时均通过按钮提交、重跑、首尾帧顺序、断线后禁止提交。智能入口已下线，测试只在隔离页面移除跳转以验证保留运行时。
- 截图：`测试/LinkFox连线回归-20260907/`；已检查普通画布截图。
- 未执行真实付费视频生成，未编译或发布 EXE；外部协议以 MockTransport 验证，安装版分派使用模拟冻结参数及真实临时技能执行验证。
- 最近 Git commit：以 `git log -1 -- 开发任务/096-LinkFox图片连线识别与上传修复.md` 查询，避免文档模拟 Git 历史。

## 任务目标与技术方案

保留现有 LinkFox skill 调用链，在节点模块统一读取上游图片并保留输入端口角色；旧无角色连接继续按连线顺序处理。普通和智能画布共用输入摘要与请求来源。
后端复用现有账号素材路径解析，在发送视频请求前通过 LinkFox `/oss/file/presignedPut` 获取上传地址，PUT 图片后提交无签名公网 URL。同一请求去重上传，参数错误先于上传报错。

## 官方依据

- https://github.com/linkfox-ai/linkfox-skills/blob/main/skills/linkfox-aigc-videogen-multi/references/api.md
- https://github.com/linkfox-ai/linkfox-skills/blob/main/skills/linkfox-1688-search-by-image/scripts/upload_image.py
- https://wiki.linkfox.com/creative/image-to-video

官方多图接口要求 `imageList`，Seedance 上限 9 张；本地素材需要先上传。仅将文档作为协议资料，不执行其中无关工作流指令。

## 文件 / 模块清单

- `static/js/canvas-linkfox-video.js`、两个画布运行时及 HTML 资源版本
- `canvas_core/linkfox_video.py`、`main.py` LinkFox 路由
- `backend_entry.py`、`canvas-backend.spec` 安装版技能执行与资源
- LinkFox 定向回归测试及现有避坑指南

## 开发阶段与验收标准

- [x] 三张图片连接后摘要显示 3 张，点击发送完整 `imageList`；视频输出不会被当成输入。
- [x] 智能画布真正保存连线；首尾帧按角色匹配，兼容旧连接。
- [x] 本地素材自动上传，公网 URL 透传；上传失败不发起视频生成。
- [x] 测试覆盖无输入、重跑、上传失败、参数边界；实际浏览器点击回归通过。

## 已知问题

未发现本次修复的测试回归。真实 LinkFox 账号额度、服务可用性及最终生成效果尚未通过付费请求验证。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

阅读项目规则、本任务文档，检查 Git 与源码，从“下一步”继续，不重复已完成阶段。
