# 视频播放与目录定位必须区分虚拟 URL 和真实文件路径

## 现象

作品管理或画布资产页面中的 MP4 显示损坏图标；“打开目录/打开链接”可能打开后端虚拟 URL、浏览器页面，或因同名文件猜测而定位到错误位置。

## 原因

桌面 WebView 的页面 origin 不保证等于后端 HTTP origin。直接把 `/assets/*`、`/output/*` 交给视频元素时，可能请求到不存在的虚拟资源。目录打开则必须先将媒体 URL 解析为当前账号下的真实路径，不能仅凭 basename 在本地搜索远程 CDN 文件。

## 处理规则

1. 视频（本地和远程）统一使用 `/api/download-output?inline=1`，保留 `Content-Type` 和 Range。
2. 目录打开统一走后端真实路径解析，再调用 Explorer `select`；远程 URL 没有本地文件时返回 404，不得猜测同名文件。
3. 前端修改脚本必须递增 query 版本，避免 WebView2 持久缓存继续使用旧代码。
4. 用真实 MP4 smoke 检查 `readyState=4`、服务端 `206 Partial Content` 和 reveal API `200`，不能只做字符串契约测试。

## 本次验证

临时账号数据 + 本地后端 + 浏览器验证通过；临时数据已清理。

## 追加经验（1.0.294）

旧作品记录可能把视频后缀只保存在 `name` 或 `original_name`，而 `url` 没有扩展名、`kind/media_type` 仍是历史任务类型。若前端只看 URL，就会把 MP4 错误渲染成 `<img>`，表现为文件名旁的破图图标。后端 `work_media_type`、画布资产 `canvas_asset_kind` 与两个前端页面必须共享同一套 `url/name/original_name/filename` 扩展名兜底；升级时同步递增版本号，强制清掉 WebView 旧脚本缓存。

## 追加经验（1.0.295）

`hidden` 不是绝对可靠的视觉隐藏方式：如果组件样式对元素写了更高优先级的 `display:block`（本案为 `.studio-preview-img` 的图片缩放样式），浏览器 UA 的 `[hidden] { display:none }` 会被覆盖。双层预览（图片和视频共用容器）必须在容器级补充 `.preview-frame > [hidden] { display:none !important; }`，并用浏览器实际计算样式和矩形尺寸确认隐藏元素为 `display:none`、宽高为 0；不能只看 `hidden=true`。
