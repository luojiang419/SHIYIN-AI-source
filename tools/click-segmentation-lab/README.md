# SHIYIN 点击抠图技术验证工具

独立的点击式局部元素分割实验工具。它不会修改主应用数据，后续可将 `segmenter.py` 和前端点选逻辑集成进画布。

## 启动

在仓库根目录执行：

```powershell
python tools/click-segmentation-lab/server.py
```

浏览器打开 `http://127.0.0.1:8791`。首次分割会从 Hugging Face 下载 `facebook/sam-vit-base`，约 375 MB；下载完成后使用本地缓存。可通过环境变量 `SHIYIN_SEGMENT_MODEL` 指定兼容的 SAM 模型目录或模型 ID。

## 操作

- 左键：选择新元素，并清除上一组提示点。
- `Ctrl+左键`：增加需要保留的区域。
- `Alt+左键`：排除误选区域。
- `Ctrl+Z`：撤销最后一个提示点。
- 导出透明 PNG：保留原图分辨率与软 alpha 边缘。
- 导出蒙版：输出与原图同尺寸的 8 位灰度 PNG。

模型输出只是候选蒙版。工具会按正提示点约束连通区域、填补小孔，并在原图尺寸上完成阈值和羽化，避免缩放预览损失原始像素。

