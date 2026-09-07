# 规则来源

核对日期：2026-09-07
类型：official-document-derived，本项目从官方指南提炼的运行时适配技能，不冒充上游原始文件。

- 官方文档：<https://www.volcengine.com/docs/82379/2222480?lang=zh>
- 用户提供原文：`Doubao Seedance 2.0 系列模型提示词使用方法和相关技巧`，2026-09-07，共 1,575 行。
- LinkFox 调用规格：<https://github.com/linkfox-ai/linkfox-skills/tree/main/skills/linkfox-aigc-videogen-multi>

运行时版本保留官方文档中的任务分类、推荐句式、主体定义、分镜时序、动作与运镜、画质/风格/约束、声音与文字、图片/视频参考、视频编辑/延长及常见问题处理。已移除网页 HTML、媒体 URL、重复版式和不参与提示词编译的后期软件操作步骤。

模型原生能力与当前网关能力分开处理：Seedance 2.0 原生支持图片、视频和音频联合生成；LinkFox 当前只开放图转视频请求，因此 LinkFox 路径不得伪造视频编辑、延长或音频参考字段。
