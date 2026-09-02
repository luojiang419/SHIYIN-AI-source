# Lookbook 联网案例研究有效性优化

状态：已完成
当前阶段：5/5
最后更新：2026-09-02 12:11

## 当前状态

已完成 Lookbook 联网案例研究有效性优化：Responses 搜索现可请求高上下文的文字+图片结果，解析并持久化真实查询、完整来源、引用和案例图片；创意总监直接消费完整视觉系统及最多 4 张案例方法图，最终生图仍只使用用户参考图。

已增加研究上下文 SHA-256 签名，需求、风格、参考图、画幅、数量或研究深度变化后自动清理旧参考分析、研究、视觉系统、策划和自动选型。搜索输出的逐张 shot card 会绑定到独立并发生图请求，不再用完全相同的 prompt 重复生成多张。

本任务只优化联网研究运行时和数据链路，不修改任何已有风格预设、预设名称、预设说明或预设 prompt。

当前 Git 工作区已有用户修改：`.gitignore`、`main.py`、`static/js/works.js`、`tests/test_works.py`、`tools/analyze_douyin_videos.py` 及未跟踪测试/任务资料。本任务保留并避开无关修改；`main.py` 现有用户修改位于图片伪扩展名兼容逻辑，与 Lookbook 研究代码不重叠。

当前阻塞：无。

## 下一步

当前任务已完成。后续使用已配置的 Responses API 做一次同素材、同图片模型的“关闭联网 / 开启联网”真实付费 A/B，人工比较四张图的构图差异、动作角色、色彩执行和系列一致性。

## 当前 TODO

- [x] 核对现有 Lookbook 搜索、策划、生成和前端持久化链路
- [x] 核对 OpenAI Responses Web Search 官方来源与图片结果结构
- [x] 扩展 Responses 搜索配置和证据解析
- [x] 实现研究上下文签名与失效
- [x] 让策划阶段消费完整视觉系统和案例图片
- [x] 强化研究产物到最终 prompt 的执行层级
- [x] 补充专项测试与静态检查
- [x] 更新任务文档并检查 diff
- [x] Git 提交并按远程状态推送

## 最近验证状态

- 静态检查：`python -m py_compile main.py canvas_core/ecommerce.py`、`node --check static/js/canvas-lookbook-node.js`、`node --check static/js/canvas.js`、`git diff --check` 通过
- 单元测试：Responses/Lookbook/视频兼容专项 `79 passed`；Responses/Lookbook/电商共享链路 `212 passed`
- 全量测试：`1066 passed, 14 failed`；14 项为当前分支既有影视节点、特殊节点、快捷动作、shell 和主题/缓存旧契约失败，与本任务改动无关
- 预设完整性：`STYLES` 块与 `HEAD` 字节级一致，`Identical=True`
- 运行测试：新源码服务 `http://127.0.0.1:3001` 健康检查通过，版本 `1.0.393`、`runtime_mode=source`；静态页面受账号中间件保护，未绕过登录执行 UI 自动化
- 付费验证：尚未执行真实 Responses 搜索与图片生成 A/B
- 最近 Git commit：`feat: make lookbook web research actionable`

---

## 任务目标

让 Lookbook 节点的联网案例研究对最终生成产生稳定、可观察的影响：研究必须保留真实检索证据，围绕当前素材缺口形成单一可执行视觉方向，并被创意总监完整消费；旧研究不能污染新需求。保持已有风格预设完全不变。

## 当前项目现状

- 后端链路为参考事实分析 → 联网研究 → 创意总监方案 → 图片生成 → 视觉质检。
- `web_search` 已通过 Responses `tools: [{type: "web_search"}]` 调用。
- `canvas_llm` 当前只返回最终文本和 usage，未返回搜索调用、完整来源和图片结果。
- `normalize_lookbook_visual_research` 已有色板、布光、材质、构图等字段，但策划请求只拼接摘要 `search_context`。
- 前端会把摘要、视觉系统、人物分析和计划写回节点；需求变化只清空计划，参考输入变化没有统一派生数据失效机制。
- 最终生图已有成熟的人物、商品、场景、姿态和版式所有权锁，本任务不改变这些锁及 Style Skill 内容。

## 技术方案

### Responses 搜索证据

- 为 Lookbook 搜索启用 `search_context_size=high`。
- 请求文本和图片搜索结果，并通过 `include` 返回 `web_search_call.action.sources` 与 `web_search_call.results`。
- 从原始 Responses output 提取查询、完整来源、引用来源和图片候选，去重后写入任务结果。

### 研究上下文签名

- 基于用户需求、Style ID/版本内容、输入 URL 与角色、画幅和数量生成稳定 SHA-256 签名。
- 签名不一致时清理参考分析、搜索摘要、视觉系统、案例证据、创意方案和自动选型等派生数据。
- 后端为最终权威；前端同步保存签名并在需求/风格变化时立即清理展示状态。

### 案例视觉证据

- 搜索图片最多保留少量高相关候选，包含 image URL、thumbnail、source page 和 caption。
- 只在创意总监多模态请求中作为“案例方法证据”使用，明确禁止复制人物、Logo、文案和独特场景。
- 最终生图仍只接收用户连接的参考图，避免第三方案例抢占身份、商品或场景所有权。

### 执行方案

- 策划阶段直接接收完整 `lookbook_visual_system`、来源摘要、搜索查询和案例图标签。
- 要求输出一个主方向、系列视觉规则和逐张 shot card，拒绝平均混合多个品牌方向。
- 最终 prompt 将创意总监方案作为执行权威；搜索过程元数据不重复堆入图片模型上下文。

## 文件 / 模块清单

预计修改：

- `main.py`
- `canvas_core/ecommerce.py`
- `static/js/canvas.js`
- `static/js/canvas-lookbook-node.js`
- `tests/test_responses_protocol.py`
- `tests/test_lookbook_premium.py`
- `tests/test_lookbook_node_frontend.py`
- 本任务文档

明确不修改：

- `static/js/canvas-lookbook-node.js` 中 `STYLES` 的任何现有预设内容

## 开发阶段

- [x] 阶段 1：现状与官方协议核对
- [x] 阶段 2：Responses 搜索证据层
- [x] 阶段 3：研究失效与案例视觉分析
- [x] 阶段 4：执行方案注入与专项测试
- [x] 阶段 5：整体回归、Git 提交与推送

## 验收标准

- Lookbook 搜索请求可启用文本+图片检索，并保留 Responses 返回的查询、sources 和 image results。
- 没有 `web_search_call` 时不能伪装成“已获得完整搜索证据”，任务元数据明确记录证据状态。
- 创意总监能接收完整视觉系统和少量案例图片，最终生图输入仍只包含用户参考图。
- 修改需求、风格、人物、商品、场景、画幅或数量后，旧研究和旧策划不会复用。
- 最终 prompt 明确包含主视觉方向和逐张 shot card，研究来源元数据不无意义堆叠。
- 所有已有风格预设文本保持字节级不变。
- Python/JavaScript 静态检查及 Lookbook、Responses 专项测试通过。

## 已完成内容

- 确认 OpenAI 官方 Web Search 文档支持 `sources`、`search_context_size` 和图片搜索结果。
- 确认当前 `canvas_llm` 丢弃原始搜索 evidence。
- 确认旧节点研究上下文存在跨需求和跨参考图复用风险。
- Responses 请求支持 `search_context_size`、`search_content_types`、`image_settings` 和 `include`，默认普通搜索协议保持不变。
- 增加搜索 evidence 解析与去重，任务保存 `queries/sources/images/evidence_status`。
- 搜索按人物、商品、场景、材质、姿态和版式输入缺口生成研究重点，只选择一个主案例方向。
- 案例图片只进入创意总监多模态分析；参数不兼容时仅对 400/422 回退到原有纯文本搜索。
- 创意总监接收完整视觉系统、主方向、搜索建议镜头和查询；最终 prompt 有策划时不再重复堆入研究摘要。
- 逐张 shot card 转为不同的独立生图 prompt，并保留单幅照片/禁止拼格约束。
- 前端保存证据、签名、方向和 shot cards；修改需求、搜索开关或风格时立即清理旧派生数据。

## 当前关键修改

- `main.py`：扩展 Responses 搜索工具配置与证据解析；增加 Lookbook 签名失效、定向研究、案例图策划、纯文本兼容回退和逐镜头生图 prompt。
- `canvas_core/ecommerce.py`：创意总监方案存在时不再重复注入搜索摘要，降低 prompt 冗余。
- `static/js/canvas.js`、`static/js/canvas-lookbook-node.js`：持久化研究证据和签名，需求/风格变化清理旧研究；未修改 `STYLES`。
- `static/canvas.html`：更新 Lookbook 与 canvas 脚本缓存版本。
- 三个专项测试文件：覆盖请求体、证据解析、签名失效、文本回退、逐镜头 prompt 和前端状态契约。

## 已知问题

- 真实 Responses 图片搜索和付费生图 A/B 尚未执行；若兼容网关对图片搜索字段返回 400/422，系统会自动使用原有纯文本搜索。
- 当前分支全量测试保留 14 个任务外既有失败，未在本任务中扩大范围修复。

## 开发日志

- 2026-09-02：完成只读诊断；用户确认使用 Responses 协议，并要求优化联网搜索且不修改已有风格预设。
- 2026-09-02：完成搜索 evidence、上下文失效、案例图策划和逐镜头生成链路；专项与共享回归通过，预设块字节级未变化。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：

1. 阅读项目规则和本任务文档。
2. 检查 Git branch 与 `git status`。
3. 保留用户现有未提交修改。
4. 从“下一步”继续。
5. 不修改任何已有 Lookbook 风格预设。
