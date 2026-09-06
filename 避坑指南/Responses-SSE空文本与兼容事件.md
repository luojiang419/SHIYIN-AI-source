# Responses SSE 空文本与兼容事件

## 问题表现

调用 Responses 协议进行图片分析或提示词自动解析时，上游返回 HTTP 200，但软件偶发提示“Responses 上游未返回有效文本”。用户再次点击相同操作有时又能成功。

## 触发条件

- 第三方兼容网关使用 SSE 返回 Responses 请求
- 上游流在 `response.created` 后提前结束，或返回 completed 但没有文本
- 网关使用 `response.content_part.done`、`response.output_item.done`、嵌套 `data` 等兼容事件
- Responses endpoint 实际返回 Chat Completions 风格的 `choices[].delta.content`
- 非 SSE 响应被包装在 APIMart 风格的 `{code, data}` 中

## 根本原因

1. HTTP 200 只表示流连接成功，不代表已经得到可交付文本。
2. 只聚合 `response.output_text.delta/done` 会遗漏兼容网关的其他合法文本载体。
3. 原请求循环对 524 和网络错误有重试，但流正常结束后抛出的“无有效文本”502 直接返回给用户，没有利用同一重试预算。
4. 非流式 Responses 文本解析没有先解开 APIMart `data` 包装。

## 无效尝试

- 只检查响应是否为 HTTP 200。
- 只判断最终对象是否存在 `output` 字段；空数组或只有工具调用仍可能没有文本。
- 仅支持标准 `response.output_text.delta`。
- 把所有 4xx/5xx 都无差别重试，会对鉴权和参数错误产生重复请求。
- 看到单元测试中标准 SSE 成功，就认为第三方网关兼容已经完整。

## 正确解决方案

1. 将“HTTP 200 但空响应、无法解析、不完整状态、无文本”归类为内部瞬时输出错误。
2. 兼容标准 output text、content part、output item、嵌套 data、Chat delta 和 APIMart data 包装。
3. 最终统一调用 Responses 文本提取器验证，不能只看字段是否存在。
4. 瞬时输出错误复用有限重试预算和退避；524、网络中断继续重试，其他 HTTP 状态直接返回。
5. 连续失败后提示实际尝试次数和自动重试次数，避免向用户暴露模糊的单次空文本错误。

## 验证方法

- 标准 `response.output_text.delta` 能聚合完整文本和 usage。
- 嵌套 `data.response.content_part.done` 能提取文本。
- `response.output_item.done` 能提取 message content。
- `choices[].delta.content` 能作为兼容 fallback。
- 第一次空流、第二次正常时请求自动成功，且确认请求次数为 2。
- 连续空流达到上限后返回 502，并包含总尝试次数和重试次数。
- 完整项目测试通过，确认共享 Responses 传输层没有破坏其他 AI 流程。

## 如何避免

- 新增 Responses 网关时用真实响应样例补充事件形态测试。
- 区分“连接成功”“任务完成”“存在可交付文本”三个状态。
- 重试只覆盖没有产生可交付结果的瞬时失败，不覆盖明确的鉴权和参数错误。
- 修改共享 LLM 传输层后必须执行全量测试。

## 影响模块

- `main.py::request_responses_stream_json`
- `main.py::request_llm_json`
- `main.py::text_from_responses_response`
- AI 助手、视频提示词自动解析、提示词润色及其他 Responses 视觉请求
