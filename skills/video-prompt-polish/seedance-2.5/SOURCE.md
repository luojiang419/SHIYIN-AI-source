# 规则来源

核对日期：2026-09-07
类型：official-skill

- 官方 Skill 分发地址：<https://arkdocs.tos-cn-beijing.volces.com/skills/>
- 官方 Skill ID：`sd25-pe`
- 安装命令：`npx --yes skills@latest add "https://arkdocs.tos-cn-beijing.volces.com/skills/" --skill sd25-pe --yes`
- 当前版本：`0.1.1`
- 官方安装产物：`.agents/skills/sd25-pe/SKILL.md`
- 安装来源锁定：`skills-lock.json`

`skills/video-prompt-polish/seedance-2.5/SKILL.md` 是官方安装产物的逐字镜像。开发环境由视频提示词注册表加载该镜像；构建安装包时，`tools/build-installer.ps1` 会再次使用 `.agents` 中的官方安装产物覆盖 staging 副本，并校验 `name: sd25-pe` 与官方标题，保证其他用户无需本机安装 skill 即可使用。

官方文件开头的“触发前的自升级”只适用于具备 shell 的 Agent。应用内提示词优化 LLM 不具备 shell，因此注册表在运行时仅过滤这一段维护指令，完整保留其后的 Prompt Optimizer 规则。模型精确路由、自然语言素材编号、上游字段能力和提交前校验仍由项目适配器负责，不改写官方 skill 文件。
