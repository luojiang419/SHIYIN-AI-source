# SHIYIN-AI ↔ filmstoryboard 双向桥接详细开发文档 v2

## 1. 文档目的

本文件是双向桥接的实施文档，覆盖：

- filmstoryboard 故事板/拍摄脚本发送到 SHIYIN-AI 无限画布；
- SHIYIN-AI 抽帧、扩展画幅、线稿分镜结果回传 filmstoryboard；
- 离线标准包、Loopback 自动发送、失败回退和冲突处理；
- 代码模块、数据契约、测试和验收标准。

第一阶段不直接跨项目操作 SQLite，所有跨项目数据均通过版本化桥接包或本机受控 API 传输。

## 2. 用户最终体验

### 2.1 film → 无限画布

在 filmstoryboard 的故事板或拍摄脚本页面点击“发送到无限画布”：

1. 选择当前故事板、当前脚本或指定镜头范围。
2. 选择原始帧、16:9 扩展帧、线稿帧或复刻帧。
3. SHIYIN-AI 自动打开/创建目标画布。
4. 创建图片节点 GROUP；每张图片携带镜头编号、时间戳和脚本字段元数据。
5. 可选创建 Prompt 节点，并将图片节点连接到对应 Prompt 节点。
6. SHIYIN-AI 返回画布 ID、GROUP ID 和导入结果。

### 2.2 无限画布 → film

在 SHIYIN-AI 选中视频抽帧 GROUP 或衍生 GROUP，点击“发送到 filmstoryboard”：

1. 选择原始/扩展/线稿变体。
2. filmstoryboard 创建或更新同一个故事板。
3. 选择同步拍摄脚本后，按稳定帧 ID 增量更新脚本图片。
4. 保留导演已经编辑的 caption、镜头描述、对白、声音和提示词。

## 3. 实施阶段

### 阶段 0：协议与安全基础

目标：两边能解析同一种 manifest 和 `.bridge.zip`，不依赖 UI。

交付：

- Python `canvas_core/bridge_manifest.py`；
- Python 桥接包读写、路径穿越防护、SHA-256 校验；
- Dart `BridgeManifest` / `BridgePackageImporter`；
- JSON schema 兼容测试和恶意压缩包测试。

### 阶段 1：film → SHIYIN-AI

目标：先打通用户最关心的“发送到无限画布”。

交付：

- film 导出 `.filmbridge.zip`；
- SHIYIN 导入 `.filmbridge.zip`；
- 自动创建目标画布、图片节点、GROUP；
- 可选创建 Prompt 节点和派生元数据。

### 阶段 2：SHIYIN-AI → filmstoryboard

目标：回传抽帧结果、扩展画幅和线稿分镜。

交付：

- SHIYIN 导出 `.shiyinbridge.zip`；
- film 导入并更新故事板；
- 变体切换；
- 拍摄脚本增量同步。

### 阶段 3：Loopback 自动发送

目标：两应用同时运行时实现“一键发送”。

交付：

- film 本机服务健康检查和一次性 token；
- SHIYIN 自动 POST 桥接包；
- 失败自动退回离线包；
- 导入结果回传和 UI 状态展示。

## 4. 统一标识和数据模型

### 4.1 稳定标识

```text
bridge_id       = <source_app>:<project_id>:<board_or_canvas_id>:<group_id>
frame_stable_id = frame:<source_group_id>:<frame_index>:<variant_family>
shot_stable_id  = shot:<bridge_id>:<shot_number>
```

变体切换不得改变 `frame_stable_id`，否则会导致拍摄脚本关联丢失。

### 4.2 manifest

```json
{
  "schema": "shiyin-film-bridge",
  "schema_version": 2,
  "bridge_id": "film:<project_id>:<board_id>",
  "direction": "film-to-shiyin",
  "exported_at": "2026-08-20T00:00:00Z",
  "source": {
    "app": "filmstoryboard",
    "app_version": "1.0.0.328",
    "project_id": "...",
    "project_name": "...",
    "board_id": "...",
    "script_id": "..."
  },
  "canvas": {
    "canvas_id": "optional-existing-canvas-id",
    "canvas_title": "",
    "layout": "grid",
    "create_prompt_nodes": true
  },
  "storyboard": {
    "board_name": "",
    "selected_variant": "original",
    "frames": []
  },
  "shots": [],
  "variants": [],
  "checksums": {}
}
```

### 4.3 frame 字段

```json
{
  "stable_id": "frame:board-1:0001:original",
  "shot_stable_id": "shot:board-1:1",
  "slot_index": 0,
  "shot_number": 1,
  "frame_index": 0,
  "timestamp_ms": 0,
  "source_name": "镜头 01",
  "relative_path": "images/original/001.png",
  "width": 1920,
  "height": 1080,
  "variant": "original",
  "caption": "",
  "sha256": "...",
  "metadata": {}
}
```

### 4.4 shot 字段

```json
{
  "stable_id": "shot:board-1:1",
  "shot_number": 1,
  "frame_stable_id": "frame:board-1:0001:original",
  "duration_seconds": 2.5,
  "visual": "",
  "content": "",
  "shot_size": "",
  "camera_movement": "",
  "camera_notes": "",
  "composition": "",
  "camera_angle": "",
  "lighting_mood": "",
  "color_palette": "",
  "visual_focus": "",
  "transition_hint": "",
  "dialogue": "",
  "sound": "",
  "prompt": ""
}
```

## 5. 标准包结构

```text
manifest.json
images/original/001.png
images/expanded-16x9/001.png
images/line-art/001.png
images/replicated/001.png
preview/contact-sheet.png
checksums.json
```

导入器必须：

- 拒绝绝对路径和 `..` 穿越；
- 限制文件数量、单文件大小和总解压大小；
- 只接受 png/jpg/jpeg/webp；
- 校验 manifest 中的 SHA-256；
- 临时目录导入失败时自动清理；
- 成功后把文件复制到目标应用自己的媒体目录。

## 6. SHIYIN-AI 落地映射

### 图片节点

```js
{
  id,
  type: "image",
  mediaKind: "image",
  url,
  name,
  bridgeId,
  bridgeFrameId,
  bridgeShotId,
  shotNumber,
  timestampMs,
  sourceApp: "filmstoryboard",
  sourceProjectId,
  sourceBoardId,
  sourceScriptId,
  bridgeVariant
}
```

### GROUP

```js
{
  id,
  type: "group",
  items: [],
  bridgeId,
  bridgeDirection: "film-to-shiyin",
  sourceBoardId,
  sourceScriptId,
  selectedVariant,
  frameCount
}
```

### Prompt 节点

每个镜头可创建一个 Prompt 节点，文本由 `visual/content/composition/dialogue/sound/prompt` 拼接而成；Prompt 节点记录 `bridgeShotId`，图片节点与 Prompt 节点建立派生连接。

## 7. filmstoryboard 落地映射

film 导入 SHIYIN 结果时使用现有 `StoryboardExternalImage` 和 `createOrReplaceBoardFromExternalImages`，不直接写库。拍摄脚本通过 `sourceStoryboardAssetId` 关联镜头，更新时默认保留导演手工编辑字段。

## 8. 冲突策略

| 场景 | 策略 |
|---|---|
| 同一 bridge_id 重复导入 | 更新同一目标，不重复创建 |
| 同一帧换变体 | 保留 stable_id，只更新路径和 variant |
| film 手工改文字、SHIYIN 回传新图片 | 保留 film 手工文字，更新图片 |
| SHIYIN 删除帧 | 标记为未关联，不立即删除 film 脚本镜头 |
| 文件校验失败 | 整包失败，不写入半成品 |
| Loopback 不可用 | 自动回退标准包 |

## 9. 模块与文件清单

### SHIYIN-AI

- `canvas_core/bridge_manifest.py`
- `canvas_core/bridge_package.py`
- `main.py`：桥接包导入/导出 API
- `static/js/canvas.js`：发送/导入 UI、GROUP 映射
- `static/canvas.html`：桥接弹窗
- `tests/test_bridge_manifest.py`
- `tests/test_bridge_package.py`
- `tests/test_canvas_bridge_api.py`

### filmstoryboard

- `lib/features/bridge/domain/bridge_manifest.dart`
- `lib/features/bridge/data/bridge_package_service.dart`
- `lib/features/bridge/application/bridge_controller.dart`
- `lib/features/bridge/presentation/bridge_import_dialog.dart`
- `lib/features/storyboard/presentation/storyboard_page.dart`：发送入口
- `lib/features/shooting_script/presentation/shooting_script_page.dart`：发送入口
- `test/features/bridge/bridge_manifest_test.dart`
- `test/features/bridge/bridge_package_service_test.dart`

## 10. 任务拆分和验收标准

### 模块 1：协议核心

- 能解析 v1/v2 manifest；
- 能拒绝缺字段、错误类型、路径穿越和超限包；
- 能生成确定性 bridge/frame/shot ID；
- Python 和 Dart 的字段命名一致。

### 模块 2：film → SHIYIN

- film 能导出当前故事板为标准包；
- SHIYIN 能导入并创建图片 GROUP；
- 镜头 Prompt 节点可选创建；
- 重复导入不会重复创建节点。

### 模块 3：SHIYIN → film

- 原始/扩展/线稿 GROUP 可导出；
- film 能更新同一故事板；
- 拍摄脚本图片同步但文字不被覆盖。

### 模块 4：Loopback

- 本机自动发现、一次性 token、上传、回执、失败回退完整可用。

### 总体验收

- 10 帧、100 帧、混合变体、重复导入、删除帧、损坏包、Loopback 关闭等场景通过；
- 两边全量测试通过；
- 真实桌面环境手工走通一次双向流程。

## 11. 当前开发顺序

本轮先完成模块 1：Python manifest/zip 核心和测试；随后再进入 film 导出和 SHIYIN 导入，避免 UI 先绑定未稳定的数据结构。
