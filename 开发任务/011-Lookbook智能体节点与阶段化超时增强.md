# Lookbook 智能体节点与阶段化超时增强

状态：已完成
当前阶段：5/5
最后更新：2026-08-31

## 当前状态

Lookbook 已升级为阶段化后台 agent：前端只提交本地电商任务并短连接轮询，后端按参考事实分析、联网研究、创意策划、图片生成、视觉质检依次运行，任务计划和阶段轨迹持久化。节点自动读取研究深度、画幅、分辨率、质量、数量和超时设置；上游或网络卡住时会以 504 终止等待并保留阶段错误。

已确认可复用的稳定方案：视频自动解析使用本地后台任务、短连接轮询、Responses SSE；联网搜索和视觉请求分离；不使用代理不支持的 `background:true`；524 只重试同一完整请求。现有 Lookbook 任务本身已经是异步持久化任务，本轮将补齐其 agent 阶段和超时边界。

当前阻塞：无。真实付费上游生成仍需用户环境提供 API Key。

## 下一步

1. 如发布安装包，重新构建并带入新的静态资源查询串。
2. 使用可用 API Key 做一次真实“人物 + 时尚街景”任务验收，确认 SSE/web_search 配置和图片生成耗时。

## 当前 TODO

- [x] 核对视频后台解析实现与联网避坑
- [x] 增加 Lookbook agent 阶段状态和后台总超时
- [x] 增加节点超时参数并透传全部节点设置
- [x] 前端轮询显示 agent 阶段和超时错误
- [x] 完成专项回归、文档更新和 Git 提交

## 最近验证状态

- 静态检查：`node --check static/js/canvas.js static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：Lookbook/电商专项 `151 passed`
- 编译：`python -m py_compile main.py canvas_core/ecommerce.py` 通过
- 运行测试：新增超时终态、agent plan 和节点参数契约测试通过；真实付费生成需 API Key
- 最近 Git commit：待本轮提交

---

## 任务目标

把 Lookbook 节点作为一个阶段化智能体运行：读取节点当前设置的风格、输入素材、画幅、分辨率、质量、生成数量、研究深度和超时，依次完成参考事实分析、联网案例研究、视觉总监策划、图片生成和视觉质检；前端通过短连接轮询获得实时阶段状态，任务超过节点超时后明确失败，不因单个长连接卡死。

## 技术方案

- 复用 `/api/ecommerce/tasks` 的本地任务 ID、SQLite 持久化和现有结果恢复，不新建重复的图片生成协议。
- 在 `execute_ecommerce_task` 中写入 `agent_stage`、`progress_status`、`progress_percent` 和 `agent_started_at`。
- Lookbook 使用 `asyncio.wait_for` 包住整个 agent；节点 `lookbook_timeout_minutes` 默认 30 分钟，限制在 5～60 分钟，超时返回 504 并持久化终态。
- 各阶段仍使用现有 `canvas_llm`：参考事实分析无 web，案例研究单独启用 Responses `web_search`，视觉策划和生图不附加 web tool；保留同 provider/model 和 SSE/524 行为。
- 前端轮询读取 task 的阶段字段并回写节点状态；客户端也按同一超时参数结束等待，避免浏览器无限轮询。后端任务不会因前端轮询超时而重复提交。
- 请求体明确透传节点设置：`provider_id`、`model`、`aspect_ratio`、`resolution`、`quality`、`count`、`lookbook_research_depth`、`lookbook_timeout_minutes`。

## 文件 / 模块清单

预计涉及：

- 修改 `main.py`
- 修改 `static/js/canvas-lookbook-node.js`
- 修改 `static/js/canvas.js`
- 修改 `static/canvas.html`
- 修改 `tests/test_lookbook_premium.py`
- 修改本任务文档

## 开发阶段

- [x] 阶段 1：现状分析与避坑对照
- [ ] 阶段 2：后端 agent 阶段与超时
- [ ] 阶段 3：前端设置透传与轮询状态
- [ ] 阶段 4：专项测试与回归
- [ ] 阶段 5：最终验收、Git 提交

## 验收标准

- Lookbook 后端任务可返回 queued、reference-analysis、web-search、art-direction、generation、quality-gate、completed/failed/timeout 阶段信息。
- 参考事实分析、联网研究、策划和图片生成均在后台任务中执行，前端使用短连接轮询，不依赖单个长 HTTP 请求。
- 节点画幅、分辨率、质量、数量、研究深度和超时设置均进入后台任务请求。
- 超时后任务记录 504 和明确阶段，前端停止轮询并显示错误；不自动切换 provider/model，不重复提交生图。
- 视频自动解析已验证的 SSE、web_search 分离、524 同请求重试和相关避坑规则不被破坏。
- Python/JavaScript 静态检查、Lookbook/电商专项测试和 `git diff --check` 通过。

## 已完成内容

- 已确认现有 Lookbook 使用 `/api/ecommerce/tasks`，任务创建后 `asyncio.create_task(run_ecommerce_task(...))`，前端 `pollEcommerceLookbookTask` 无超时且无阶段展示。
- 已确认视频自动解析的后台任务和 Responses SSE 方案可直接作为实现参考。
- 已参考 LangGraph 的节点级持久化状态与可恢复执行、Temporal 的 durable execution 思路，并采用当前 SQLite/任务体系实现轻量状态图，避免引入新的服务依赖。

## 当前关键修改

- `main.py`：增加 Lookbook agent plan、agent trace、阶段进度、5～60 分钟总超时和 504 终态；完成/失败/超时均持久化。
- `static/js/canvas-lookbook-node.js`：增加 5～60 分钟超时控件和 agent 阶段显示。
- `static/js/canvas.js`：轮询阶段状态，使用节点超时结束客户端等待，透传全部生成设置并持久化任务阶段。
- `static/canvas.html` / `static/css/canvas.css`：升级缓存版本和超时控件样式。
- `tests/test_lookbook_premium.py`：增加 agent plan、超时和参数透传契约。

## 已知问题

- 真实上游是否在配置环境中持续返回 SSE、web_search 和图片结果，需要 API Key 才能验证；自动化测试不提交付费请求。
- 如果电商视觉 provider 不是 Responses 协议，现有能力层不会附加 `web_search` 工具；应在 API 设置中使用已验证的 Responses provider/model。

## 开发日志

- 2026-08-31：建立任务，确认 Lookbook 需要将现有异步任务升级为阶段化 agent，并补齐总超时。
- 2026-08-31：完成 agent plan/trace、总超时、前端阶段轮询、节点超时控件和专项测试。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
