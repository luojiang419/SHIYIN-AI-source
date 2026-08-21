# PowerShell 内联 JSON 与正则校验需避免双引号抢解析

## 问题现象

在 PowerShell 中用 `ConvertFrom-Json` 读取 `package-lock.json` 时，空字符串属性名会触发非终止错误；继续执行的脚本可能错误打印“版本一致”。随后用双引号包裹 `node -e` 程序时，正则中的方括号又被 PowerShell 提前解析，产生 `ParserError`。

## 根因

- Windows PowerShell 的 `ConvertFrom-Json` 默认对象模式不接受空字符串属性名。
- PowerShell 双引号字符串会继续解释其中的特殊字符，不适合直接承载包含正则的 JavaScript 程序。
- 未设置终止错误时，校验脚本可能在中间失败后继续输出误导性成功信息。

## 处理方式

- 对 npm 锁文件优先使用 Node 的 `JSON.parse` 做结构化读取。
- 在 PowerShell 中执行 `node -e` 时，用单引号包裹整段 JavaScript，并在 JavaScript 内使用双引号。
- 校验必须以非零退出码失败，不只依赖最后一行文本。

## 本轮验证

最终使用 Node 同时校验 `VERSION`、npm、Tauri、Cargo、后端和更新摘要，六处版本均为 `1.0.230`，命令退出码为 0。
