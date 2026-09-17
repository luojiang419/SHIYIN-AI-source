# 自动抠像节点编辑器

此目录由独立验证工具迁入，运行于主应用同源 iframe，不依赖 8791 验证服务。
API 挂载于 /api/cutout，透明结果通过主应用 /api/ai/upload 保存为账号隔离的持久素材。

运行源码主服务需安装 tools/click-segmentation-lab/requirements.txt；本机已验证 torch 2.6.0+cu126、Transformers SAM 与 NVIDIA CUDA。
首次加载模型需要下载 facebook/sam-vit-base，后续复用本机缓存。
当前尚未制作可分发的 SAM 可选运行组件。现有 canvas-backend.spec 排除了 torch/transformers，
因此安装版发布前必须补齐独立推理运行时；本次未构建或发布安装包/热更新。

编辑器发送 cutout:ready / cutout:saved / cutout:fullscreen 消息；宿主校验同源与 iframe 来源。
保存结果包含原图 URL、点选参数和持久透明 PNG；下游只取 outputUrl。
