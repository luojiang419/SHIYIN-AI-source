# Lookbook 参考图优先与高级感生成修复

状态：已完成
当前阶段：4/4
最后更新：2026-09-01

## 当前状态

用户反馈 Lookbook 生成结果虽能复现水果店场景，但人物服装、场景文字和画面气质发生漂移，整体接近普通目录图，达不到杨沛林yppl公开作品所体现的高级时尚大片感；后续又指出首轮测试对比度过高、自然阳光和胶片颗粒不足。

代码核查发现：无文字需求的自动模式为了降低成本，直接跳过人物/素材事实分析、联网研究和创意总监方案，只拼接通用提示词后生成。这会让模型在“时尚”语义下自行换装、重绘场景文字并回退到普通站姿。Chrome 复核主页后又确认 28 张封面具有明确的曝光宽容度、环境主色、自然光动机、非中心机位和系列叙事规律，不能用单一“低对比”替代。

## 下一步

当前任务已完成。后续可选增强：把四种镜头角色、色彩脚本和事实摘要在节点 UI 中显式展示。

## 当前 TODO

- [x] 自动模式启用参考图事实分析与 art direction
- [x] 强化人物/场景/服装/文字的所有权约束
- [x] 补充测试并通过验证
- [x] 生成测试 Lookbook 图片并完成柔光胶片二次编辑
- [x] 输出分析报告与 Lookbook 节点改造方案

## 最近验证状态

- Git branch：`feat/storyboard-merge-node`
- 工作区：仅有用户提供的 `测试/` 目录未跟踪素材
- 最近相关 commit：`e883a24 fix: honor lookbook image count setting`
- Chrome 主页：已滚动读取 28 条作品标题与封面缩略图
- Lookbook 专项测试：26 passed
- JS/Python 静态检查：通过
- 色彩复测：完成 soft-film-v2 四张定向编辑与 soft-film-v3 单张 hero 复测

---

## 任务目标

将 Lookbook 节点从“无需求时通用自动生图”改为“参考图事实 → 视觉导演方案 → 受约束生成”的稳定链路，降低 AI 感、服装漂移、场景重绘和目录化构图，并用真实参考素材验证。

## 当前项目现状

- 前端节点：`static/js/canvas-lookbook-node.js`、`static/js/canvas.js`
- 后端任务：`main.py` 中 Lookbook agent 状态机与 `canvas_core/ecommerce.py` 提示词构建
- 现有 Skill：`static/lookbook-skills/yangpeilin-methods/SKILL.md`
- 现有测试：`tests/test_lookbook_premium.py`、`tests/test_lookbook_node_frontend.py`
- 生成路由默认优先 `gemini-3-pro-image-preview`；最终效果仍取决于配置的平台和模型。

## 技术方案

- 自动模式保留快速生成入口，但先执行一次参考图事实分析和一次 art direction；联网研究仍由开关控制。
- 将人物、服装、场景、场景内印刷人物/文字视为不同所有权，显式禁止串用。
- 在 Lookbook prompt 中增加 wardrobe immutable、scene typography fidelity、editorial camera grammar、自然阳光色彩脚本（暖蜂蜜亮部/橄榄绿阴影/奶油高光/保护高光）与胶片 finish 约束。
- 保留旧节点已保存配置，不改变非 Lookbook 节点。

## 验收标准

- 自动模式有输入参考图时，执行参考图事实分析和 art direction。
- 人物-场景 Lookbook prompt 明确保持人物现有服装/配饰，场景中的海报人物只作为平面图形，场景文字不被重绘或虚构。
- 相关测试、静态检查通过。
- 生成的验证组图具有连续身份、服装一致、真实接触、明确摄影机语法和非目录化构图。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
