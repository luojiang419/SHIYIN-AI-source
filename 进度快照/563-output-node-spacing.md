# 输出节点自动避让修复进度快照

## 已完成内容

- 修复经典画布中通用输出节点、图片编辑输出、姿态输出和姿态复刻输出的重叠问题。
- 修复智能画布中普通生成输出、建筑多视图输出、姿态参考图输出、循环输出槽、网格拆分输出和工作流输出的重叠问题。
- 所有自动创建的输出节点都统一使用基于节点实际尺寸的安全空位算法：优先放在上游节点右侧并保留 72px 间距，若位置被占用则按列/行寻找不相交位置。
- 新增布局回归测试，覆盖经典画布和智能画布的自动输出定位契约。

## 当前修改模块

- `static/js/canvas.js`
  - 在四类自动创建输出节点的 `nodes.push(...)` 后调用 `positionCanvasNodeRelative(..., 'downstream')`。
  - 复用经典画布已有的 `canvasFreeNodePoint`，按 DOM 或节点尺寸避开已有节点。
- `static/js/smart-canvas.js`
  - 新增 `smartOutputPointForImages`，为带图片结果的输出计算安全坐标。
  - 将 `nextOutputPositionForSource` 改为调用 `smartFreeNodePoint`。
  - 将姿态、循环、建筑、网格拆分和工作流输出接入统一避让算法。
- `tests/test_arrange_selected_layout.py`
  - 新增自动输出节点使用安全定位算法的静态回归断言。

## 代码前后对比

### 经典画布通用输出

修改前：

```js
out = {id:uid('out'), type:'output', x:node.x + dx, y:node.y, images:[]};
nodes.push(out);
```

修改后：

```js
out = {id:uid('out'), type:'output', x:node.x + dx, y:node.y, images:[]};
nodes.push(out);
positionCanvasNodeRelative(out, node, 'downstream');
```

### 智能画布输出定位

修改前：输出节点直接使用 `source.x + source.width + 40/80`，只按部分同类输出的纵向位置避让。

修改后：所有自动输出先构造候选节点，再交给 `smartFreeNodePoint` 检查实际节点尺寸与全部现有节点的矩形相交情况，找到安全位置后再创建或入画布。

## 验证结果

- `node --check static/js/canvas.js`：通过。
- `node --check static/js/smart-canvas.js`：通过。
- 相关布局/节点测试：60 passed。
- 全量测试：634 passed，42 subtests passed，16 个既有弃用警告。
- `git diff --check`：通过，仅报告 Windows 换行转换提示。

## 待办清单

- 递增版本号至 `1.0.241`。
- 生成源码差异备份并清理开发缓存。
- 提交并推送当前分支，确认工作区只保留用户已有的未跟踪报告文件。

## 下一步

执行版本递增、备份、缓存清理和 GitHub 推送，完成本轮输出节点布局修复交付。
