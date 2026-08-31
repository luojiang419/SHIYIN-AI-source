# 平面广告 Lookbook 节点开发

状态：开发中  
当前阶段：5/5（质量增强）
最后更新：2026-08-31

## 当前状态

已完成经典无限画布独立 `CanvasLookbookNode` 模块、视觉风格卡片弹窗、GitHub Skill 解析/安装接口、Skill 封面生成接口、节点参数与生成结果回写。后端复用电商视觉 API 路由，并在 Lookbook 任务开始前执行“联网案例研究 → 视觉创意总监策划 → 生图”的质量增强链路；未重新暴露已弃用的电商工作流节点组。局部回归验证已通过。

## 下一步

1. 检查最终 diff，提交质量增强模块。

## 当前 TODO

- [x] Lookbook 节点与输入/输出端口
- [x] 视觉风格 Skill 卡片弹窗、封面自由设置
- [x] 文本需求、画幅/分辨率/质量/生成数量
- [x] 电商 API 复用、联网案例研究、生成结果回写
- [x] 视觉创意总监策划与多图一致性约束
- [x] 细化人物、商品、场景、材质、Logo 五类输入端口并保留语义映射
- [x] 局部验证、任务文档更新、Git 提交

## 最近验证状态

- 静态检查：`node --check`、`python -m py_compile` 已通过
- 单元测试：电商与画布电商回归 `148 passed`
- 编译：未开始（前端为静态资源）
- 运行测试：未开始
- 最近 Git commit：`75deb02 feat: add standalone lookbook canvas node`

---

## 任务目标

在无限画布中提供“Lookbook”平面广告节点：用户可连接图片，可输入需求，选择视觉风格 Skill，设置图片参数与生成数量，点击“生成 Lookbook”得到多张广告图。风格选择以卡片弹窗呈现，每种风格支持用户自定义封面。生成使用已配置的电商专用视觉 API，并在联网可用时先检索优秀公开案例，只吸收可迁移的构图、材质、灯光和版式方法。

## 技术方案

- 前端使用独立 `CanvasLookbookNode`，只复用画布通用节点生命周期和电商任务轮询；不把 Lookbook 注册到已弃用的 `CanvasEcommerceNodes` 节点组。
- 新类型 `lookbook` 具有一个输入端口、一个输出端口；上游图片与文本需求合并为 `universal` 电商任务，`prompt_policy` 使用 `lookbook`，风格 Skill 作为结构化 options 传给后端。
- 风格 Skill 保存 `id/name/description/prompt/cover`，内置可选风格只提供默认渐变/内置图片封面，不覆盖用户自定义封面。
- 后端将 Lookbook 风格和联网研究摘要加入最终 prompt；联网研究失败时保留图片生成主流程，并在任务元数据记录状态。
- 生成结果存入节点 `generatedOutputs`，可继续连接 Output 或其他生成节点。

## 验收标准

- 菜单可创建 Lookbook 节点，节点显示输入端口、输出端口和完整控件。
- 点击视觉风格打开卡片弹窗，选择后回到画布；自定义封面可持久化。
- 连接图片后可不填需求直接生成；填写需求时模型同时参考图片、风格 Skill 和联网案例方法。
- 画幅、分辨率、质量、数量设置被提交，数量限制 1～4。
- 任务失败在节点显示错误，成功结果显示缩略图并可向下游输出。
- `python -m py_compile main.py canvas_core/ecommerce.py` 与前端语法检查通过。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
