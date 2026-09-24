# LinkFox SD2mini 本地回传与积分显示

[CODEX_LONG_TASK_CONTINUE_V3]

- 状态：源码与真实验证已完成；待 Git 交付及必要发布。
- 下一步：检查本任务差异，隔离其他任务改动后提交并评估热更新发布。
- TODO：Git 交付、必要发布及安装版验收。
- 最近验证：SD2.0mini 与 SD FAST 均真实生成成功，下载后完整解码；LinkFox 适配器、积分接口和浏览器节点验证通过。
- branch/commit：`feat/linkfox-mini-fast-balance` / 待提交；工作区有大量其他任务改动，已仅暂存本任务差异。
- 阻塞：无。

## 目标与验收

- 查明 LinkFox 视频任务到本地文件的实际链路与故障，并让失败不能被误记为成功。
- 使用 SD2.0mini 做最小真实生成，核验返回、下载、文件解码及本地 URL。
- 在 LinkFox 视频生成相关界面显示实时剩余积分；查询失败不得显示虚构数字。

## 当前证据

- 本地旧版两个 LinkFox 历史任务已成功，任务结果分别指向 `/assets/output/linkfox_*.mp4`，对应安装版 `data/media/generated` 文件实际存在。不能将“始终无法保存”归因于这两条；需要验证当前用户场景。
- 现有实现只支持旧 `tool-gateway.linkfox.com` 的 `SEED` 等模型枚举，未接入 SD2.0mini。官方当前 V3 模型 ID 为 `doubao-seedance-2-0-mini`，任务响应为 `data.id`，查询状态为 `data.status` 数值，结果在 `data.resultList[].url`；与旧响应结构不同。
- 官方套餐接口实际可用；剩余点数可按 `data.total - data.usage` 计算。首次查询总点数 1500000、已用 79380；两次生成后查询已用 79520、剩余 1420480（同期可能有其他任务，不把全部差额归于测试）。旧任务回传时云端视频 URL 可以直接下载（HTTP 200、MP4 文件头）。

## 真实生成与本地验证（2026-09-24）

- SD2.0mini：官方 V3 `doubao-seedance-2-0-mini`、1 张无品牌蓝色方盒图、5 秒、480p、16:9、无声。taskId=`2103060316882571264`，`data.status=3`，`data.count=35`，结果 URL 可下载。文件 `.codex-tmp/linkfox-mini-test/sd2mini-5s-480p.mp4`，778177 字节，SHA-256=`ffdf85ff47ae5cad5b758533bde0613d1e97f547629dbab1b6b3f1cb733eae99`。
- SD FAST：现有技能网关 `SEED_FAST`，相同最小参数与测试图。taskId=`2103061161080844288`，状态 `SUCCESS`，结果 URL 可下载。文件 `.codex-tmp/linkfox-fast-test/sd2fast-5s-480p.mp4`，668087 字节，SHA-256=`6e4520398f3d96f7ab192b4f65da8356087f1f0015456a7f472b90bf4d8088ae`。
- 两个文件 `ffprobe` 均为 H.264、864×496、121 帧、5.041667 秒；`ffmpeg` 完整解码无报错。另调用当前源码的 `save_remote_video_to_output` 函数对两条成功任务实际落盘，分别得到 `/assets/output/linkfox_mini_*.mp4` 和 `/assets/output/linkfox_fast_*.mp4`，文件存在、大小一致、MP4 文件头正确。
- 当前已安装版的两条旧 LinkFox 任务也均有实际 `/assets/output` 本地文件。此前“始终无法获取到本地”的具体用户任务未提供 taskId，因此不能据这几条成功任务推断该任务的失败原因。

## 修改与验证

- `canvas_core/linkfox_video.py`：增加 Mini 模型，按官方 V3 响应提交与查询；保留旧模型任务的旧网关续查路径。
- `main.py`：提供官方套餐积分查询，保留未知余额状态；成功任务记录 V3 返回的实际消耗积分。
- `static/js/canvas-linkfox-video.js` 与两个画布页面：显示和手动刷新 LinkFox 剩余积分，生成完成后自动刷新；增加 Mini 模型并关闭其不支持的 Pro/多段运镜开关。
- `canvas_core/video_prompt_registry.py`：让 Mini 使用 Seedance 2.0 提示词规则。
- Python 定向测试 79 项通过；Node 异步交互测试通过；经典视频与影视视频节点浏览器实测显示余额、Fast 与 Mini 模型切换和回传通过；`py_compile`、JS 语法检查和 `git diff --check` 通过。

## 官方文档

- https://wiki.linkfox.com/docs/linkfox-ai/image-to-video-v3
- https://wiki.linkfox.com/docs/linkfox-ai/task-result
- https://wiki.linkfox.com/docs/linkfox-ai/monthly-points
- https://wiki.linkfox.com/docs/linkfox-ai
