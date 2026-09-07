# Seedance 2.0 / 2.5 官方提示词规则集成

状态：已完成（源码）
当前阶段：7/7
最后更新：2026-09-07 18:52

## 当前状态

Seedance 2.0 官方规则集成已在提交 `bf47255` 完成并推送。用户现提供 Seedance 2.5 官方指南，需要在不改变 2.0 既有行为的前提下新增独立 2.5 运行时规则。

官方材料已经完整核对。2.5 与 2.0 存在不能合并覆盖的差异：2.5 响应整数秒时间戳、允许多视图主体参考，支持锁定/非锁定任务、30 秒直出、最多 50 个多模态素材、关键帧/故事板/白模、视频音频编辑和 MOV 延长工作流；2.0 仍应优先镜头序号与相对时序。

独立 `seedance-2.5` profile、Skill、精确路由、解析/润色/跨模型共享规则与契约测试已经完成。Seedance 2.0 与 2.5 按精确型号使用互不冲突的时间和任务规则。功能提交 `e41352a` 已推送。

LinkFox 当前没有 Seedance 2.5 型号和原生视频/音频字段，因此本阶段只集成提示词能力，没有新增不可用的上游模型或字段。

当前无阻塞问题。工作区仍有大量任务外既有修改，均不纳入本任务。

## 下一步

下一步首先执行：

本次源码任务已完成。正式安装版生效需后续重新构建安装包；真实 2.5 成片效果需在可用 provider 接入后，使用相同素材、设置和随机条件进行付费 A/B 审片。

## 当前 TODO

- [x] 阅读官方指南、项目规则、现有任务和调用链
- [x] 集成完整 Seedance 2.0 运行时规则
- [x] 修复精确型号路由与专用 LinkFox 节点漏接
- [x] 增加模型规则、前端请求和提交链测试
- [x] 完成静态检查、定向回归与 Git 检查
- [x] Git 提交与正常推送
- [x] 完整阅读 Seedance 2.5 官方指南并核对与 2.0 的差异
- [x] 新增 Seedance 2.5 独立运行时 Skill 与来源说明
- [x] 精确路由 Seedance 2.5，保持 2.0/1.x/即梦型号隔离
- [x] 接入解析、润色和跨模型转换共享链
- [x] 增加并通过 Seedance 2.5 定向测试
- [x] Git 提交与正常推送

## 最近验证状态

- 静态检查：2.5 相关 `py_compile`、`git diff --check` 与 staged `git diff --cached --check` 通过
- 单元测试：核心视频提示词与共享 LinkFox 链 100 项通过；扩大视频提示词/LinkFox 回归 199 项通过
- 编译：本任务不涉及安装包构建
- 运行测试：全量 1,438 项中 1,435 通过；3 个既有失败仍为 `test_canvas_video_clip_editor`、`test_ecommerce`、`test_kling_remote_web_access`，对应任务前已有工作区变化，与本任务无关；未发起付费视频生成
- 最近 Git commit：e41352a（Seedance 2.5 功能提交，已推送）
- 当前 branch：feat/film-workflow-canvas

---

## 任务目标

以用户提供的 Doubao Seedance 2.0 与 2.5 官方提示词指南为首要规范来源，使自动解析、润色和跨模型转换按精确型号采用对应任务类型、主体绑定、分镜时序、动作、运镜、声音、素材引用和约束规则；已有专用 LinkFox 2.0 节点继续保持原行为。

## 当前项目现状

- `canvas_core/video_prompt_registry.py` 负责模型到 profile 的路由。
- `canvas_core/video_prompt_adapter.py` 负责跨模型转换系统提示和结果校验。
- `skills/video-prompt-polish/seedance/SKILL.md` 已包含完整 Seedance 2.0 运行时规则。
- 普通视频与影视视频节点通过 `CanvasFilmNodes.videoPromptSubmission` 开启适配。
- 专用 LinkFox 节点通过共享适配器执行本地 Skill，再由 `linkfox_direct` 提交已验证的实际提示词。
- LinkFox 当前只接收图片；Seedance 原生视频/音频能力只能在实际支持这些字段的 provider 中使用。
- 当前没有 Seedance 2.5 profile；型号会落入 `generic`，无法获得官方锁定任务、时间戳、关键帧、白模与编辑规则。

## 技术方案

- 把官方指南整理为面向 LLM 的紧凑完整 Skill，去除 HTML、媒体 URL 和重复案例，但保留全部规则类别、关键句式和边界条件。
- 精确识别 Seedance 2.0 / Fast；Seedance 1.x、即梦 3.x继续使用通用规则，避免型号能力污染。
- 专用 LinkFox 节点提交时设置 `auto_adapt_prompt`、来源与稳定 origin key，复用共享后端适配器；同模型同输入复用已成功提交词。
- Seedance 校验继续检查自然语言素材编号，并增加官方结构性关键词契约测试；语义保持由转换系统指令和固定样例测试覆盖。
- 官方规则优先于辅助导演 Skill：采用空间、物理、连续性 QA，但不强制 Cinedance 的英文、精确秒段或平台 @tag 语法。
- Seedance 2.5 使用独立 profile，不覆盖 2.0；通过精确型号函数识别 `seedance2.5`、`doubao-seedance-2-5[-pro][-日期]` 等明确 2.5 名称。
- 2.5 Skill 保留官方“有锁定/无锁定”任务决策、整数秒时间戳、多素材映射、白模/故事板/关键帧、编辑/延长/转场和多语言音频规则。
- 2.0 与 2.5 共用图片N/视频N/音频N自然语言引用与主体绑定基础逻辑，但各自使用独立输出约束。

## 文件 / 模块清单

- 修改 `skills/video-prompt-polish/seedance/SKILL.md`
- 修改 `skills/video-prompt-polish/seedance/SOURCE.md`
- 修改 `canvas_core/video_prompt_registry.py`
- 修改 `canvas_core/video_prompt_adapter.py`
- 修改 `static/js/canvas-linkfox-video.js`
- 修改相关 `tests/`
- 新增本任务文档
- 新增 `skills/video-prompt-polish/seedance-2.5/SKILL.md`
- 新增 `skills/video-prompt-polish/seedance-2.5/SOURCE.md`

## 开发阶段

- [x] 阶段 1：现状与官方规则核对
- [x] 阶段 2：运行时 Skill 与路由
- [x] 阶段 3：专用节点接入与测试
- [x] 阶段 4：整体回归与文档
- [x] 阶段 5：Seedance 2.5 官方规则与精确路由
- [x] 阶段 6：共享链适配与定向测试
- [x] 阶段 7：回归、文档、提交与推送

## 验收标准

- Seedance 2.0 / Fast 的解析、润色和转换 system prompt 包含官方任务类型、主体绑定、镜头时序、动作、运镜、声音和风险规避规则。
- 非 Seedance 2.0 型号不会误命中该 profile。
- 专用 LinkFox 节点的经典/智能画布请求均进入共享适配器；同模型同输入可复用成功词。
- LinkFox 不支持的视频/音频输入仍在付费提交前明确阻止，不虚构原生能力。
- 相关 Python/Node 测试与静态检查真实通过。
- Seedance 2.5 型号命中独立 profile，Seedance 2.0、1.x 和普通即梦型号不受影响。
- 2.5 的解析、润色和跨模型 system prompt 包含锁定任务、整数秒时间戳、多素材映射、关键帧/故事板/白模、编辑、延长和声音规则。
- 2.5 提示词继续使用图片N/视频N/音频N自然语言编号，且只引用实际提交素材。

## 已完成内容

- 将用户提供的 1,095 行 Seedance 2.5 官方指南提炼为独立运行时 Skill，保留锁定/非锁定决策、素材上限、时间戳、多视图、白模、故事板、关键帧、编辑、延长、转场和多语言声音规则。
- 新增 Seedance 2.5 精确型号识别和 profile，2.0、1.x、普通即梦及相似名称保持隔离。
- 解析、润色和跨模型适配共用 Seedance 自然语言素材编号与主体绑定，同时按版本使用互不冲突的时间规则。
- 完成官方 1,575 行指南、Cinedance QA 规范、现有实现与发布包资源核对。
- 将官方规则提炼为 12 个运行时章节，移除网页 HTML、媒体链接和重复案例，不丢失规则类别与关键边界。
- 精确识别 Seedance 2.0 / Fast / VIP / 带日期型号，隔离 Seedance 1.x和即梦 3.x。
- 修复 Seedance 官方自然素材编号与旧通用“禁止自然编号”指令冲突。
- 专用 LinkFox 节点接入共享适配器、实际词复用和跨模型转换，保留显式 API 直传兼容。
- 关闭专用节点的 LinkFox 二次 prompt optimizer，保证本地官方 Skill 输出为最终提交词。
- 完成核心 100 项、扩大 199 项及全量 1,438 项回归；全量仅保留 3 个任务前已知失败。

## 当前关键修改

- `skills/video-prompt-polish/seedance-2.5/`：Seedance 2.5 完整运行时规则与可追踪来源。
- `canvas_core/video_prompt_registry.py`、`video_prompt_adapter.py`：2.5 精确识别和专属跨模型转换摘要。
- `main.py`：2.0/2.5 共用自然语言引用和主体绑定，分别使用相对镜头时序与整数秒时间戳输出约束。
- `tests/test_video_prompt_adapter.py`：新增 2.5 型号隔离、规则完整性、系统提示与引用校验契约。
- 对应 Git commit：`e41352a`
- `skills/video-prompt-polish/seedance/`：完整官方规则及来源边界。
- `canvas_core/video_prompt_registry.py`、`video_prompt_adapter.py`：精确型号识别和官方任务编译摘要。
- `main.py`：专用节点适配入口、Seedance 主体绑定/引用规则及输出约束。
- `static/js/canvas-linkfox-video.js`：适配请求、实际词追踪、同模型复用和二次优化关闭。
- 相关测试：型号隔离、规则完整性、真实 manifest、专用节点前后端链路。
- 对应 Git commit：`bf47255`

## 已知问题

- 不进行真实付费成片 A/B；自动测试不能证明不同生成模型输出完全一致。
- Seedance 2.0 原生支持视频/音频参考，但 LinkFox 当前接口只开放图转视频，本任务不会伪造未接入字段。
- 全量回归的 3 个既有失败：`test_canvas_video_clip_editor`、`test_ecommerce`、`test_kling_remote_web_access`，均对应任务开始前已有的 Kling/provider 工作区变化。
- 当前项目没有可真实提交的 Seedance 2.5 provider/model；本任务只完成提示词规则集成，未伪造上游能力，也未进行付费成片验证。

## 开发日志

- 2026-09-07：确认官方规则内容与四处现有集成缺口，确定最小修复范围。
- 2026-09-07：完成官方 Skill、精确路由、专用 LinkFox 节点接入与二次优化关闭；118 项定向回归通过。
- 2026-09-07：完成全量 1,432 项回归，1,429 通过，确认 3 个失败来自既有未提交修改。
- 2026-09-07：功能提交 `bf47255` 已推送至 `origin/feat/film-workflow-canvas`。
- 2026-09-07：完成 Seedance 2.5 官方材料核对，确认锁定任务、整数秒时间戳、多视图、白模、关键帧和 MOV 工作流等与 2.0 的差异。
- 2026-09-07：完成独立 2.5 Skill、精确路由、共享链适配和测试；功能提交 `e41352a` 已推送至 `origin/feat/film-workflow-canvas`。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：

1. 阅读项目规则
2. 阅读本任务文档
3. 检查 Git branch
4. 检查 git status
5. 从“下一步”直接继续
6. 不重复已经完成的阶段
7. 不重复询问已经确认的问题
8. 继续遵守本协议
