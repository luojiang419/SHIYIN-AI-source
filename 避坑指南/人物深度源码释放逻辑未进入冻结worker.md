# 人物深度源码释放逻辑未进入冻结 worker

## 表现

动作迁移深度图提取结束后，`person-depth-worker.exe` 长时间常驻并占用专用显存。源码 `person_depth_worker/worker.py` 已有把模型移回 CPU、调用 `torch.cuda.empty_cache()` 和 300 秒空闲卸载的逻辑，源码测试也可通过，但用户实际使用的冻结程序没有这些方法。

## 根因

旧的 512 worker 是从更早的冻结程序只修改分割输入尺寸得到的；该程序只改尺寸，不会自动携带后来添加的显存释放源码。主后端使用常驻 worker，源码运行模式还曾默认调用固定组件中的旧 EXE。只更新前端或后端的 Python 源码，都不能改变已经冻结的 worker。

## 解决与验证

从当前可信 `person-depth-worker.spec` 重新冻结 worker；检查冻结 `worker` 代码对象确有 `_release_gpu_and_schedule_unload`、`_unload_if_idle`，且 `estimate` 在结束路径调用释放方法。用新 SHA-256 绑定后端覆盖程序，写入新的版本化运行文件名，保留原固定程序与模型权重。源码模式直接启动仓库的 worker 源码，避免继续使用旧 EXE。

使用正式固定模型和同一张 A-pose.jpg 做冻结程序真实推理：新旧 512 深度图逐像素一致；新 worker 的 Windows GPU Process Memory 专用显存采样峰值约 1,980.5 MiB，返回后约 282.5 MiB，第二次推理成功且返回后仍约 282.5 MiB。再将新 EXE 放入已安装组件的原运行时目录，复用其原有 `_internal` 依赖和模型，输出仍逐像素一致、返回后仍为 282.5 MiB。整卡显存还包含其他程序和 CUDA 上下文，不能把整卡占用要求为零。发布候选必须再检查冻结后端仅目标模块变化、覆盖程序摘要、完整 ZIP、签名目录与公开整包回读。

记录与构建器见 `开发任务/233-人物深度提取后自动释放显存.md`、`tools/build-person-depth-vram-hotfix.py`。
