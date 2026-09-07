# LinkFox SD2.0 实测与返回数据排查

状态：已完成（真实生成与源码修复；未重新打包）
当前阶段：2/2
最后更新：2026-09-07

## 当前状态

运行中的安装版位于 D:\Program Files\SHIYIN AI，监听 3000。已登录并确认 LinkFox installed/configured 均为 true。工作区分支 feat/film-workflow-canvas，存在其他任务已暂存和未暂存修改，保持原状。
已通过安装版 /api/canvas-video 提交真实 seedance2.0（上游 SEED）5 秒、720p、16:9 测试。第一条 taskId=2096848468580376576，267.37 秒后 FAILED，原始 errorMsg=图片审核不通过，costToken=0。更换无人物的蓝色产品盒测试图后，第二条 176.68 秒返回 HTTP 200，视频 URL=/assets/output/linkfox_1788763097922_1.mp4，已下载并逐帧解码通过。
发现安装路径空格导致错误 JSON 路径正则不匹配；旧脚本 GBK 落盘又与适配器 UTF-8 读取冲突，隐藏平台真实失败原因。源码已修复兼容读取、任务号提示，以及双脚本 UTF-8 响应留存；尚未重新构建安装包。

## 下一步

当前真实生成测试任务已完成，不再重复调用付费生成。源码错误提示修复待后续安装包发布时生效。

## 当前 TODO

- [x] 检查实际程序、配置状态、参数映射和调用链
- [x] 提交真实 5 秒测试
- [x] 收到并验证生成结果
- [x] 定位本次失败原因为图片审核；修复隐藏原因的 Windows 路径与编码错误
- [x] 用户原始画布未提供，不能认定原故障也一定由图片审核导致

## 最近验证状态

- 安装版登录 HTTP 200；能力接口 configured=true。
- 第一条已确认上游接受后审核失败；第二条 HTTP 200，文件 1,745,965 字节。
- 完整解码 121 帧，24fps，1280×720，时长 5.0417 秒，SHA-256=c79990fe2efbb1a34f95ab01e029f4e9ee95bbeef2d529d8df7c42a7a6120e3e。
- 64 项定向测试通过，覆盖安装路径空格、GBK/UTF-8、冻结/非冻结模式，以及两种技能响应留存。
- Python py_compile、git diff --check 通过。
- 修复提交：87d59d7，已正常推送 origin/feat/film-workflow-canvas。其他任务修改保持原状。

## 任务目标与验收

使用已配置 API 实际提交 SD2.0 5 秒视频，收到返回数据并检查文件可读与时长；发现实现错误时最小修复并回归。

## 技术方案与文件

复用安装版统一 /api/canvas-video → LinkFox 图片上传 → 原生异步生成/轮询 → 下载与返回链路。
测试脚本和原始返回位于 .codex-artifacts/linkfox-real-test/，不记录凭据。
源码修改：canvas_core/linkfox_video.py（含空格路径解析、旧 GBK 响应兼容、明确错误和任务号）；两个 LinkFox 底层脚本（UTF-8 响应及提交记录）；tests/test_linkfox_response_errors.py（6 项真实错误形态回归）。

## 已知限制

本次是已安装应用真实 HTTP 调用，没有模拟网关。现有调用在整个生成结束后返回，因此等待期间 UI 仍只有计时；本次不扩展为完整持久化异步任务系统。未重建或替换安装程序；源码修复后续打包生效。成功任务的上游 taskId 未被旧安装版接口透传，不能虚构；成功的响应和可解码文件已保存。

## 接力信息

[CODEX_LONG_TASK_CONTINUE_V3]

先查看本文件、git status 和测试产物；不要重复提交已经接受的付费任务。
