# Topaz 运行验证与崩溃修复

状态：已完成。Topaz Video 1.7.1 官方安装程序修复重装完成；用已安装客户端后端生成的命令完成 `prob-4` 2× 视频放大，MPEG-4 和 H.264 输入均通过。

下一步：无。用户可刷新画布页面以清除先前缓存的检测错误。

TODO：
- [x] 让 `prob-4` 2× 最小任务生成非空视频，并用 `ffprobe` 验证 1280×720 输出。
- [x] 验证 H.264 输入，输出 15 帧、1280×720、3 秒 MP4。

最近验证（2026-09-24）：
- 已安装客户端后端的原始字节码检测结果为 `ready=True`，可识别 45 个模型定义，模型数据位于 `D:\ProgramData\Topaz Labs LLC\Topaz Video\models`。
- 用户指出的 `D:\ProgramData\Topaz Video AI\models` 保存旧版 Topaz 模型权重，修复前后均为 38,205 个文件、11,679,272,065 字节；该目录无 `tvai.tz` 和 `prob-4.json`，不能直接替代当前 Topaz Video 模型定义目录。项目目录修复前后均为 3 个文件、892,091 字节。
- Topaz 两处 `proxy.json` 原指向未运行的 `127.0.0.1:7890`，已禁用该代理；直连后缺失的 `prob-4`、`amq-13` 当前版本模型文件自动下载到 `D:\ProgramData\Topaz Labs LLC\Topaz Video\models`。
- 从 Topaz 官方 1.7.1 发布帖取得已签名 MSI，签名为 Topaz Labs LLC；静默安装返回 0，安装后的产品代码为 `{5C888877-2A5F-43C5-824D-99C83EDC2C86}`。原有模型与项目目录未减少文件。
- 单帧输入会使 Topaz FFmpeg 在 `opencv_world4120.dll` 以 `0xC0000005` 崩溃；将测试改为 3 秒、15 帧后，裸 `tvai_up` 滤镜返回 0，全部 15 帧处理成功。后续实际视频输入应至少包含多个帧。
- 已安装客户端后端构造的 `prob-4` 2× 命令：MPEG-4 输入得到 `.codex-tmp/topaz-e2e/topaz-prob4-2x-15frames.mp4`（455,708 字节）；H.264 输入得到 `.codex-tmp/topaz-e2e/topaz-prob4-h264-input.mp4`（434,368 字节）。`ffprobe -count_frames` 对两者均确认 H.264、1280×720、15 帧、3 秒；预览帧为 `.codex-tmp/topaz-e2e/topaz-preview.png`。
- 后续复测 `amq-13` 2×：H.264 输入得到 `.codex-tmp/topaz-e2e/topaz-amq13-2x-15frames.mp4`（442,502 字节），`ffprobe` 确认 H.264、1280×720、15 帧、3 秒。45 个模型定义中仅 `prob-4` 与 `amq-13` 经过实际输出验证；当前经典模型数据目录只有这两族的 3 个 `.tz3` 权重文件，其他模型依赖按需自动下载，未逐一验证。
- `python -m pytest tests/test_topaz_video.py tests/test_hot_update_release_guard.py -q`：19 passed。

分支：`fix/kling-cli-video-reference-routing`；相关提交：`6b8a2e5d`（已推送）。本任务的本机 Topaz 安装与配置改动不在 Git 中；工作区其他改动属于并行任务，勿覆盖。

验收：实际 Topaz 命令返回 0，输出文件非空，`ffprobe` 证实视频流为 1280×720 且至少 1 帧。

[CODEX_LONG_TASK_CONTINUE_V3]
