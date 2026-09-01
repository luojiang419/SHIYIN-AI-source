# Lookbook 生成数量严格生效

状态：已完成
当前阶段：3/3
最后更新：2026-09-01

## 当前状态

用户反馈 Lookbook 节点设置生成数量为 4 时最终只得到 1 张。当前前端同时发送顶层 `count` 与 `options.lookbook_count`，后端 `prepare_ecommerce_request` 只使用顶层 `count` 解析最终生成设置；两者出现不一致时，Lookbook 数量可能退回默认单张。现已让后端对 Lookbook 专用数量字段做权威规范化，并保留最终值供 agent 与批量生成使用。

## 下一步

当前任务已完成。

## 当前 TODO

- [x] 修复后端 Lookbook 数量规范化
- [x] 增加数量 1～4 的回归测试
- [x] 完成静态检查、测试和 Git 提交

## 最近验证状态

- 静态检查：`python -m py_compile main.py`、`node --check static/js/canvas.js`、`node --check static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：`tests/test_ecommerce.py`、`tests/test_lookbook_premium.py`、`tests/test_lookbook_node_frontend.py`，166 项通过
- Git：用户原有未跟踪目录 `测试/` 保留

---

## 任务目标

Lookbook 节点设置 1～4 张时，后端任务、实际图片生成批次、任务结果和画布输出均严格对应设置数量。

## 技术方案

- 在 `prepare_ecommerce_request` 中识别 `prompt_policy=lookbook`，优先读取 `options.lookbook_count`，统一交给 `resolve_ecommerce_generation_settings`。
- 将规范化后的数量同步回 `options.lookbook_count`，保证后续 Lookbook agent 阶段、提示词和任务快照使用同一个值。
- 保留其他电商功能使用顶层 `count` 的现有行为。

## 文件 / 模块清单

- 修改：`main.py`
- 修改：`tests/test_ecommerce.py`
- 新增：本文档

## 验收标准

- Lookbook 请求中 `options.lookbook_count=4`、顶层 `count=1` 时，最终快照和生成设置为 4。
- Lookbook 1～4 张生成批次调用次数与设置一致。
- 既有电商功能数量逻辑不受影响。
- 相关测试和静态检查通过。

## 已完成内容

- `main.py`：当 `prompt_policy=lookbook` 时优先读取 `options.lookbook_count`，解析后回写规范化数量；其他电商操作仍使用顶层 `count`。
- `tests/test_ecommerce.py`：覆盖 Lookbook 数量 1～4，验证任务快照、参数快照和 options 均保持对应值。

## 已知问题

- 当前未连接真实上游图片平台进行付费生成冒烟；实际生图批次复用已通过的 `execute_ai_image_batch(count=...)` 路径。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
