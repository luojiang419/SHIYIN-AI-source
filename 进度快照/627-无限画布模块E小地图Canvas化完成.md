# 进度快照 627：无限画布模块 E 小地图 Canvas 化完成

日期：2026-08-24

## 已完成内容

- 经典画布小地图使用单个 `canvas.minimap-canvas` 绘制节点矩形。
- 智能画布小地图使用单个 `canvas.minimap-canvas` 绘制可见节点矩形，并排除智能日志预览节点。
- 两套小地图维护 `nodeId → minimap rect` 索引；节点拖动、尺寸变化时只清理旧矩形与新矩形联合区域，并在脏区内补绘相交节点。
- 视口框和整理按钮继续使用 DOM；Canvas 设置 `pointer-events:none`，不改变小地图拖动、定位和按钮事件层。
- 两套路径均保留开关与 DOM 全量回退：`CLASSIC_MINIMAP_CANVAS_ENABLED`、`SMART_MINIMAP_CANVAS_ENABLED`。Canvas 尺寸或 DPR 变化会自动触发一次全量重绘。
- 新增模块 E 静态契约测试 `tests/test_canvas_minimap_canvas.py`。

## 当前模块

模块 E“ 小地图 Canvas 化与脏区域更新”已完成，等待模块 F。

## 具体代码前后对比

### 经典画布 `static/js/canvas.js`

修改前：`renderMinimap()` 每次计算所有节点矩形并通过 `minimapContent.innerHTML` 重建全部 `.minimap-node`；节点移动更新通过 `querySelector()` 找到每个 DOM 节点后逐个改 style。

修改后：`renderMinimap()` 只确保 Canvas、全量绘制节点矩形并更新视口 DOM；`redrawClassicMinimapDirty()` 使用矩形索引清理旧/新联合区域，再补绘区域内节点。旧 DOM 路径保留在 `renderClassicMinimapDomFallback()` 中。

### 智能画布 `static/js/smart-canvas.js`

修改前：`renderMinimap()` 过滤节点后拼接 `nodeHtml`，通过 `innerHTML` 替换节点和视口；节点移动更新依赖 `.minimap-node[data-node-id]` 查询。

修改后：`renderMinimap()` 只使用单 Canvas 绘制可见节点，视口框保留为 DOM；`redrawSmartMinimapDirty()` 按矩形索引执行脏区清理与重绘。原 DOM 路径保留在 `renderSmartMinimapDomFallback()` 中。

### 样式与测试

新增两份 CSS 的 `.minimap-canvas` 规则，Canvas 覆盖内容层但不接收指针事件。新增测试验证开关、回退、单 Canvas 主路径、脏区索引、无逐节点 DOM 查询和交互层隔离。

## 验证命令与结果

- `node --check static/js/canvas.js`：通过。
- `node --check static/js/smart-canvas.js`：通过。
- `python -m unittest tests.test_canvas_minimap_canvas tests.test_canvas_safe_lod tests.test_canvas_incremental_connections tests.test_canvas_hotpath_indexes tests.test_canvas_performance_baseline tests.test_canvas_performance_observer tests.test_canvas_interaction_performance tests.test_canvas_initial_load_performance tests.test_performance_contracts`：63 passed。
- `git diff --check`：通过。仅有 Git 的 LF/CRLF 提示，无空白错误。
- `python -m unittest discover -s tests`：全量 619 项，617 项通过；1 项为既有 grsai API Key 环境缺失错误，1 项为既有 pose-reference 字符串契约失败，与模块 E 无关。

## 未完成待办

- 模块 F：保存序列化 revision/单飞队列、媒体自然尺寸测量和非关键交互层隔离。
- 需要在后续模块完成后执行更大范围的功能回归和大场景手工验收。

## 下一步

读取本快照后进入模块 F。先梳理经典/智能画布保存入口、revision 语义、序列化调用和媒体测量调用边界，再设计可回退的保存队列与空闲任务隔离。

## 已解决踩坑点

- Canvas 覆盖层不能接收指针，否则会遮挡原有小地图拖动；已通过 `pointer-events:none` 保持 DOM 事件层。
- 脏区只清理移动节点会留下重叠节点残影；已在联合区域内扫描并补绘相交节点。
- Canvas 尺寸或 DPR 变化会清空位图；已在脏更新检测到 resize 时回退到一次全量 Canvas 重绘。
- 高风险 Canvas 路径必须可回退；已保留两套 DOM 全量回退函数和显式开关。
