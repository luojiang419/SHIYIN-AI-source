# 视频生成节点固定框架与 Responses 稳定性修复

状态：已完成
当前阶段：4/4
最后更新：2026-09-07

## 当前状态

2026-09-07 回归已修复：700px 下长提示词经 `fitAutoTextNode` 自动增至 12 行，使不可收缩的底栏超出框架，被 body 的 overflow 裁切。既有 Playwright 仅覆盖空提示词，未检测此场景。本次让视频节点跳过文本驱动的尺寸调整，编辑器内部滚动，并限制底栏高度、保留媒体区空间。修复前新增测试真实失败于生成按钮越界断言；修复后 8 种输入/恢复/宽高/重试布局场景通过，最小尺寸按钮边界与点击命中均正常。

本轮功能提交 `79e66ca` 已推送至 `origin/feat/film-workflow-canvas`，未混入工作区其他既有改动。本轮源码修复已完成，安装包尚未重新构建。

视频生成节点已统一为 `440–520px` 宽、最小 `700px` 高。旧画布低于下限的节点会自动提升；节点 body 不滚动，只有上方媒体/引用内容区滚动，底部参数、提示词和生成按钮不可收缩并固定在框架内。

MiniMax H3 默认参数已经统一为常量，新建 H3 节点、统一视频节点默认选中 H3、切换 provider 到 H3、旧节点缺失字段四条路径均显式落盘 `5s / 16:9 / 0.2MP 16:9 - 608x352`。

Responses SSE 已兼容标准 delta/done、content part、output item、嵌套 data、Chat 风格 delta 和 APIMart data 包装；HTTP 200 空流、不可解析响应、未完成状态和无文本结果会按现有次数有限退避重试，后续正常响应可自动恢复。

专项 66 项测试、全量 1282 项测试和两套隔离 Playwright 验证均通过。H3 旧节点实测从 `320px` 提升到 `700px`；12 个参考素材下内容区 `scrollHeight=203 > clientHeight=174`，底栏与按钮均完整可见。

功能提交 `ff371e8` 已推送至 `origin/feat/ecommerce-batch-outfit-depth-grid`。当前无阻塞问题。

## 下一步

当前任务已完成。后续若需要安装版交付，按项目构建发布流程另行生成新安装包。

## 当前 TODO

- [x] 阅读项目规则、历史任务、Git 状态与截图
- [x] 定位视频节点布局、默认参数和 Responses 请求链
- [x] 实现视频节点最小尺寸与固定底部操作区
- [x] 实现 MiniMax H3 新节点默认参数
- [x] 修复 Responses 偶发无有效文本
- [x] 补充自动化测试并完成真实布局验证
- [x] 更新文档、精确提交并推送

## 最近验证状态

- 2026-09-07 本轮：14 项定向测试通过；视频固定框架 8 种布局场景及现有画布节点 UI 回归通过，页面错误 0；JS 语法与差异检查通过。
- 本轮产物：`.codex-artifacts/089-video-node-layout-regression/after/` 和 `node-ui/`；深色 1:1 截图已目视核对。未编译或发布新安装包。
- 本轮 branch：`feat/film-workflow-canvas`；以下 2026-09-06 记录为上轮验证与交付历史。

- 静态检查：Python/JavaScript 语法与 `git diff --check` 通过
- 专项测试：66 passed
- 全量测试：1282 passed
- 浏览器布局验证：专项 H3 固定底栏与项目既有画布节点 UI 回归均通过，页面错误 0
- Git index 快照：相关 68 项测试与专项 Playwright 通过；全量测试有 13 个远程 HEAD 既有电商/Lookbook 失败，当前真实工作树对应修复存在且全量通过
- 验证产物：`.codex-artifacts/089-video-node-layout/`、`.codex-artifacts/089-canvas-node-regression/`（已被 `.gitignore` 忽略）
- 当前 branch：`feat/ecommerce-batch-outfit-depth-grid`
- 功能 Git commit：`ff371e8`
- Push：已推送至 `origin/feat/ecommerce-batch-outfit-depth-grid`

---

## 任务目标

1. 无限画布视频生成节点具有明确且统一的最小宽高，节点框架完整显示。
2. 节点内容超出时只滚动内容区，底部参数、提示词和“生成视频”按钮固定可见，不被折叠或挤出框架。
3. 自动解析对 Responses 兼容网关的常见 SSE 文本形态均能解析；瞬时空流自动重试，避免用户反复点击。
4. MiniMax H3 视频节点创建或切换到该 provider 时默认使用 `16:9`、`0.2MP 16:9 - 608x352`、`5s`。

## 当前项目现状

- `static/js/canvas.js` 统一负责经典画布节点创建、尺寸归一化、视频参数和自动解析调用。
- `static/css/canvas.css` 已有通用 `.node-bottom-controls` sticky 样式，但 `.video-node` 将其覆盖为普通相对定位。
- `defaultNodeSize('video')` 当前返回 `{w:440,h:0}`，无法形成稳定的固定框架。
- `main.py::request_responses_stream_json` 对标准 delta 有覆盖，但兼容事件和空输出重试不足。
- `tests/test_responses_protocol.py`、`tests/test_video_reference_grid_layout.py`、`tests/test_minimax_h3_canvas_frontend.py` 已提供相关回归基础。
- 相关源文件包含其他任务的未提交修改，本任务必须基于现状做局部编辑并精确隔离提交。

## 技术方案

1. 为经典视频节点增加统一最小高度常量，并让默认尺寸直接使用该宽高；旧画布中较小高度在渲染归一化时自动提升到下限。
2. 固定尺寸视频节点使用纵向 flex：媒体/引用内容区独立滚动，底部操作区不参与滚动并固定在框架底部。
3. 提取 MiniMax H3 默认参数初始化函数，新节点为 H3 时及 provider 切换到 H3 时写入 5 秒、16:9、0.2MP 分辨率。
4. Responses SSE 兼容标准 Responses、content part/output item、嵌套 data 和 Chat Completions 风格 delta；最终使用统一文本解析器验证。
5. 对 HTTP 200 但空响应、无文本或 incomplete/failed 且无完整结果的瞬时响应纳入有限退避重试，最终失败时返回包含尝试次数的明确错误。
6. 单元测试覆盖各类响应形态、重试次数、默认参数和布局契约；使用隔离 fixture + Playwright 测量节点框架、滚动区和按钮可见性。

## 文件 / 模块清单

预计修改：

- `main.py`
- `static/js/canvas.js`
- `static/css/canvas.css`
- `static/canvas.html`
- `tests/test_responses_protocol.py`
- `tests/test_video_reference_grid_layout.py`
- `tests/test_minimax_h3_canvas_frontend.py`
- 可能修改 `tests/support/canvas_node_ui_check.cjs`
- 可能修改 `tests/support/canvas_startup_fixture.py`

新增：

- `开发任务/089-视频生成节点固定框架与Responses稳定性修复.md`

## 开发阶段

- [x] 阶段 1：现状与根因分析
- [x] 阶段 2：节点布局和 H3 默认参数
- [x] 阶段 3：Responses 稳定性修复
- [x] 阶段 4：整体验证、文档与 Git 交付（2026-09-06）

## 验收标准

1. 新建视频节点宽度不低于 440px、高度不低于最终实测可完整承载 H3 底部控制区的统一下限。
2. 旧画布中低于下限的视频节点打开后自动提升到下限。
3. 节点增加多项媒体输入后，媒体区可滚动且生成按钮始终完整位于节点框架内并可见。
4. H3 新节点的 `duration=5`、`aspectRatio=16:9`、`resolution=0.2MP 16:9 - 608x352`。
5. Responses 标准 delta、content part/output item、嵌套 data、Chat 风格 delta 均可提取文本。
6. 瞬时空 Responses 流自动重试并能在后续正常返回时成功，连续失败才报告明确错误。
7. 相关 Python/JavaScript 测试、语法检查、差异检查和隔离浏览器布局验证通过。

## 已完成内容

- 完成相关历史任务、尺寸契约、视频节点渲染、H3 参数和 Responses SSE 请求链检查。
- 确认偶发错误是“兼容事件解析不足 + 空结果不重试”的组合问题。
- 完成 700px 最小高度、独立内容滚动区、固定不可收缩底栏和滚轮事件隔离。
- 完成 H3 默认参数集中初始化与创建/切换/旧数据补齐。
- 完成 Responses 兼容事件提取、统一文本校验、瞬时空/不完整结果有限重试和明确终态错误。
- 新增 Responses 单元测试和真实浏览器布局探针，并完成全量回归。

## 当前关键修改

- `main.py`：新增 Responses 瞬时空结果异常、兼容事件文本提取、统一结果验证和有限重试。
- `static/js/canvas.js`：新增视频节点 700px 最小高度、H3 默认参数集中初始化和内容区滚轮隔离。
- `static/css/canvas.css`：视频节点固定框架、独立内容滚动区和不可收缩底栏。
- `static/canvas.html`：增加 `video-fixed-frame.1` 缓存标识。
- `tests/`：补充 Responses、H3 默认值、布局契约、启动 VM 依赖和 Playwright 实测。

## 已知问题

- `main.py`、`canvas.js`、`canvas.css` 和部分测试文件已有其他任务未提交改动，提交时必须精确暂存。
- 当前远程 HEAD 的电商生成设置调用已传入 `max_count`，但配套 `canvas_core/ecommerce.py` 参数支持仍是用户未提交改动；因此不带用户改动的 index 快照全量测试有 13 个既有失败。本任务相关 68 项及 Playwright 均通过，当前真实工作树全量 1282 项通过。

## 开发日志

- 2026-09-07：复现最小框架长提示词导致底栏裁切；隔离视频节点文本撑高行为，补齐 8 种布局场景及按钮命中测试，14 项定向和已有 UI 回归通过。
- 2026-09-06 14:39：启动任务，完成现状、历史实现和两类根因分析。
- 2026-09-06 14:46：完成视频节点固定框架与 H3 默认参数，14 项前端契约测试通过。
- 2026-09-06 14:50：完成 Responses 兼容解析与空结果重试，43 项后端相关测试通过。
- 2026-09-06 14:53：专项与既有画布节点 Playwright 回归通过，截图确认底栏无折叠或遮挡。
- 2026-09-06 14:55：修复启动测试桩直接依赖后，全量 1282 项测试通过，进入最终交付。
- 2026-09-06 15:05：完成精确 hunk 暂存和 Git index 快照验证，确认提交候选未混入其他任务改动。
- 2026-09-06 15:06：功能提交 `ff371e8` 已推送至远程功能分支，任务完成。

## Git 交付

- branch：`feat/ecommerce-batch-outfit-depth-grid`
- 功能 commit：`ff371e8`
- remote：已推送至 `origin/feat/ecommerce-batch-outfit-depth-grid`
- 其他工作区修改：保持原样，未混入本任务提交

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：

1. 阅读项目规则、README 和本任务文档。
2. 检查当前 branch 与 `git status`。
3. 以当前源代码和 Git 状态校正文档。
4. 本任务已完成；除非出现实际回归，不重复实现。
5. 若继续修改 Responses 或视频节点布局，先阅读本文档与对应避坑指南。
