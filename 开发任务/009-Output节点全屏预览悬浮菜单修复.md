# Output 节点全屏预览悬浮菜单修复

状态：已完成
当前阶段：4/4（文档、提交与推送）
最后更新：2026-08-31

## 当前状态

Output 图片点击/双击进入 `outputLightbox` 时，画布上的 `selectionHub` 悬浮功能菜单没有被清理。由于 `.selection-hub` 的 z-index 高于 `.output-lightbox`，菜单会叠加在全屏预览图片上；菜单状态还会保留到关闭全屏后，导致点击功能像是在下一层延迟生效。

## 下一步

已完成全屏预览前清理、全屏期间渲染保护、专项测试和 Git 提交；发布时需带入新的静态资源查询串。当前修复提交为 `85c091f`。

## 当前 TODO

- [x] 打开全屏预览前清理悬浮菜单和图片选中态
- [x] 全屏期间禁止悬浮菜单重新渲染
- [x] 补充专项测试并验证
- [x] 更新任务文档并提交

## 最近验证状态

- 静态检查：`node --check static/js/canvas.js`、`git diff --check` 通过
- 单元测试：`tests/test_canvas_output_lightbox.py tests/test_lookbook_node_frontend.py tests/test_canvas_inline_generation_prompt.py` 共 19 passed
- 编译：不适用（静态前端）
- 运行测试：未执行桌面 WebView 视觉冒烟
- 最近 Git commit：`85c091f`

---

## 任务目标

Output 图片进入全屏预览后只显示预览层，不显示画布悬浮功能菜单；全屏期间点击、键盘操作不应让菜单延迟显示；关闭或按 Esc 后画布状态保持干净，重新选中图片时才重新显示菜单。

## 技术方案

- 新增 `hideSelectionHubForLightbox`，移除 `selectionHub` 的 open 类、清空内容、清除 `selectionHubAnchor`、取消 `selectedOutputMedia` 和 Output 图片 quick-selected 标记，并关闭节点菜单。
- `openOutputLightbox` 在任何预览内容初始化前调用清理函数。
- `renderSelectionHub` 在 `outputLightbox.open` 时立即清理并返回，阻止刷新/键盘/窗口变化重新创建菜单。
- `openOutputNodeMenu` 在全屏状态下直接关闭并返回，避免右键菜单越过预览层。

## 验收标准

- 单击/双击 Output 图片进入全屏后，画面上没有悬浮功能菜单。
- 全屏期间执行键盘快捷键、窗口刷新或点击预览，不会重新出现菜单。
- 关闭全屏或按 Esc 后，菜单不会自动残留；重新单击图片可正常显示菜单。
- `node --check`、专项 pytest 与 `git diff --check` 通过。

## 文件 / 模块清单

- `static/js/canvas.js`
- `static/canvas.html`（如需升级静态资源查询串）
- `tests/test_canvas_output_lightbox.py`（新增）
- `开发任务/009-Output节点全屏预览悬浮菜单修复.md`

## 开发阶段

- [x] 根因分析与方案
- [x] 菜单清理与全屏保护
- [x] 测试与回归
- [x] 文档、提交与推送


## 已完成内容

- 新增 `hideSelectionHubForLightbox`，打开预览前清空悬浮菜单、Output 节点菜单、选中图片状态和 quick-selected 标记。
- `renderSelectionHub` 在全屏打开时直接清理并返回；`openOutputNodeMenu` 在全屏状态下拒绝显示右键菜单。
- 升级 `canvas.js` 静态资源查询串，并新增 3 项全屏菜单契约测试。

## 开发日志

- 2026-08-31：完成全屏预览菜单清理与状态保护，专项测试 19 项通过。

## 已知问题

- 真实桌面 WebView 视觉冒烟需要运行实例；本次先用静态契约和前端语法验证。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
