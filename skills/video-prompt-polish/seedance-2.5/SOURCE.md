# 规则来源

核对日期：2026-09-07
类型：official-document-derived，本项目从官方指南提炼的运行时适配技能，不冒充上游原始文件。

- 官方 Skill 分发地址：<https://arkdocs.tos-cn-beijing.volces.com/skills/>，Skill ID：`sd25-pe`。
- 官方文档媒体与示例路径：<https://arkdocs.tos-cn-beijing.volces.com/videos/video-generation/sd25-pe/>。
- 用户提供原文：`Doubao Seedance 2.5 模型提示词使用方法和相关技巧`，2026-09-07，共 1,095 行。
- 对照规范：Doubao Seedance 2.0 官方指南与项目内 `seedance` 运行时 Skill。

运行时版本保留官方文档中的锁定/非锁定任务决策、素材上限与稳定范围、多素材映射、整数秒时间戳、多视图、白模、故事板、独立关键帧、视频和音频编辑、延长、一键成片、无缝转场、多语言声音与 2.0 差异。网页 HTML、远程媒体、重复版式和仅用于展示结果的长案例已移除。

模型原生能力与当前网关能力分开处理：Seedance 2.5 原生支持图片、视频和音频联合输入；当前 LinkFox 模型表仅有 Seedance 2.0 / Fast 且接口只开放图片，因此不得借提示词虚构 LinkFox 2.5、视频编辑、延长或音频字段。
