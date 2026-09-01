# Lookbook 快速自动模式与生活化系列生成

状态：已完成
当前阶段：5/5（新增参考图真实感 Skill）
最后更新：2026-09-01

## 当前状态

现有 Lookbook 无论是否填写创作需求，都会串行执行参考图分析、联网搜索和创意策划，解析阶段可能长时间停留在“智能体任务已提交，等待执行”。人物与场景组合也缺少专门的生活化随拍系列约束。

## 下一步

当前任务已完成。已将抖音公开视频中可核验的“多人物/多场景参考图 + 预设 + 零文字提示词 + 自然互动批量生成”抽象为本地 Lookbook Skill，并设为新节点默认风格；旧节点显式选择的风格保持不变。

## 当前 TODO

- [x] 增加 Lookbook 无需求快速模式
- [x] 增加人物+场景生活化高级随拍 prompt
- [x] 保留有需求时联网搜索与创意策划链路
- [x] 完成测试、文档和 Git 提交
- [x] 新增 `reference-first-naturalism` Skill 与多人物互动/场景融合提示词约束

## 最近验证状态

- 静态检查：`node --check`、`python -m py_compile`、`git diff --check` 通过
- 单元测试：`tests/test_lookbook_premium.py tests/test_lookbook_node_frontend.py`，23 passed
- 最近 Git commit：`bc63094 docs: record lookbook skill integration`；功能实现 commit：`72a1d90 feat: add reference-first naturalism lookbook skill`（均已推送 `origin/feat/storyboard-merge-node`）

## 任务目标

无创作需求时，Lookbook 只读取连接的人物、场景等参考图并快速生成多张协调的生活化高级抓拍；有创作需求时，按用户需求进行联网案例研究和创意理解后生成。

## 验收标准

- 无创作需求的 Lookbook 任务不调用参考图视觉解析、联网搜索或创意策划模型。
- 人物+场景无需求时 prompt 明确生活化、不经意抓拍、真实环境互动、系列多组构图和高级质感，并保持人物身份连续。
- 有创作需求时仍保留联网搜索与创意策划。
- 任务阶段不再长期停留在初始提交文案，前端能看到自动模式状态。

## 已完成内容

- 后端按是否存在用户 brief 分流：无需求时直接构建参考图驱动的自动 prompt，跳过参考图视觉解析、联网搜索和创意策划；有需求时保持原有研究链路。
- 默认 prompt 增加人物+场景生活化抓拍、真实环境互动、系列多组构图和高级胶片质感约束，禁止拼贴/接触表/棚拍退化。
- 前端 Lookbook 提交改用阶段感知短轮询，并在提交前显示自动模式或联网研究模式，持续回写 agent 阶段文案。
- 新增自动模式计划、人物场景 prompt 与前端轮询契约测试。
- 新增 `static/lookbook-skills/reference-first-naturalism/SKILL.md`，记录来源边界、参考图所有权、多人物互动和反 AI 感检查。
- 新增内置“参考图真实感”风格卡片；新建 Lookbook 节点默认启用该 Skill，并更新静态资源查询串。
- 后端 `build_prompt` 增加 Skill 注入、多人物独立身份锁、互动关系锁和参考场景真实融合锁；视觉策划阶段同步接收 Skill 约束。

## 修改文件

- `main.py`
- `canvas_core/ecommerce.py`
- `static/js/canvas.js`
- `tests/test_lookbook_premium.py`
- `tests/test_lookbook_node_frontend.py`

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
