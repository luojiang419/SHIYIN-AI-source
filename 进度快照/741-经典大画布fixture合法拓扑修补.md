# 进度快照 741：经典大画布 fixture 合法拓扑修补

日期：2026-08-26

## 已完成内容

- 修复经典 500/1000 fixture 使用业务无效 `image -> image` 连线的问题。
- 前半节点保持图片，后半节点改为生成器，连接变为合法 `image -> generator`。
- 新增 fixture 业务校验契约和专项避坑指南。
- 记录 `python main.py --help` 会启动默认端口服务的命令陷阱。

## 当前修改模块

模块 4 真实 Chromium 验收基础设施修补。修改 `static/js/canvas.js`、`tests/test_canvas_performance_baseline.py`、避坑指南和两份主方案。

## 具体代码前后对比

```text
改动前：500 个 image + 1000 条 image -> image；保存校验后连线全部被移除。
改动后：250 个 image + 250 个 generator + 1000 条 image -> generator；保存校验后仍保留。
```

## 验证命令与结果

- `python -m unittest tests.test_canvas_performance_baseline -v`：6 项通过。
- `node --check static/js/canvas.js`：通过。
- `git diff --check`：通过，仅有工作区行尾提示。

## 待办清单

- reload 经典 QA 页面并重新安装 500/1000 fixture。
- 重新验证创建、合法内部连接粘贴、删除、撤销/重做和回退。
- 验证智能 500/1000 普通连接增量与复杂拓扑回退。
- 模块验收后版本化、backup、完整回归、清理、提交并推送。

## 下一步

重新加载当前经典页面，确认触发保存并等待后连接数组、连接模型索引和 DOM 仍保持 1000，再执行完整功能序列。

## 已知边界与恢复说明

- QA 服务 PID `36020`，端口 `3012`，隔离目录 `.qa-canvas-module4-20260826-01`；结束时必须精确停止并清理。
