# 进度快照 733：经典连接结构增量 patch 完成

日期：2026-08-26

## 已完成内容

- 经典 mutation 增加新增、删除、受影响连接 ID 差异集合。
- 粘贴、Alt 拖拽复制、单删和批删在数据变更处收集连接差异。
- 经典连接模型邻接索引与 SVG path/hit/control 按 ID 写入和删除。
- 连接 patch 失败时交由完整画布 render 回退。

## 当前修改模块

模块 4 的经典连接结构子功能完成。修改 `static/js/canvas.js`、两份方案和本快照。

## 具体代码前后对比

```text
改动前：mutation 只有节点 ID；节点变化后 refreshGeometryAfterLayout -> 全部连接刷新。
改动后：mutation 携带连接 ID；patchClassicMutationConnections -> 只删除/插入/更新目标连接。

改动前：renderClassicConnectionPatch 对每个脏 ID 执行 connections.find。
改动后：直接从 classicConnectionModelIndex O(1) 读取连接模型。

改动前：索引不一致可能进入全连接刷新但不说明原因。
改动后：连接 patch 返回失败 -> console.warn(connection-structure-patch) -> 完整 render。
```

## 验证命令与结果

- `node --check static/js/canvas.js`：通过。
- `python -m unittest tests.test_canvas_interaction_performance tests.test_canvas_clipboard_performance -v`：40 项通过。
- `git diff --check`：通过，仅有工作区行尾提示。

## 待办清单

- 智能连接补稳定 ID 和结构差异字段。
- 智能简单连接按 ID 插入/删除/更新 SVG。
- 智能复杂分组、历史、级联拓扑记录原因并完整回退。
- 收口选择高清图、媒体状态、小地图和 500/1000 功能验证。

## 下一步

实现 `ensureSmartConnectionIds()` 与智能连接模型索引，事件优先使用稳定 ID；再实现 `patchSmartMutationConnections()`，不得依赖易漂移的数组下标。

## 避坑记录

- 结构删除会改变连接数组下标；增量连接 DOM 必须以稳定连接 ID 为主键，不能继续把数组位置当作长期身份。
