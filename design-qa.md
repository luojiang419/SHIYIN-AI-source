# 深度图节点高级控制 Design QA

- source visual truth path: `C:/Users/jiang/AppData/Local/Temp/codex-clipboard-f41e0d58-5980-4953-abd6-0fbeaa3b8e2a.png`
- implementation screenshot path: `E:/APP/SHIYIN-AI/.codex-artifacts/depth-map-controls/implementation-node.png`
- modal screenshot path: `E:/APP/SHIYIN-AI/.codex-artifacts/depth-map-controls/implementation-modal.png`
- combined comparison path: `E:/APP/SHIYIN-AI/.codex-artifacts/depth-map-controls/node-comparison.png`
- viewport: desktop Chrome，`1920 × 920` CSS px
- density: browser screenshot `deviceScaleFactor 1`，实现截图为 `1920 × 920` px
- source pixels: `684 × 745` px
- comparison normalization: 从实现全屏截图裁出 `495 × 535` 节点区域，保持比例缩放后与原图并排；没有拉伸图片内容
- state: 深色主题；连接图片、深度输出与高精度组件均为就绪态；弹窗为默认参数态

## Findings

最终复核未发现仍需修复的 P0、P1 或 P2 问题。

- 字体与层级：节点标题、预览标签、按钮和状态文字延续原节点的 Inter/系统字体、粗细与小字号密度；弹窗标题和分组标题层级清楚，没有截断。
- 间距与布局：节点仍保持双图等宽结构，“高级控制”位于“重新生成”右侧；弹窗在 `1920 × 920` 视口完整显示，双图区大于参数区，底部状态和操作按钮固定可见。
- 色彩与主题：背景、边框、卡片、主文字、弱文字和状态色均复用现有主题变量；没有引入蓝色选中态或与原节点冲突的强调色。
- 图片质量：输入图使用 `object-fit: contain`，实时 Canvas 保持原始宽高比；默认参数不会重复压缩，非默认参数从保存的原始深度 PNG 重新计算。
- 文案与可理解性：远景、近景、中间层次、对比度、亮度、平滑、反转均有简短结果导向说明；数值单位和正负方向可直接看懂。
- 图标：继续使用项目现有 Lucide 图标，没有新增占位图、手工 SVG 或图片资产。
- 交互与无障碍：按钮无结果时禁用；弹窗具有 `role="dialog"`、`aria-modal`、标题关联、Escape 关闭、打开后焦点进入关闭按钮并在关闭后返回触发按钮。

## Full-view comparison evidence

原图只给出了深度图节点本体，没有给出高级控制弹窗的视觉稿。并排对比确认实现保留了原节点的标题栏、双图比例、标签、圆角、按钮高度、状态条和输出信息；新增按钮在指定位置，没有挤压或改变预览区结构。

弹窗全屏截图确认在同一深色主题中使用双图预览加右侧控制区，所有核心控件在首屏可见，没有溢出遮挡或持久操作按钮丢失。

## Focused region comparison evidence

重点比较了原图与实现的按钮行及双图预览区域。按钮行保持相同高度、边框、图标和间距，只在“重新生成”右侧增加“高级控制”；预览标签位置、卡片圆角和图片 contain 行为保持一致。

## Interaction verification

- 点击“高级控制”打开弹窗并显示连接图片和实时深度图。
- “人像增强”预设一次更新远景、近景、中间层次、对比度和平滑。
- 将远景调至 `93%` 时，近景自动约束为 `98%`，两端始终保留有效间隔。
- 反转深度后实时预览黑白关系立即交换。
- 防抖结束后状态显示“已同步到节点输出”，节点输出文件名更新并显示“已调校”。
- 刷新页面后 `93/98/+10/112/0/1/反转` 参数完整恢复。
- “恢复默认”回到 `0/100/0/100/0/关闭/不反转`，节点重新使用原始深度图。
- 浏览器控制台 warning/error：`0`。

## Comparison history

1. 首次检查发现实时 Canvas 使用 `width:100%; height:100%` 会把非同宽高图片拉伸，且弹窗打开后键盘焦点仍停留在背景按钮，记为 P2。
2. 修复为 Canvas 按固有尺寸 `max-width/max-height` contain 展示；打开弹窗后聚焦关闭按钮，关闭后尝试恢复到触发按钮。
3. 首次有效图片预览完成后底部仍显示“正在准备实时预览”，记为 P2；已在渲染完成且无待提交任务时更新为“实时预览已就绪”。
4. 修复后的节点并排图、弹窗全屏图与 AX 状态复核均未发现新的 P0/P1/P2 问题。

## Open Questions

无。原始参考未规定弹窗具体排版，当前弹窗依据用户的双图、实时生效和直观参数要求，并严格复用现有产品视觉语言。

## Implementation Checklist

- [x] 节点按钮位置与禁用态
- [x] 双图实时预览
- [x] 参数、预设、约束和恢复默认
- [x] 防抖持久化与刷新恢复
- [x] 主题、响应式和键盘关闭
- [x] 控制台与自动化回归

## Follow-up Polish

无阻塞项。

final result: passed
