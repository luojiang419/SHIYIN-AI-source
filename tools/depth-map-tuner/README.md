# SHIYIN 深度图调参器

这是一个与 SHIYIN AI 主应用业务代码隔离的 Tauri 2 桌面工具。它直接复用主应用已经安装的 `person-depth` 组件，不会复制、下载或重新部署模型。

## 启动

在仓库根目录执行：

```powershell
Set-Location tools/depth-map-tuner
npm run dev
```

构建独立可执行文件：

```powershell
npm run build
```

产物位于 `tools/depth-map-tuner/src-tauri/target/release/SHIYIN-Depth-Tuner.exe`。

## 使用

1. 工具会自动寻找仓库或已安装 SHIYIN AI 的 `data/system/components/person-depth`。
2. 若未自动找到，点击顶部“重新定位”，选择 `person-depth` 目录或其当前安装目录。
3. 在左上区域点击或拖入图片。首次处理会加载共享模型，耗时取决于显卡和图片尺寸。
4. 在底部调整参数，右上预览会即时更新；调参不会重复执行模型推理。
5. 点击右下“导出深度图”保存完整分辨率 PNG，或“导出参数配置”保存 JSON。

## 隔离边界

- 只读取共享组件目录与输入图片。
- 只向本工具自己的应用配置目录写入“共享组件位置”偏好。
- 只在用户通过保存对话框选定的位置写入 PNG/JSON。
- 不修改 `main.py`、`canvas_core/`、`static/`、主 `src-tauri/` 或模型文件。

Depth Anything V2 Large 使用 `CC-BY-NC-4.0`，当前共享候选组件仅限个人非商业用途；BiRefNet 使用 MIT。
