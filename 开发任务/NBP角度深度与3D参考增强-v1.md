# NBP角度深度与3D参考增强-v1

状态：已完成（首版）
当前阶段：5/5
最后更新：2026-08-30

## 当前状态

已完成后端深度模型管理、CPU ONNX 推理、深度接口和角度节点几何参考 UI。角度节点现在支持自动生成 Depth Anything V2 深度图，或从相连的 3D 导演台节点读取最近一次导出截图，并按原图→几何参考→上一轮结果顺序传给 Nano Banana Pro。新方案不使用 LoRA。当前尚未实现从 directorProject 在角度节点内按任意相机自动重渲染，仍复用导演台已导出的 2D 截图。

## 下一步

1. 完成静态检查、相关测试和 Git diff 审核。
2. 更新任务文档和调研报告。
3. 提交并推送独立模块。
4. 后续评估 directorProject 活动机位自动捕获协议。

## 当前 TODO

- [x] 深度模型管理器与 Depth Anything V2 Small FP16 ONNX 推理
- [x] `/api/depth/status` 与 `/api/depth/estimate`
- [x] 角度节点深度参考 UI 与节点字段
- [x] 3D 导演台截图作为结构参考
- [x] 前后端测试与文档
- [ ] directorProject 任意活动机位自动重渲染（后续优化）

## 最近验证状态

- 静态检查：`py_compile`、3 个 `node --check` 已通过
- 单元测试：`pytest -q tests/test_depth_reference.py tests/test_nbp_angle_mode.py`，7 passed
- 运行测试：已下载并校验约 50MB 权重，真实深度推理输出 1792×2400；imgx 深度参考角度测试 4/4 成功
- 最近 Git commit：`ef6fde1 feat: 增加角度节点深度与3D几何参考`
- Git push：已推送到 `origin/feat/storyboard-merge-node`

---

## 任务目标

实现不依赖 LoRA 的几何参考增强路径：角度节点可自动从原图生成深度图，也可复用 3D 导演台的三维人物/场景导出截图，将其作为结构参考传给 Nano Banana Pro，用于更稳定地控制左右角度、透视和遮挡关系。

## 当前项目现状

- 后端已有 DWPose ONNX 模型管理和 CPU 推理，可作为下载、状态和错误处理模式。
- 前端角度节点已有语义机位字段与多参考图请求，但没有深度/3D 几何字段。
- 3D 导演台通过 iframe 保存项目并维护 `directorCaptures`，截图本身是可复用的图像资产。
- Nano Banana Pro 接收额外参考图时属于软条件，不能把灰度深度图当作原生 ControlNet 深度通道，因此必须在提示词中明确参考图角色。

## 技术方案

- 首选 Depth Anything V2 Small FP16 ONNX：约 50 MB、CPU 友好、Apache-2.0 许可，首请求自动下载，输入按比例缩放到 518 短边，输出相对深度灰度 PNG。
- 新增 `DepthModelManager` 和 `DepthInference`，模型存储在账号系统模型目录的 `depth` 子目录。
- 新增深度状态、管理员重试和估计接口；接口返回 PNG，前端再上传到现有媒体服务获得持久 URL。
- 角度节点新增 `angleGeometryMode: none|depth|director3d`、`angleDepthUrl`、`angleDirectorCaptureUrl` 等字段。
- 生成时参考顺序固定为：原图（身份/外观）→ 深度图或导演台截图（几何）→ 上一轮结果（连续性）。
- 3D 导演台先复用最近导出截图，避免直接修改压缩后的 iframe bundle；后续可增加父子窗口的“按活动机位自动捕获”消息协议。

## 验收标准

1. 首次调用深度接口能自动准备模型并返回与原图尺寸一致的灰度 PNG。
2. 角度节点可切换深度/3D 几何参考并显示准备状态，失败时不阻塞普通角度生成。
3. 角度请求在启用几何参考时确实携带第二张参考图，并保留上一轮结果的兼容行为。
4. 3D 导演台最近一次截图可作为角度节点的几何参考，不需要 LoRA。
5. 静态检查、相关单元测试和前端语法检查通过，任务文档记录已知限制。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

新会话启动：阅读本任务文档、检查 Git 状态，从“下一步”继续。

## 已完成内容

- 新增 `canvas_core/depth_models.py`：Depth Anything V2 Small FP16 ONNX 权重下载、SHA-256/大小校验、状态与重试。
- 新增 `canvas_core/depth_inference.py`：CPUExecutionProvider 推理和同尺寸灰度深度图输出。
- `main.py` 新增深度状态、管理员重试和 `/api/depth/estimate` 接口，启动时可按环境变量自动补齐模型。
- 角度节点新增几何参考模式、深度生成按钮、director3d 最近截图引用和几何参考提示词；经典/智能画布均按固定顺序提交参考图。
- 新增 `tests/test_depth_reference.py` 并更新调研报告。

## 已知问题

- NBP 接收深度图和 3D 截图仍是软条件，不是 ControlNet/原生深度通道。
- 导演台复用的是最近导出截图，尚未做到根据 `directorProject` 在角度节点内自动按任意相机重渲染。
- 首次下载需要网络；未下载完成时深度按钮返回 503，普通语义角度仍可继续使用。

## 开发日志

- 2026-08-30：完成 Depth Anything V2 Small FP16 ONNX 管理、深度接口、角度节点几何参考模式、3D 导演台截图引用和测试；提交 `ef6fde1` 并推送。

## 当前关键修改

- `main.py`、`canvas_core/depth_models.py`、`canvas_core/depth_inference.py`：新增深度模型生命周期和 CPU 推理。
- `static/js/canvas-special-nodes.js`：新增几何参考选择、深度生成和导演台截图同步。
- `static/js/canvas.js`、`static/js/smart-canvas.js`：固定多参考图顺序并避免导演台截图抢占原图主输入。
- `static/canvas.html`、`static/smart-canvas.html`、CSS：更新缓存版本和节点样式。

## 追加验证

- 2026-08-30：使用 `D:\data\图片\20260820-195103.png` 和真实 Depth Anything V2 深度图进行左 40°、右 40°、背面 180°、顶部约 35° 四角度 imgx 测试，3:4、2K、4 张，4/4 成功。详细结果见 `开发文档/NBP深度参考四角度测试报告-20260830.md`。左侧、背面、顶部命中明显，右侧 40° 偏正面，验证深度图是软几何约束。

## 第二轮精度升级

- 2026-08-30：将 MiDaS Small 替换为 Depth Anything V2 Small FP16 ONNX，增加外部权重文件校验；按 `keep_aspect_ratio` 等比例缩放，真实复测右侧 40°、背面和顶部视角。右侧小角度明显改善，3D 导演台仍按计划留到下一阶段。

- 2026-08-30：修复“人物扭头代替相机移动”问题，加入 CAMERA-ONLY/RIGID SUBJECT LOCK，并完成左右 40°复测。
