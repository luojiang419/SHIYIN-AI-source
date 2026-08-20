# SHIYIN-AI ↔ filmstoryboard 桥接方案 v1

## 1. 目标与边界

目标是让 SHIYIN-AI 无限画布中的“视频抽帧 GROUP”能够进入 `E:\APP\film\filmstoryboard`，自动生成或更新故事板，并可继续生成/同步拍摄脚本。

本方案不直接读写 filmstoryboard 的 SQLite 数据库。filmstoryboard 已提供稳定的外部图片故事板入口 `StoryboardController.createOrReplaceBoardFromExternalImages`，因此桥接只传输文件和结构化清单，由 filmstoryboard 自己完成数据库写入。

第一阶段支持：

- SHIYIN-AI 视频抽帧 GROUP → filmstoryboard 故事板。
- 原始帧、16:9 扩展帧、线稿分镜帧作为可选变体。
- 帧顺序、时间戳、来源节点、抽帧策略、衍生操作等溯源信息。
- 已存在的故事板幂等更新，不重复创建。
- 已存在的拍摄脚本按原有 `sourceStoryboardAssetId` 关联增量同步。

暂不在第一阶段做：

- SHIYIN-AI 直接操作 filmstoryboard 数据库。
- 两个应用之间的实时双向编辑同步。
- 自动覆盖导演在 filmstoryboard 中手工修改的镜头描述。

## 2. 标准交换包

扩展名：`.shiyinbridge.zip`

包内结构：

```text
manifest.json
images/original/001.png
images/original/002.png
images/expanded-16x9/001.png
images/line-art/001.png
preview/contact-sheet.png
checksums.json
```

`manifest.json` 采用 `schema = "shiyin-film-bridge"`、`schema_version = 1`：

```json
{
  "schema": "shiyin-film-bridge",
  "schema_version": 1,
  "bridge_id": "shiyin:<canvas_id>:<group_id>",
  "exported_at": "2026-08-20T00:00:00Z",
  "source": {
    "app": "SHIYIN-AI",
    "app_version": "1.0.193",
    "canvas_id": "...",
    "canvas_title": "...",
    "group_id": "...",
    "group_name": "...",
    "source_video_node_id": "...",
    "source_video_url": "/assets/input/...",
    "extract_run_id": "...",
    "strategy": "sceneAndInterval"
  },
  "storyboard": {
    "board_key": "shiyin:<canvas_id>:<group_id>",
    "board_name": "视频帧分镜",
    "selected_variant": "original",
    "variants": ["original", "expanded-16x9", "line-art"],
    "frames": [
      {
        "stable_id": "frame:<extract_run_id>:0001",
        "slot_index": 0,
        "frame_index": 0,
        "timestamp_ms": 0,
        "source_name": "视频 · 00:00.000 · 01",
        "relative_path": "images/original/001.png",
        "width": 1920,
        "height": 1080,
        "caption": "",
        "variant": "original",
        "sha256": "..."
      }
    ]
  },
  "script_seed": {
    "enabled": true,
    "shots": [
      {
        "shot_number": 1,
        "frame_stable_id": "frame:<extract_run_id>:0001",
        "duration_seconds": 0,
        "content": "",
        "visual": "",
        "prompt": ""
      }
    ]
  }
}
```

## 3. filmstoryboard 落地映射

导入器解压到当前工程的桥接缓存目录，并把每帧映射为 `StoryboardExternalImage`：

| Bridge 字段 | filmstoryboard 字段 |
|---|---|
| `bridge_id` | `sourceId`，形成稳定的 `external-board:<sourceId>` |
| `board_name` | `boardName` |
| `stable_id` | `StoryboardExternalImage.stableId` |
| `source_name` | `sourceName` |
| 解压后的绝对路径 | `path` |
| `width/height` | `width/height` |
| `caption` | 初始 `StoryboardItem.caption` |
| `slot_index` | `StoryboardItem.slotIndex` |

调用：

```dart
await storyboardController.createOrReplaceBoardFromExternalImages(
  sourceId: manifest.bridgeId,
  boardName: manifest.storyboard.boardName,
  images: selectedVariantImages,
  preserveExistingCaptions: true,
);
```

若用户勾选“同步拍摄脚本”，再调用：

```dart
shootingScriptController.createFromStoryboard(board);
// 已存在主脚本时使用：
shootingScriptController.syncFromStoryboard(board, previousBoard: oldBoard);
```

这样可以复用 filmstoryboard 当前已有的脚本字段、手工描述、镜头编辑和版本控制逻辑。

## 4. 幂等、冲突与删除策略

- 同一个 SHIYIN GROUP 的 `bridge_id` 固定不变，重复导入更新同一块故事板。
- `stable_id = frame:<extract_run_id>:<frame_index>`，同一轮抽帧内稳定。
- 导入时默认保留 filmstoryboard 已手工填写的 caption 和脚本字段。
- 新增帧追加到末尾；已删除帧从故事板移除，但不自动删除已有脚本中的手工镜头，先标记为未关联，避免误删导演工作。
- 变体切换只替换图片路径，不改变 `stable_id`，因此拍摄脚本关联不丢失。
- 每帧使用 SHA-256 校验，避免包损坏或错误覆盖。

## 5. 两种传输方式

### A. 标准包导入（第一阶段，推荐）

SHIYIN-AI 点击“发送到 filmstoryboard”后导出 `.shiyinbridge.zip`；filmstoryboard 的项目入口增加“导入 SHIYIN 分镜桥接包”。

优点：实现简单、可离线、可回滚、不会依赖两个应用同时运行。

### B. Loopback 自动发送（第二阶段，无缝体验）

filmstoryboard 启动本机 `127.0.0.1` 临时服务并生成一次性 token；SHIYIN-AI 通过健康检查发现 filmstoryboard 后，直接 POST manifest 和图片包；filmstoryboard 返回 `board_id`、`script_id` 和导入结果。

安全约束：

- 只监听 `127.0.0.1`。
- 每次启动生成随机 token，5 分钟过期且只能使用一次。
- 请求体限制和文件 SHA-256 校验。
- 不接受任意路径，只接收 multipart 文件或内存流。
- Loopback 不可用时自动回退到标准包导入。

## 6. 无缝衔接 UI

SHIYIN-AI GROUP 菜单新增：

- `发送到 filmstoryboard`
- `选择发送变体：原始帧 / 16:9 扩展帧 / 线稿分镜`
- `同步或创建拍摄脚本`
- `导出桥接包`

状态显示：准备中、传输中、故事板已更新、拍摄脚本已同步、已回退为离线包、失败可重试。

## 7. 推荐实施顺序

1. 先实现共享 manifest 校验器和 SHIYIN-AI 标准包导出。
2. 在 filmstoryboard 增加导入器，调用现有 `createOrReplaceBoardFromExternalImages`。
3. 完成变体切换和拍摄脚本同步的 UI。
4. 最后增加 Loopback 自动发送；标准包保留为兜底路径。
