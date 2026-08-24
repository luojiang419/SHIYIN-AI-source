# 626-无限画布模块 D 安全视口 LOD 完成

日期：2026-08-24

## 已完成内容

- 经典画布新增 `CLASSIC_SAFE_LOD_ENABLED` 和 `CLASSIC_SAFE_LOD_MARGIN`，通过 rAF 合并视口 LOD 更新。
- 经典画布只给普通节点 body 标记 `canvas-lod-outside`；特殊节点、`group/promptGroup`、选中节点、拖动节点、缩放节点和端口连线源节点保持完整。
- 智能画布新增 `SMART_SAFE_LOD_ENABLED` 和 `SMART_SAFE_LOD_MARGIN`，按当前 world viewport 更新普通节点 body 的 `smart-lod-outside` 状态。
- 智能画布排除特殊节点、Prompt、Loop、历史节点、多图组和 `smart-group`，这些节点始终保持完整内容。
- 两套 CSS 仅对视口外 body 应用 `content-visibility:auto` 和 intrinsic size；节点外壳、端口、连线和模型数据均不删除。
- 新增 `tests/test_canvas_safe_lod.py`，覆盖开关、排除规则、视口调度、选中/交互保护和“不删除 DOM”契约。

## 当前模块

模块 D：安全视口 LOD，已完成。未进入模块 E 小地图 Canvas 化。

## 具体代码前后对比

### 经典画布

修改前：大场景仅通过静态 `.canvas-lod-safe > .node-body { content-visibility:auto }` 交给浏览器处理，没有根据视口和交互状态显式保护节点。

修改后：

```js
const CLASSIC_SAFE_LOD_ENABLED = true;
const CLASSIC_SAFE_LOD_MARGIN = 480;

function updateClassicSafeLod(){
    // 只切换普通节点 body 的 canvas-lod-outside
    // 选中、拖动、缩放、端口连线节点加入 keepIds
}
```

`renderNode()` 将 `group/promptGroup` 从 `canvas-lod-safe` 排除；`applyViewport()` 和选择变化会调度 LOD 更新。

### 智能画布

修改前：大场景静态按非特殊节点应用 body LOD，Prompt、Loop、历史和分组节点没有统一的动态安全边界。

修改后：

```js
const SMART_SAFE_LOD_ENABLED = true;
const SMART_SAFE_LOD_MARGIN = 480;

function updateSmartSafeLod(){
    // 只切换 smart-lod-safe 节点 body 的 smart-lod-outside
    // 端口拖动、节点拖动、缩放、选中节点加入 keepIds
}
```

`render()` 为普通单图节点写入 `smart-lod-safe`，Prompt/Loop/历史/多图组/智能分组/特殊节点不进入 LOD。

## 验证命令与结果

```text
node --check static/js/canvas.js                         通过
node --check static/js/smart-canvas.js                   通过
python -m unittest tests.test_canvas_safe_lod tests.test_canvas_incremental_connections tests.test_canvas_hotpath_indexes tests.test_canvas_performance_baseline tests.test_canvas_performance_observer tests.test_canvas_interaction_performance tests.test_canvas_initial_load_performance tests.test_performance_contracts
                                                            59 passed
git diff --check                                          通过
```

## 未完成待办

- 模块 E：小地图 Canvas 化与脏区域更新。
- 模块 F：保存序列化、媒体测量与交互层隔离。
- 需要在真实浏览器中使用 500 节点/1000 连线 fixture 验证视口进入/离开时的 p95/p99 帧数据。

## 下一步

读取本快照后进入模块 E，先评估经典/智能小地图当前 DOM 重建和节点 patch 路径，再设计 Canvas 绘制与视口框/交互层保留方案。

## 已解决踩坑点

- 不能通过删除视口外节点来做 LOD，否则端口命中、连线端点和拖动恢复会失效；本模块始终保留节点外壳和端口。
- `content-visibility:auto` 不能施加到节点外层，否则会裁剪外伸端口；本模块只施加到 `.node-body`，并保留 `overflow:visible` 外壳。
- Prompt、Loop、历史、多图组和分组节点包含输入控件或复杂布局，统一排除出安全 LOD；普通节点才允许视口外延迟。
- LOD 更新通过 rAF 合并，且只在状态变化时写入 class/data，避免平移时重复触发布局。
