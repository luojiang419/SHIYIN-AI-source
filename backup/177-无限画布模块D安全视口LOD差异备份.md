# 177-无限画布模块 D 安全视口 LOD 差异备份

日期：2026-08-24

## 备份范围

- `static/js/canvas.js`
- `static/js/smart-canvas.js`
- `static/css/canvas.css`
- `static/css/smart-canvas.css`
- `tests/test_canvas_safe_lod.py`
- `开发文档/无限画布性能优化开发文档-v1.md`

## 经典画布差异

修改前：大场景只依赖静态 `.canvas-lod-safe > .node-body { content-visibility:auto }`，没有显式判断视口和交互状态。

修改后：

- 增加 `CLASSIC_SAFE_LOD_ENABLED`、`CLASSIC_SAFE_LOD_MARGIN` 和 rAF 调度。
- `updateClassicSafeLod()` 根据 `currentWorldViewRect()` 加扩展边界计算普通节点是否视口外。
- 只给 body 切换 `canvas-lod-outside`；选中、拖动、缩放、临时连线源和连接创建源加入保护集合。
- `renderNode()` 将 panorama、multiView、特殊节点、ecommerce/film 节点及 `group/promptGroup` 排除出 `canvas-lod-safe`。

## 智能画布差异

修改前：大场景静态按非特殊节点启用 body LOD，缺少 Prompt、Loop、历史、多图组和分组节点的统一排除规则。

修改后：

- 增加 `SMART_SAFE_LOD_ENABLED`、`SMART_SAFE_LOD_MARGIN` 和 rAF 调度。
- `updateSmartSafeLod()` 使用 viewport 世界坐标和 `smartNodeRectIndex` 计算安全边界。
- `render()` 为普通单图节点写入 `smart-lod-safe`；特殊、Prompt、Loop、历史、多图组和 `smart-group` 不进入 LOD。
- 端口拖动源/目标、节点拖动组、缩放节点、选中节点和插入预览节点加入保护集合。

## CSS 差异

两套 CSS 新增 active/outside 规则：视口外 body 使用 `content-visibility:auto` 与 intrinsic size，进入扩展视口后恢复 `content-visibility:visible`；未改动节点外层 overflow 和端口布局。

## 测试差异

新增 `tests/test_canvas_safe_lod.py`，静态验证开关、视口调度、排除规则、交互保护、CSS 规则以及实现中不存在删除节点 DOM 的逻辑。

## 回滚方式

将本次提交中的 LOD 开关置为 `false` 即可保留静态 body LOD 和原有渲染流程；必要时恢复本备份对应的 JS/CSS 文件。节点、端口、连线、媒体、输入法、远程同步和撤销重做数据结构未修改。
