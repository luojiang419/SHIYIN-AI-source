# Lookbook 文本数量优先与独立系列质量一致性

状态：已完成
当前阶段：4/4
最后更新：2026-09-03

## 当前状态

用户反馈 Lookbook 故事需求中写明“生成 9 张”时，结果可能仍按节点数量生成；同时同一需求写成“9 宫格”时一次联合构图质量明显高于 9 张独立图片。

已定位：`canvas_core/lookbook_story.py` 的数量合并规则允许节点手动数量覆盖文本，`static/js/canvas.js` 会在服务端解析前按旧节点数量创建输出占位；独立故事批次虽按单镜头并发生成，但缺少统一的系列质量锚点和针对多张输出的质量复核策略。

## 下一步

当前任务已完成，后续可使用真实 API 做 9 张地铁车厢广告的付费冒烟验收。

## 当前 TODO

- [x] 文本数量优先于节点设置
- [x] 前端动态占位槽同步最终数量
- [x] 独立系列统一视觉锚点与质量门
- [x] 回归测试、任务文档更新和 Git 提交

## 最近验证状态

- 静态检查：`python -m py_compile main.py canvas_core/lookbook_story.py`、`node --check static/js/canvas.js`、`node --check static/js/canvas-lookbook-node.js`、`git diff --check` 通过
- 单元测试：Lookbook/电商专项 `213 passed`
- Git：保留用户现有未提交改动，不覆盖或清理；本任务提交待完成

---

## 任务目标

1. 当 Lookbook 需求明确写出“9 张/九张图片”等数量时，最终生成数量必须采用文本值，即使节点当前数量不同。
2. “9 张独立图片”与“9 宫格”在视觉策划、人物表演、场景情绪和质量检查上使用同等级约束；前者仍必须输出 9 张独立 full-bleed 图片，不能退化成拼图。

## 验收标准

- `resolve_lookbook_settings("生成9张...", node_settings={"count": 1}, manual_overrides={"count": 1})` 返回 `count=9` 且来源为 `brief`。
- Lookbook 前端在服务端返回最终数量后补齐/裁剪同一批次占位槽，数量为 9 时不丢失镜头，也不保留多余槽位。
- 独立系列提示词包含统一视觉圣经、系列质量锚点、单幅 full-bleed 约束和镜头级动作/情绪要求。
- 多张独立系列的质量门覆盖所有弱镜头，最多按镜头重试配置执行，不把九宫格排版授权泄漏到单幅输出。
- 相关 Lookbook 测试与静态检查通过。

## 已完成内容

- `resolve_lookbook_settings`：文本明确数量覆盖节点及历史手动数量，其他字段保持原优先级。
- `static/js/canvas.js`：服务端返回最终数量后立即重建同组占位槽，并继续用 `shot_index` 幂等同步 partial result。
- `build_lookbook_series_quality_lock`：独立多图请求共享视觉圣经、人物表演、商品材质、光线和出版级质检约束，同时硬性禁止把数量画成宫格。
- `execute_lookbook_story_batch`：先生成首帧作为连续性锚点，后续镜头携带该锚点并保留镜头卡景别/动作控制；质量门默认最多修复 6 个弱镜头。
- 新增数量优先、系列质量锚点、首帧连续性参考和前端槽位同步回归测试。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：阅读本任务文档、检查 Git 状态，从“下一步”继续；保留用户现有改动。
