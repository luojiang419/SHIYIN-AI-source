# MiniMax H3 skill 来源

本目录内的 `SKILL.md`、`references/base-en.txt` 和 `references/ref-en.txt` 来自 MiniMax 官方公开仓库：

- 仓库：https://github.com/MiniMax-AI/MiniMax-H3
- 官方 skill 路径：`skills/h3-prompt-writing/`
- 原始文件：
  - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/SKILL.md
  - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/base-en.txt
  - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/ref-en.txt

后端会同时读取 `SKILL.md` 和 `references/*.txt`，将完整规则注入视觉模型，而不是只发送摘要。

