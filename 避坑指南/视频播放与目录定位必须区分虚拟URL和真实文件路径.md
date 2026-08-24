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

## 追加经验（1.0.296）

全屏播放的空格控制不能依赖浏览器默认快捷键：焦点可能停留在全屏按钮或全屏容器，默认行为还可能滚动页面。应在文档级监听 `keydown`，仅当 `document.fullscreenElement` 是作品预览容器/视频时处理 `Space`，调用 `preventDefault()` 后显式执行 `play()`/`pause()`；同时过滤 `repeat` 与组合键，避免长按造成状态抖动。

## 追加经验（1.0.297）

如果监听器只在 `document.fullscreenElement` 成立时处理空格，非全屏时焦点落在“全屏”按钮会让浏览器先执行按钮的 Space 激活行为，导致第一次空格进入全屏。预览视频对话框打开且视频可见时就应拦截空格；只有输入框、文本域、下拉框和可编辑区域放行默认行为。

## 追加经验（1.0.298）

作品批量删除必须把“永久删除文件”和“移到回收站”拆成不同后端动作，不能只在前端隐藏卡片。批量永久删除需校验本地路径、同步移除历史/画布引用和媒体索引；回收站只更新 `trashed` 元数据，保证恢复时文件仍存在。Shift 框选要在虚拟列表当前已渲染卡片上计算矩形相交，并在拖选期间阻止卡片预览点击。

## 追加经验（1.0.299）

桌面 WebView 中 Shift 可能在 iframe、系统窗口切换或自动化鼠标拖拽期间无法稳定传递给页面，不能把 Shift 作为唯一的多选入口。作品管理应提供显式多选开关，并在卡片上提供真实 checkbox 作为可见兜底；开启多选后点击和拖拽均直接进入选择逻辑，同时保留 document 级 `keydown`/`keyup` 状态监听和事件自身的 `shiftKey` 判断。复选框标签必须从框选起点过滤，避免点击复选框被拖拽选择逻辑吞掉。

实机回归时，后端 stderr 里的 `ConnectionResetError [WinError 10054]` 来自 WebView/浏览器关闭或取消请求时的连接断开，不代表视频流或作品接口失败；判断功能是否异常应结合页面交互结果和接口状态，不能把这类断开回调误判成播放器缺少组件。

## 追加经验（1.0.300）

虚拟列表的选择状态不应通过频繁 `innerHTML` 全量重建来同步，否则每次鼠标移动都会重新创建图片/视频元素并绑定事件，表现为拖拽卡顿、视频闪烁甚至 WebView 黑屏。应把“数据列表重建”和“选中状态变化”分离：选择只修改已有卡片的 class、ARIA 和 checkbox，并用 `requestAnimationFrame` 合帧。批量删除也不能在请求开始时先清空列表；应保留界面、锁定操作按钮，成功后再按 id 增量移除，失败则恢复可操作状态。

## 追加经验（1.0.301）

Windows Explorer 会对 `subprocess.Popen` 的参数列表再次进行命令行解析。将 `/select,"C:\\Program Files\\..."` 作为带内层引号的列表参数传入时，Explorer 可能静默解析失败并打开默认“文档”目录。

目录定位必须在已解析出真实磁盘文件后，传入完整命令行字符串 `"explorer.exe" /select,"C:\\真实路径\\文件"`，并通过 Shell.Application 实测最终 Explorer 的 `LocationURL`；不能只断言 API 返回路径。
