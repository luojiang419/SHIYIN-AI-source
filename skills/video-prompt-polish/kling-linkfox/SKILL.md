---
name: kling-linkfox-video-prompt
description: LinkFox 可灵 Omni / 2.6 自动解析与跨模型视频提示词适配规范。
source_status: official-document-adapter
---

# LinkFox 可灵 Omni / 2.6

遵循可灵的场景/主体、动作时间线、镜头、光线、声音描述方法。图像定义身份、外观及构图，提示词定义连续变化。每个镜头指定一个主要运镜；台词逐字保留并绑定说话人。LinkFox仅传imageList或首尾帧图片，并未注册Omni element/voice ID，必须用图片1等自然描述，不使用<<<element_N>>>、<<<voice_N>>>等虚构绑定。Omni和2.6的声音、首尾帧能力以LinkFox实际接口为准。

保留用户的主体身份、动作因果、方向、情绪、风格、对白及否定要求。输出直接用于生成的提示词，不输出分析，不堆叠质量标签。素材编号与请求清单完全一致；不支持的能力不得伪造。节点设置控制时长、画幅和分辨率，正文不重复接口参数。

软件适配预算：2000 字符。LinkFox统一不超过2000字符。超限精简重复叙述，不截断对白、动作结尾或引用。
