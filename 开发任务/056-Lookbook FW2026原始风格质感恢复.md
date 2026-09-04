# Lookbook FW2026 原始风格质感恢复

状态：已完成
当前阶段：3/3
最后更新：2026-09-04

## 当前状态

用户反馈调整后的 FW2026 失去了此前的风格质感，要求恢复原来的视觉表现。

经 Git 历史核对，风格变化主要来自 `121fd28` 引入的 `FW TONAL CONTRAST LOCK`、前端 structured S-curve prompt，以及后端从 `apply_lookbook_natural_sun_grade` 切换到 `apply_lookbook_fw_contrast_grade`。本次以调整前提交 `56c59e8` 为真实来源恢复这三处，不回退后续新增的颗粒强度滑块、编辑框焦点修复、拼图控制和场景母图保真。

## 下一步

当前任务已完成。后续生成 FW2026 时，已有和新建节点都会使用恢复后的原始视觉预设。

## 当前 TODO

- [x] 后端 FW 原始视觉锁恢复
- [x] 前端 FW 原始预设与旧节点迁移
- [x] 原始自然阳光后处理恢复
- [x] 测试与影响检查
- [x] Git 提交与推送

## 验收标准

- FW prompt 不再包含 `FW TONAL CONTRAST LOCK` 或 structured S-curve 强制语言。
- FW 后处理重新调用 `apply_lookbook_natural_sun_grade`。
- 颗粒强度仍由 `lookbook_grain_strength` 控制，默认 `0.095`。
- 已有内置 FW 节点自动同步恢复后的 prompt。
- 后续场景保真、版式、焦点修复功能保持不变。

## 已完成内容

- `canvas_core/ecommerce.py`：FW 核心视觉锁逐字恢复为调整前提交 `56c59e8` 的版本，移除 `FW TONAL CONTRAST LOCK`。
- `static/js/canvas-lookbook-node.js`：内置 FW 名称、描述和 prompt 逐字恢复为调整前版本。
- 旧节点迁移：内置 FW 节点首次加载时更新为 `original-v1`，清除旧视觉研究派生状态，但保留用户颗粒强度。
- `main.py`：FW finish 恢复 `apply_lookbook_natural_sun_grade`，颗粒继续读取滑块值，默认 `0.095`。
- `static/canvas.html`：缓存版本升级为 `2026.09.04.lookbook.36`。

## 最近验证状态

- 精确核对：前端 FW prompt 与 `56c59e8` 逐字一致；后端 FW 核心锁与 `56c59e8` 逐字一致。
- 保留功能：颗粒滑块、场景母图保真、拼图版式均存在。
- 静态检查：`python -m py_compile main.py canvas_core/ecommerce.py`、`node --check static/js/canvas-lookbook-node.js static/js/canvas.js`、`git diff --check` 通过。
- 定向回归：Lookbook、故事分镜与焦点专项 `105 passed`。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
