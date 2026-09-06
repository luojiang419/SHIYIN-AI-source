# Tauri WebView2 F11 全屏快捷键

## 问题表现

Tauri 2 桌面应用通过 `WebviewWindowBuilder::initialization_script` 注入捕获阶段 `keydown` 监听后，脚本单元模拟通过，但真实 Windows WebView2 窗口按 F11 没有进入全屏。

改用 `tauri-plugin-global-shortcut` 后，热键事件可以收到，但在插件回调内调用 `WebviewWindow::is_focused()` 可能返回 false，即使 Windows 的前台窗口句柄和进程都明确属于当前 Tauri 主窗口。

## 触发条件

- Windows Tauri 2 + WebView2 桌面壳
- 使用 F11 这类宿主级 accelerator
- 从 global-shortcut 事件线程查询 Tauri 窗口焦点
- 自动化测试通过 `SetForegroundWindow` 将窗口置前时更容易暴露焦点状态差异

## 根本原因

1. F11 会被 WebView2/宿主作为 accelerator 处理，不能把页面 DOM `keydown` 当作可靠的窗口级快捷键入口。
2. global-shortcut 回调线程中，Tauri `is_focused()` 返回值可能没有反映 Windows 当前真实前台 HWND。
3. `WebviewWindowBuilder::build()` 刚返回时 `is_focused()` 也可能仍为 false，若据此决定是否首次注册，窗口已经显示但快捷键可能从未注册。

## 无效尝试

- 在每个文档初始化时注入 `window.addEventListener('keydown', ..., true)`，再通过 `window.__TAURI__.core.invoke()` 切换全屏。
- 仅在 `view.is_focused()` 为 true 时进行首次快捷键注册。
- 在 global-shortcut 回调中仅依赖 `window.is_focused()` 判断当前软件是否在前台。
- 只运行 Rust 编译、单元测试或 JavaScript 事件模拟后就判断窗口快捷键已经生效。

## 正确解决方案

1. 使用官方 `tauri-plugin-global-shortcut` 注册无修饰键 `Code::F11`。
2. 主窗口创建完成后立即注册，后续通过 `WindowEvent::Focused` 在失焦时注销、重新聚焦时注册，减少对其他软件 F11 的占用。
3. 回调只处理 `ShortcutState::Pressed`。`global-hotkey` 在 Windows 注册时使用 `MOD_NOREPEAT`，长按不会反复触发。
4. Windows 回调中比较 `WebviewWindow::hwnd()` 与 Win32 `GetForegroundWindow()`；其他平台再回退到 `is_focused()`。
5. 通过 `is_fullscreen()` 读取当前状态，并调用 `set_fullscreen(!current)` 切换。

## 验证方法

必须启动真实桌面壳验证，不能只模拟 DOM 事件：

1. 使用独立数据目录与独立后端端口启动调试桌面实例，避免影响正在运行的开发服务。
2. 记录切换前的窗口矩形、显示器矩形和 `GWL_STYLE`。
3. 第一次 F11 后确认窗口矩形覆盖完整显示器，且标题栏和可调边框样式消失。
4. 第二次 F11 后确认窗口位置、尺寸、标题栏和边框精确恢复。
5. 关闭隔离桌面与后端，确认测试端口释放。

本次实测：普通窗口 `1456×939`，第一次 F11 后为 `1920×1080` 且无标题栏/可调边框，第二次 F11 恢复为原窗口；全屏与恢复断言均通过。

## 如何避免

- 宿主级快捷键优先在桌面壳实现，不依赖 Web 页面键盘事件。
- 涉及焦点、安全范围的逻辑同时检查框架状态与目标平台原生状态。
- 窗口交互功能必须完成真实窗口行为验证，编译和脚本模拟只能作为前置检查。
- global shortcut 不应在软件失焦后继续注册，避免抢占其他应用快捷键。

## 影响模块

- `src-tauri/src/lib.rs`
- Tauri/WebView2 Windows 桌面窗口快捷键
- 使用 `tauri-plugin-global-shortcut` 的焦点与注册生命周期
