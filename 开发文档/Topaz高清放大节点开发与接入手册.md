# Topaz 高清放大节点开发与接入手册

> 适用源码版本：SHIYIN AI `1.0.176`<br>
> 功能提交范围：`672bb14`（接入前基线）至 `7d52a32`（当前稳定实现）<br>
> 目标平台：Windows x64<br>
> 外部软件：Topaz Video AI（需由使用者合法安装和授权）

## 1. 文档目的

本文记录 Topaz 高清放大节点从能力验证、后端适配、画布接入、任务管理、参数设计到安装包集成的完整实现，供其他开发者：

- 在 SHIYIN AI 中继续维护或扩展该节点；
- 将节点迁移到另一套无限画布或本地视频应用；
- 快速定位 Topaz、FFmpeg、NVENC、弹窗或任务恢复问题；
- 使用随附的源码和 Git 补丁复现本功能。

本文所说的“Topaz 插件”不是 Premiere Pro 或 After Effects 的宿主插件。当前实现直接调用 Topaz Video AI 安装目录中自带、且含 `tvai_up` 滤镜的 `ffmpeg.exe`/`ffprobe.exe`。这种方式更适合独立桌面应用，也不依赖 PR/AE 进程。

## 2. 交付边界与运行结论

### 2.1 已实现

- 无限画布中的 `Topaz 高清放大` 节点；
- 节点正面只显示三项常用设置：AI 模型、输出尺寸、质量预设；
- 节点右下角“高级设置”弹窗，集中显示全部精细参数；
- 自动检测或手动选择 Topaz Video AI 安装目录；
- 校验 Topaz FFmpeg 的 Windows Authenticode 数字签名；
- 检测 `tvai_up` 滤镜与本机模型定义；
- 本地异步任务、进度轮询、取消、持久化和重启中断处理；
- 2×、4×、1080p、1440p、2160p 输出；
- H.264/H.265 NVENC 自动选择，支持超过 4096 像素的 8K/超宽输出；
- 音频 AAC、原流复制、移除三种策略；
- 节点输出继续连接 Output 或下游视频节点；
- 单节点运行与全画布级联运行；
- 单元测试、静态集成测试和安装包资源完整性检查。

### 2.2 不包含

- 不分发 Topaz 主程序、模型、许可证或任何 Topaz 二进制文件；
- 不绕过 Topaz 登录、授权或模型许可；
- 不加载 PR/AE 插件；
- 不支持未安装 Topaz 时使用普通系统 FFmpeg 替代；
- 当前编码器只开放 NVIDIA NVENC，不包含 CPU 编码或 AMD/Intel 硬件编码；
- 当前任务并发固定为 1，防止多个模型实例同时挤占显存。

### 2.3 Topaz 主程序是否需要运行

执行节点时不需要保持 Topaz Video AI 主界面运行。需要满足：

1. Topaz Video AI 已正常安装并完成合法授权；
2. 安装目录存在 `ffmpeg.exe` 与 `ffprobe.exe`；
3. Topaz 模型定义和模型数据可用；
4. 首次使用的模型若尚未下载，需要先在 Topaz 主程序中准备，或在高级设置中允许自动下载；
5. NVIDIA 驱动与 NVENC 可正常工作。

## 3. 技术选型与依赖

| 层级 | 使用内容 | 用途 |
| --- | --- | --- |
| 桌面运行环境 | Windows x64、Tauri 2 | 承载本地 Web UI 和 Python 服务 |
| 后端接口 | Python、FastAPI、Pydantic | 能力检测、参数校验、任务 API |
| 进程管理 | `asyncio.subprocess` | 无 Shell 启动 Topaz FFmpeg、读进度、取消进程 |
| Topaz 能力 | Topaz 自带 `ffmpeg.exe`、`ffprobe.exe`、`tvai_up` | 视频探测、AI 放大、编码 |
| 安全检测 | PowerShell `Get-AuthenticodeSignature` | 验证调用的是 Topaz Labs LLC 签名文件 |
| 模型发现 | Topaz 模型 JSON、`tvai.tz`、注册表与环境变量 | 动态生成可用模型列表 |
| 前端 | 原生 JavaScript、HTML、CSS、Lucide | 节点 UI、模态框、进度和任务控制 |
| 数据层 | 项目现有任务数据库接口 | 持久化任务，按账号隔离 |
| 测试 | Python `unittest` | 适配器、UI 合同、设置和任务生命周期测试 |

没有新增 Python 第三方依赖。后端复用了项目已有 FastAPI、Pydantic、数据库和账号上下文。

## 4. 总体架构与调用链

```text
视频节点/本地视频素材
        │ 画布连接，取第一个视频引用
        ▼
canvas-topaz-node.js
  ├─ GET  /api/topaz-video/capabilities
  ├─ POST /api/topaz-video/tasks
  ├─ GET  /api/topaz-video/tasks/{id}  每秒轮询
  └─ POST /api/topaz-video/tasks/{id}/cancel
        │
        ▼
main.py Topaz 任务控制器
  ├─ 账号隔离、内部媒体 URL 校验
  ├─ 数据库持久化、状态机、并发限制
  ├─ ffprobe 读取输入宽高与时长
  ├─ 临时输出文件 + 成功后原子替换
  └─ stdout 读取 FFmpeg progress，stderr 保留末尾诊断
        │
        ▼
canvas_core/topaz_video.py
  ├─ 安装目录/模型目录发现
  ├─ Authenticode 与 tvai_up 能力校验
  ├─ 参数验证、尺寸计算、编码器选择
  └─ 生成参数数组
        │
        ▼
Topaz 安装目录/ffmpeg.exe -vf tvai_up=...
        │
        ▼
data/.../output/topaz_xxxxxxxxxxxx.mp4
        │
        └─ 注册为内部视频并回填画布节点输出
```

## 5. 文件与模块清单

### 5.1 核心新增文件

| 文件 | 责任 |
| --- | --- |
| `canvas_core/topaz_video.py` | Topaz 安装与模型发现、签名/滤镜检测、参数模型、命令构造、探测与进度解析 |
| `static/js/canvas-topaz-node.js` | 节点状态、三项常用设置、高级弹窗、任务创建/轮询/取消/恢复 |
| `static/css/canvas-topaz-node.css` | 节点、进度条、高级弹窗样式 |
| `tests/test_topaz_video.py` | 后端适配器和 FFmpeg 命令测试 |
| `tests/test_topaz_video_canvas.py` | 节点显示、模态框、生命周期和画布接线合同测试 |
| `tests/test_topaz_video_settings.py` | 软件设置页接入测试 |
| `tests/test_topaz_video_tasks.py` | 任务持久化、路径脱敏、创建、取消与进程回收测试 |
| `tools/stamp-web-cache-version.mjs` | 安装包暂存目录中的 Web 资源版本戳 |

### 5.2 被改造的宿主文件

| 文件 | 改造内容 |
| --- | --- |
| `main.py` | 导入适配器；增加请求模型、任务容器、四个任务 API、运行/取消/恢复逻辑；扩展应用设置 API |
| `canvas_core/app_config.py` | 持久化 `topaz_video_install_dir` |
| `static/canvas.html` | 加载节点 CSS/JS；在工具栏和右键菜单添加入口 |
| `static/js/canvas.js` | 节点创建分发、渲染、端口、尺寸、级联执行、复制/删除、输出媒体识别与连接校验 |
| `static/app-settings.html` | 增加 Topaz 安装路径与健康状态区 |
| `static/js/app-settings.js` | 选择、保存、重置目录并重新检测能力 |
| `static/css/app-settings.css` | Topaz 设置卡片布局 |
| `tools/build-installer.ps1` | 构建时检查 Topaz 节点资源和缓存版本是否进入安装包 |
| `VERSION`、`package.json`、`package-lock.json`、`src-tauri/*` | 应用版本同步 |
| `static/update-notes.json`、`tests/test_desktop_updater_contract.py` | 发布说明和更新器合同 |
| `tests/test_app_config.py` | Topaz 路径配置测试 |

## 6. Topaz 安装与能力发现

### 6.1 安装目录查找顺序

`candidate_topaz_install_dirs()` 按以下来源生成候选项并去重：

1. 软件设置中的 `topaz_video_install_dir`；
2. 环境变量 `TOPAZ_VIDEO_AI_DIR`；
3. `%ProgramW6432%\Topaz Labs LLC\Topaz Video AI`；
4. `%ProgramFiles%\Topaz Labs LLC\Topaz Video AI`；
5. Windows 各盘符下的 `Program Files\Topaz Labs LLC\Topaz Video AI`。

传入值可以是安装目录，也可以直接指向 `ffmpeg.exe` 或 `Topaz Video AI.exe`。候选目录必须同时包含 `ffmpeg.exe` 和 `ffprobe.exe`。

当前用户安装路径示例：

```text
D:\Program Files\Topaz Labs LLC\Topaz Video AI
```

### 6.2 模型目录发现

- 模型定义目录优先读取 `TVAI_MODEL_DIR`；
- 默认尝试 `%PROGRAMDATA%\Topaz Labs LLC\Topaz Video AI\models`；
- 目录必须包含 `tvai.tz`；
- 模型数据目录优先读取 `TVAI_MODEL_DATA_DIR`；
- 其次读取注册表 `HKCU\Software\Topaz Labs LLC\Topaz Video AI` 的 `veaiDataFolder`；
- 最后回退到模型定义目录。

启动子进程时只在子进程环境中设置 `TVAI_MODEL_DIR` 和 `TVAI_MODEL_DATA_DIR`，不会修改当前 Python 进程或系统环境变量。

### 6.3 安全与可用性门槛

`TopazInstallation.ready` 只有在下列条件全部满足时才为真：

- 安装目录、FFmpeg、FFprobe 均存在；
- 模型定义目录和模型数据目录存在；
- `ffmpeg.exe` 的签名状态为 `Valid`；
- 签名者包含 `Topaz Labs LLC`；
- 执行 `ffmpeg.exe -hide_banner -filters` 能找到 `tvai_up`。

这是重要设计边界：普通系统 FFmpeg 即使可执行，也通常没有 Topaz 私有滤镜，不能作为替代品。

### 6.4 模型列表

从模型目录的 `*.json` 文件名提取模型 ID，只接受已知的视频增强模型前缀。当前包含 Proteus、Iris、Rhea、Artemis、Gaia、Theia、Dione、Nyx 等系列。默认模型按以下优先级选择：

```text
prob-4 → prob-3 → prob-2 → amq-13 → ahq-12 → 第一个可用模型
```

模型列表来自本机安装，不应在前端写死完整版本列表。

## 7. 节点 UI 与参数设计

### 7.1 节点正面三项常用设置

| 设置 | 可选值 | 默认值 | 说明 |
| --- | --- | --- | --- |
| AI 模型 | 能力接口返回的本机模型 | `prob-4` 或本机推荐模型 | 控制 Topaz 增强模型 |
| 输出尺寸 | `2x`、`4x`、`1080p`、`1440p`、`2160p` | `2x` | 倍率或目标短边 |
| 质量预设 | `high`、`balanced`、`compact` | `balanced` | 映射 NVENC 恒定 QP 18/23/28 |

节点正面必须保持只有这三项 `<select data-topaz-common>`。对应测试会验证数量，新增常用项时应同步产品要求和测试。

### 7.2 高级设置参数

| 前端键 | `tvai_up` 参数/后端用途 | 范围或选项 | 默认 | UI 步长 | 作用 |
| --- | --- | --- | --- | --- | --- |
| `preblur` | `preblur` | -1～1 | 0 | 0.05 | 反锯齿/去模糊控制 |
| `noise` | `noise` | -1～1 | 0 | 0.05 | 降噪强度 |
| `details` | `details` | -1～1 | 0 | 0.05 | 细节恢复 |
| `halo` | `halo` | -1～1 | 0 | 0.05 | 去光晕 |
| `blur` | `blur` | -1～1 | 0 | 0.05 | 锐化/模糊校正 |
| `compression` | `compression` | -1～1 | 0 | 0.05 | 压缩伪影修复 |
| `pre_noise` | `prenoise` | 0～0.1 | 0 | 0.005 | 模型前置噪声 |
| `estimate` | `estimate` | 0～100 | 0 | 1 | 自动分析帧数 |
| `blend` | `blend` | 0～1 | 0 | 0.05 | 原始细节混合比例 |
| `grain` | `grain` | 0～0.1 | 0 | 0.005 | 输出颗粒量 |
| `grain_size` | `gsize` | 0～5 | 0 | 0.1 | 颗粒尺寸 |
| `device` | `device` | `-2` 自动、`0` GPU 0、`-1` CPU | `-2` | 选择 | 计算设备 |
| `vram` | `vram` | 0.1～1 | 1 | 0.05 | 可用显存比例 |
| `instances` | `instances` | 0～3 | 0 | 1 | 模型并行实例 |
| `download_models` | `download` | 布尔 | true | 复选 | 允许下载缺失模型 |
| `color_correction` | `kcolor` | 布尔 | true | 复选 | 模型颜色校正 |
| `encoder` | 输出编码器 | `auto`、`h264_nvenc`、`hevc_nvenc` | `auto` | 选择 | 视频编码策略 |
| `audio_mode` | 音频策略 | `aac`、`copy`、`none` | `aac` | 选择 | 重编码、复制或移除音频 |
| `audio_bitrate_kbps` | `-b:a` | 64～512 kbps | 320 | 32 | AAC 码率 |

前端和后端都做范围校验。前端负责交互约束，Pydantic 和 `TopazUpscaleSettings.validated()` 负责最终安全边界，不能只依赖浏览器控件。

### 7.3 高级弹窗实现要点

- 点击节点右下角按钮调用 `openTopazAdvancedSettings(node.id)`；
- 弹窗根元素直接追加到 `document.body`，避免被画布节点的 `overflow`、缩放或层叠上下文裁切；
- 支持右上角关闭、完成按钮、点击遮罩和 `Escape`；
- 修改参数时直接写入当前节点的 `topazAdvanced` 并调用 `scheduleSave()`；
- 关闭时移除键盘事件监听，避免重复打开后监听器泄漏；
- 老节点若保存了旧默认 `h264_nvenc`，`topazEncoderPolicyVersion < 2` 时自动迁移为 `auto`。

## 8. 输出尺寸与编码策略

### 8.1 尺寸计算

- `2x`、`4x`：输入宽高分别乘以 2 或 4；
- `1080p`、`1440p`、`2160p`：将短边设为 1080、1440、2160，保持宽高比；
- 输出宽高向下取偶数，最低 16；
- 最大边不能超过 16384；
- 实际宽高在 ffprobe 完成后写入 `TopazUpscaleSettings.output_width/output_height`；
- 对固定分辨率目标，`tvai_up` 使用 `scale=0:w=...:h=...`。

### 8.2 质量映射

| 质量 | NVENC QP | 特征 |
| --- | --- | --- |
| `high` | 18 | 体积较大、质量较高 |
| `balanced` | 23 | 默认平衡 |
| `compact` | 28 | 体积较小 |

编码使用 `constqp`，不是目标码率模式。

### 8.3 自动编码器

`encoder=auto` 在输出最大边不超过 4096 时选择 `h264_nvenc`，超过 4096 时选择 `hevc_nvenc`。原因是部分消费级 NVIDIA GPU 的 H.264 NVENC 会直接拒绝宽度大于 4096 的视频，而 HEVC NVENC 可以处理常见 8K 输出。

用户显式选择 `h264_nvenc` 且输出最大边超过 4096 时，命令执行前直接返回中文错误，避免运行很久后才在编码阶段失败。

### 8.4 音频

- `aac`：默认，将可选音频流编码为 AAC，默认 320 kbps；
- `copy`：复制原音频流，速度快但源音频编码可能与 MP4 容器不兼容；
- `none`：添加 `-an`，不输出音频。

视频流固定映射 `0:v:0`，音频使用可选映射 `0:a?`，无音频输入不会报错。

## 9. FFmpeg 命令构造

命令由 `build_topaz_upscale_command()` 返回字符串数组，并由 `asyncio.create_subprocess_exec(*command)` 执行。禁止拼接 Shell 字符串。

命令结构示意：

```text
<Topaz>/ffmpeg.exe
  -hide_banner -nostdin -y
  -i <input>
  -map 0:v:0 -map 0:a?
  -vf tvai_up=model=prob-4:scale=2:preblur=0:...:kcolor=1
  -c:v h264_nvenc|hevc_nvenc ...
  -c:a aac -b:a 320k
  -map_metadata 0
  -movflags frag_keyframe+empty_moov+delay_moov+use_metadata_tags+write_colr
  -progress pipe:1 -nostats
  <temporary-output>
```

Topaz FFmpeg 运行目录设为 Topaz 安装目录，子进程环境注入模型路径。进度写 stdout，诊断信息写 stderr，两者必须并行消费，否则 stderr 管道写满可能阻塞子进程。

## 10. 后端 API 合同

### 10.1 `GET /api/topaz-video/capabilities`

返回安装状态、路径、版本、签名、滤镜、模型、尺寸选项、质量选项、高级默认值和最大并发数。

关键字段示例：

```json
{
  "installed": true,
  "ready": true,
  "install_dir": "D:\\Program Files\\Topaz Labs LLC\\Topaz Video AI",
  "signature_valid": true,
  "filter_available": true,
  "models": [{"id":"prob-4","name":"Proteus 4"}],
  "default_model": "prob-4",
  "targets": ["2x","4x","1080p","1440p","2160p"],
  "qualities": ["high","balanced","compact"],
  "advanced_defaults": {},
  "max_concurrency": 1
}
```

### 10.2 `POST /api/topaz-video/tasks`

请求示例：

```json
{
  "input_url": "/media/input/example.mp4",
  "model": "prob-4",
  "target": "2x",
  "quality": "balanced",
  "advanced": {
    "preblur": 0,
    "noise": 0,
    "details": 0,
    "halo": 0,
    "blur": 0,
    "compression": 0,
    "pre_noise": 0,
    "estimate": 0,
    "blend": 0,
    "grain": 0,
    "grain_size": 0,
    "device": "-2",
    "vram": 1,
    "instances": 0,
    "download_models": true,
    "color_correction": true,
    "encoder": "auto",
    "audio_mode": "aac",
    "audio_bitrate_kbps": 320
  },
  "canvas_id": "canvas-id",
  "node_id": "node-id"
}
```

接口只接受项目已登记的内部媒体 URL，并检查其路径存在且 MIME 类型为视频。外部 URL、任意本地路径和非视频文件会被拒绝。

### 10.3 查询与取消

- `GET /api/topaz-video/tasks?canvas_id=...&limit=100`：列出当前账号任务；
- `GET /api/topaz-video/tasks/{task_id}`：读取单个任务；
- `POST /api/topaz-video/tasks/{task_id}/cancel`：请求取消。

任务公开响应会删除所有以下划线开头的内部字段，例如 `_input_path`、`_output_path`、`_temp_path` 和 `_account_id`，防止本地路径泄漏到前端。

## 11. 任务状态机和持久化

```text
queued → probing → running → succeeded
   │         │         ├────→ failed
   │         │         ├────→ canceling → canceled
   │         │         └────→ interrupted（程序关闭/重启）
   └─────────┴───────────────→ canceled
```

- 活跃状态：`queued`、`probing`、`running`、`canceling`；
- 终态：`succeeded`、`failed`、`canceled`、`interrupted`；
- 内存最多保留 200 个任务；
- 通过现有数据库 `upsert_task/load_tasks/delete_task/save_tasks` 持久化；
- 按当前账号隔离；
- 进度变化最多约每秒持久化一次，减少数据库写入；
- 应用重启后不会盲目重跑本地任务，原活跃任务改为 `interrupted`，要求用户重新运行；
- `asyncio.Semaphore(1)` 限制同一进程只运行一个 Topaz 任务。

### 11.1 临时文件与原子完成

输出先写入：

```text
.<最终文件名>.topaz-part-<任务后8位>.mp4
```

只有 FFmpeg 返回 0 且文件存在、大小大于 0 时，才用 `os.replace()` 原子移动为最终文件。失败、取消和中断时，只允许删除输出根目录内且文件名含 `.topaz-part-` 的文件。

### 11.2 进程取消与回收

取消流程先 `terminate()`，等待最多 5 秒；仍未退出则 `kill()`，随后再次 `wait()` 回收句柄。stderr reader 也会等待或取消，防止 Windows 上残留 FFmpeg 进程锁住临时文件。

## 12. FFprobe 与进度解析

`probe_video()` 使用 Topaz 自带 ffprobe 读取：视频宽高、编码、像素格式、视频流时长与容器时长。若流级 `duration` 是 `N/A`，回退到 `format.duration`。

FFmpeg 使用 `-progress pipe:1` 输出键值块。解析规则：

- 优先 `out_time_us`，兼容 `out_time_ms`；
- `N/A`、空值、`NaN`、正负无穷或非法数字都作为未知值处理；
- 不允许直接 `int('N/A')`；
- `progress=end` 强制进度为 1；
- 同时记录 `frame`、`fps`、`speed`。

## 13. 前端画布接入细节

### 13.1 节点数据结构

核心字段：

```javascript
{
  id, type: 'topazVideo', x, y,
  model, target, quality,
  topazAdvanced: {...},
  topazEncoderPolicyVersion: 2,
  topazTaskId, topazLastTaskId, topazLoggedTaskId,
  topazProgress, topazSpeed, topazMessage,
  inputs: [], generatedOutputs: [],
  running, runStatus, runError
}
```

`normalizeTopazVideoNode()` 每次渲染或恢复时补齐默认字段，保证旧画布数据可以迁移。

### 13.2 宿主函数依赖

`canvas-topaz-node.js` 不是完全独立运行的组件，它依赖 `canvas.js` 提供的宿主能力，包括：

- 节点与画布：`nodes`、`canvas`、`addNode`、`uid`、`defaultPoint`；
- 保存与刷新：`scheduleSave`、`saveCanvas`、`refreshNodes`、`refreshRunNodes`；
- 连接解析：`orderedSources`、`generatorSources`、`videoRefsOnly`；
- 网络：`cascadeFetch`、`responseErrorMessage`、`sleep`；
- 输出：`outputForNode`、`appendOutputImagesWithoutDuplicates`、`mergeGeneratedOutputs`；
- 日志：`runSnapshot`、`addGenerationLog`；
- UI：`showErrorModal`、`escapeHtml`、`escapeAttr`、`canvasVideoPreviewHtml`；
- 级联：`ensureCascadeActive`、`cascadeTargetIdFromOptions`。

迁移到其他项目时，可以保留这些函数名并实现兼容层，或重写该文件的宿主调用。

### 13.3 画布生命周期改造点

`static/js/canvas.js` 中必须同时接入：

1. 新建节点分发与右键菜单；
2. 节点标题、状态徽章和主体渲染；
3. 输入/输出端口、节点默认尺寸；
4. 生成器类型、媒体输出类型集合；
5. 连接后刷新输入预览；
6. 单节点运行和全画布拓扑级联运行；
7. 删除节点时取消运行任务；
8. 复制节点时清理任务 ID 和运行状态；
9. 输出媒体类型标记为 `video`；
10. 只允许视频来源连接到 Topaz 节点，并保持循环检测。

仅添加菜单按钮而遗漏这些生命周期入口，会出现“能看到节点但不能运行、不能级联或输出无法继续连接”的半接入状态。

### 13.4 输入和输出行为

- 节点可以收到多个引用，但当前只处理第一个视频，并在 UI 中提示；
- 无输入时阻止运行；
- 任务成功后将返回视频合并到 `generatedOutputs`；
- 如果存在显式 Output 连接，将结果追加到 Output 节点；
- 级联运行时结果可以继续作为下游 Topaz 或其他视频消费者的输入。

## 14. 软件设置页接入

应用配置新增字段：

```json
{
  "topaz_video_install_dir": "D:\\Program Files\\Topaz Labs LLC\\Topaz Video AI"
}
```

设置页提供：

- 选择文件夹：Windows 原生 `FolderBrowserDialog`；
- 自动检测：保存空字符串，恢复多路径扫描；
- 重新检测：请求能力接口；
- 状态显示：可用性、模型数、版本、签名状态和详细错误。

保存自定义目录时后端要求绝对路径、目录存在、并包含 `ffmpeg.exe` 与 `ffprobe.exe`。完整签名、模型和滤镜检查由能力接口完成。

## 15. 从零开发过程回顾

1. 先验证 Topaz 安装目录中的 FFmpeg 是否暴露 `tvai_up`，确认独立调用可行；
2. 将安装发现、签名、模型、参数和命令封装进独立适配器，避免散落在 `main.py`；
3. 建立能力接口，让前端不猜测本机模型和安装状态；
4. 建立持久化异步任务，而不是让一次 HTTP 请求等待数分钟；
5. 使用临时文件和原子替换，防止半成品进入素材库；
6. 实现三项常用参数和 body 级高级弹窗；
7. 补齐画布端口、级联、输出、复制、删除和恢复；
8. 实机处理视频后修复 H.264 4096 限制，增加自动 HEVC 策略；
9. 再次实机处理后发现进度字段可能是 `N/A`，增加有限数解析；
10. 加入安装包资源检查，防止开发环境正常但发布包漏文件或缓存仍指向旧脚本。

## 16. 迁移到另一项目的接入步骤

### 16.1 推荐方式：应用补丁

源码包内的 `patches/topaz-node-feature.patch` 基于提交 `672bb14`。目标仓库与该基线相近时：

```powershell
git apply --check .\patches\topaz-node-feature.patch
git apply .\patches\topaz-node-feature.patch
```

先执行 `--check`。如果宿主文件已经演进，请使用下方手动方式，不要强行覆盖。

### 16.2 手动方式

1. 复制 `canvas_core/topaz_video.py`；
2. 将 `main.py` 中以 `TopazAdvancedSettingsRequest`、`TopazUpscaleTaskRequest`、`TOPAZ_VIDEO_*`、`current_topaz_installation`、`run_topaz_video_task` 和 `/api/topaz-video/*` 为锚点的代码合入；
3. 合入 `canvas_core/app_config.py` 的设置字段；
4. 复制节点 JS/CSS；
5. 在 `canvas.html` 加载 CSS、JS，并添加创建入口；必须先加载节点脚本，再加载调用它的 `canvas.js`；
6. 按“画布生命周期改造点”逐项合并 `canvas.js`；
7. 合入软件设置页三份文件；
8. 复制四个 Topaz 测试和相关配置测试；
9. 合入 Web 缓存戳与安装包完整性断言；
10. 在目标机器安装 Topaz，调用能力接口验证 `ready=true`；
11. 用短视频做 2×，再用会超过 4096 像素的输出验证自动 HEVC；
12. 测试取消、关闭应用再启动、无音频和异常输入。

### 16.3 迁移时不要覆盖的内容

- 不要把源码包中的 `main.py` 直接覆盖到已演进的宿主项目；它作为完整参考文件提供，应按锚点合并；
- 不要复制 Topaz 二进制或模型进自己的安装包；
- 不要把本机绝对路径写死在源码；
- 不要把 `_input_path` 等内部字段返回给浏览器；
- 不要把用户视频或生成结果放进源码包。

## 17. 测试与验收

### 17.1 自动测试

在项目根目录运行：

```powershell
python -m unittest tests.test_topaz_video tests.test_topaz_video_canvas tests.test_topaz_video_settings tests.test_topaz_video_tasks
python -m unittest tests.test_app_config tests.test_desktop_updater_contract
python -m unittest discover -s tests
```

当前稳定版本全量结果为 445 项测试通过，另有 38 个子测试通过。

### 17.2 能力验收

1. 打开软件设置，选择 Topaz 安装目录；
2. 确认运行状态“可用”、签名有效、模型数大于 0；
3. 请求 `GET /api/topaz-video/capabilities`，确认 `ready=true`；
4. 打开无限画布，工具栏或右键菜单能看到 `Topaz 高清放大`；
5. 节点正面只有三个常用选项；
6. 点击高级设置能看到独立弹窗，四种关闭方式均有效；
7. 连接视频，运行后能看到进度、速度、取消按钮；
8. 成功输出视频，尺寸和音频符合设置；
9. 输出能连接 Output 或后续视频节点；
10. 8K/超宽任务在自动模式下使用 `hevc_nvenc`。

### 17.3 已完成的实机样例

- 输入：1056×608、约 4.458 秒；
- 模型：`prob-4`；
- 目标：2×；
- 输出：2112×1216、约 4.458 秒；
- FFmpeg 返回码：0；
- 进度块：13 个；
- 验证了 `out_time_us=N/A` 不再导致任务失败。

## 18. 已踩坑与处理方式

### 18.1 `No accelerated colorspace conversion found`

这是 swscaler 在 `yuv420p → rgb48le` 转换时没有加速路径的警告，不等于任务失败。Topaz 模型通常需要高位深 RGB 中间格式。处理方式：保留在 stderr 供诊断，但向用户展示错误时过滤重复警告，最终以 FFmpeg 返回码和输出文件为准。

### 18.2 `Width 7680 exceeds 4096` / `No capable devices found`

根因通常不是 Topaz 模型，而是 H.264 NVENC 的分辨率限制。处理方式：自动编码器在最大边超过 4096 时切到 HEVC；显式选择 H.264 时提前拒绝并给出操作提示。

### 18.3 `invalid literal for int() with base 10: 'N/A'`

Topaz FFmpeg 的 `-progress` 在模型预热或尚未输出帧时可能返回：

```text
out_time=N/A
out_time_ms=N/A
out_time_us=N/A
```

不能直接转换为整数。当前统一用 `_finite_float()`、`_finite_int()` 兼容未知值、NaN 和无穷值。

### 18.4 高级设置点了没反应或被遮挡

把弹窗放在节点内部会受到画布缩放、拖动、`overflow` 和层叠上下文影响。当前弹窗挂到 `document.body`，使用独立遮罩和 z-index，并停止按钮事件冒泡。

### 18.5 开发环境能看到，安装版看不到

常见原因是安装包漏复制新增 JS/CSS，或 HTML 缓存参数仍是旧版本。构建流程会统一盖 Web 缓存版本，并断言暂存目录包含 Topaz 脚本、菜单入口和正确版本戳。

### 18.6 取消后文件仍被占用

仅调用 `terminate()` 不够，必须等待进程退出；超时后 `kill()`，再 `wait()`，最后清理 stderr reader 和临时文件。

## 19. 安全与隐私检查表

- [ ] 仅运行 Topaz Labs LLC 签名有效的 FFmpeg；
- [ ] 所有子进程使用参数数组，未启用 Shell；
- [ ] 输入只允许已登记的内部视频；
- [ ] 输出限制在应用输出目录；
- [ ] 临时文件删除同时检查目录边界和专用文件名；
- [ ] API 不返回以下划线开头的本地字段；
- [ ] 任务按账号隔离；
- [ ] 不把 Topaz 二进制、模型、许可证或用户媒体打入源码包；
- [ ] 日志不记录授权凭据；
- [ ] 模型自动下载由用户参数控制。

## 20. 后续扩展建议

1. 增加 CPU、AV1 NVENC、Intel QSV 或 AMD AMF 输出编码；
2. 按 GPU 显存动态控制并发，而不是固定为 1；
3. 读取 Topaz 模型定义生成不同模型的专属参数面板；
4. 增加预览片段、局部裁切和前后对比；
5. 支持队列优先级、暂停和批量视频输入；
6. 对 `audio_mode=copy` 做容器兼容性预检；
7. 将 `main.py` 中的任务控制器进一步拆成 `canvas_core/topaz_tasks.py`，降低主模块体积；
8. 增加显卡能力探测，在能力接口中公开可用编码器；
9. 把前端宿主依赖封装为正式节点 SDK，减少迁移成本。

扩展时优先保持三个边界：适配器不依赖 Web 层、任务 API 不泄漏本地路径、前端不写死本机模型。

## 21. 源码包使用说明

分发压缩包应包含：

```text
README.md
VERSION.txt
SOURCE-COMMIT.txt
MANIFEST-SHA256.txt
docs/Developer-Guide.zh-CN.md
source/<按仓库相对路径保存的完整文件>
patches/topaz-node-feature.patch
```

- `source/`：当前版本的完整相关文件；
- `patches/`：接入前基线到当前实现的 Git 二进制安全补丁；
- `MANIFEST-SHA256.txt`：包内文件逐项 SHA-256；
- 压缩包旁的 `.sha256`：整个 ZIP 的 SHA-256。

收到压缩包后先校验 ZIP 哈希，再解压并校验清单。PowerShell 示例：

```powershell
Get-FileHash .\SHIYIN-AI-Topaz-Node-v1.0.176.zip -Algorithm SHA256
Get-Content .\SHIYIN-AI-Topaz-Node-v1.0.176.zip.sha256
```

## 22. 维护联系人需要关注的信息

- 当前应用版本：`1.0.176`；
- 接入前基线：`672bb14`；
- 初始功能提交：`7a4765f`；
- 8K/高级弹窗修复：`2f2a2f0`；
- `N/A` 进度修复：`7d52a32`；
- 默认安装目录可由用户设置，不应假设一定在 C 盘；
- 源码包不赋予 Topaz 软件或模型的再分发权。
