# film 与 SHIYIN 后台直连双端安装包

状态：构建中
当前阶段：3/3
最后更新：2026-09-08

## 当前状态
SHIYIN 1.0.422 安装器已生成、校验通过，完整 runtime smoke 与打包态无页面工作流初始化通过。film 1.1.0.375 Windows Release（44.6 秒）和配套 Web（22.8 秒）编译通过，Inno Setup 正在压缩深度组件运行库。两端构建日志位于 C:/Users/jiang/AppData/Local/Temp/film-dual-installers-20260908。

工作树有其他功能的既有未提交改动，沿用之前安装包构建规则，按当前工作树打包、只提交本次版本与构建记录差异。不安装覆盖用户程序，不发布 GitHub Release。

## 下一步
1. 等待 film Inno Setup 完成，运行 scripts/verify_release_artifact.ps1 -Version 1.1.0.375。
2. 更新记录，精准提交并推送两端版本文件，交付两个安装器。

## 当前 TODO
- [x] 检查源码、版本、构建入口、运行进程
- [ ] 两端正式版本同步与完整构建
- [ ] 安装器及后台直连回归验证
- [ ] 文档、提交推送及交付

## 最近验证状态
- 上轮源码回归：65 Python、14 Dart、9 JavaScript 与 9 Chromium 通过。
- SHIYIN：9 个版本源一致；runtime smoke 启动 8933ms，内存 206.37MB/250MB，单实例与父进程退出清理通过。
- SHIYIN：安装器 92,627,907 bytes；SHA-256 96f6c5f650ad20923f0ae777f90d1ca66cecb7bc2221b68885d015390b80ce5c；NotSigned。
- 冻结后端：health 1.0.422、首次导出即初始化三步快照、媒体字节、重复导出幂等与工程包往返全部通过，结果保存在 Temp/film-dual-installers-20260908/packaged-smoke-v2.json。
- 首轮专项脚本把 stdout/stderr 日志放在待迁移的数据根目录，触发 WinError 32；已按避坑指南 006 修正到 logs 子目录，并在新隔离目录重跑成功。没有修改或关闭产品迁移逻辑。
- film 安装器：压缩中，Windows/Web 构建版本均为 1.1.0+375。
- Git branch：SHIYIN feat/film-workflow-canvas；film feat/infinite-canvas-workflow。

## 任务目标与技术方案
SHIYIN 由 tools/increment-version.ps1 与 tools/build-installer.ps1 统一同步版本并打包；film 由 scripts/prepare_release.py 同步四段版本，Flutter 编译后使用既有 installer/filmstoryboard.iss。双方版本源、exe、安装器保持一致。扩展打包联动 smoke，要求回执 workflow_ready=true 且三个节点脚本快照已在首次导出时保存，无需页面请求。

## 文件 / 模块清单
- 两端既有版本源、更新说明。
- SHIYIN tools/smoke-film-workflow-packaged.py。
- dist/installer/SHIYIN-AI-Setup-1.0.422.exe 与校验文件。
- E:/APP/film/filmstoryboard/dist/installer/filmstoryboard-Setup-1.1.0.375.exe 与校验文件。

## 验收标准
- 两端安装器真实生成，版本与源码一致。
- SHA-256 校验文件匹配实际安装器。
- SHIYIN runtime smoke 和冻结后端后台直连测试通过。
- film 正式构建及安装器依赖完整性校验通过。
- 既有用户改动、安装目录和用户数据不被覆盖。

## 已知问题
当前无阻塞。沿用未签名安装器交付方式。

## 接力信息
[CODEX_LONG_TASK_CONTINUE_V3]
读取项目规则、本文件及任务 094，检查两仓库状态，从“下一步”继续；不重复递增版本，不覆盖既有改动。
