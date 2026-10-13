# Chat 接口文档

本文档面向前端开发者，描述 `POST /api/v1/chat` 接口的使用方式。

---

## POST /api/v1/chat — 对话接口

### 1.1 认证

需要携带有效的 Bearer Token：

```
Authorization: Bearer <token>
```

未登录或 Token 无效时返回 `401 Unauthorized`。

### 1.2 请求头

```
Content-Type: application/json
Accept: text/event-stream
```

### 1.3 请求体（JSON）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `message` | `string \| VoiceInput` | ✅ | — | 用户消息；可为纯文本或语音（见下方 VoiceInput） |
| `history` | `ChatMessage[]` | ❌ | `[]` | 历史消息列表（无状态时使用） |
| `conversation_id` | `string \| null` | ❌ | `null` | 会话 ID；传入则续写该会话历史 |
| `stateful` | `boolean` | ❌ | `false` | 是否开启服务端有状态会话；为 `true` 且未传 `conversation_id` 时由服务端自动生成 |
| `model` | `string \| null` | ❌ | 系统默认 | 指定 Chat 模型名称（需与 models 表 name 一致） |
| `model_settings` | `ModelSettings` | ❌ | — | 模型参数（见下文） |
| `agent_name` | `string \| null` | ❌ | — | Agent 标识；指定后使用该 Agent 的提示词和关联工具 |
| `refs` | `ChatRef[]` | ❌ | `[]` | 引用列表（prompt/tool 类型） |
| `context` | `dict \| null` | ❌ | — | 额外上下文；服务端会自动注入 `user_id` |
| `reasoning` | `boolean` | ❌ | `true` | 是否开启思考过程输出 |

#### 1.3.1 ModelSettings

```json
{
  "max_tokens": 4096,
  "temperature": 0.7,
  "top_p": 0.9,
  "frequency_penalty": 0.5,
  "presence_penalty": 0.5
}
```

所有字段均为可选，不传则使用模型默认值。

#### 1.3.2 VoiceInput（语音消息）

当 `message` 为语音时传入此结构：

```json
{
  "type": "voice",
  "data": "<Base64 编码的音频内容>",
  "format": "wav",
  "language": "zh"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `type` | `"voice"` | ✅ | — | 固定值，标识语音输入 |
| `data` | `string` | ✅ | — | Base64 编码的音频内容 |
| `format` | `string` | ❌ | `"wav"` | 音频格式，支持 wav/mp3/m4a 等，用于 Whisper 识别 |
| `language` | `string \| null` | ❌ | `null` | 音频语言 ISO-639-1 代码，如 `zh`、`en`；不传则自动检测 |

#### 1.3.3 ChatMessage（历史消息）

```json
{
  "content": "消息内容",
  "role": "user | assistant"
}
```

`content` 支持：
- 纯文本字符串
- 结构化内容（服务端内部会标准化处理）

#### 1.3.4 ChatRef（引用）

```json
{
  "type": "prompt | tool",
  "value": "引用值",
  "args": {}
}
```

- `type=prompt`：将 `value` 作为提示词注入
- `type=tool`：将 `value` 作为工具名使用

### 1.4 响应格式：SSE 流式

接口返回 `text/event-stream`，每个数据块格式为：

```
data: {...JSON...}

```

前端按行读取 `data:` 前缀的 JSON 即可解析事件。

#### 1.4.1 input 事件（首个事件）

用户发送消息后，服务端首先返回 input 事件，包含本次请求的元信息：

```json
{
  "kind": "input",
  "message": "用户消息文本",
  "agent_name": "my-agent",
  "model": "gpt-4o",
  "reasoning": true,
  "conversation_id": "uuid-xxxx",
  "model_settings": {...},
  "done": true
}
```

#### 1.4.2 text 事件（模型回复）

```json
{"chunk": "这是回复的", "kind": "text", "done": false}
{"chunk": "一部分内容", "kind": "text", "done": false}
{"chunk": "完整内容。", "kind": "text", "done": true}
```

`done: true` 表示文本流结束。

#### 1.4.3 reasoning 事件（思考过程）

```json
{"chunk": "让我思考一下", "kind": "reasoning", "done": false}
{"chunk": "首先...", "kind": "reasoning", "done": false}
{"chunk": "所以答案是...", "kind": "reasoning", "done": true}
```

仅当 `reasoning: true`（默认）时返回。

#### 1.4.4 component 事件（组件渲染请求）

```json
{
  "kind": "component",
  "name": "组件名",
  "props": {"key": "value"},
  "done": true
}
```

前端可据此动态渲染对应组件。

#### 1.4.5 action 事件（操作请求）

```json
{
  "kind": "action",
  "name": "操作名",
  "payload": {"key": "value"},
  "done": true
}
```

前端可据此触发对应动作，如跳转、打开弹窗等。

#### 1.4.6 tool 事件（工具调用）

```json
{"kind": "tool_start", "name": "search", "inputs": {"query": "xxx"}}
{"kind": "tool_end", "name": "search", "result": {...}}
```

#### 1.4.7 finished 事件（流式结束）

```json
{"kind": "finished"}
```

收到此事件后表示本次对话流已完全结束。

### 1.5 完整 SSE 事件序列示例

```
data: {"kind": "input", "message": "帮我查一下天气", "agent_name": null, "model": "gpt-4o", "reasoning": true, "conversation_id": "uuid-xxxx", "done": true}

data: {"chunk": "让我先查一下", "kind": "reasoning", "done": false}

data: {"chunk": "好的", "kind": "reasoning", "done": true}

data: {"chunk": "正在查询天气", "kind": "text", "done": false}

data: {"kind": "tool_start", "name": "weather", "inputs": {"city": "北京"}}

data: {"kind": "tool_end", "name": "weather", "result": {"temp": 22, "weather": "晴"}}

data: {"chunk": "北京今天的天气是晴，气温22度。", "kind": "text", "done": true}

data: {"kind": "finished"}
```

---

## 三、关键行为说明

### 3.1 有状态与会话管理

- **无状态**：不传 `conversation_id`，所有历史由前端通过 `history` 字段维护
- **有状态**：服务端自动管理会话历史
  - `stateful: true` + 无 `conversation_id`：服务端创��新会话并生成 `conversation_id`
  - 有 `conversation_id` 且用户已登录：服务端续写该会话历史
  - 新会话时后台异步生成标题

### 3.2 语音输入

后端自动调用 Whisper 模型将语音转为文字，再作为普通文本消息处理。前端无需关心识别细节。

### 3.3 Agent 模式

通过 `agent_name` 字段指定 Agent，系统会自动：
- 加载该 Agent 的系统提示词
- 绑定对应的 MCP 工具集
- 激活关联的技能（Skill）

### 3.4 记忆系统

向量记忆由服务端自动管理：
- 根据 `agent_name` 和 `user_id` 加载相关记忆
- 自动注入到模型上下文
- 前端无需传递 `context.memory`

### 3.5 错误处理

SSE 流中遇到服务端异常时，会发送错误事件：

```json
{"chunk": "Error: 错误描述", "kind": "error"}
```

建议前端在收到 `error` 类型的 chunk 时展示用户友好的错误提示，并以 `finished` 结束流式处理。

---

## 四、前端集成示例

### 4.1 文本对话

```javascript
async function sendMessage(message, conversationId) {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      stateful: true,
      reasoning: true,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n').filter(line => line.startsWith('data: '));

    for (const line of lines) {
      const jsonStr = line.slice(6);
      const event = JSON.parse(jsonStr);

      switch (event.kind) {
        case 'input':
          console.log('输入事件:', event.message);
          break;
        case 'text':
          process.stdout.write(event.chunk);
          if (event.done) console.log('\n--- 文本结束 ---');
          break;
        case 'reasoning':
          process.stdout.write('[思考] ' + event.chunk);
          break;
        case 'component':
          renderComponent(event.name, event.props);
          break;
        case 'action':
          performAction(event.name, event.payload);
          break;
        case 'finished':
          console.log('\n对话结束');
          break;
        case 'error':
          console.error('错误:', event.chunk);
          break;
      }
    }
  }
}
```

### 4.2 语音输入

```javascript
async function sendVoiceMessage(audioBase64, format = 'wav', language = 'zh') {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      message: {
        type: 'voice',
        data: audioBase64,
        format,
        language,
      },
      stateful: true,
    }),
  });
  // 同上文的流式处理逻辑...
}
```

```

---

## 五、类型定义汇总

### 5.1 请求类型

```typescript
interface ChatRequestInput {
  message: string | VoiceInput;
  history?: ChatMessage[];
  conversation_id?: string | null;
  stateful?: boolean;
  model?: string | null;
  model_settings?: ModelSettings | null;
  agent_name?: string | null;
  refs?: ChatRef[];
  context?: Record<string, any> | null;
  reasoning?: boolean;
}

interface VoiceInput {
  type: 'voice';
  data: string;
  format?: string;
  language?: string | null;
}

interface ModelSettings {
  max_tokens?: number;
  temperature?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
}

interface ChatMessage {
  content: any;
  role?: 'user' | 'assistant';
}

interface ChatRef {
  type: 'prompt' | 'tool';
  value: string;
  args?: Record<string, any>;
}
```

### 5.2 SSE 事件类型

```typescript
// input 事件
interface InputEvent {
  kind: 'input';
  message: string;
  agent_name: string | null;
  model: string | null;
  reasoning: boolean;
  conversation_id: string | null;
  model_settings?: ModelSettings;
  done: true;
}

// 文本/思考事件
interface ChunkEvent {
  kind: 'text' | 'reasoning';
  chunk: string;
  done: boolean;
}

// 组件事件
interface ComponentEvent {
  kind: 'component';
  name: string;
  props: Record<string, any>;
  done: true;
}

// 操作事件
interface ActionEvent {
  kind: 'action';
  name: string;
  payload: Record<string, any>;
  done: true;
}

// 工具事件
interface ToolStartEvent {
  kind: 'tool_start';
  name: string;
  inputs: Record<string, any>;
}

interface ToolEndEvent {
  kind: 'tool_end';
  name: string;
  result: any;
}

// 结束事件
interface FinishedEvent {
  kind: 'finished';
}
```
