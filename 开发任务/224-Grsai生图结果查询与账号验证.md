[CODEX_LONG_TASK_CONTINUE_V3]

状态：代码修复、真实结果下载及选择性代码提交已完成；运行实例尚未更新。当前 branch：feat/pose-transfer-fidelity；修复 commit：03cf64f4。
下一步：隔离工作区中其他未提交变更后发布 backend 热更新，使运行中的安装实例使用修复代码；旧失败请求若要恢复，仍需上游任务 ID。
TODO：推送本任务提交；在适合的发布窗口进行热更新。
最近验证：2026-09-26 Grsai GPT-Image-2.5 带参考图异步任务 `16-50b5691d-2bf3-4223-b1e6-b11a4159262f` 成功，`/v1/api/result` 返回图片；保存 1254×1254 PNG（1,569,276 字节）到 `D:\Program Files\SHIYIN AI\data\accounts\a0a7851b20ec4650874aaf44215bac45\exports\grsai-validation-1790430439.png`。项目查询与保存函数再次查询同一任务并写出 `data/media/generated/SHIYIN-000067-20260926.png`，两文件 SHA-256 一致。Grsai 相关回归 7 passed；`py_compile` 通过。完整相关前端测试因工作区已有的 `static/gpt-chat.html` 删除而无法启动，非本次改动。
阻塞：旧版 `/images/edits` 断连前没有返回任务 ID，`ljhledqs` 21:24 的失败记录和作品历史均未保存该次云端 ID，用户也无法提供，不能唯一恢复旧图。一次验证请求上游返回 `generate image failed`；换用该账号已有正常尺寸参考图后成功。

目标：修复 Grsai GPT-Image-2 参考图生成时 `/v1/images/edits` 长连接断开导致已生成结果无法取回；验证 `ljhledqs` 最近一次生成图片可获取并保存。

方案：Grsai 的 Nano Banana 与 GPT-Image-2 统一走原生 `generate`，设置 `replyType: async` 使接口尽快返回任务 ID，随后查询 `result`；GPT 使用像素尺寸与 `quality`。保留其他供应商现有 OpenAI 兼容路径。公共手动任务查询按 Grsai 的 `result?id` 路由，查询失败保留上游 ID，避免重复扣费。

涉及文件：`main.py`、`tests/test_ecommerce.py`、`tests/test_grsai_image_result.py`、本任务文档。

验收：请求参数与官方文档一致；直接结果和异步结果都能提取并落盘；失败时可用任务 ID 查询恢复；目标账号新的验证结果完成实际查询及下载。旧失败任务因缺失 ID 不在可恢复范围内。
