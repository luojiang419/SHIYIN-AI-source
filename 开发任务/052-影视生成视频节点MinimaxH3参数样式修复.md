# 影视生成视频节点 Minimax H3 参数样式修复

状态：已完成
当前阶段：3/3
最后更新：2026-09-03

## 当前状态

已完成修复：影视制作组的 `film-video` 节点现在依据 `MiniMax H3` 模型切换到 H3 专用分辨率、采样步数和参考模式设置；绑定器、经典画布和智能画布提交链路均已同步。

## 下一步

1. ~~为影视 `film-video` 节点增加 H3 专用参数面板和切换时默认值归一化。~~
2. ~~绑定 H3 控件，并将 `steps` / 参考模式透传到经典、智能画布的视频请求。~~
3. ~~执行 JS 语法检查与影视节点相关测试，更新文档并提交 Git。~~

## 当前 TODO

- [x] H3 参数面板与模型切换默认值
- [x] 经典/智能画布提交参数同步
- [x] 静态契约、语法和相关测试

## 最近验证状态

- 静态检查：`node --check static/js/canvas-film-nodes.js static/js/canvas.js static/js/smart-canvas.js` 通过
- 单元测试：H3/视频/影视相关 63 passed；完整影视集合另有 1 项既有契约失败
- 最近 Git commit：`b0b7ade fix: sync film video node with minimax h3 settings`

---

## 任务目标

当影视制作节点组的“生成视频”节点选择 `MiniMax H3` 时，参数区应显示 H3 专用设置样式，并且用户设置的步数、分辨率、时长、画幅、全能参考/首尾帧模式实际进入生成请求；切换到其他模型时继续显示通用参数。

## 验收标准

- `film-video` 选择 MiniMax H3 后显示 H3 分辨率预设、采样步数（4–30）及互斥参考模式按钮。
- H3 时长上限为 15 秒，分辨率不再显示通用 480P/720P/1080P/4K 枚举。
- 切换模型会清理不兼容参数并触发面板重绘；经典和智能画布提交 `steps`、`multimodal`、`useFrameRoles` 对应设置。
- `node --check` 与影视相关 Python 测试通过。

## 已完成内容

- `canvas-film-nodes.js` 增加 H3 分辨率预设、H3 参数面板、模型切换归一化和互斥参考模式绑定。
- `canvas.js` 将影视视频请求的 `steps` 改为读取节点设置；智能画布将 `videoSteps`、`videoMultimodal`、`videoUseFrameRoles` 透传到视频生成设置。
- `canvas-film-nodes.css` 增加 H3 参数面板和说明样式；新增静态契约测试覆盖面板与提交字段。

## 已知问题

- `tests/test_canvas_film_nodes.py::test_line_art_storyboard_node_has_classic_and_smart_execution_branches` 仍因分支已有的旧字符串契约失败，与本次改动无关。

## 开发日志

- 2026-09-03：定位影视 `film-video` 参数区硬编码问题，完成 H3 面板、切换归一化、提交字段同步和验证。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]
