# Lookbook 颗粒强度控制与实测

状态：已完成
当前阶段：4/4
最后更新：2026-09-03

## 当前状态

FW2026 已固定使用结构化高键色彩和原始胶片颗粒强度 `0.095`。用户希望在 Lookbook 节点内增加“颗粒强度”控制滑块，默认显示 FW 值，调整后必须真正作用于最终图片后处理。

当前需要确认并打通：前端节点字段 → 请求 snapshot/options → 服务端 `apply_lookbook_film_finish` → `apply_lookbook_organic_film_grain(amount=...)`，并保持其他风格现有行为不变。

## 下一步

当前任务已完成；后续可根据真实用户反馈微调滑块上限，但默认 FW 值保持 `0.095`。

## 当前 TODO

- [x] 前端颗粒滑块与默认值
- [x] 节点参数持久化与请求传递
- [x] 服务端颗粒强度生效
- [x] 回归测试
- [x] 实际生成验证
- [x] 文档、Git 提交与推送

## 验收标准

- Lookbook 节点显示“颗粒强度”滑块和数值，默认 `0.095`。
- 调整值会随节点保存/生成请求传递，旧节点缺省时仍使用 `0.095`。
- FW 最终后处理使用用户值，限制在安全范围；非 FW 风格不受影响。
- 至少两组不同滑块值的真实生成结果可证明颗粒强度变化。
- 定向测试、静态检查和 `git diff --check` 通过。

## 最近验证状态

- 前端/后端定向测试：`61 passed`
- 静态检查：`python -m py_compile main.py`、`node --check static/js/canvas-lookbook-node.js static/js/canvas.js`、`git diff --check` 通过
- imgx：`fw_grain_slider_validation_20260903`，2/2 成功，`image-to-image`，`16:9`、`2K`，参考图顺序写入 manifest
- 参数对比：同一生成图应用 `0.020` 与 `0.140`；高频颗粒标准差分别为 `8.0176→19.7590`、`6.7369→16.3249`
- 对比预览：`generated-images/fw_grain_slider_validation_20260903/processed/contact-sheet.jpg`

## 已完成内容

- 节点新增“颗粒强度” range 控件，范围 `0–0.2`、步进 `0.005`，默认 FW 值 `0.095`，实时显示三位小数。
- 旧节点缺省字段自动回填 `0.095`；滑块值随节点保存并传入 `options.lookbook_grain_strength`。
- 服务端对值做有限数值校验和 `0–0.2` 收敛，只在 FW finish 中使用；其他风格保持原逻辑。
- 前端缓存版本升级为 `lookbook.34` 并增加 `lookbook-grain-slider.1`。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
