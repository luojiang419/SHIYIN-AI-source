# 178：无限画布模块 E 小地图 Canvas 化差异备份

日期：2026-08-24

## 变更范围

- `static/js/canvas.js`
- `static/js/smart-canvas.js`
- `static/css/canvas.css`
- `static/css/smart-canvas.css`
- `tests/test_canvas_minimap_canvas.py`
- `开发文档/无限画布性能优化开发文档-v1.md`

## 代码前后对比

### 经典小地图

- 之前：`renderMinimap()` 通过 `minimapContent.innerHTML` 创建全部节点矩形；节点更新使用 `querySelector()` 查询目标 DOM。
- 现在：增加 `CLASSIC_MINIMAP_CANVAS_ENABLED`、Canvas 初始化/尺寸管理、节点矩形索引和 Canvas 全量绘制；`redrawClassicMinimapDirty()` 只清理旧/新矩形联合区域并补绘相交节点。原 DOM 渲染保留于 `renderClassicMinimapDomFallback()`。

### 智能小地图

- 之前：过滤节点后拼接 `nodeHtml` 并替换整个小地图内容；节点更新依赖 `.minimap-node[data-node-id]` 查询。
- 现在：增加 `SMART_MINIMAP_CANVAS_ENABLED`、Canvas 初始化/尺寸管理、可见节点矩形索引和脏区绘制；视口 DOM 保持独立。原 DOM 渲染保留于 `renderSmartMinimapDomFallback()`。

### 交互与样式

- Canvas 覆盖层设置 `pointer-events:none`，小地图拖动、视口框定位和整理按钮继续由原 DOM 交互层负责。
- Canvas 尺寸与 DPR 变化自动触发一次全量重绘；脏区绘制会考虑重叠节点，避免移动后残影。

## 验证结果

- 两份画布 JavaScript `node --check` 通过。
- 模块 E 专项及 A/B/C/D 回归测试：63 passed。
- `git diff --check` 通过。

## 回滚方式

将 `CLASSIC_MINIMAP_CANVAS_ENABLED` 或 `SMART_MINIMAP_CANVAS_ENABLED` 改为 `false`，即可恢复对应小地图的 DOM 全量渲染；若 Canvas 创建/绘制异常，先关闭对应开关止损，必要时可整体回退本备份对应提交。
