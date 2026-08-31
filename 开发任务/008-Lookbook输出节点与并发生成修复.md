# Lookbook 输出节点与并发生成修复

状态：已完成
当前阶段：4/4（测试与回归）
最后更新：2026-08-31

## 当前状态

Lookbook 节点当前会在自身 body 中渲染 generatedOutputs 图片；生成流程虽然调用 outputForNode，但没有给输出节点写入 `_pending` 占位，因此生成期间没有输出节点 spinner，完成结果也可能只停留在 Lookbook 节点内。`runLookbookNode` 还会在 node.running 时直接 return，连续点击无法提交多个独立任务。

## 下一步

Lookbook 输出节点、pending spinner、并发任务与恢复轮询修复已完成；当前提交已生成，发布时需带入新的静态资源查询串。

## 当前 TODO

- [x] Lookbook 结果移出节点 body，统一进入 Output 节点
- [x] 输出节点 pending spinner 与任务完成回填
- [x] 连续点击创建多个并行任务并保持结果不覆盖
- [x] 静态检查与专项测试
- [x] 更新任务文档并提交

## 最近验证状态

- 静态检查：`node --check static/js/canvas.js static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：`tests/test_lookbook_node_frontend.py tests/test_canvas_inline_generation_prompt.py` 共 16 passed
- 编译：`python -m py_compile main.py canvas_core/ecommerce.py` 通过
- 运行测试：未执行付费图片 API；静态契约覆盖输出节点、pending、并发与恢复轮询
- 最近 Git commit：`83965d7`

---

## 任务目标

使 Lookbook 节点行为与图片生成节点一致：首次生成自动创建并连接 Output 节点；任务运行时 Output 节点显示 spinner 占位；任务完成后结果写入 Output 节点而不在 Lookbook 节点内显示；生成按钮可连续点击并为每次点击提交独立任务，多个任务结果互不覆盖。

## 技术方案

- 每次点击先调用 `outputForNode(node, 520)`，为该次运行创建一个唯一 pending id，并将包含 `canvasTaskType: 'ecommerce-lookbook'`、任务快照和 Lookbook 参数的记录追加到 `out._pending`。
- API 任务返回后把 task id 写入对应 pending，并由 Lookbook 专用轮询等待 `/api/ecommerce/tasks/:id`；成功时移除 pending、追加图片到 Output 节点、追加到 Lookbook generatedOutputs，失败时移除 pending并回写错误。
- `node.running` 只作为约 2 秒按钮状态提示，pending 数量才代表真实并行任务；不因已有任务阻止新点击。
- Lookbook body 保留状态/质检信息，不再渲染图片缩略图。

## 验收标准

- Lookbook 生成首次点击后自动出现 Output 节点并有旋转等待占位。
- 生成期间再次点击可提交新任务，Output 节点同时显示多个 pending。
- 每个任务完成后只追加自己的图片，Lookbook 节点不显示图片网格。
- 失败任务清理对应占位并显示错误，其他并行任务继续运行。
- `node --check`、Lookbook 专项 pytest 与 `git diff --check` 通过。

## 文件 / 模块清单

- `static/js/canvas-lookbook-node.js`
- `static/js/canvas.js`
- `开发任务/008-Lookbook输出节点与并发生成修复.md`
- `tests/test_lookbook_node_frontend.py`（必要时补充契约断言）

## 开发阶段

- [x] 根因分析与方案
- [x] Lookbook 节点展示修复
- [x] 并发 pending/输出回填修复
- [x] 测试与回归


## 已完成内容

- `canvas-lookbook-node.js` 不再在节点内渲染生成图片，按钮保持可连续点击并通过 `aria-busy` 表示当前运行状态。
- `canvas.js` 每次 Lookbook 点击调用 `outputForNode(node, 520, true)` 创建或复用 Output 节点，追加独立 `ecommerce-lookbook` pending，Output 节点显示 spinner；任务完成后按任务追加图片并同步 generatedOutputs。
- 增加 Lookbook 任务失败清理、页面刷新后的恢复轮询和静态资源查询串升级。

## 开发日志

- 2026-08-31：完成输出节点迁移、并发任务与恢复轮询，专项测试 16 项通过。

## 已知问题

- 付费图片 API 运行需要本地配置有效 API Key，本次以静态契约和现有测试验证逻辑。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
