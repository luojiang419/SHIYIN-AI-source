# Seedance 2.0 官方提示词规则集成

状态：已完成（源码）
当前阶段：4/4
最后更新：2026-09-07 18:20

## 当前状态

用户提供的 Seedance 2.0 官方提示词指南已经整理为完整运行时 Skill，覆盖参考生成、编辑、延长/补全、主体绑定、分镜时序、动作、运镜、声音、文字和常见失败预防。Seedance 2.0 型号已精确匹配，Seedance 1.x 与即梦 3.x不再误套。

普通视频、影视视频和专用 LinkFox 视频节点均已进入共享模型适配链。专用节点会保存实际提交词，同模型同素材同设置直接复用，切换模型后从上次实际词转换；LinkFox 网关二次提示词优化已关闭，避免覆盖官方编译结果。

当前无阻塞问题。工作区仍有大量任务外既有修改，均未纳入本任务。

## 下一步

本次源码任务已完成。正式安装版生效需后续重新构建安装包；成片一致性需使用相同素材、设置和随机条件进行真实付费 A/B 审片。

## 当前 TODO

- [x] 阅读官方指南、项目规则、现有任务和调用链
- [x] 集成完整 Seedance 2.0 运行时规则
- [x] 修复精确型号路由与专用 LinkFox 节点漏接
- [x] 增加模型规则、前端请求和提交链测试
- [x] 完成静态检查、定向回归与 Git 检查
- [x] Git 提交与正常推送

## 最近验证状态

- 静态检查：`py_compile`、四份相关 JavaScript `node --check`、`git diff --check` 通过
- 单元测试：Seedance/视频提示词/LinkFox 定向 118 项通过；两个 Node 支持脚本共 4 组检查通过
- 编译：本任务不涉及安装包构建
- 运行测试：全量 1,432 项中 1,429 通过；3 个既有失败属于任务前的 API provider/Kling 工作区改动，与本任务无关；未发起付费视频生成
- 最近 Git commit：bf47255（功能提交，已推送）
- 当前 branch：feat/film-workflow-canvas

---

## 任务目标

以用户提供的 Doubao Seedance 2.0 官方提示词指南为首要规范来源，使自动解析、润色、跨模型转换和专用 LinkFox 节点真正采用 Seedance 2.0 的任务类型、主体绑定、分镜时序、动作、运镜、声音、素材引用和约束规则。

## 当前项目现状

- `canvas_core/video_prompt_registry.py` 负责模型到 profile 的路由。
- `canvas_core/video_prompt_adapter.py` 负责跨模型转换系统提示和结果校验。
- `skills/video-prompt-polish/seedance/SKILL.md` 目前只有简短摘要。
- 普通视频与影视视频节点通过 `CanvasFilmNodes.videoPromptSubmission` 开启适配。
- 专用 LinkFox 节点通过 `linkfox_direct` 直接提交，不执行本地 Skill。
- LinkFox 当前只接收图片；Seedance 原生视频/音频能力只能在实际支持这些字段的 provider 中使用。

## 技术方案

- 把官方指南整理为面向 LLM 的紧凑完整 Skill，去除 HTML、媒体 URL 和重复案例，但保留全部规则类别、关键句式和边界条件。
- 精确识别 Seedance 2.0 / Fast；Seedance 1.x、即梦 3.x继续使用通用规则，避免型号能力污染。
- 专用 LinkFox 节点提交时设置 `auto_adapt_prompt`、来源与稳定 origin key，复用共享后端适配器；同模型同输入复用已成功提交词。
- Seedance 校验继续检查自然语言素材编号，并增加官方结构性关键词契约测试；语义保持由转换系统指令和固定样例测试覆盖。
- 官方规则优先于辅助导演 Skill：采用空间、物理、连续性 QA，但不强制 Cinedance 的英文、精确秒段或平台 @tag 语法。

## 文件 / 模块清单

- 修改 `skills/video-prompt-polish/seedance/SKILL.md`
- 修改 `skills/video-prompt-polish/seedance/SOURCE.md`
- 修改 `canvas_core/video_prompt_registry.py`
- 修改 `canvas_core/video_prompt_adapter.py`
- 修改 `static/js/canvas-linkfox-video.js`
- 修改相关 `tests/`
- 新增本任务文档

## 开发阶段

- [x] 阶段 1：现状与官方规则核对
- [x] 阶段 2：运行时 Skill 与路由
- [x] 阶段 3：专用节点接入与测试
- [x] 阶段 4：整体回归与文档

## 验收标准

- Seedance 2.0 / Fast 的解析、润色和转换 system prompt 包含官方任务类型、主体绑定、镜头时序、动作、运镜、声音和风险规避规则。
- 非 Seedance 2.0 型号不会误命中该 profile。
- 专用 LinkFox 节点的经典/智能画布请求均进入共享适配器；同模型同输入可复用成功词。
- LinkFox 不支持的视频/音频输入仍在付费提交前明确阻止，不虚构原生能力。
- 相关 Python/Node 测试与静态检查真实通过。

## 已完成内容

- 完成官方 1,575 行指南、Cinedance QA 规范、现有实现与发布包资源核对。
- 将官方规则提炼为 12 个运行时章节，移除网页 HTML、媒体链接和重复案例，不丢失规则类别与关键边界。
- 精确识别 Seedance 2.0 / Fast / VIP / 带日期型号，隔离 Seedance 1.x和即梦 3.x。
- 修复 Seedance 官方自然素材编号与旧通用“禁止自然编号”指令冲突。
- 专用 LinkFox 节点接入共享适配器、实际词复用和跨模型转换，保留显式 API 直传兼容。
- 关闭专用节点的 LinkFox 二次 prompt optimizer，保证本地官方 Skill 输出为最终提交词。

## 当前关键修改

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

## 开发日志

- 2026-09-07：确认官方规则内容与四处现有集成缺口，确定最小修复范围。
- 2026-09-07：完成官方 Skill、精确路由、专用 LinkFox 节点接入与二次优化关闭；118 项定向回归通过。
- 2026-09-07：完成全量 1,432 项回归，1,429 通过，确认 3 个失败来自既有未提交修改。
- 2026-09-07：功能提交 `bf47255` 已推送至 `origin/feat/film-workflow-canvas`。

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
