# SHIYIN AI Topaz 高清放大节点源码包

本包用于把 SHIYIN AI `1.0.176` 中的 Topaz 高清放大节点交接给其他开发者。

请先阅读 `docs/Developer-Guide.zh-CN.md`。如果目标仓库与 SHIYIN AI 接入前提交 `672bb14` 接近，可以先执行：

```powershell
git apply --check .\patches\topaz-node-feature.patch
```

检查通过后再应用补丁。目标项目已经演进时，请按文档中的模块锚点手动合并，不要用 `source/main.py` 覆盖现有主文件。

包内内容：

- `source/`：相关文件的当前完整版本；
- `patches/topaz-node-feature.patch`：从接入前基线到稳定实现的补丁；
- `docs/`：完整开发、接入、测试和排错文档；
- `VERSION.txt`、`SOURCE-COMMIT.txt`：应用和源码版本；
- `MANIFEST-SHA256.txt`：包内逐文件校验清单。

运行要求：Windows x64、合法安装并授权的 Topaz Video AI、可用模型、支持所选 NVENC 编码器的 NVIDIA 驱动。运行节点不要求 Topaz 主界面保持打开。

本包不包含 Topaz 主程序、模型、许可证、用户媒体、生成结果、数据库、日志或安装程序。Topaz 相关软件和模型的使用与分发应遵守其许可条款。
