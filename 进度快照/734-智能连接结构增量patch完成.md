# 进度快照 734：智能连接结构增量 patch 完成

日期：2026-08-26

## 已完成内容

- 所有智能连接获得稳定 ID，新建、粘贴和复制连接不再依赖数组位置作为身份。
- 新增连接模型索引、节点邻接 ID 索引和普通连接 SVG 四元素增量维护。
- 连接事件优先按稳定 ID 断开；复杂拓扑带原因回退完整 SVG。
- 智能 mutation 携带新增、删除和受影响连接 ID 差异。

## 当前修改模块

模块 4 的双画布连接结构子模块完成。修改 `static/js/smart-canvas.js`、两份方案和本快照。

## 具体代码前后对比

```text
改动前：智能旧连接常无 id；mutation -> scheduleConnectionLayerRefresh -> 完整 SVG。
改动后：ensureSmartConnectionIds；普通 mutation -> patchSmartMutationConnections -> 按 id patch path/hit/dot/cut。

改动前：连接点击依赖 data-conn-index，删除一条后其余下标可能漂移。
改动后：普通连接事件使用 data-connection-id；合并复杂线才保留下标回退。

复杂拓扑：group/history/cascade/insert-preview -> console.warn(reason) -> refreshConnectionLayer。
索引损坏：patch false -> fallbackSmartRenderMutation -> 完整 render。
```

## 验证命令与结果

- 连接差异、稳定 ID、智能无全量连接路径：3 项专项契约通过。
- 交互、剪贴板、撤销相关回归：53 项通过。
- `node --check` 双画布：通过。
- `git diff --check`：通过，仅有工作区行尾提示。
- 模块 4 专项当前：10 项中 7 项通过，2 项失败、1 项错误。

## 待办清单

- 经典选择高清图只处理受影响节点。
- 经典目标节点图标、预览 fallback 和小地图只处理受影响集合。
- 智能菜单创建函数统一走 `commitSmartNodeCreate()`。
- 完成 500 节点/1000 连线功能一致性验证和模块收尾。

## 下一步

先收口经典 mutation 的局部选择/媒体/小地图，再统一智能菜单节点创建提交路径，使 10 项专项契约全部转绿。

## 避坑记录

- 增量删除后数组下标会整体漂移；普通连接 DOM 与事件必须使用稳定 ID。分组合并线没有一对一 ID，必须保留完整 SVG 回退。
