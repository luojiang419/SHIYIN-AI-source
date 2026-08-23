# 进度快照 578：GitHub 正式发布 1.0.272 安装包

## 已完成内容

- 已在桌面端更新器实际读取的公开仓库 `luojiang419/SHIYIN-AI` 发布正式版 `v1.0.272`。
- Release 地址：<https://github.com/luojiang419/SHIYIN-AI/releases/tag/v1.0.272>。
- 发布资产严格为：
  - `SHIYIN-AI-Setup-1.0.272.exe`（`69,723,246` 字节）；
  - `SHIYIN-AI-Setup-1.0.272.exe.sha256`（`94` 字节）。
- GitHub 资产摘要、本地 EXE SHA-256 和公开下载的 `.sha256` 文件三者一致：`5f3ecf74a05031411cfc7356db637965dbb0e89eb2e19a927feb7d93e375ffbf`。
- `releases/latest` 已返回 `v1.0.272`，且 Release 不是草稿、不是预发布版；桌面更新器可按既有精确命名契约发现并下载该安装包。
- 发布仓库的 `main` 与 `refs/tags/v1.0.272` 均指向清单提交 `283d079ad9c4bf5ac003ed527fee9a2ef3a6f3d5`；清单记录源仓库提交 `8bc93bfa5700b9025b910e20bd8a3727141d62ee`。
- 新增 PowerShell 校验下载内容的兼容性避坑记录：`.sha256` 响应可能返回字节数组，比较前需显式 UTF-8 解码。

## 当前修改模块

- GitHub 更新仓库：`luojiang419/SHIYIN-AI` 的 `v1.0.272` Release 与 `releases/v1.0.272.json` 发布清单。
- 源码仓库：`release-notes/current.md`、本快照和校验下载兼容性说明。

## 发布前后对比

```diff
- releases/latest -> v1.0.269
+ releases/latest -> v1.0.272
+ Release assets: SHIYIN-AI-Setup-1.0.272.exe + .sha256
+ EXE digest: sha256:5f3ecf74a05031411cfc7356db637965dbb0e89eb2e19a927feb7d93e375ffbf
```

## 待办清单

- [x] 发布 1.0.272 Windows 安装包到 GitHub 更新仓库。
- [x] 核验最新 Release、标签、清单、资产大小、资产摘要及独立校验文件。
- [x] 清理构建阶段临时目录；仅保留可复用构建缓存与 1.0.271/1.0.272 安装包。
- [ ] 如需消除 Windows SmartScreen 的未签名提示，后续配置代码签名证书并重新发布签名版安装包。

## 下一步

用户可从 Release 页面下载安装包；已安装旧版桌面端将在下一次自动或手动检查更新时发现 `v1.0.272`。
