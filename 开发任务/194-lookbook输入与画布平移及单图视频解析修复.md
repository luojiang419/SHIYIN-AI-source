# Lookbook输入与画布平移及单图视频解析修复

状态：已完成  
下一步：无。  
TODO：无。  
最近验证：`npm run canvas:engine-build` 通过；`pytest -q tests/test_video_auto_parse.py tests/test_lookbook_node_frontend.py` 通过（60 passed）；局域网目录/补齐计划 Ed25519 验签、公开 blob Range 下载及 SHA-256 核验通过。  
branch/commit：`fix/hot-update-catchup` / `3c50c2a6`  
阻塞：无。  

目标：修复 Lookbook 输入框失焦、Ctrl 临时平移失效，以及单图视频自动解析生成跳跃多镜头的问题。

验收：Lookbook 编辑不重建活动控件；任意画布操作后可按 Ctrl 临时平移；单图自动解析明确输出同一场景的连续单镜头提示词，多图继续按全部参考图综合编排。已通过定向测试。

发布：完整热更新 `20260919094154` 已发布，包含桌面宿主、后端和前端，不是全量安装包。包 `SHIYIN-Hot-Update-20260919094154.shiyin-update` 为 2,952,363,987 字节，SHA-256 `4b134860bf46d8b15ac2368579c8c3998afe5f9dcd6454a29f120c3b79f68c11`。公开 blob Range 请求返回 206，签名目录与补齐计划已用 Ed25519 公钥验证。固定模型 `fixed-models.json` SHA-256 保持 `b6af134be3a3e5f18f07d05dfc00bb9fcfbc05301858c9cbf80ee79affdb68a8`。

[CODEX_LONG_TASK_CONTINUE_V3]
