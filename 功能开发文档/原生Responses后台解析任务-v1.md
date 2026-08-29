# 原生 Responses 后台解析任务 v1

状态：已完成
当前阶段：4/4
最后更新：2026-08-29

## 当前状态

用户确认电商专用 provider 使用原生 Responses API，且同一 `gpt-5.6-sol` 配置在 OpenCode 中可正常联网搜索。当前视频润色/自动解析仍是同步 HTTP 请求；复杂多图请求可能被上游网关提前返回 524。

## 下一步

1. 安装新版后通过 GUI 点击一次润色/自动解析做最终验收。

## 当前 TODO

- [x] 后端后台解析任务及状态查询接口
- [x] 前端轮询与阶段状态处理
- [x] 原生 Responses `web_search` 能力探测与同模型调用
- [x] 真实 1 图解析验证
- [x] 编译并更新安装包记录

## 已完成内容

- 新增 `/api/canvas-prompt-polish-tasks`、`/api/canvas-video-auto-parse-tasks` 和 `/api/canvas-prompt-tasks/{task_id}`。
- 前端画布、智能画布和 film 节点统一提交后台任务并轮询，最长等待 30 分钟。
- 联网搜索先以无图片文本请求执行，再把摘要交给同一 provider/model 的视觉解析请求；视觉请求不再同时附加搜索工具。
- 按用户最终要求移除紧凑版导演规则：自动解析和润色始终使用完整版规则；遇到 524 时仅对完全相同的完整请求重试。
- 真实安装目录配置验证：`ecommerce-vision + gpt-5.6-sol`，搜索请求日志 `tools=1`，视觉请求日志 `tools=0`，最终自动解析返回 200。
- 严格真实验证：4 张参考图 + 完整长导演规则 + 原生 Responses 联网搜索，后台任务约 111.5 秒完成，返回 974 字符并完整覆盖 `<<<image_1>>>` 至 `<<<image_4>>>`；搜索和视觉阶段均保持 `ecommerce-vision / gpt-5.6-sol`。
- 静态检查：`python -m py_compile main.py`；测试：163 passed。
- 安装包构建：PyInstaller、Tauri、运行时 smoke、Inno Setup 全部通过。

## 安装包

- `dist/installer/SHIYIN-AI-Setup-1.0.371.exe`
- 大小：73,233,193 bytes
- SHA-256：`0FA9F63C4F6240853D232B82B4181A1852751F6E46AB42FE72CD84DA375BA28E`

## 设计约束

- 不使用 CLI 伪造其它模型；解析始终使用节点配置的 provider 和 model。
- 后台任务只能解决浏览器长连接问题；若上游仍有同步 524，保留紧凑提示词重试。
- 网络搜索与视觉解析优先拆成可追踪步骤；不得在未确认支持时给电商代理附加工具。
