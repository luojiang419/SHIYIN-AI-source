# 进度快照 742：智能分组成员 owner 索引修补

日期：2026-08-26

## 已完成内容

- 修复智能分组成员 DOM 重索引误删 `smartGroupOwnerIndex` 的问题。
- 成员重索引保留 owner；分组重索引清理并重建旧成员映射；真实删除仍清理 owner。
- 新增专项契约，模块 4 契约共 13 项全部通过。

## 当前修改模块

模块 4 的智能分组成员归属索引一致性已修补。修改 `static/js/smart-canvas.js`、专项测试和两份主方案。

## 具体代码前后对比

```text
改动前：indexSmartNodeDom(member) -> removeSmartNodeDomIndex(member.id) -> owner 映射被删除。
改动后：成员重索引传 preserveGroupOwner:true；分组和真实删除仍走完整清理。
```

## 验证命令与结果

- `python -m unittest tests.test_canvas_incremental_render_performance -v`：13 项通过。
- `node --check static/js/smart-canvas.js`：通过。
- `git diff --check`：通过，仅有工作区行尾提示。

## 待办清单

- reload 智能 QA 页面并重新安装 500/1000 fixture。
- 复验分组成员创建、删除、撤销和 owner 映射。
- 收束真实 Chromium 验收结果并运行全部画布回归。
- 模块验收后版本化、backup、完整回归、清理、提交并推送。

## 下一步

复跑同一真实分组场景，要求成员存在时 owner 指向分组、删除时映射消失、撤销时恢复，最终回到 500 节点/1000 连线。

## 已知边界与恢复说明

- 分组及成员变动继续触发完整 SVG 回退，这是正确的复杂拓扑保护。
