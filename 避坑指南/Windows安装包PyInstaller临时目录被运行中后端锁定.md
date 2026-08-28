# Windows 安装包：PyInstaller 临时目录被运行中后端锁定

## 现象

执行 `npm run installer:build` 时，版本同步检查通过，但清理 `.build/installer/backend-work` 失败，提示 `PYZ-00.pyz` 正被其他进程使用。

## 原因

当前机器上仍运行着已安装版 `D:\Program Files\SHIYIN AI\app\backend\canvas-backend\canvas-backend.exe`（PID 52124）。Windows 文件锁会阻止 PyInstaller 删除临时工作目录，即使该进程并非从项目目录启动。

## 处理

不要直接结束未核验的同名进程，以免丢失用户数据。构建安装包前先让用户关闭 SHIYIN AI，并确认对应路径的 `canvas-backend.exe` 已退出，再重新执行 `npm run installer:build`。本次未强制结束该进程，因此 1.0.344 安装包构建暂未完成。
