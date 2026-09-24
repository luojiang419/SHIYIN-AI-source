# LinkFox 首次密钥引导与积分校验

[CODEX_LONG_TASK_CONTINUE_V3]

- 状态：画布首次配置流程已实现并提交，浏览器验证通过。
- 下一步：若需向局域网客户端发布，按现有热更新流程从已验证提交构建。
- TODO：无代码未完成项。
- 最近验证：`node --check` 检查 3 个修改过的 JS、`node tests/support/linkfox_key_setup_browser_check.cjs`、`node tests/support/linkfox_async_unit.cjs`、`node tests/support/linkfox_unified_browser_check.cjs` 及暂存区 `git diff --check` 通过；浏览器截图检查弹窗布局正常。
- branch/commit：`feat/linkfox-mini-fast-balance` / `8c654e15`；推送状态待更新。
- 阻塞：无。

## 目标与实现

用户进入 LinkFox 视频生成节点且尚未配置 API Key 时，画布自动显示密钥弹窗。第一次确定后调用已有 `/api/linkfox-config` 接口，将密钥写入本机安全存储，然后请求 `/api/linkfox/balance`。弹窗滚动显示保存、查询等待、积分结果或错误；只有积分查询成功后，第二次确定才关闭弹窗并继续使用画布。查询失败可修改密钥重试。已有密钥直接显示节点余额，不重复弹窗。

复用现有后端安全存储与积分接口，避免密钥进入画布节点、日志或截图。改动集中在 `static/js/canvas-linkfox-video.js`、配套 CSS、画布平台切换接线和资源版本号。独立浏览器用例模拟首次配置、查询失败、慢速查询滚动进度、重试、成功确认和同页复用；现有双节点浏览器用例覆盖已配置密钥时的平台切换。

## 验收标准

- LinkFox 节点首次显示时，缺密钥自动弹窗；空密钥不能提交。
- 确认后自动保存并查询积分，查询进度可见且日志可滚动；查询失败不显示虚构余额。
- 查询成功显示真实剩余积分；第二次确认关闭弹窗，节点仍可正常工作。
- 已配置密钥时无需再次输入，其他视频平台不受影响。
