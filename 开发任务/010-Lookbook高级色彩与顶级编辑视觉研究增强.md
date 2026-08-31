# Lookbook 高级色彩与顶级编辑视觉研究增强

状态：已完成
当前阶段：5/5
最后更新：2026-08-31

## 当前状态

当前 Lookbook 节点已经支持选择视觉 Skill，并在后台执行联网案例摘要、视觉创意总监策划、生图和视觉质检。现有检索提示词只要求输出一段 500 字以内的综合方法摘要，最终生成 recipe 也没有独立的色彩系统、参考来源类型、材质与摄影工艺字段，导致“联网研究”对画面高级感的约束不够强。

当前已完成 `main.py`、`canvas_core/ecommerce.py`、`static/js/canvas-lookbook-node.js`、`static/js/canvas.js` 与样式/缓存版本增强：把优秀杂志/时尚品牌案例研究变为结构化的色彩与编辑视觉 brief，明确只学习方法、不复制具体品牌资产，并将结构化结果强制注入最终生成提示词。只有人物输入时会先解析面貌、发型、体态和现有穿着，再据此搜索街拍/时装大片方法。

当前阻塞：无。

## 下一步

1. 如发布安装包，重新构建并带入新的静态资源查询串。
2. 使用可用图片 API Key 做一次真实的“人物 + 时尚街景”联网研究与生图验收，重点观察人物身份、现有穿着、城市环境和非白底构图。

## 当前 TODO

- [x] 核对现有 Lookbook 节点、任务链路和测试
- [x] 创建结构化高级视觉研究选项
- [x] 升级全网案例检索与色彩分析输出
- [x] 将高级色彩/编辑视觉 brief 注入生成提示词
- [x] 在节点显示研究与高级视觉状态
- [x] 完成专项回归、文档更新和 Git 提交

## 最近验证状态

- 静态检查：`node --check static/js/canvas.js static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：Lookbook/电商专项 `149 passed`；新增高级研究专项 4 项包含在内
- 编译：`python -m py_compile main.py canvas_core/ecommerce.py` 通过
- 全量回归：`999 passed, 14 failed`；失败集中在当前分支已有的影视节点、smart-canvas 旧契约和旧主题缓存断言，与本轮 Lookbook 改动无关
- 运行测试：未执行付费生图；新增测试验证“先人物事实分析、后 web_search、再注入结构化视觉系统”
- 最近 Git commit：待本轮提交

---

## 任务目标

让 Lookbook 节点在用户选择风格的基础上，自动联网研究全网优秀时尚视觉案例，重点解析世界知名时尚杂志、品牌 campaign 和编辑摄影的色彩、光影、材质、构图与版式方法，生成可执行的高级视觉 brief，并把它稳定注入生图提示词，使最终画面具有明确的色彩策略和顶级商业质感。

## 技术方案

- 复用现有 Responses `web_search` 能力，不下载或复制受版权保护的案例图，不复刻具体品牌 Logo、人物或文案。
- 研究阶段输出结构化字段：参考类型与来源、主色/辅色/强调色、明度与饱和度关系、色彩比例、光色、材质、摄影/印刷工艺、构图与留白、可迁移方法及禁止复制内容。
- 研究查询根据用户需求、已选 Style Skill、画幅和输入角色生成，并优先覆盖 Vogue、Harper's Bazaar、Numéro、Dazed、i-D、032c、The Face、W、AnOther、品牌 campaign 等高质量来源类型；来源由联网模型实际检索确认，不能虚构。
- 解析结果保留原文摘要兼容性，同时新增 `lookbook_visual_system` 字段供最终 prompt 使用。
- 最终生成 recipe 加入高级视觉硬约束：有限色板、色彩比例、层次对比、材料与高光控制、胶片/印刷颗粒边界、反模板化和反随机奢华词堆砌规则。
- 前端默认开启“高级视觉研究”，提供研究强度选择，并显示研究状态；旧画布节点数据继续兼容。

## 文件 / 模块清单

预计涉及：

- 修改 `main.py`
- 修改 `canvas_core/ecommerce.py`
- 修改 `static/js/canvas-lookbook-node.js`
- 修改 `static/js/canvas.js`
- 修改 `static/canvas.html`
- 修改 `static/css/canvas.css`
- 修改或新增 `tests/test_lookbook_node_frontend.py`、`tests/test_ecommerce.py`
- 修改本任务文档

## 开发阶段

- [x] 阶段 1：现状分析与任务文档
- [x] 阶段 2：后端案例研究与视觉系统
- [x] 阶段 3：生成提示词与前端选项
- [x] 阶段 4：专项测试与回归
- [x] 阶段 5：最终验收、Git 提交

## 验收标准

- Lookbook 默认会提交高级视觉研究选项，用户可关闭或调整研究强度。
- 联网研究请求明确要求检索高质量杂志/品牌 campaign 案例，输出可执行的色彩系统，而非泛泛的“高级、质感”形容词。
- 最终 Lookbook prompt 明确包含色板、色彩比例、光色、材质、摄影/印刷工艺、构图和反普通化约束，并保留用户素材与 Logo 事实锁定。
- 联网失败时生图主流程继续，任务中记录失败原因；旧版 `search_context`/`lookbook_plan` 数据仍可使用。
- 前端节点能显示高级研究选项和研究状态，不破坏已有创建、选择、生成、输出连接行为。
- `python -m py_compile main.py canvas_core/ecommerce.py`、`node --check`、专项 pytest、`git diff --check` 全部通过。

## 已完成内容

- 已定位现有 Lookbook 后端三段链路：`enrich_lookbook_search`、`enrich_lookbook_plan`、`build_prompt`。
- 已确认前端生成请求从 `runLookbookNode` 提交 `lookbook_search`、`search_context`、`lookbook_plan` 和 `lookbook_style`。
- 已新增人物/商品参考事实分析阶段；深度研究默认交叉检索至少 4 组高质量杂志/品牌来源类型。

## 当前关键修改

- `main.py`：新增参考图事实分析、结构化联网研究归一化和高质量杂志/品牌来源约束；研究输出包含色板、比例、光色、造型、材质、城市环境、镜头和反普通化规则。
- `canvas_core/ecommerce.py`：Lookbook 生图 recipe 增加人物单输入 editorial 锁定、有限色板、动态街景、摄影工艺和反白底棚拍硬约束；视觉质检额外拦截普通目录构图。
- `static/js/canvas-lookbook-node.js` / `static/js/canvas.js`：新增“时尚街景”内置 Skill、研究深度选项、研究状态展示，并持久化事实分析/结构化视觉系统。
- `static/canvas.html` / `static/css/canvas.css`：升级静态资源版本并加入研究控件样式。
- `tests/test_lookbook_premium.py`：覆盖人物事实分析先于联网搜索、结构化视觉系统解析和最终提示词反普通化规则。

## 已知问题

- 真实付费生图和真实 Responses 联网耗时验证需要当前环境配置可用 API Key，本轮以单元测试和请求契约验证为主。

## 开发日志

- 2026-08-31：建立增强任务，确认现有联网摘要对高级色彩输出的结构化约束不足。
- 2026-08-31：完成参考事实分析、结构化色彩研究、时尚街景 Skill、反白底棚拍 recipe、研究状态 UI 与专项测试。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
