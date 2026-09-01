# 平面广告 Lookbook 节点开发

状态：已完成
当前阶段：16/16（平台/模型菜单改为点击展开）
最后更新：2026-09-01

## 当前状态

已完成经典无限画布独立 `CanvasLookbookNode` 模块、视觉风格卡片弹窗、GitHub Skill 解析/安装接口、Skill 封面生成接口、节点参数与生成结果回写。后端复用电商视觉 API 路由，并在 Lookbook 任务开始前执行“联网案例研究 → 视觉创意总监策划 → 生图”的质量增强链路；未重新暴露已弃用的电商工作流节点组。生成后视觉模型会按 0-100 分检查输出，定位弱图并最多自动替换两张，再执行二次验收，质检分数和修复数量回写节点。人物与商品输入现在带有明确的组装约束：人物作为身份/身体基底，商品作为唯一 SKU 来源。Lookbook 已从一级创建菜单移入“平面广告”二级菜单。本轮补齐了旧 immutable cache 查询串、选择按钮事件兜底、内置 visual-skills/image 风格集、图片快捷面板定位/溢出修复、7 个 Lookbook 输入端口的独立垂直布局、端口对应文本标签、节点内部标签栏、标题提供器按节点类型隔离、影视制作/平面广告二级菜单互斥关闭、Lookbook 选择风格弹窗兼容旧 WebView、紧凑端口间距，以及平台/模型二级菜单改为点击展开，鼠标移入不再自动展开。

## 下一步

1. 当前修复已提交并推送；如发布安装包，重新构建即可带入新静态资源查询串。

## 当前 TODO

- [x] Lookbook 节点与输入/输出端口
- [x] 视觉风格 Skill 卡片弹窗、封面自由设置
- [x] 文本需求、画幅/分辨率/质量/生成数量
- [x] 电商 API 复用、联网案例研究、生成结果回写
- [x] 视觉创意总监策划与多图一致性约束
- [x] 细化人物、商品、场景、材质、Logo 五类输入端口并保留语义映射
- [x] 增加姿态、版式输入端口
- [x] 增加 Logo/文字保护与质量检查约束
- [x] 生成后视觉质检与弱图自动修复
- [x] 局部验证、任务文档更新、Git 提交
- [x] 修复旧静态缓存导致的选择器无响应
- [x] 内置 `smixs/visual-skills/image` 衍生风格卡片并保留署名
- [x] 修复图片快捷面板定位与生成按钮横向溢出
- [x] 增加 Lookbook 前端契约回归测试
- [x] 修复 7 个输入端口重叠导致只能连接一个端口
- [x] 启动隔离端口 Web 服务并完成登录、创建节点、弹窗选择和端口位置冒烟
- [x] 为 7 个输入端口显示对应中文文本标签
- [x] 将端口文本标签放入节点内部并预留内容区宽度
- [x] 修复 Lookbook 标题提供器覆盖所有节点的问题
- [x] 兼容旧 Web 页面事件路径并强制弹窗可见状态
- [x] 修复影视制作与平面广告二级菜单互相遮挡
- [x] Lookbook 选择风格增加 `mousedown` 事件兜底
- [x] 收紧 Lookbook 左侧输入端口垂直间距
- [x] 平台/模型菜单改为点击展开，移除 Lookbook 悬停展开

## 最近验证状态

- 静态检查：`node --check static/js/canvas.js static/js/canvas-lookbook-node.js`、`git diff --check` 已通过
- 单元测试：Lookbook/画布菜单/经典节点专项 `29 passed`
- 编译：未开始（前端为静态资源）
- 运行测试：`http://127.0.0.1:3017` Web 冒烟通过（Lookbook 创建、10 张风格卡片、选择回写、7 个端口纵向分布、内部文本标签、影视/图片/Lookbook 标题恢复）；未执行桌面实例级付费生成冒烟（当前环境无可复用实例/API Key）
- 最近 Git commit：待本轮提交

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

## 当前关键修改

- `static/js/canvas-lookbook-node.js`：内置 10 张 visual-skills/image 衍生风格、上游来源署名、直接/委托点击监听双保险。
- `static/js/canvas.js`：快捷面板优先定位到节点上方并按可用高度滚动，避免覆盖节点和按钮溢出。
- `static/css/canvas.css`：快捷面板 z-index、画布内最大高度、六列/移动端两列 minmax 布局，生成按钮保持面板内。
- `static/canvas.html`：升级 Lookbook/CSS/Canvas 查询串，避免 immutable cache 命中旧脚本。
- `static/lookbook-skills/image/SKILL.md`：记录上游 visual-skills/image 映射原则与 CC BY 4.0 署名。
- `tests/test_lookbook_node_frontend.py`：覆盖内置风格、按钮绑定、面板定位/布局和缓存查询串。
- `static/js/canvas.js` / `static/css/canvas.css`：给多角色输入端口写入 `--canvas-port-top` 并按节点高度分布，避免 7 个端口重叠。
- `static/css/canvas.css`：使用 `data-role-label` 为每个输入端口渲染对应中文文本标签。
- `static/css/canvas.css`：标签改为端口右侧的节点内标签，并为 Lookbook body 预留 74px 左侧标签栏。
- `static/js/canvas-lookbook-node.js`：标题函数只对 `lookbook` 类型返回 Lookbook 标题，其他节点交给通用标题逻辑。
- `static/js/canvas-lookbook-node.js`：选择按钮同时绑定 pointerup、onclick 与祖先委托，打开弹窗时显式设置 `display:flex`。
- `static/js/canvas.js`：进入另一组二级菜单时立即关闭当前 fixed 子菜单；Lookbook 输入端口额外写入紧凑的 `--lookbook-port-top`。
- `static/js/canvas-lookbook-node.js`：选择风格/生成按钮增加 `mousedown` 事件兜底，兼容桌面 WebView 的点击事件路径。
- `static/css/canvas.css`：Lookbook 端口使用紧凑垂直间距，弹窗打开态显式启用指针事件。

## 已知问题

- 全量画布回归仍有 10 个既有基线断言失败，集中在旧版本资源字符串、已移除的影视线稿/灯光重塑节点契约；本轮专项 156 项全部通过，未发现与 Lookbook 或快捷编辑面板相关的回归。
- 桌面实例级“点击选择风格 → 上传/安装 → 生成”中的付费图片调用需要可用图片 API Key，本环境未执行该付费调用；非付费 UI、端口和缓存行为已在隔离 Web 服务完成。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
