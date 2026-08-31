# Lookbook 图片平台与模型二级菜单

状态：已完成
当前阶段：3/3
最后更新：2026-08-31

## 当前状态

Lookbook 节点已增加图片生成平台和图片模型二级菜单，使用与图片生成节点下方面板相同的 `image-quick-choice` 交互语言。平台切换会自动刷新模型列表，所选 `provider_id`、`model` 与画幅、分辨率、质量、数量一起提交到 Lookbook 任务。

## 当前 TODO

- [x] 增加平台/模型二级菜单
- [x] 切换平台自动刷新模型并保存节点选择
- [x] 透传节点平台和模型到生成任务
- [x] 升级静态缓存并完成专项验证

## 最近验证状态

- 单元测试：Lookbook 专项 `17 passed`
- JavaScript：`node --check static/js/canvas.js static/js/canvas-lookbook-node.js` 通过
- Diff：`git diff --check` 通过
- 最近 Git commit：待本轮提交

## 技术方案

- `CanvasLookbookNode` 使用 `data-lookbook-choice="provider/model"` 和既有 `image-quick-choice` CSS，避免原生 select 与图片节点交互不一致。
- 节点切换平台后读取 `allImageModels(providerId)`，首个可用模型自动成为当前模型；没有平台或模型时显示空状态。
- `runLookbookNode` 将节点 `apiProvider/model` 写入 `/api/ecommerce/tasks` 的 `provider_id/model`，后端仍按既有候选路由和兼容性校验执行。

## 修改文件

- `static/js/canvas-lookbook-node.js`
- `static/js/canvas.js`
- `static/css/canvas.css`
- `static/canvas.html`
- `tests/test_lookbook_node_frontend.py`

## 已知问题

无。真实付费生成仍需用户配置可用 API Key。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
