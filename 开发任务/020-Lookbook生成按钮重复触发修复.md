# Lookbook 生成按钮重复触发修复

状态：已完成
当前阶段：2/2
最后更新：2026-09-01

## 当前状态

Lookbook 节点的数量参数已经透传到后端，但按钮同时绑定了 `pointerdown`、`mousedown`、`pointerup` 和 `click` 多套事件。节点重绘或按住按钮超过时间阈值时，同一次用户操作可能提交两个 Lookbook 任务，表现为数量选 1 却得到两张图。

## 下一步

已将 Lookbook 动作统一收敛到 `click` 事件，并完成回归验证。

## 当前 TODO

- [x] 收敛生成按钮事件分发
- [x] 增加重复触发回归测试
- [x] 完成静态检查与专项测试

## 最近验证状态

- 静态检查：`node --check static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：`tests/test_lookbook_node_frontend.py tests/test_lookbook_premium.py`，30 passed
- Git commit：待提交

## 任务目标

保证一次用户点击最多创建一个 Lookbook 生成任务，同时保留风格选择按钮和节点事件委托的正常交互。

## 验收标准

- Lookbook 生成按钮只在 `click` 事件上触发生成回调。
- 不再存在因 `pointerdown`、`mousedown`、`pointerup` 与 `click` 叠加导致的重复请求路径。
- 数量设为 1 时，请求仍提交 `count=1`，且一次点击只创建一个任务。
- 相关测试和静态检查通过。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
