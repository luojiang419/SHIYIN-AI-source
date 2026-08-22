# Windows PowerShell 调用 Python 快照脚本中文参数编码

## 现象

在 Windows PowerShell 5.1 中直接向 Python 快照脚本传递包含中文和中文标点的长参数时，Python 端收到乱码，并可能把乱码拆成额外参数，导致 `argparse` 报 `unrecognized arguments`。

## 原因

PowerShell 5.1 启动外部 Python 进程时，命令行参数编码不一定按 UTF-8 传递；即使文件本身是 UTF-8，进程 argv 仍可能出现系统代码页转换。

## 处理方式

快照脚本调用阶段使用简短 ASCII 参数保证文件稳定生成；需要补充中文说明时，再通过 UTF-8 文件编辑工具修改快照内容。不要把长中文段落直接拼入 PowerShell 外部进程命令行。

## 复用规则

以后在 Windows PowerShell 下运行 Python 文档生成脚本时，优先传 ASCII 标题/摘要，或改用脚本读取 UTF-8 输入文件，避免依赖命令行中文 argv 编码。
