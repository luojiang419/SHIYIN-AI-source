# LinkFox 统一视频节点与跨模型提示词适配

状态：已完成
当前阶段：4/4
最后更新：2026-09-07

## 当前状态

已接入 LinkFox 7 模型、5 组带来源的运行时提示词技能，复用现有 H3/可灵技能。两个独立节点及智能画布的生成提交均接入共享转换逻辑。
按用户最新补充：模型 A 的解析/实际生成词直接转换为模型 B 的规则，不以 H3 为中间格式。节点保存上次成功提交词及素材顺序；已有词时转换请求不携带图片/视频给 LLM，首次无词或主动解析才调用视觉模型。同模型同设置直接复用实际词。
分支 feat/film-workflow-canvas。功能提交 13ebd9f 已推送 origin。已核对保留所有既有未提交修改；增量基线在系统临时目录 shiyin-linkfox-unified-1dl6rgaq。

## 下一步

当前任务已完成。源码运行即可使用；本次未构建安装包，未发起真实付费视频任务。
成片质量需要用户提供案例后进行 A/B 审片，不能由提示词规范或模拟测试保证。

## 当前 TODO

- [x] 调用链和 LinkFox 模型矩阵核对
- [x] 官方模型技能、来源与适用范围注册表
- [x] LinkFox provider 与统一参数面板
- [x] 任意模型直接转换与首次图片/视频自动解析
- [x] 回归、浏览器验证与文档
- [x] commit/push：13ebd9f，已推送 origin/feat/film-workflow-canvas

## 最近验证状态

- 本任务最终回归：21 个相关测试文件，242 passed；包含缺少 Key 前置拦截、同模型复用、任意来源直接迁移及海螺运镜语法迁移。
- Python py_compile、四个 JS 的 node --check 通过。
- 隔离浏览器：两个节点选择 LinkFox、模型参数限制、真实点击提交、前一模型实际词作为后一模型输入、关闭重复解析、编辑器原文保留均通过。生成接口由 fixture 拦截，不消耗额度。
- FFmpeg 实测：6 秒红/蓝视频均匀抽帧，验证起点及结尾都被解析采样覆盖。
- 截图与请求证据：.codex-artifacts/linkfox-unified/two-nodes.png、result.json。
- 独立暂存版本通过 Python AST / JS 语法检查；既有未提交源码修改单独保留。
- 提交后核对原有未提交差异完整保留；隔离浏览器已关闭，测试 fixture 服务已停止。
- 上一任务：180 项定向测试通过，功能 f7639b1 / 文档 3bbd142 已推送

## 任务目标与验收

- 视频生成及影视制作的生成视频节点可直接选择 LinkFox 及其 7 种模型；参数、图片数量、首尾帧和声音符合实际网关能力。
- 自动解析、手动润色和点击生成时的转换共用同一目标模型技能；支持 H3 以外的来源，保持原文与提交词可追踪。
- 视频素材可作为解析依据；目标不支持直接视频引用时不得悄悄丢弃，使用明确的分析/首帧转移流程并记录实际采用方式。
- 校验失败不提交付费视频；同模型重复请求不反复改写已规范化词，切换模型直接采用前一模型实际词，保留编辑器创意原文供追溯。
- 不承诺不同模型随机生成必然一致或更好，最终质量需要真实成片 A/B 验收。

## 技术方案

- 后端 LinkFox 合成 provider 接入已有配置与调用链，复用现有本地素材 OSS 上传和 skill 子进程。
- 前端复用 CanvasLinkfoxVideo 的模型矩阵，提供统一节点设置组件；自动处理模型固定参数，无法兼容的素材数量明确报错。
- 模型技能注册表记录官方来源、核对日期、规范类型（官方技能/官方文档整理）和传输限制。第三方 GitHub 技能不冒充官方。
- 通用转换器保留主体、动作因果、镜头方向、节拍、对白、声音和参考关系；不原样跨传私有标签，不硬截断，不追加无意义质量词。
- 自动解析只处理用户已连接的素材；视频不能由提示词保证像素级复现。
- 生成成功后记录实际提示词、provider/model、生成设置及真实素材顺序；后一次按原始输入指纹匹配，直接转换该词。编辑器原词不被覆盖；用户改词或素材后不会串用旧记录。
- 有解析词时 LLM 请求的 images/videos 均为空。源视频转图入口只保留必要起始帧提取，不重新做视觉语义解析；原词不足时用户可主动点击解析。
- 账户隔离的转换缓存：成功结果最多 128 项，1 小时有效，目标模型/规则、素材、参数和助手路由变化使缓存失效。

## 规范来源与适用范围

- LinkFox 官方网关技能：[linkfox-ai/linkfox-skills](https://github.com/linkfox-ai/linkfox-skills)，核对单图/多图调用规格。
- 海螺：[MiniMax-AI/skills 视频指南](https://github.com/MiniMax-AI/skills/blob/main/skills/frontend-dev/references/minimax-video-guide.md)，运行时整理为海螺技能。
- Wan：[阿里云官方提示词指南](https://help.aliyun.com/zh/model-studio/text-to-video-prompt)。
- HappyHorse：[公开创作技能](https://github.com/modelstudioai/awesome-happyhorse-prompts/blob/main/happyhorse-prompt-craft-SKILL.md)，采用 [ImageN] 图片引用并记录仓库来源；不额外假定组织归属。
- Seedance：[官方文档目录](https://www.volcengine.com/docs/82379/2222480?lang=zh)；正文读取受限，采用保守自然语言适配，明确标记来源限制。
- 可灵：[官方模型指南](https://kling.ai/quickstart/klingai-video-3-model-user-guide)，LinkFox 接口不创建 CLI 的 element/voice 绑定。
- 未识别型号使用通用视频规范，不能宣称已具备该未知型号的官方专用技能。

## 文件 / 模块清单

main.py；canvas_core/linkfox_video.py、video_prompt_adapter.py 与新增规则注册表模块；static/js/canvas.js、canvas-film-nodes.js、canvas-linkfox-video.js、smart-canvas.js；skills/video-prompt-polish/；相关 tests。

## 已知问题

LinkFox 当前图转视频接口没有直接视频/音频参考字段；外部 film 应用代理列表不属于本项目独立节点生成接口。
LinkFox 官方多图 API 文档与本地高层技能对部分能力的描述有差异；可灵 Omni 时长采用官方多图接口的保守 5/10 秒集合，HappyHorse 固定声音沿用现有编排能力，不宣称已做真实网关验证。
尚未进行真实付费成片比较或安装包构建。模型固有的图像数量、声音、时长限制无法用提示词消除。

## 已完成内容与开发日志

- 2026-09-07：读取 LinkFox 本地技能，确认官方仓库 linkfox-ai/linkfox-skills 和 MiniMax-AI/skills，开始逐模型核对。
- 2026-09-07：完成共享 provider/参数组件/模型规则和跨模型迁移；浏览器发现并修复影视声音固定关闭及 Wan 空比例被改为16:9。
- 2026-09-07：依据用户补充，切换模型直接复用上一模型实际提示词；文本迁移不再携带视觉素材，增加成功记录和同模型直接复用测试。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

读取项目规则和本文，检查 branch/status，以实际代码为准从“下一步”继续；保留其他任务的工作区修改，仅提交本任务增量。
