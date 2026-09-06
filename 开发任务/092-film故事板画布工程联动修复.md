# film 故事板画布工程联动修复

状态：已完成（源码与集成验证）
当前阶段：3/3
最后更新：2026-09-07

## 当前状态

已修复 film 发送端携带 active_canvas_id、SHIYIN 接收端优先当前画布、工程列表未处理实时事件的问题。现在按来源 bridge_id 新建或增量更新对应工程，列表自动刷新且保留视口。导入导出修复记录在任务 032。两个仓库代码均已提交并 push。

## 下一步

源码任务已完成。安装版交付时需同步更新两端：重建 SHIYIN 安装包，并使用本次 film Release 构建；尚未覆盖用户已安装客户端。

## 当前 TODO

- [x] 检查项目、Git、调用链
- [x] 修改两端目标工程选择与列表刷新
- [x] 接口集成与 Dart 专项测试
- [x] 更新文档、代码提交与推送

## 最近验证状态

- SHIYIN 工程包与桥接回归 27 项通过；真实 HTTP 验证 A/B 独立、重发 A 幂等、无关画布不变、ZIP 往返与媒体字节。
- Chromium 9 项流程检查通过，验证菜单点击、下载/导入、实时显示、静默保存与失败状态。
- film 桥接测试 7 项通过；修改文件 flutter analyze 无问题；Windows Release 编译通过（59.5 秒）。
- branch：fix/canvas-package-film-link / fix/shiyin-board-project-link。
- 代码 commit：SHIYIN b1f34b7 / film fea4586；均已正常 push。
- 原工作区无关修改保留，main.py 只暂存本次接收目标选择的差异。

## 任务目标与技术方案

任意有图片的故事板右栏发送后，在 SHIYIN 默认项目创建以画板命名的画布工程。按稳定 bridge_id 复用已有对应画布，保持帧增量同步。显式指定 canvas_id 的 API 保持兼容；自动发送不再指定当前画布。列表复用现有 RuntimeSync 的消息，合并刷新并保持视口。

## 文件 / 模块清单

- SHIYIN：main.py、static/js/canvas-list.js、static/canvas-list.html、相关测试。
- film：lib/features/bridge/data/bridge_loopback_client.dart、桥接测试。

## 验收标准

- 有其他画布打开时，画板 A/B 分别创建独立工程。
- 重发 A 更新 A，节点与工程不重复，原画布不变。
- 工程列表接收新建事件自动显示；媒体可读取。
- 服务缺失或不支持直连接收时给出可操作错误。

## 已知问题

已安装客户端和原生 WebView 文件保存窗口尚未实测；没有自动发布或替换用户安装版。源码及隔离集成测试无遗留失败。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

读取本文件与任务 032、检查两仓库 Git 与源码，从下一步继续。
