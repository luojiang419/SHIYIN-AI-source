# Lookbook 联网搜索改为可选并优先选定风格

状态：已完成
当前阶段：3/3（前后端修改、风格约束与回归验证完成）
最后更新：2026-09-03

## 当前状态

已确认 Lookbook 故事模式在前端新建节点、节点归一化、请求提交和后端请求准备阶段强制开启联网搜索；后台还把故事模式搜索失败/跳过视为任务失败。用户希望默认关闭联网搜索，改成可选，并优先执行选中的视觉风格，避免搜索结果稀释风格导致画面呆滞。

## 下一步

已完成 `static/js/canvas-lookbook-node.js`、`static/js/canvas.js`、`main.py` 和 `static/canvas.html` 修改；搜索默认关闭且可手动勾选，搜索状态不再阻断故事生成，选定风格锁已注入 art direction、storyboard 和逐镜头 prompt。

## 当前 TODO

- [x] 前端默认关闭并移除故事模式禁用态
- [x] 后端不再强制搜索或因搜索失败中止
- [x] 选定风格优先注入策划与逐镜头提示词
- [x] 更新测试、任务文档和 Git 提交

## 最近验证状态

- 静态检查：`python -m py_compile main.py canvas_core/ecommerce.py canvas_core/lookbook_story.py`、`node --check static/js/canvas.js`、`node --check static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：`pytest -q tests/test_lookbook_story.py tests/test_lookbook_node_frontend.py tests/test_lookbook_premium.py`，71 passed
- 最近 Git commit：待提交；工作区其余用户改动未纳入本任务

---

## 任务目标

Lookbook 节点的联网案例研究默认关闭，仅在用户勾选时启用；搜索为增强信息而非必经步骤，即使未启用、无结果或失败，仍使用用户选定的视觉风格完成生成。选定风格的 prompt 应优先于搜索摘要及泛化的自动风格建议。

## 验收标准

- 新建 Lookbook 节点 `lookbookSearch` 为 `false`，故事模式 checkbox 可操作且文案不再写“必选”。
- 前端提交的 `lookbook_search` 严格反映 checkbox，不因故事模式改写为 `true`。
- 后端保留 `lookbook_search=false`，默认值为关闭；故事模式不因 disabled/skipped/failed 搜索而返回 422。
- 选定风格名称与 prompt 在 art direction、storyboard 和每张图片 prompt 中明确作为主视觉约束，联网内容仅作为可选补充方法。
- `node --check`、`python -m py_compile` 及相关 Lookbook 测试通过。

## 已完成内容

- 新建节点与缺省节点归一化将 `lookbookSearch` 设为关闭；故事模式 checkbox 恢复可操作，文案标明“可选，优先执行已选风格”。
- 请求提交和后端快照保留显式 `lookbook_search` 值，未提供时默认为 `false`。
- 搜索 disabled/skipped/failed 时继续执行视觉策划、故事分镜和图片生成，不再因故事模式搜索状态返回 422。
- 选定风格锁写入策划、分镜和每张故事帧的 global bible，联网研究明确降级为补充方法。
- 更新前端脚本缓存版本至 `2026.09.03.lookbook.31`。
