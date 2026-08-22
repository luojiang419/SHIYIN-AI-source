# PowerShell foreach 结果需先赋值再接管道

## 现象

在 PowerShell 中直接把语句级 `foreach (...) { ... }` 后面接 `| Format-Table`，解析器报错：`An empty pipe element is not allowed`。

## 原因

`foreach` 语句不是可直接放在该管道位置的表达式；右花括号后的管道会被解析成缺少左侧输入。

## 正确做法

先把循环结果收集到明确变量，再把变量送入管道：

```powershell
$probeResults = @()
foreach ($port in $ports) {
    $probeResults += [pscustomobject]@{ Port = $port }
}
$probeResults | Format-Table -AutoSize
```

如果只需流式输出，也可以用 `$ports | ForEach-Object { ... } | Format-Table`。
