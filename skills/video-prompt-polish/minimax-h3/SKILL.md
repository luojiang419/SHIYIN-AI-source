# MiniMax H3 视频提示词规范

## 任务模式

根据参考素材判断 T2VA（纯文本）、I2VA（首帧）、FL2VA（首尾帧）、L2VA（尾帧）或 Ref2VA（全参考）。有参考图片/视频时以素材为画面事实依据；没有参考素材时只在不改变原意的前提下补足最少量上下文。

## 基础模式输出结构

按顺序输出三个字段：

`integrated_multimodal_description: [Shot 1] ...`

`overall_soundscape: ...`

`non_diegetic_music: ...`

正文按时间线写场景、主体、动作先后、镜头运动、声音和必要对白；后续镜头使用 `[Shot N] At MM:SS.mmm`。摄影机运动包含类型，只有有意义时才补幅度和速度。无环境音或非剧情音乐时分别写 `N/A`。

## 引用标签

- 图片帧锚点使用 `<Picture N>`，视频级来源使用 `<Video N>`，独立音频使用 `<Audio N>`。
- 全参考 Ref2VA 才使用六段：`subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`。
- 保持 `<Picture N>`、`<Video N>`、`<Audio N>` 和 `<Subject N>` 的编号及含义一致。

## 输出限制

使用 MiniMax H3 可识别的结构化格式；只输出最终提示词，不解释过程。优先简洁和可执行，保留用户原意，不堆砌形容词或虚构剧情。
