# 630-统一验收 fixture 基线与交互观测

## 已完成内容

- 用户已完成本地登录，真实浏览器进入无限画布编辑器。
- 经典画布和智能画布分别建立验收画布，使用 `CanvasPerformance.installFixture()` 完成 100/300/500/1000 节点、200/600/1000/2000 条连接四档基线采集。
- 采集 `render`、`renderLinks/renderConnections`、`frame.interval`、long task 以及节点拖动、画布平移、滚轮缩放、端口连线、框选、小地图拖动交互指标。
- 发现经典小地图结束回调漏掉性能完成标记，已在 `static/js/canvas.js` 补充 `markPaintFrom('classic.minimap-drag', ...)`；不改变小地图定位、视口保存和交互逻辑。

## 当前模块

统一验收与性能基线复测。A-F 性能模块实现已经完成，本快照不重复实现增量连线、LOD 或保存隔离。

## 具体代码前后对比

```diff
// static/js/canvas.js：经典小地图拖动结束回调
 window.onmouseup = () => {
     minimapDrag = false;
+    window.CanvasPerformance?.markPaintFrom?.('classic.minimap-drag', 'classic.minimap-drag', {nodes:nodes.length});
     window.onmousemove = null;
     window.onmouseup = null;
     scheduleViewportSave();
 };
```

## 浏览器基线结果

经典画布（`render p95 / renderLinks p95 / long task`）：

- 100 节点：18.6 / 4.1 ms / 0
- 300 节点：45.4 / 7.9 ms / 2
- 500 节点：68.7 / 9.6 ms / 2
- 1000 节点：173.5 / 19.8 ms / 1

智能画布（`render p95 / renderConnections p95 / long task`）：

- 100 节点：21.1 / 1.1 ms / 0
- 300 节点：39.9 / 2.3 ms / 1
- 500 节点：67.9 / 3.4 ms / 1
- 1000 节点：151.8 / 6.8 ms / 1

1000 节点交互样本（单位 ms，单次样本 p95 等于该样本耗时）：

- 经典：node-drag 447.4、pan 499.3、zoom 37.8、port-link 108.9、marquee 416.1；小地图原事件在合成 MouseEvent 下未触发完成标记，源码已修复，待真实鼠标事件复核。
- 智能：node-drag 357.5、pan 72.5、zoom 67.6、port-link 579.6、marquee 269.4、minimap-drag 102.1。

## 验证命令与结果

- `python -m unittest tests.test_canvas_performance_baseline tests.test_canvas_performance_observer tests.test_canvas_interaction_performance`：30 passed。
- `node --check static/js/canvas.js`：通过。
- `node --check static/js/smart-canvas.js`：通过。
- `node --check static/js/canvas-performance.js`：通过。
- `git diff --check`：通过（仅提示工作树换行符转换）。
- 浏览器验收：fixture 清理回调执行，节点/连接/视口恢复；智能画布六类交互均产生指标，经典画布除小地图合成事件外其余五类产生指标。

## 未完成待办

- 用真实鼠标事件复核经典小地图拖动的 `classic.minimap-drag` 指标。
- 500/1000 节点下首次 render、node-drag、pan、port-link、marquee 的 p95 超出统一验收目标，需要继续定位热路径。
- 尚未将统一验收结论标记为全部达标，也未创建大模块源码 backup。

## 下一步

读取本快照后，先完成经典小地图真实事件复核；随后按最大耗时排序检查全量 render、节点拖动/框选布局读取和端口连线刷新，制定下一轮低风险优化模块，保留开关与全量 render 兜底。

## 已解决踩坑点

- 浏览器静态脚本带固定版本 query，修改后必须禁用缓存或重新加载 iframe 才能观察新代码；强制刷新顶层页面可能触发一次 API Key 提示，应点击“稍后设置”，不输入未知凭据。
- 经典小地图拖动使用独立 `window.onmouseup`，不会经过统一 `endDrag`；性能标记必须在该回调内显式完成，否则只能看到 `beginInteraction` 而没有交互耗时。
- fixture 只在浏览器内存中替换节点/连接，验收脚本临时拦截画布保存请求并在 `finally` 中恢复，避免污染用户画布。
