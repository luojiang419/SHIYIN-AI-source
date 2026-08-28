# 影视制作二级菜单 pointerover 捕获关闭

## 现象

影视制作二级菜单从主菜单触发后，鼠标移动到主菜单或二级菜单内部会立即消失，表现为无法选择二级菜单项。

## 原因

`document` 上的捕获阶段 `pointerover` 监听器会识别影视菜单区域，但在 `inFilm` 分支仍调用 `closeCanvasSubmenu(...)`。由于影视二级菜单被移动到 `document.body`，主菜单触发器和二级菜单内部的 `pointerover` 都会走该分支，导致刚打开就关闭。

## 修复

影视菜单区域命中时只清除延迟关闭计时器并保持展开；只有指针进入其他菜单区域时才调用 `scheduleCanvasSubmenuClose()`。相关回归断言位于 `tests/test_canvas_menu_performance.py`。
