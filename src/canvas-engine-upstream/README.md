# 上游无限画布核心来源

- 来源：`https://github.com/tigerowo/infinite-canvas`
- 固定版本：`f30b8d7f8a01573d0332c98f214f4bf4d1e3de14`
- 上游文件：`web/src/app/(user)/canvas/components/infinite-canvas.tsx`
- 上游许可：AGPL-3.0，完整文本见本目录 `LICENSE`

`infinite-canvas.tsx` 保留上游 React 视口容器与平移调度，适配了本项目的主题、画布 DOM ID、滚轮步进、节点手势和全尺寸样式。`bridge.tsx` 接入上游编辑页按视口挂载节点的规则，保留本项目现有工程数据、节点内容及业务事件。

本项目现有 `LICENSE` 含商业使用限制。用户已选择保留现有许可并取得上游另行授权；在取得相应书面授权前，不推送或发布本目录源码及其编译产物。
