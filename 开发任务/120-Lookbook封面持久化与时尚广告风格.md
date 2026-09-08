# Lookbook 封面持久化与时尚广告风格

状态：已完成
当前阶段：3/3
最后更新：2026-09-08

## 当前状态

- 封面已改为账号级服务端持久保存，修复内置风格覆盖上传封面，支持旧 localStorage 迁移。
- “时尚广告”已集成 v1.2 核心规则；完整原始 ZIP 技能归档于 skills，运行时使用紧凑规则并尊重节点数量、比例和版式。
- 六款封面全部通过安装版保存的拾影配置实生成成功（gemini-3-pro-image-preview，3:4，1K），已随 static 资源提供；支持上传或手动重新生成。
- 123 项相关测试通过；真实浏览器上传、无缓存重开、保存失败保留原图通过；后端进程重启后记录与媒体均可读取。
- 本任务未打包或替换当前安装程序；源码和静态资源已完成。
- 工作区存在其他任务修改，仅提交本任务文件及相关增量。
- branch：feat/film-workflow-canvas。

## 下一步

当前源码任务已完成。若需要在已安装软件中使用，下一步按现有发布流程编译安装包；本任务不自动替换运行中的安装程序。

## 当前 TODO

- [x] 封面持久化、旧数据迁移与前端反馈
- [x] 时尚广告技能及生成链路集成
- [x] 六款预设封面实生成与默认展示
- [x] 回归验证、浏览器与后端重启实测、文档
- [x] Git 提交与 push（功能提交 3777275 已正常推送 origin/feat/film-workflow-canvas）

## 最近验证状态

- JavaScript：node --check 通过。
- Python：main.py、ecommerce.py、lookbook_styles.py、封面生成脚本 py_compile 通过。
- pytest：Lookbook styles/node_frontend/story/premium/latency 共 123 项通过。
- 浏览器：真实隔离后端，上传与自动保存、全新 Edge 进程清空缓存恢复、模拟磁盘失败、新风格选用与数量/比例不变均通过。
- 后端重启：停止并重新启动同一隔离数据目录的后端，确认风格 URL 不变且媒体 HTTP 200。
- 实图：六款封面全部成功，896×1200，合计约 0.92MB；manifest 记录平台与模型，不含密钥。
- 安装打包：现有构建脚本递归复制 static，运行时导演规则位于 Python 模块；本任务未产生新安装包。
- 验证截图与运行报告：.codex-artifacts/lookbook-styles-ui/。
- Git diff --check：通过；仅暂存本任务 18 个文件，main.py 与 canvas.css 仅暂存本任务增量，其他任务未提交修改保留。
- 避坑记录：避坑指南/Lookbook内置风格封面覆盖与持久化.md（该目录被项目 .gitignore 忽略，按现有规则本地保留）。
- 功能 Git commit：3777275（feat: persist Lookbook covers and add fashion advertising style），已 push。本文档完成状态随后独立提交。

## 任务目标与验收标准

- 上传封面立即生效，软件/浏览器重启后仍能恢复；保存失败明确提示。
- 数据写入当前账号持久目录，内置预设更新不覆盖用户封面。
- 新增“时尚广告”，按 v1.2 参考角色、身份/外观分离、环境光、肤质、连续性、轴线和镜头多样性规则生成。
- 六款预设各有对应生成封面，用户可手动上传替换；不得在每次打开节点时重复收费生成。

## 技术方案与文件清单

- canvas_core/lookbook_styles.py：持久化、时尚广告适配提示词及拾影封面路由。
- main.py：风格读写 API、封面生成 API。
- static/js/canvas-lookbook-node.js：覆盖合并、迁移、保存、默认封面与新预设。
- canvas_core/ecommerce.py：新增风格的生成约束适配。
- skills/fashion-editorial-sequence-director/SKILL.md：原始 ZIP 技能归档。
- static/img/lookbook-covers/：实生成封面。
- tests/：持久化、路由与前端运行回归。

## 已知问题

无功能阻塞。ZIP 默认 contact-sheet-first 已适配为先联合规划连续性，仅用户选择拼图时输出拼图，避免改变独立成片数量。安装版仍需后续打包更新才能使用本次源码功能。

## 开发日志

- 2026-09-08：完成问题定位与集成规划。
- 2026-09-08：完成持久化、技能适配、拾影六款封面实生成及 123 项回归、浏览器/后端重启验证。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

阅读项目规则与本文档，检查 Git branch/status，从“下一步”继续，以源码与 Git 状态为准，不覆盖其他任务修改。
