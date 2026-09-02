# Lookbook 真实生图任务层生命周期误判

## 问题表现

使用 FastAPI `TestClient` 创建 Lookbook 电商任务后，任务被返回为“服务已重启，未完成的电商任务已中断”，临时数据目录中的可选模型下载线程还可能持有 `.part` 文件，退出时清理失败。

## 触发条件

测试进程临时设置 `CANVAS_DATA_DIR`，同时通过 HTTP 任务接口启动后台 `asyncio.create_task`；应用任务恢复逻辑与测试客户端生命周期重叠。若未显式关闭 `CANVAS_DEPTH_AUTO_DOWNLOAD`，启动阶段还可能拉起深度模型下载。

## 根本原因

这是测试 harness 的事件循环/任务持久化生命周期问题，不是 Lookbook prompt 或图片模型调用失败。任务接口的后台任务没有在测试客户端结束前稳定完成，随后恢复逻辑按重启中断处理。

## 正确解决方案

真实图片 API 验证使用同一 `build_prompt`、`lookbook_generation_prompts` 和 `execute_ai_image_batch`，在独立 asyncio 上下文直接执行批次；测试前强制设置 `CANVAS_DWPOSE_AUTO_DOWNLOAD=0` 与 `CANVAS_DEPTH_AUTO_DOWNLOAD=0`。HTTP 任务层仍由单元测试覆盖快照和路由契约。

## 验证方法

使用 `tools/smoke-levis-lookbook-real.py`，确认四次独立请求返回 4 张本地图片，并检查每张尺寸、单幅构图和系列一致性。

## 如何避免

不在临时 TestClient 生命周期中启动需要长时间运行的后台付费任务；需要真实上游验证时使用直接 batch harness 或长期运行的本地服务，并关闭未使用的本地模型自动下载。

## 影响模块

Lookbook 真实生图测试、`main.py` 任务恢复、深度/DWPose 可选模型启动。
