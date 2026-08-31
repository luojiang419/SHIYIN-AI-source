# AI助手连续视觉对话与参考资产复用

状态：开发中  
当前阶段：3/5  
最后更新：2026-08-31

## 当前状态

已完成当前项目结构、AI 助手前后端调用链和已有图片预览/拖拽能力的基线检查。当前分支为 `feat/storyboard-merge-node`，工作区在开发前保持干净。

现有 AI 助手已经支持对话持久化、附件上传/粘贴/文件拖拽、Agent 意图路由、图片生成和上一张图片编辑；本轮已补充生成图片卡片操作、内部生成图拖拽、共享预览缩放平移，以及后端批量图片资产基础记录。

## 下一步

下一步首先完成自动引用准备和提交确认：

1. 为参考图托盘增加来源、角色和锁定信息。
2. 设计自动引用准备接口，先返回候选，不直接静默生成。
3. 用对话资产摘要进行实体匹配，保留手动覆盖。
4. 执行后端接口测试和完整相关回归，再接入图片生成。

## 当前 TODO

- [x] 生成图片快捷操作栏：查看、复用、下载、编辑、右键快捷菜单。
- [x] 生成图片内部拖拽到输入框参考图区域。
- [x] 全屏预览滚轮缩放、平移、双击复位。
- [x] 图片级删除与安全软删除语义。
- [x] 对话视觉资产记录与稳定 asset_id。
- [ ] 多轮对话按实体/角色自动选择参考图。
- [ ] 自动引用预览、确认和手动调整。
- [ ] 多图批量下载、批量复用。
- [ ] 兼容不同图片供应商的多图参考限制。

## 最近验证状态

- 静态检查：`git diff --check` 通过；gpt-chat 内联 JS 语法通过。
- 单元测试：`python -m pytest tests/test_chat_continuity.py tests/test_generated_image_browser_cache.py tests/test_focus_guard.py tests/test_performance_contracts.py -q`，24 passed。
- 编译：`python -m py_compile main.py` 通过。
- 运行测试：接口手动冒烟被项目现有账号鉴权拦截（401），未判定为功能通过；完整桌面运行冒烟尚未启动。
- 最近 Git commit：`a0c5bc0 docs: close staged canvas performance fixes`

## 任务目标

在不破坏现有 AI 助手、图片生成、图片编辑和对话历史功能的前提下，增加连续视觉对话能力：历史生成图片可按语义自动复用，用户可手动拖拽/选择参考图并在提交前预览；同时完善图片下载、右键管理、全屏缩放平移、重试和分支操作。

## 当前项目现状

- 前端页面：`static/gpt-chat.html`，当前默认 Agent 模式。
- 后端接口：`/api/chat`、`/api/chat/agent`、`/api/chat/stream`、`/api/ai/upload`。
- 对话存储：SQLite `conversations` 表以 `payload_json` 保存消息，结构可向后兼容扩展。
- 图片生成：`generate_ai_image` 支持多种 OpenAI/Gemini/ModelScope/即梦等适配器，参考图上限由 `ONLINE_IMAGE_REFERENCE_MAX` 控制。
- 图片保存：生成结果通常落在 `/assets/output` 或 `/output`，并登记 `media_objects`。
- 现有公共能力：`static/js/image-preview.js` 已有滚轮缩放/拖拽平移；`static/js/canvas.js` 已有 `application/x-canvas-output-image` 和 `application/x-canvas-output-media` 拖拽协议。

## 技术方案

### 阶段一：低风险交互（已完成）

仅修改 AI 助手前端，保持现有请求字段和旧客户端兼容：

- 生成图片带 `data-message-id`、`data-image-index` 和 URL 元数据。
- 复用按钮把图片加入当前 `refs`，不改变现有 `reference_images` 提交格式。
- 拖拽时优先读取画布统一的输出媒体协议，再回退 `text/uri-list` 和本地文件上传。
- 下载复用现有 `/api/download-output`，不新增重复下载实现。
- 预览优先复用 `StudioImagePreview.attach`，避免重复维护缩放算法。

### 阶段二：视觉资产记录（已完成基础部分）

在不改变旧消息格式的前提下，为图片消息增加 `generated_assets` 和 `used_references` 字段；每张图片建立稳定 `asset_id`、来源消息、图片序号、提示词、供应商/模型和父级参考图关系。旧消息仍可从 `image_url/image_urls` 兼容读取。

### 阶段三：智能连续引用

增加参考图准备/确认过程，Agent 根据历史资产摘要和用户当前文本给出引用候选；前端在发送前展示候选图，用户确认后才进入图片生成。自动引用始终限制数量、校验用户归属并保留手动覆盖。

### 阶段四：生命周期和高级操作

增加图片级右键菜单、回收站、引用保护、批量操作、重试和对话分支。物理文件只在没有任何对话/作品引用时清理。

图片级删除已先采用软删除：消息保留 `deleted_assets`，只从可见 `image_urls/generated_assets` 中移除，物理文件暂不清理。

## 验收标准

1. 现有普通聊天、Agent、生图、编辑、文件上传和历史对话功能继续可用。
2. 生成图片可以点击“复用”或拖拽到参考图区域，并在发送前看到缩略图。
3. 外部文件拖拽行为不回归，参考图仍能按现有格式提交给后端。
4. 图片全屏查看支持滚轮缩放、按住拖拽平移、双击复位和 Esc 关闭。
5. 图片卡片可以下载，操作失败时给出可理解的提示。
6. 连续对话中可以区分并选择人物、动物、背景等历史资产，用户能在提交前修改自动引用。
7. 删除不会误删仍被后续消息引用的物理文件。

## 已完成内容

- 完成现有前后端能力和缺口分析。
- 确认复用已有下载、预览和画布拖拽协议，避免引入重复实现。
- 完成 AI 助手生成图片快捷操作、内部拖拽复用和共享预览缩放平移。
- 完成对话图片资产基础记录和批量图片兼容读取。
- 新增 `tests/test_chat_continuity.py`，覆盖新旧消息结构。
- 完成图片级右键移除接口和前端持久化刷新，保留被删除资产记录并保护物理文件。

## 当前关键修改

- `static/gpt-chat.html`：生成图片操作栏、拖拽协议、下载入口、共享预览和右键快捷菜单。
- `main.py`：扩展 `AIReference` 元数据，新增对话图片资产记录和兼容读取函数，并在两条生图路径写入 `generated_assets`。
- `tests/test_chat_continuity.py`：覆盖资产 ID、批量图片和旧消息兼容。
- `main.py`：新增 `delete_chat_message_asset` 和 `/api/conversations/{conversation_id}/messages/{message_id}` 图片/消息软删除接口。

## 已知问题

- 即梦适配器当前倾向只使用第一张参考图，多图自动引用需要供应商能力降级策略。
- 当前 `latest_chat_image_refs` 只选最近单张生成图，不能满足多实体组合引用。
- 当前图片类型消息在普通历史转换中不会自动作为视觉输入发送给模型。

## 开发日志

- 2026-08-31：建立任务文档，完成基线检查，准备从低风险前端交互开始。
- 2026-08-31：完成前端图片操作与拖拽复用；完成后端视觉资产基础记录，22 项相关测试通过。
- 2026-08-31：完成图片级软删除和右键移除，相关回归测试 24 项通过；接口手动冒烟因现有登录保护返回 401，未作为运行验证结论。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：

1. 阅读项目规则。
2. 阅读本任务文档。
3. 检查 Git branch 和 git status。
4. 从“下一步”直接继续。
5. 不重复已经完成的基线分析。
