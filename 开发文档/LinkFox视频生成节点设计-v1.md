# LinkFox 视频生成节点设计（v1）

## 任务目标

在普通画布和智能画布中增加“LinkFox 视频生成”节点，调用已安装的
`linkfox-expert-aigc-videogen-image-to-video` 编排技能，提供模型选择和生成参数编辑，
并将生成的视频作为画布媒体输出，保持现有节点的保存、预览、失败提示和下游连接能力。

## 技能到节点的转换原则

节点不直接复制 LinkFox 的 HTTP 协议，而是把节点状态转换成技能入口 JSON：

```json
{
  "entry": "img2video",
  "mode": "reference",
  "imageList": ["https://..."],
  "videoType": "seedance2.0",
  "videoTime": 5,
  "prompt": "...",
  "promptOptimizer": false,
  "isPro": false,
  "voice": true,
  "camera": "single",
  "aspectRatio": "16:9",
  "resolution": "720p"
}
```

前端只负责端口收集、参数编辑和节点状态；后端负责调用已安装的底层 skill、等待任务、
解析 `Saved full response:` 中的本地视频路径，并拒绝把临时远程 URL直接交给画布。

## 节点状态与端口

| 字段 | 说明 |
|---|---|
| `type` | `linkfox-video`，用于普通画布序列化和运行时分派 |
| `specialType` | 智能画布使用 `linkfox-video`，沿用特殊节点渲染分支 |
| `mode` | `reference` 或 `first_last_frame` |
| `model` | 业务模型名，使用技能支持的稳定名称 |
| `duration` | 秒数，按模型限制为 5/10/15 或海螺的 6/10 |
| `resolution` | `480p`、`720p`、`768p`、`1080p`，按模型动态过滤 |
| `aspectRatio` | `16:9`、`9:16`、`1:1`、`adaptive`，按模型动态过滤 |
| `voice` | 可选时显示开关；固定声音模型不显示可编辑控件 |
| `promptOptimizer` | 是否启用提示词优化 |
| `isPro` | 是否启用 Pro/高质量模式 |
| `camera` | `single` 或 `multi` |
| `inputs` | 连接的图片引用；首尾帧模式按端口角色区分首帧/尾帧 |

普通画布保留一个图片输入端口和一个可选尾帧端口；参考图模式允许多个图片连接，数量上限
由模型矩阵限制。智能画布使用稳定角色 `reference-image`、`first-frame`、`last-frame`，
使连接关系在节点重绘和恢复后仍可还原。

## 模型和参数矩阵

### 参考图模式

| 模型 | 底层 skill | 时长 | 分辨率 | 比例 | 声音 | 图片上限 |
|---|---|---|---|---|---|---|
| seedance2.0 | multi | 5/10/15 | 480/720/1080p | 16:9/9:16/adaptive | 可选，默认开 | 9 |
| seedance2.0fast | multi | 5/10/15 | 480/720p | 16:9/9:16 | 可选，默认开 | 9 |
| 可灵Omni | multi | 5/10/15 | 720/1080p | 16:9/9:16/1:1 | 固定关 | 7 |
| HappyHorse | multi | 5/10/15 | 720/1080p | 16:9/9:16 | 固定开 | 9 |
| 海螺2.3 | single | UI 5/10（底层 6/10） | 768/1080p | 按模型 | 固定关 | 1 |
| wan2.6 | single | 5/10/15 | 按模型 | 不支持显式比例 | 可选，默认开 | 1 |

### 首尾帧模式

| 模型 | 底层 skill | 时长 | 分辨率 | 比例 | 声音 | 尾帧规则 |
|---|---|---|---|---|---|---|
| seedance2.0 | single | 5/10/15 | 480/720/1080p | 16:9/9:16/adaptive | 可选 | 可选 |
| seedance2.0fast | single | 5/10/15 | 480/720p | 16:9/9:16 | 可选 | 可选 |
| 可灵2.6 | single | 5/10 | 720/1080p | adaptive | 1080p 可选 | 仅 1080p + 关闭声音 |

## 后端调用边界

1. 新增 LinkFox 专用服务适配器，定位项目内已安装的 skill 脚本，不在前端拼接网关请求。
2. 调用前执行入口、URL、模式、模型组合、时长、图片数量等校验。
3. 通过子进程调用底层 `aigc_videogen.py` 或 `aigc_videogen_multi.py`，传递 JSON；保留
   `LINKFOX_AGENT_API_KEY` / `LINKFOXAGENT_API_KEY` 环境变量，不把密钥写入节点数据。
4. 成功只返回已下载的本地媒体路径；失败返回技能落盘 JSON 中的可读错误。
5. 本地画布 `/assets/...` 图片不是公网 URL，若节点收到该类输入应明确提示“请先提供
   可访问的 HTTP(S) 图片 URL”，不伪造公网地址。

## 验收标准

- 两种画布都能从菜单创建节点，节点标题为“LinkFox 视频生成”。
- 模型切换会同步刷新合法时长、分辨率、比例、声音和尾帧控件。
- 运行请求始终包含 `entry=img2video`，单图/多图和首尾帧路由与技能矩阵一致。
- 生成成功后输出节点可预览、保存、下载并能继续连接下游节点。
- 缺图、非法 URL、非法参数、缺少 API Key 时不提交任务，界面显示可修复原因。
- 既有 `video`、`ecom-video`、影视节点和历史画布数据保持兼容。
