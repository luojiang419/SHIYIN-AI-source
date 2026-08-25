# SHIYIN-AI API 配置与 Responses 原生适配方案 v1

## 1. 目标与范围

本方案解决三个问题：

1. 让 API 平台、鉴权、传输协议、模型能力和业务用途分层管理。
2. 在不破坏现有 OpenAI Chat Completions、Gemini、RunningHub 等配置的前提下，增加原生 Responses。
3. 让视觉模型的“图片理解”和“图片生成”成为可验证、可配置的独立能力，而不是依赖模型名称猜测。

本阶段只覆盖远程 LLM/视觉 API 的配置和调用适配，不改变即梦 CLI、Codex CLI、RunningHub 工作流和本地视觉模型的专用流程。

## 2. 当前实现审计

### 2.1 已有能力

- `main.py:ApiProviderPayload` 已支持平台 ID、名称、Base URL、协议、模型分组、优先级和 Key 更新。
- API Key 不直接存入平台 JSON，保存时写入后端 env，页面只返回 `has_key` 与脱敏预览。
- `/api/providers`、`/api/providers/test-connection`、`/api/providers/fetch-models` 已形成配置管理闭环。
- 平台列表顺序就是优先级，旧的 `primary` 字段继续作为兼容字段。
- 前端 `static/js/api-settings.js` 已有平台拖拽、模型拉取、模型分类和密钥清除流程。

### 2.2 需要改造的耦合点

- `resolve_chat_provider()` 会统一补 `/v1`，并把多个业务入口固定请求到 `/chat/completions`。
- 意图路由、普通聊天、画布 LLM、智能画布等入口分别拼接 `/chat/completions`，协议逻辑无法集中切换。
- OpenAI 兼容探测目前以 `/v1/models` 和空 `messages` 的 `/chat/completions` 为主；没有 Responses 探测和响应解析。
- `protocol` 同时承担“平台协议”和“请求路径协议”的含义，无法表达同一平台同时提供 Chat Completions 与 Responses。
- `chat_models`、`image_models` 仅按用途分组，未保存模型是否支持图片输入、流式输出或工具调用等能力。
- `/v1/models` 不存在的服务会被误判为不可发现；像 `api.3366.ai` 这类服务需要允许手动填写模型名和端点。

## 3. 推荐的配置模型 v2

保留现有平面字段作为兼容层，在内部逐步引入以下结构。数据库中增加 `schema_version: 2`，旧配置读取时即时归一化，不要求一次性迁移全部历史数据。

```json
{
  "schema_version": 2,
  "id": "3366-responses",
  "name": "3366 Responses",
  "enabled": true,
  "priority": 10,
  "base_url": "https://api.3366.ai",
  "auth": {
    "type": "bearer",
    "secret_ref": "API_PROVIDER_3366_RESPONSES_KEY"
  },
  "transports": {
    "responses": {
      "enabled": true,
      "endpoint": "/v1/responses",
      "streaming": true
    },
    "chat_completions": {
      "enabled": false,
      "endpoint": "/v1/chat/completions"
    }
  },
  "models": [
    {
      "id": "供应商实际模型名",
      "roles": ["chat", "vision_input"],
      "transport": "responses",
      "enabled": true
    }
  ]
}
```

### 3.1 字段职责

- `base_url` 只表示服务根地址，不带具体业务路径；允许用户直接填写带 `/v1` 的地址，归一化时不得重复拼接。
- `transports` 表示请求协议和端点，不再用 `protocol=openai` 推断路径。
- `models[].roles` 表示模型能力。`vision_input` 代表能接收图片，不代表能生成图片；图片生成应使用 `image_generation` 角色。
- `secret_ref` 只保存 env 名称，绝不把密钥写入平台 JSON、运行时配置或日志。
- `priority` 继续兼容列表顺序和 `primary`，后续可增加 `role_priority`，让聊天、视觉理解、图片生成分别排序。

### 3.2 与现有字段的兼容映射

| 现有字段 | v2 映射 | 兼容策略 |
| --- | --- | --- |
| `protocol=openai` | `transports.chat_completions` | 默认保持 Chat Completions，不自动改成 Responses |
| `protocol=gemini` | Gemini 专用 transport | 保留现有固定协议分支 |
| `chat_models` | `models[].roles=[chat]` | 读取时生成，保存时同时写回旧字段 |
| `image_models` | `models[].roles=[image_generation]` | 不把图片生成模型误标为视觉输入模型 |
| `model_protocols` | `models[].transport` | 继续支持单模型协议覆盖 |
| `base_url` | transport endpoint 的根 | 统一 URL 拼接函数处理 `/v1`、`/v1beta` |
| `api_key` | `auth.secret_ref` 对应 env | 继续使用现有脱敏、清除和轮换流程 |

## 4. Responses 请求适配层

### 4.1 集中网关

新增 `canvas_core/ai_gateway.py`，不要继续在 `main.py` 的业务函数中拼接 URL。网关至少提供：

```python
await gateway.generate_text(
    provider_id, model, messages, images=None, stream=False
)
await gateway.analyze_image(
    provider_id, model, prompt, images, stream=False
)
```

内部按 transport 分发：

- `chat_completions`：生成 `messages`，解析 `choices[0].message.content`。
- `responses`：生成 `input`，解析 `output_text` 或 `output[].content[]`。
- `gemini`、RunningHub、Codex CLI 等专用协议继续走现有适配器。

第一阶段只迁移普通聊天、意图路由和画布 LLM 三条链路；图片生成和视频链路保持现状，待网关稳定后再迁移。

### 4.2 原生 Responses 请求格式

文本请求：

```json
{
  "model": "供应商实际模型名",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "用户消息"}
      ]
    }
  ],
  "stream": false
}
```

视觉请求：

```json
{
  "model": "支持视觉的模型名",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "请描述这张图片"},
        {
          "type": "input_image",
          "image_url": "https://example.com/image.jpg",
          "detail": "auto"
        }
      ]
    }
  ]
}
```

图片引用需要统一转换为可访问 URL 或 data URL。转换失败时应返回“图片无法上传/访问”的可读错误，不要把原始本地路径发送给上游。

### 4.3 响应解析

解析器按以下顺序取文本：

1. 顶层 `output_text`；
2. `output` 中 `type=message` 的 `content[].type=output_text`；
3. 兼容部分代理返回的 `choices[].message.content`。

同时保留 `response.id`、`usage`、`model` 和原始响应的安全摘要，禁止把 Authorization、完整输入图片 data URL 或密钥写入日志。

## 5. URL 与端点规则

新增一个唯一的端点拼接函数，所有探测和业务请求共用：

```text
用户填 https://api.3366.ai       + /v1/responses -> https://api.3366.ai/v1/responses
用户填 https://api.3366.ai/v1    + /responses    -> https://api.3366.ai/v1/responses
用户填 https://api.3366.ai/v1/   + /v1/responses -> https://api.3366.ai/v1/responses
```

规则：

- 端点可以是相对路径或完整 `http(s)` URL。
- 禁止查询参数、片段、用户名和密码出现在 Base URL。
- 禁止把 `/v1` 重复拼成 `/v1/v1`。
- `responses_endpoint` 允许显式覆盖默认 `/v1/responses`，以兼容第三方网关。

## 6. 连通性探测和模型管理

### 6.1 探测顺序

1. 校验 Base URL 和密钥是否为空。
2. 若服务实现 `/models`，拉取模型列表并允许用户手动修正分类。
3. 若 `/models` 返回 404，不能直接判定失败；改为请求 Responses 端点的最小无副作用探测，区分 401、400、404 和 5xx。
4. 只有收到 401/403 才显示鉴权失败；400 且提示缺少 `model` 或 `input` 时，说明端点存在。
5. 视觉能力必须通过模型配置或用户发起的明确视觉测试确认，不根据 `vl`、`vision` 等名称自动下结论。

### 6.2 手动模型入口

模型列表拉取失败时，界面仍提供“手动添加模型”。每个模型至少选择：

- 对话；
- 图片理解；
- 图片生成；
- 使用的 transport。

保存时不能因为 `/models` 不可用而清空用户已配置模型。

## 7. API 设置页改造

### 7.1 平台编辑器

保留现有平台列表和拖拽优先级，编辑区拆为四个区块：

1. **基本信息**：名称、唯一 ID、Base URL、启用状态。
2. **鉴权**：Bearer/API Key 类型、密钥输入、保留当前 Key、轮换、清除；页面只显示脱敏预览。
3. **传输协议**：Chat Completions、Responses、Gemini/专用协议，可同时启用多个协议；每个协议显示端点路径和流式开关。
4. **模型与能力**：模型 ID、用途标签、transport、启用状态。模型列表拉取和手动添加共存。

新增 3366 Responses 时建议填写：

- 名称：`3366 Responses`；
- Base URL：`https://api.3366.ai`；
- transport：`Responses`；
- endpoint：默认 `/v1/responses`；
- 模型：填写服务商提供的实际模型名；
- 能力：按服务商文档勾选 `图片理解`，不要默认勾选图片生成。

### 7.2 验证按钮

现有“验证地址”拆成两级结果：

- **端点验证**：只验证地址、鉴权和协议可达性；
- **能力测试**：用户主动选择模型并上传一张图片，验证 `input_image` 是否可用。

能力测试必须明确提示会产生上游调用费用，不得在页面加载或保存配置时自动发起。

## 8. 安全与密钥管理

- 延续现有 env 存储策略，新增平台沿用 `API_PROVIDER_<ID>_KEY`，ID 归一化后生成。
- API 返回只包含 `has_key`、脱敏预览和 env 名称；运行时配置不包含 Base URL、Key 或 secret_ref。
- 日志统一过滤 `Authorization`、`api_key`、`data:image/...;base64` 和完整请求头。
- 导入/导出配置时只导出 `secret_ref` 和 `has_key`，禁止导出密钥。
- 密钥更新使用“空值保持原 Key、勾选清除才删除”的语义，避免自动保存时误删。
- 用户在聊天中粘贴密钥时不写入对话记录；本次公开过的密钥应先撤销再测试。

## 9. 分阶段实施

### 阶段 A：协议与数据层

- 增加 schema v2 归一化函数和旧配置兼容读取。
- 增加 Responses endpoint URL 规范化。
- 增加 `responses` transport 常量和 `ApiProviderPayload` 字段。
- 新增单元测试，不改变现有请求路径。

### 阶段 B：网关与探测

- 新增 `canvas_core/ai_gateway.py` 和 Responses 请求/响应适配器。
- 将 `resolve_chat_provider` 改为返回结构化 transport 配置，而非仅返回 URL、headers、model。
- 迁移普通聊天、意图路由、画布 LLM。
- 增加 Responses 端点探测和无 `/models` 的手动模型流程。

### 阶段 C：设置页

- 增加 Responses 协议选择、端点覆盖、模型能力标签和手动模型入口。
- 保留现有平台拖拽、旧字段、密钥脱敏和自动保存行为。
- 增加视觉能力测试按钮，默认不自动调用。

### 阶段 D：扩展业务链路

- 在需要图片理解的节点中使用 `vision_input` 能力选择器。
- 迁移需要多模态输入的图片编辑/分析链路。
- 最后再评估流式 Responses、工具调用、`previous_response_id` 和后台任务能力。

## 10. 验收标准

### 配置兼容

- 现有配置文件读取后字段不丢失，旧平台仍按原协议工作。
- 保存新配置不会把 Key 写入 JSON 或前端响应。
- Base URL 不会出现 `/v1/v1`、`/v1beta/v1beta` 等重复路径。

### Responses

- 纯文本 Responses 请求成功，能解析 `output_text`。
- 带 `input_image` 的请求成功时能返回图片分析文本。
- Responses 端点返回 400/401/404/5xx 时，界面给出不同且可操作的提示。
- `/models` 404 时，仍能手动添加模型并调用。

### 回归

- 现有 Chat Completions、Gemini、RunningHub、Codex CLI 测试全部通过。
- 普通聊天、智能画布、意图路由至少各有一个 Responses mock 测试。
- `pytest -q`、前端 `node --check`、`git diff --check` 通过。
- 完成一个大模块后生成进度快照和源码差异备份；版本号递增并同步发布说明。

## 11. 建议的首个落地切片

先实现“阶段 A + 阶段 B 的纯文本子集”，即：

1. 新增 `request_protocol=responses` 和 `responses_endpoint`，但保留全部旧字段。
2. 只迁移普通聊天到网关，使用 mock 验证请求体和解析器。
3. 再加入 `input_image` 和视觉能力标签。

这样可以先验证 `api.3366.ai/v1/responses` 的真实模型名、鉴权和返回结构，不会同时改动图片生成、视频任务和现有专用平台。

