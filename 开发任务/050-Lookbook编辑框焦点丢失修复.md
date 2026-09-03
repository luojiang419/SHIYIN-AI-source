# Lookbook 编辑框焦点丢失修复

状态：已完成
当前阶段：3/3
最后更新：2026-09-03

## 当前状态

用户反馈 Lookbook 节点编辑框在光标插入文字中间后，等待数秒会失焦且无法继续输入。

已定位：Lookbook 任务/状态轮询约每 1.8 秒调用 `refreshNodes` 替换节点 DOM；全局 `StudioFocusGuard` 会捕获并恢复焦点，但稳定选择器属性白名单缺少 `data-lookbook-field`。Lookbook textarea 没有 id/name/class，节点替换后 `selectorFor()` 返回空字符串，导致光标恢复失败。

## 下一步

当前任务已完成。

## 当前 TODO

- [x] 稳定定位 Lookbook 编辑框
- [x] 防止跨节点错误恢复
- [x] 自动化测试
- [x] 浏览器交互验证
- [x] 文档、Git 提交与推送

## 验收标准

- Lookbook textarea 能被焦点恢复器生成带节点作用域的选择器。
- 节点 DOM 刷新后恢复原 value、selectionStart、selectionEnd 和焦点。
- 多个 Lookbook 节点存在时不会恢复到其他节点的同名 textarea。
- 静态检查、定向测试和浏览器等待输入验证通过。

## 已完成内容

- `static/js/focus-guard.js` 将 `data-lookbook-field` 纳入稳定选择器，并优先组合最近节点的 `data-id`，确保 DOM 替换后定位到同一节点同一控件。
- `static/canvas.html` 将焦点恢复脚本缓存版本升级为 `2026.09.03.lookbook-focus.1`。
- `tests/test_focus_guard.py` 增加 Lookbook 节点作用域选择器和缓存版本契约。

## 最近验证状态

- 静态检查：`node --check static/js/focus-guard.js static/js/canvas-lookbook-node.js static/js/canvas.js`、`git diff --check` 通过。
- 定向测试：焦点恢复 + Lookbook 专项 `65 passed`。
- 浏览器交互：本地源码服务创建真实 Lookbook 节点，输入“开头结尾”，把光标置于索引 2，等待 5.5 秒后焦点仍为 active、selectionStart/End 均为 2；继续输入“插入”后值为“开头插入结尾”、光标索引为 4。
- 本地测试服务已关闭；测试数据位于 `.build/focus-test-data`，不进入 Git。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
