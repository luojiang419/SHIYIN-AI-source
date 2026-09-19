# Lookbook输入与画布平移及单图视频解析修复

状态：已完成  
下一步：无。  
TODO：无。  
最近验证：`npm run canvas:engine-build` 通过；`pytest -q tests/test_video_auto_parse.py tests/test_lookbook_node_frontend.py` 通过（60 passed）。  
branch/commit：`fix/hot-update-catchup` / 未提交  
阻塞：无。  

目标：修复 Lookbook 输入框失焦、Ctrl 临时平移失效，以及单图视频自动解析生成跳跃多镜头的问题。

验收：Lookbook 编辑不重建活动控件；任意画布操作后可按 Ctrl 临时平移；单图自动解析明确输出同一场景的连续单镜头提示词，多图继续按全部参考图综合编排。已通过定向测试。

[CODEX_LONG_TASK_CONTINUE_V3]
