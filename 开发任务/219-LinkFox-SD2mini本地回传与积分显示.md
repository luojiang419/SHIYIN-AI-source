# LinkFox SD2mini 本地回传与积分显示

[CODEX_LONG_TASK_CONTINUE_V3]

- 状态：源码、真实生成和局域网热更新发布已完成；当前安装版文件与发布包一致，后端已在发布后重启。
- 下一步：用户在当前安装版打开 LinkFox 视频节点，检查实际画布中的积分文字和视频结果；若特定旧任务仍失败，凭 taskId 精确排查。
- TODO：用户实际节点交互反馈（如有）。
- 最近验证：SD2.0mini 与 SD FAST 均真实生成成功并下载、完整解码；浏览器节点显示余额，局域网发布签名和整包下载哈希通过。
- branch/commit：`feat/linkfox-mini-fast-balance` / `09602f6b`，已推送 `origin/feat/linkfox-mini-fast-balance`；发布从该提交的隔离工作目录构建，未包含工作区其他任务改动。
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
- 提交到首次查询成功：Mini 约 165 秒，Fast 约 124 秒；提交到本地文件下载完成：Mini 约 180 秒，Fast 约 138 秒。查询为轮询，实际平台完成时间可能早于首次成功查询。
- 两个文件 `ffprobe` 均为 H.264、864×496、121 帧、5.041667 秒；`ffmpeg` 完整解码无报错。另调用当前源码的 `save_remote_video_to_output` 函数对两条成功任务实际落盘，分别得到 `/assets/output/linkfox_mini_*.mp4` 和 `/assets/output/linkfox_fast_*.mp4`，文件存在、大小一致、MP4 文件头正确。
- 当前已安装版的两条旧 LinkFox 任务也均有实际 `/assets/output` 本地文件。此前“始终无法获取到本地”的具体用户任务未提供 taskId，因此不能据这几条成功任务推断该任务的失败原因。

## 修改与验证

- `canvas_core/linkfox_video.py`：增加 Mini 模型，按官方 V3 响应提交与查询；保留旧模型任务的旧网关续查路径。
- `main.py`：提供官方套餐积分查询，保留未知余额状态；成功任务记录 V3 返回的实际消耗积分。
- `static/js/canvas-linkfox-video.js` 与两个画布页面：显示和手动刷新 LinkFox 剩余积分，生成完成后自动刷新；增加 Mini 模型并关闭其不支持的 Pro/多段运镜开关。
- `canvas_core/video_prompt_registry.py`：让 Mini 使用 Seedance 2.0 提示词规则。
- Python 定向测试 79 项通过；Node 异步交互测试通过；经典视频与影视视频节点浏览器实测显示余额、Fast 与 Mini 模型切换和回传通过；`py_compile`、JS 语法检查和 `git diff --check` 通过。

## 局域网热更新交付

- 隔离 worktree：`D:\data\codex\tree\linkfox-mini-release\SHIYIN-AI`，从提交 `09602f6b` 构建。前端使用已发布 `20260924174208` 为底稿，仅覆盖四个 LinkFox 文件；桌面宿主复用当前 2.0.6 已安装 EXE，后端 sidecar 重新编译。未执行全量安装器流程。
- 热更新 `20260924184255` 已发布，1037 文件，整包 229034282 字节，SHA-256=`1fb8a35fba7d155fddcd83e33e9f520428e40bc121518266227a9472da6f4178`。客户端目录和计划签名有效，整包下载哈希与本地 manifest 一致；最低桌面版本保持当前活动热更新的 `2.0.0`，继续支持旧 2.0.x 过渡客户端。
- 冻结后端包含 Mini V3 提交、查询和积分路由；发布包前端 JS/CSS 与提交源码逐字节一致。当前 `D:\Program Files\SHIYIN AI\app` 中的 LinkFox JS 和后端 EXE 与发布包哈希相同，后端进程于 18:52:06 启动（晚于文件应用时间 18:51:57）。当前安装版实际画布没有通过人工点击复核。
- `.build` 与 `.codex-tmp` 上限已检查，主工作区分别约 12.20 GiB 与不足 0.01 GiB；隔离构建目录清理脚本已执行。

## 官方文档

- https://wiki.linkfox.com/docs/linkfox-ai/image-to-video-v3
- https://wiki.linkfox.com/docs/linkfox-ai/task-result
- https://wiki.linkfox.com/docs/linkfox-ai/monthly-points
- https://wiki.linkfox.com/docs/linkfox-ai
