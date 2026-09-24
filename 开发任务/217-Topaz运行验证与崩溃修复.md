# Topaz 运行验证与崩溃修复

状态：模型目录检测已恢复；最小放大任务失败，Topaz 自带 FFmpeg 在 `opencv_world4120.dll` 中访问冲突。等待确认是否修复重装 Topaz Video。

下一步：获得授权后，按 Topaz 官方安装流程修复当前 1.7.1 安装，保留现有项目与模型数据；然后重跑下述最小任务，检查输出尺寸与帧数。

TODO：
- [ ] 让 `prob-4` 2× 最小任务生成非空视频，并用 `ffprobe` 验证 1280×720 输出。
- [ ] 再验证 H.264 输入。当前随 Topaz 提供的 FFmpeg 自动选用 `h264_qsv` 解码，在本机失败；显式 `h264_cuvid` 解码单独测试通过。

最近验证（2026-09-24）：
- 已安装客户端后端的原始字节码检测结果为 `ready=True`，可识别 45 个模型定义，模型数据位于 `D:\ProgramData\Topaz Labs LLC\Topaz Video\models`。
- 测试输入：`.codex-tmp/topaz-e2e/input-640.mp4`，640×360、1 帧、MPEG-4。运行 `prob-4` 2× 和 `amq-13` 2× 均退出 `0xC0000005`，输出文件为 0 字节。
- Windows 应用程序事件 1000 指向 `D:\Program Files\Topaz Labs LLC\Topaz Video\opencv_world4120.dll`。裸 `tvai_up=model=prob-4:scale=2` 命令、NVIDIA/CPU、精简子进程环境、默认和自定义模型数据目录均复现相同崩溃。
- Topaz 两处 `proxy.json` 原指向未运行的 `127.0.0.1:7890`，已禁用该代理，直连模型服务后成功下载 `prob-4` 文件。目录检测与模型下载已不再阻塞。
- `python -m pytest tests/test_topaz_video.py tests/test_hot_update_release_guard.py -q`：19 passed。

分支：`fix/kling-cli-video-reference-routing`；相关提交：`6b8a2e5d`（已推送）。本任务的本机 Topaz 配置改动不在 Git 中；工作区其他改动属于并行任务，勿覆盖。

验收：实际 Topaz 命令返回 0，输出文件非空，`ffprobe` 证实视频流为 1280×720 且至少 1 帧。

[CODEX_LONG_TASK_CONTINUE_V3]
