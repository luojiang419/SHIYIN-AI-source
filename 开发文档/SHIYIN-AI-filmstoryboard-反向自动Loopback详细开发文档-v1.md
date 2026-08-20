# SHIYIN-AI ↔ filmstoryboard 反向自动 Loopback 开发文档 v1

## 1. 目标

用户在 SHIYIN-AI 无限画布中点击“发送到 filmstoryboard”后，若 filmstoryboard 的故事板页面正在运行，则自动把桥接包发送到本机接收器并完成帧级增量同步；若接收器不可用，则保留原有下载桥接包流程，不丢失用户操作结果。

## 2. 端到端流程

1. SHIYIN-AI 调用 `/api/canvas-bridges/film/export` 生成 `.filmbridge.zip`。
2. 前端探测 `http://127.0.0.1:3210/api/canvas-bridges/shiyin/capabilities`。
3. 能力声明匹配 `app=filmstoryboard`、`automatic_receive=true` 后，读取导出包并以原始 ZIP 字节 POST 到 `/api/canvas-bridges/shiyin/receive`。
4. filmstoryboard 接收器将 ZIP 写入临时目录，调用既有 `BridgePackageService.importShiyinToFilm` 与 `createOrReplaceBoardFromExternalImages`，按 `external-cut:<stableId>` 选择性新增、更新、删除资源。
5. 同步成功后返回 `board_id`、`frame_count`、`sync_mode`、`sync_stats`；临时包随后删除。
6. 探测失败、CORS/网络失败或业务返回非 2xx 时，SHIYIN-AI 自动下载同一个桥接包作为离线兜底。

## 3. 协议

### 能力探测

`GET /api/canvas-bridges/shiyin/capabilities`

```json
{
  "app": "filmstoryboard",
  "schema": "shiyin-film-bridge",
  "schema_version": 2,
  "automatic_receive": true,
  "incremental_sync": true,
  "port": 3210
}
```

### 接收

`POST /api/canvas-bridges/shiyin/receive?canvas_title=...`

- `Content-Type: application/zip`
- Body 为完整桥接 ZIP，不使用 multipart，避免浏览器端 FormData 边界和额外解析差异。
- 成功响应至少包含 `ok=true`、`board_id`、`frame_count`；同步字段透传 `sync_mode` 和 `sync_stats`。
- 允许 `OPTIONS` 预检并返回 `Access-Control-Allow-Origin: *`、`Access-Control-Allow-Headers: Content-Type`。

## 4. 生命周期与容错

- 接收器在 filmstoryboard `StoryboardPage` 挂载时启动，在页面销毁时停止。
- 端口占用、Provider 尚未初始化或启动异常不会阻塞故事板页面；手工文件导入仍可用。
- 临时 ZIP 在导入回调结束后删除；导入失败也执行清理。
- 当前版本的自动接收前提是 filmstoryboard 故事板页面已打开。后续可将接收器上移到应用级 Provider，使其覆盖其它页面。

## 5. 增量一致性

- 同一 `bridge_id` 与帧 `stable_id` 复用现有记录和节点。
- 内容 SHA-256 未变的帧不写数据库、不替换媒体、不重置排版属性。
- 内容变化的帧原位更新资源；新增/删除帧只影响对应记录。
- SHIYIN-AI 继续使用内容寻址媒体路径，避免浏览器缓存旧图。

## 6. 验收标准

- film 页面打开：点击发送后无需手工下载/选择文件，故事板自动更新。
- 修改单个分镜图后再次发送：仅该帧更新，其他帧 ID、位置和翻转属性保持。
- film 页面关闭或端口不可用：SHIYIN-AI 自动下载桥接包，并提示“film 未运行”。
- 接收器预检、原始 ZIP 接收、临时文件清理和前端契约测试通过。
