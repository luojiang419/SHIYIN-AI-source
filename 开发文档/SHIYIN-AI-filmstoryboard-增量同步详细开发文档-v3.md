# SHIYIN-AI ↔ filmstoryboard 增量同步详细开发文档 v3

## 1. 任务目标

在既有 `shiyin-film-bridge` v2 全量桥接包之上增加幂等、可追踪的增量更新语义。用户修改 filmstoryboard 中某一张分镜图后再次点击“发送到无限画布”，SHIYIN-AI 应更新原画布中的原节点，而不是新建重复画布和 GROUP。

本阶段不改变 zip 协议版本。帧内容指纹优先读取 `storyboard.frames[].sha256`，为空时读取已经过桥接包校验的 `checksums[relative_path]`，因此兼容现有 filmstoryboard 导出包。

## 2. 用户可见效果

1. 首次发送：创建画布、图片网格 GROUP 和可选 Prompt 节点。
2. 再次发送同一 `bridge_id`：自动定位原画布和原 GROUP。
3. 未变化帧：保留节点 ID、坐标、尺寸、连线和用户在画布中的排版。
4. 已变化帧：保留节点 ID/坐标，替换图片 URL、名称和桥接元数据。
5. 新增帧：在原 GROUP 网格尾部补充节点。
6. 删除帧：移除对应源图片节点和关联连线。
7. 派生结果：只删除来源于变化/删除帧的“扩展画幅”或“线稿分镜”图片；其余派生帧保留。
8. Prompt：按 `bridgeShotStableId`（回退到镜号）原位更新；未在新包中的桥接 Prompt 删除，用户手工节点不受影响。
9. 接口返回 `created/updated/unchanged/removed/invalidated_derived` 等统计，便于 filmstoryboard 明确提示同步结果。

## 3. 模块拆分

### 模块 A：纯增量合并核心

新增 `canvas_core/bridge_sync.py`：

- `find_bridge_target(canvases, bridge_id)`：从未删除画布中定位 `film-to-shiyin` 源 GROUP。
- `sync_film_bridge_canvas(...)`：按稳定 ID 与 SHA-256 合并图片、Prompt、GROUP 和派生节点。
- 核心只接收普通字典和 URL 回调，不依赖 FastAPI、数据库或账户上下文，可独立单元测试。

### 模块 B：Loopback 接收接入

修改 `main.py`：

- 无显式 `canvas_id` 时先扫描数据库中的现有桥接目标；找不到才新建画布。
- 媒体落盘后调用增量核心，统一保存一次。
- `/capabilities` 增加 `incremental_sync: true`。
- 响应增加 `sync_mode` 和详细统计。

### 模块 C：手工导入一致性

后续将文件选择导入路径改为同一后端同步服务，避免自动发送与手工导入产生两套更新语义。本阶段优先完成自动发送主路径。

### 模块 D：反向同步

在 filmstoryboard 接收 SHIYIN-AI 回传时增加同样的帧级指纹索引和局部更新。已有同 `bridge_id` 替换同一外部故事板的能力，本阶段之后继续细化到资源级差异更新。

## 4. 数据键与合并规则

| 对象 | 主键 | 内容指纹 | 保留字段 |
|---|---|---|---|
| 源图片 | `bridgeFrameStableId` | `bridgeSha256` | `id/x/y/w/h`、未知用户字段 |
| Prompt | `bridgeShotStableId`，回退镜号 | 标准化文本与桥接字段 | `id/x/y/w/h`、未知用户字段 |
| 源 GROUP | `bridgeId + bridgeDirection` | 不适用 | `id/x/y` 与用户布局字段 |
| 派生图片 | `bridgeSourceFrameStableId` | 来源帧稳定 ID | 未受影响的节点全部保留 |

指纹相同但标题、镜号、caption 等桥接元数据改变时，节点计入 `updated_metadata`，不替换媒体 URL，也不失效派生图。

## 5. 删除与派生失效

- 删除范围只包含目标桥接 GROUP 的 `items`、`bridgePromptNodeIds` 以及明确标记 `derivedFromGroupId` 的派生节点。
- 不通过 `bridgeId` 全局删除，避免误伤用户复制出的独立节点。
- 对变化帧，删除派生节点中 `bridgeSourceFrameStableId` 命中的图片；同步修正派生 GROUP 的 `items` 与 `frameCount`。
- 派生 GROUP 为空时删除 GROUP 及其连接；仍有图片时保留 GROUP ID、坐标和其余派生结果。

## 6. 文件清单

- 新增：`canvas_core/bridge_sync.py`
- 新增：`tests/test_bridge_sync.py`
- 修改：`main.py`
- 修改：`tests/test_bridge_loopback_receive.py`
- 修改：`package.json`、`src-tauri/Cargo.toml`、`src-tauri/tauri.conf.json`、`main.py` 版本字段
- 新增：`进度快照/465-...md`
- 大模块完成后新增：`backup/<递增序号>-...md`

## 7. 待办清单

- [x] 实现纯增量合并核心与单元测试。
- [x] 接入 loopback 自动接收并实现跨画布定位。
- [x] 增加重复发送端到端测试：更新、增加、删除、位置保留、派生局部失效。
- [x] 统一手工文件导入更新语义。
- [x] 完成版本递增、全量测试、桌面构建、快照、备份和 GitHub 推送。
- [ ] 继续 filmstoryboard 反向帧级增量接收。

## 8. 验收标准

- 同一包连续发送两次，数据库只存在一个桥接画布和一个源 GROUP。
- 仅修改第 N 帧后再次发送：第 N 帧节点 ID/坐标不变、URL/指纹改变；其他帧节点和 URL 不变。
- 新增/删除帧后 GROUP 成员与包内容一致，用户非桥接节点不变。
- 只清理变化/删除帧对应的派生图，未变化帧的派生图 ID 不变。
- Prompt 文本更新但节点位置不变。
- SHIYIN-AI 全量 Python 测试通过，桌面生产构建通过。
