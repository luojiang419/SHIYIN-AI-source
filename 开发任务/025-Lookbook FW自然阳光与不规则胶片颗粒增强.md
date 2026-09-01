# Lookbook FW 自然阳光与不规则胶片颗粒增强

状态：已完成
当前阶段：4/4
最后更新：2026-09-01

## 当前状态

用户反馈上一版 FW Lookbook 已接近目标，但光线仍不够自然通透，胶片颗粒缺少粗粝感且呈规则/均匀噪点。现已把“自然阳光”从色彩描述提升为可执行的曝光与光照关系，并增加不规则、分尺度、随亮度变化的模拟胶片颗粒。

## 下一步

当前任务已完成。后续如需更强颗粒，可在 `apply_lookbook_organic_film_grain` 调整 `amount`，默认值已控制在不污染肤色和白色服装的范围。

## 当前 TODO

- [x] 强化自然阳光/透亮曝光规则
- [x] 实现不规则粗颗粒后处理
- [x] 增加回归测试并生成样本
- [x] 更新文档、提交并推送

## 验收标准

- FW prompt 明确自然直射阳光、空气透亮、暖亮部/青绿阴影和高光保护，不再只依赖“暖色调”。
- 颗粒为多尺度、非周期、亮度相关、轻微色彩随机的有机颗粒，不出现规则棋盘/网格/均匀电视噪声。
- 只有 FW preset 应用该后处理，其他 Lookbook 风格保持原行为。
- 测试图能看到自然阳光氛围、真实人物细节和粗颗粒胶片感。

## 已完成内容

- `canvas_core/ecommerce.py`：增加自然直射阳光/透亮空气/天空反射阴影/高光保护提示；增加普通脸、雀斑、飞丝和不对称保留规则；增加 FW 单独有机颗粒后处理。
- `main.py`：新增多尺度随机场颗粒算法，颗粒大小、密度和 RGB 响应不规则，且在中间调/阴影更明显；FW 质量门完成后再应用 finish。
- `static/js/canvas-lookbook-node.js`：同步更新 FW preset 文案。
- `static/canvas.html`：缓存版本升级到 `lookbook.20`，增加 `fw-natural-sun-grain.1`。
- `tests/test_lookbook_premium.py`、`tests/test_lookbook_node_frontend.py`：增加自然阳光、粗颗粒和后处理回归断言。

## 最近验证状态

- `python -m py_compile main.py canvas_core/ecommerce.py`：通过
- `node --check static/js/canvas-lookbook-node.js`：通过
- Lookbook + 电商回归测试：170 passed
- 真实生图：`shiying / gemini-3-pro-image-preview` 生成 `fw_lookbook_test_v4_e7790dbd04.jpg`，视觉上已出现方向性午后阳光、透亮空气、青绿阴影和不规则粗颗粒；首次请求遇到一次 TLS EOF，重试成功。
- Git：`b100c52 fix: strengthen FW sunlight and organic film grain`，已推送 `origin/feat/storyboard-merge-node`

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
