# Seedance 2.5 官方 skill 安装与自动调优集成

状态：已完成
当前阶段：4/4
最后更新：2026-09-07 20:05

## 当前状态

已按官方地址安装 `sd25-pe`，官方源副本位于 `.agents/skills/sd25-pe/SKILL.md`，并生成 `skills-lock.json`。
安装包运行时镜像与官方源副本字节一致；后端 Seedance 2.5 精确路由会加载完整 PE 正文，仅过滤不适用于应用内 LLM 的 shell 自升级段。
安装包构建会用官方源副本覆盖 staging 运行时文件，并校验官方标识。SD2.5 模型切换自动适配、自动解析和润色链契约已通过。
Windows 安装包 `1.0.420` 已完成完整构建、桌面运行时冒烟和安装器契约验证；官方源、运行时镜像与 staging skill 的 SHA-256 完全一致。

## 下一步

本任务已完成。后续如发布 GitHub Release，使用已验证的 `dist/installer/SHIYIN-AI-Setup-1.0.420.exe`；真实 SD2.5 成片效果需等待可用 provider 后付费 A/B 验证。

## 当前 TODO

- [x] 执行官方 `sd25-pe` 安装命令
- [x] 将官方 skill 固化到安装包源目录
- [x] 补齐安装包 profile 校验与官方内容校验
- [x] 增加 SD2.5 模型切换自动调优测试
- [x] 完成 175 项定向回归和静态检查
- [x] 构建并验证新版本安装包
- [x] 完成文档更新与功能 Git 提交
- [ ] 推送版本构建记录（本次最终提交后执行）

## 最近验证状态

- 静态检查：相关 Python `py_compile`、PowerShell parser、定向 `git diff --check` 通过
- 单元测试：视频提示词、影视节点与 H3 相关定向回归 175 项通过
- 编译：`SHIYIN-AI-Setup-1.0.420.exe` 构建成功，大小 92,616,494 字节，SHA-256 `0d4ec4bbc8eb727b3e30e1fc34a7859d3368f713b20b28bcd1fe431aa55a031e`
- 运行测试：桌面启动、内存、单实例、父进程退出清理冒烟通过；DWPose 真人输入冒烟因未提供素材按构建规则跳过
- 全量测试：1,452 项通过；3 个任务前既有失败仍为 `test_canvas_video_clip_editor`、`test_ecommerce`、`test_kling_remote_web_access`，无新增失败
- 打包资源：官方源、运行时镜像、staging skill SHA-256 均为 `ee04557ba9a1c9f5517b574e24fc73d0022b22254373074db4c11f3d0635ea57`
- 最近 Git commit：`a3abed4`（官方 skill 与自动调优功能）

## 任务目标

使用官方 `sd25-pe` Seedance 2.5 Prompt Optimizer，并将其编译进安装包，使所有用户在视频生成功能节点切换到 Seedance 2.5 时自动调用提示词调优；保持 Seedance 2.0、其他视频模型和既有视频生成链路行为不变。

## 技术方案

- 官方 `sd25-pe` 作为项目内 `skills/video-prompt-polish/seedance-2.5/SKILL.md` 的唯一运行时正文，`skills-lock.json` 记录来源和 hash。
- 复用 `canvas_core.video_prompt_registry` 的精确 `seedance-2.5` profile；自动解析、手动润色、模型切换适配和视频提交共享 `_video_prompt_skill`。
- 前端 `CanvasFilmNodes.videoPromptSubmission` 继续以目标 provider/model 和上一模型结果判断是否需要 `auto_adapt_prompt`，切换到 SD2.5 必须为 true。
- `tools/build-installer.ps1` 复制整个 `skills/video-prompt-polish` 到安装包，并在 staging 校验 2.5 文件存在且包含官方 skill 标识。

## 验收标准

- 安装包 staging 中包含官方 `seedance-2.5/SKILL.md`，且构建脚本拒绝非官方/空文件。
- `seedance2.5`、`doubao-seedance-2-5-pro-*` 等型号加载 `sd25-pe`，不影响 Seedance 2.0 和其他模型。
- 视频节点从任意模型切换到 SD2.5 时请求 `auto_adapt_prompt=true`，自动解析、润色和提交入口均使用官方规则。
- 定向 Python/Node 测试和静态检查真实通过。

## 已知问题

- 本任务不伪造尚未接入的 Seedance 2.5 上游 provider；只保证提示词调优和安装包携带。
- 真实付费视频成片效果仍需在可用 provider 上另行 A/B 验证。
- 安装器当前为未签名状态，与项目现有发布方式一致。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：阅读项目规则、本任务文档，检查 Git 状态，从“下一步”继续；不要重复官方 skill 安装和已完成的固化步骤。
