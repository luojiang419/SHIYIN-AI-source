[CODEX_LONG_TASK_CONTINUE_V3]

状态：局域网与魔搭热更新 `20260926215915` 均已发布并完成公开验证；2.0.6 仍是唯一全量安装基准，固定模型未变。当前 branch：feat/pose-transfer-fidelity；修复 commit：03cf64f4，已推送。
下一步：客户端检查并应用更新后，在实际画布上确认 Grsai 图片可进入作品；不自动重发旧失败请求。
TODO：客户端实际应用验收。
最近验证：2026-09-26 Grsai GPT-Image-2.5 带参考图异步任务 `16-50b5691d-2bf3-4223-b1e6-b11a4159262f` 成功，`/v1/api/result` 返回图片；保存 1254×1254 PNG（1,569,276 字节）到 `D:\Program Files\SHIYIN AI\data\accounts\a0a7851b20ec4650874aaf44215bac45\exports\grsai-validation-1790430439.png`。项目查询与保存函数再次查询同一任务并写出 `data/media/generated/SHIYIN-000067-20260926.png`，两文件 SHA-256 一致。Grsai 相关回归 7 passed；`py_compile` 通过。冻结后端隔离启动及带参考图异步提交、查询、保存、手动查询端到端通过。双端签名目录/更新计划、魔搭匿名完整回读、局域网完整下载 SHA-256 通过；2.0.1/2.0.5/2.0.6 客户端计划均指向本版。完整相关前端测试因工作区已有的 `static/gpt-chat.html` 删除而无法启动，非本次改动。
阻塞：旧版 `/images/edits` 断连前没有返回任务 ID，`ljhledqs` 21:24 的失败记录和作品历史均未保存该次云端 ID，用户也无法提供，不能唯一恢复旧图。一次验证请求上游返回 `generate image failed`；换用该账号已有正常尺寸参考图后成功。已配置的本机代理导致 GitHub TLS 握手失败，本次临时绕过该代理后正常推送，未修改全局代理设置。

目标：修复 Grsai GPT-Image-2 参考图生成时 `/v1/images/edits` 长连接断开导致已生成结果无法取回；验证 `ljhledqs` 最近一次生成图片可获取并保存。

方案：Grsai 的 Nano Banana 与 GPT-Image-2 统一走原生 `generate`，设置 `replyType: async` 使接口尽快返回任务 ID，随后查询 `result`；GPT 使用像素尺寸与 `quality`。保留其他供应商现有 OpenAI 兼容路径。公共手动任务查询按 Grsai 的 `result?id` 路由，查询失败保留上游 ID，避免重复扣费。

涉及文件：`main.py`、`tests/test_ecommerce.py`、`tests/test_grsai_image_result.py`、本任务文档。

验收：请求参数与官方文档一致；直接结果和异步结果都能提取并落盘；失败时可用任务 ID 查询恢复；目标账号新的验证结果完成实际查询及下载。旧失败任务因缺失 ID 不在可恢复范围内。

发布结果：从已发布 `20260924142326` 后端底包只替换冻结 `main` 的 5 个 Grsai 相关函数；桌面宿主沿用原包，前端沿用 `20260926121358`，仅统一 HTML 缓存版本并追加更新历史。新包 `dist/hot-update/20260926215915/SHIYIN-Hot-Update-20260926215915.shiyin-update`，1,177 文件、236,643,362 字节，SHA-256 `cfef22e05502e41dc5d624fbc89ebe1b75a9c2ab494fdd81fa73b635fc81b0e5`。局域网活动版 `hot-20260926215915`；魔搭路径 `releases/20260926215915/SHIYIN-Hot-Update-20260926215915.shiyin-update`，公开目录 `public/catalog.json`。无全量安装包编译，无固定模型替换；固定台账 SHA-256 `b6af134be3a3e5f18f07d05dfc00bb9fcfbc05301858c9cbf80ee79affdb68a8`。
