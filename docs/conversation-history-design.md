# 对话历史持久化 — 设计文档

> 版本：v7　|　日期：2026-07-21　|　状态：待实现

## 1. 目标

为当前 Agent 服务增加对话历史持久化能力，采用“会话表 + 事件表 + 内存/Redis 运行态”的模型，支持：

- 多轮对话上下文自动加载
- 按 `conversation_id` 恢复对话
- 按 `agent_key` 隔离会话历史：前端切换不同 Agent 时只展示对应 Agent 的聊天记录
- 会话列表、详情与删除
- SSE 事件持久化回放，前端可直接按事件重建 UI
- 后台执行：客户端断开后 Agent 继续运行，并把结果写入 DB
- 归属绑定：Session 用户 → `user_id`，API Key → `api_key_id`
- 管理员全局查询：独立管理入口，按用户、API Key、Agent、关键词、日期范围分页筛选

## 2. 总体方案

历史记录不再拆成 `role + content + tool_calls` 的消息行，而是持久化当前项目已经在前后端之间流转的事件流：

```
conversations              conversation_events
会话元数据                   事件流 — 每行一个事件
id / title / agent_key      用户 input + 每个 SSE 事件单独一行
user_id / api_key_id        纯追加写入，不 UPDATE
last_active_at 用于列表排序    自增 id 用于顺序回放
                             task_id 在 JSONB 内关联同一轮事件
```

核心原则：

- `conversations` 只存会话归属和列表查询所需字段。
- `conversation_events` 中每行只存一个事件，用户输入和每个 SSE 事件（`message_start`、`tool_start`、`message`、`message_end` 等）各占一行。
- 写入模式为纯追加（INSERT only），后台每产生一个 SSE 事件就 INSERT 一行，不对已有行做 UPDATE，彻底消除 MVCC 膨胀。
- `task_id` 保留在 JSONB 内，不作为表列。同一轮 AI 回复的所有事件共享同一个 `task_id`，前端回放时按 `task_id` 归组。
- 前端详情页按 `id ASC` 顺序读取事件流，按 `type` 分发、按 `task_id` 归组，重建聊天 UI。
- LLM 历史上下文从事件流中按 `task_id` 归组后抽取 `input` + `message` 得到，而不是从单独 message 表读取。
- Redis Pub/Sub 只负责实时转发，DB 是最终状态来源。

## 3. 数据模型

### 3.1 `conversations` 会话表

旧项目使用 `sys_users.id`；当前项目用户表为 `users`，并且还支持 API Key 调用，因此保留 `user_id` / `api_key_id` 互斥归属。

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | UUID | PK，默认 `uuid4` | 主键 |
| `user_id` | UUID? | FK → `users.id`，INDEX | Session 用户会话 |
| `api_key_id` | UUID? | FK → `api_keys.id`，INDEX | API Key 会话 |
| `name` | VARCHAR(256) | 对话名称(首次ai生成后自动命名) | |
| `agent_key` | VARCHAR(64) | DEFAULT `''`，INDEX | 会话所属 Agent，首页列表按它隔离展示 |
| `is_deleted` | bool | NOT NULL | 软删除标记 |
| `created_at` | TIMESTAMP(6) | NOT NULL | 创建时间 |
| `last_active_at` | TIMESTAMP(6) | NOT NULL | 每次追加事件时更新 |

约束：

- `user_id` 和 `api_key_id` 互斥：`(user_id IS NULL) <> (api_key_id IS NULL)`。
- 删除会话时级联删除对应 `conversation_events`。

索引：

| 索引 | 字段 | 用途 |
|---|---|---|
| `ix_conversations_user_id` | `user_id` | 按用户过滤 |
| `ix_conversations_api_key_id` | `api_key_id` | 按 API Key 过滤 |
| `ix_conversations_user_last_active_id` | `(user_id, last_active_at DESC, id DESC)` | 用户会话分页 |
| `ix_conversations_api_key_last_active_id` | `(api_key_id, last_active_at DESC, id DESC)` | API Key 会话分页 |
| `ix_conversations_last_active_id` | `(last_active_at DESC, id DESC)` | 管理员全局分页 |

### 3.2 `conversation_events` 事件表

每条事件独立一行，纯追加写入。用户输入一行；后端每个 SSE 事件（`message_start`、`message`、`tool_start`、`tool_end`、`message_end` 等）各占一行。同一轮 AI 回复的所有事件在 JSONB 内共享同一个 `task_id`。

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | 自增 PK | 事件自增序号，作为稳定排序键 |
| `conversation_id` | UUID | FK → `conversations.id`，NOT NULL，INDEX | 所属会话 |
| `event` | JSONB | NOT NULL | 单个事件负载，每行只存一个事件 |
| `created_at` | TIMESTAMP(6) | NOT NULL | 事件产生时间 |

`event` 保存规则：

- **每行一个事件**，纯 INSERT，不 UPDATE。
- `task_id` 保留在 JSONB 内，不作为表列。每个事件都携带 `task_id`，同一轮 AI 回复的所有事件共享同一个 `task_id`。
- 不把 `message`、`content`、`name`、`input`、`output`、`task_id` 等拆成事件表列；这些字段都保留在 JSONB 内。
- 对外详情接口直接返回按 `id ASC` 排序的事件负载数组，数据库行 `id` 不返回。
- 后端读取时按 `conversation_events.id ASC` 排序，保证回放顺序。

保存示例 — 一次"查北京天气 → 调工具 → 返回结果"的对话，每行一个事件：

```json
[
  {"type":"input",      "task_id":"t1","message":"帮我查一下北京天气","agent_key":"default","done":true},
  {"type":"message_start","task_id":"t1"},
  {"type":"tool_start",   "task_id":"t1","name":"get_weather","input":{"city":"北京"}},
  {"type":"tool_end",     "task_id":"t1","name":"get_weather","output":{"temp":25,"desc":"晴"}},
  {"type":"message",      "task_id":"t1","content":"北京今天晴天，25°C"},
  {"type":"message_end",  "task_id":"t1","status":"completed"},
  {"type":"input",        "task_id":"t2","message":"那明天呢","agent_key":"default","done":true},
  {"type":"message_start","task_id":"t2"},
  {"type":"tool_start",   "task_id":"t2","name":"get_weather","input":{"city":"北京","day":"tomorrow"}},
  {"type":"tool_end",     "task_id":"t2","name":"get_weather","output":{"temp":22,"desc":"多云"}},
  {"type":"message",      "task_id":"t2","content":"明天北京多云，22°C"},
  {"type":"message_end",  "task_id":"t2","status":"completed"}
]
```

索引：

| 索引 | 字段 | 用途 |
|---|---|---|
| `ix_conversation_events_conversation_id` | `conversation_id` | 按会话过滤事件 |
| `ix_conversation_events_conversation_id_id` | `(conversation_id, id)` | 按追加顺序稳定回放 |
| `ix_conversation_events_event_gin` | `event` GIN | 管理员关键词检索 + 按 `task_id` 查找（stop / 重连），按需添加 |

> 需要按 `task_id` 精确查找时，GIN 索引配合 `event @> '{"task_id": "xxx"}'` 即可定位相关事件，不需要把 `task_id` 提到表列再建 B-tree 索引。

### 3.3 事件类型

所有事件平铺在事件流中，每行一个，按 `type` 区分种类。前端读取历史时复用现有映射逻辑将 `type` 转换为 UI `kind`。

| `type` | `role` | 含义 | 核心字段 |
|---|---|---|---|
| `input` | `user` | 用户输入 | `task_id`, `message`, `agent_key`, `model`, `done` |
| `message_start` | `assistant` | AI 回复开始 | `task_id` |
| `message` | `assistant` | 模型文本 chunk | `task_id`, `content` |
| `reasoning` | `assistant` | 模型推理/思考 chunk | `task_id`, `content` |
| `tool_start` | `assistant` | 工具调用开始 | `task_id`, `name`, `input` |
| `tool_end` | `assistant` | 工具调用结束 | `task_id`, `name`, `output` |
| `skill` | `system` | 技能激活结果 | `task_id`, `skills` |
| `message_end` | `assistant` | 本轮正常结束 | `task_id`, `status="completed"` |
| `interrupted` | `assistant` | 用户主动停止 | `task_id`, `status="stopped"` |
| `error` | `assistant` | 本轮异常结束 | `task_id`, `detail`, `status="failed"` |

> `message_start` 到 `message_end` / `interrupted` / `error` 之间、共享同一 `task_id` 的事件属于同一个 AI 回复。前端按 `task_id` 归组，遇到 `message_start` 创建新的 assistant 消息，遇到 `message_end` / `interrupted` / `error` 结束当前 assistant 消息。

## 4. 事件回放与上下文构建

### 4.1 前端回放

`GET /conversations/{id}` 返回按 `id ASC` 排序的平铺事件数组。事件表的自增 `id` 只用于 DB 内部排序，不返回给前端。前端按 `type` 分发 + `task_id` 归组重建聊天 UI。

1. 按 `id ASC` 读取事件负载。
2. 遇到 `type="input"` 创建一条 user 消息。
3. 遇到 `type="message_start"` 创建一条新的 assistant 消息（同一 `task_id` 的后续 `message`、`tool_start`、`tool_end`、`reasoning`、`skill` 事件都归入此 assistant 消息）。
4. 遇到 `type="message"` 追加文本到当前 assistant 消息。
5. 遇到 `type="reasoning"` 追加思考内容（折叠区）。
6. 遇到 `type="tool_start"` 追加工具调用卡片（loading 态）。
7. 遇到 `type="tool_end"` 完成对应工具调用卡片。
8. 遇到 `type="skill"` 追加技能激活提示。
9. 遇到 `type="message_end"` / `interrupted` / `error` 结束当前 assistant 消息并设置完成/停止/异常状态。
10. 遇到新的 `type="input"` 时，上一轮 assistant 消息自动截止（如果没收到结束事件），开始新一轮对话。

### 4.2 LLM 历史上下文

加载历史时不把所有 UI 事件原样塞给模型，而是从事件流中按 `task_id` 归组后抽取最近 N 轮对话，归并出 LangChain 消息：

| 遇到的事件（同一 `task_id` 内） | LangChain 消息 |
|---|---|
| `type="input"` | `HumanMessage(content=message)` |
| `type="message"` chunks | 拼接为 `AIMessage(content=text)` |
| `tool_start` + `tool_end` | 可还原为 `AIMessage(tool_calls=...)` + `ToolMessage(...)` |
| `reasoning` | 思考过程事件，默认不注入模型上下文 |
| `skill` | 技能激活事件，默认不注入模型上下文 |
| `message_end` / `interrupted` / `error` | 任务状态事件，默认不注入模型上下文 |

MVP 可先只注入用户 `input` + AI `message` 文本，保证多轮对话连续；工具事件完整存储，后续如需高保真回放工具链，再按 `tool_start/tool_end` 还原为工具上下文。

技能选择仍仅基于当前用户输入，避免历史上下文干扰技能路由。

## 5. API 设计

所有端点挂在 `/agent/v1` 下。

### 5.1 新增端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/conversations` | 会话列表 |
| `GET` | `/conversations/{id}` | 会话详情，返回平铺事件流 |
| `DELETE` | `/conversations/{id}` | 删除会话，级联删除事件 |
| `POST` | `/conversations/batch-delete` | 批量删除会话，级联删除事件 |
| `GET` | `/admin/conversations` | 管理员全局会话列表 |
| `GET` | `/admin/conversations/{id}` | 管理员查看任意会话详情 |
| `GET` | `/chat-messages/{task_id}/events` | 可选：重连实时事件流 |
| `POST` | `/chat-messages/{task_id}/stop` | 停止正在执行的后台任务 |

> 会话不提供单独的“创建空会话”接口。首轮聊天请求 `POST /chat-messages` 在 `stateful=true` 且未传 `conversation_id` 时自动创建会话，并通过首个 `input` 事件返回 `conversation_id`。

#### `GET /conversations`

首页/普通会话列表入口。普通用户、API Key、管理员都只返回当前身份自己的会话；管理员全局查询走 `/admin/conversations`。

| 参数 | 类型 | 默认 | 谁可用 | 说明 |
|---|---|---|---|---|
| `agent_key` | string | — | 所有人 | 当前页面选中的 Agent，必填 |
| `page` | int | `1` | 所有人 | 页码 |
| `page_size` | int | `20` | 所有人 | 每页条数，1–100 |

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "帮我写一个 Python 脚本"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

#### `GET /conversations/{id}`

返回当前身份有权访问的平铺事件流数组。管理员在首页侧也只看自己的会话；查看任意会话详情使用 `/admin/conversations/{id}`。

```json
{
  "id": "uuid",
  "events": [
    {"type":"input","task_id":"t1","message":"帮我查一下北京天气","agent_key":"default","done":true},
    {"type":"message_start","task_id":"t1"},
    {"type":"tool_start","task_id":"t1","name":"get_weather","input":{"city":"北京"}},
    {"type":"tool_end","task_id":"t1","name":"get_weather","output":{"temp":25,"desc":"晴"}},
    {"type":"message","task_id":"t1","content":"北京今天晴天，25°C"},
    {"type":"message_end","task_id":"t1","status":"completed"}
  ]
}
```

#### `POST /conversations/batch-delete`

批量删除当前身份有权访问的会话及其事件。普通用户/API Key/管理员在首页侧都只能删除自己归属的会话。请求中包含无权限或不存在的 ID 时不整体失败，逐条返回结果，方便前端批量操作后局部刷新。

Request:

```json
{
  "ids": ["uuid-1", "uuid-2"]
}
```

Response:

```json
{
  "deleted": ["uuid-1"],
  "not_found": ["uuid-2"],
  "forbidden": []
}
```

约束：

- `ids` 非空，单次最多 100 个。
- 删除成功的会话级联删除 `conversation_events`。
- 若会话存在 running task，应先尝试停止任务并写入 `interrupted` 事件，再删除会话；如果任务已不在本进程/Redis meta 中，则直接删除 DB 记录。

#### `GET /admin/conversations`

管理员全局查询入口，仅 `role="admin"` 的 Session 用户可访问。这个接口不用于首页聊天记录列表，而是用于管理后台/审计视图。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `user_id` | UUID? | — | 按 Session 用户过滤 |
| `api_key_id` | UUID? | — | 按 API Key 过滤 |
| `agent_key` | string? | — | 按 Agent 过滤 |
| `keyword` | string? | — | 搜索标题或事件文本 |
| `start_date` | ISO 8601? | — | `created_at >=` |
| `end_date` | ISO 8601? | — | `created_at <=` |
| `page` | int | `1` | 页码 |
| `page_size` | int | `20` | 每页条数，1–100 |

Response 基于 `GET /conversations` 的列表项额外返回管理字段，用于管理员识别和审计：

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "帮我写一个 Python 脚本",
      "agent_key": "default",
      "owner": {"type": "user", "id": "uuid", "name": "zhangsan", "account": "zhangsan"},
      "created_at": "2026-06-26T10:00:00",
      "last_active_at": "2026-06-26T10:05:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

#### `GET /admin/conversations/{id}`

管理员查看任意会话详情。响应在 `GET /conversations/{id}` 的历史内容基础上额外返回管理字段：

```json
{
  "id": "uuid",
  "title": "帮我写一个 Python 脚本",
  "agent_key": "default",
  "owner": {"type": "api_key", "id": "uuid", "name": "integration-key"},
  "events": [],
  "created_at": "2026-06-26T10:00:00",
  "last_active_at": "2026-06-26T10:05:00"
}
```

### 5.2 修改 `POST /chat-messages`

请求体新增字段：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `conversation_id` | UUID? | `null` | 传入则追加到已有会话 |
| `stateful` | bool | `true` | 为 true 且未传 `conversation_id` 时自动创建新会话 |
| `history_limit` | int | `20` | 加载最近 N 轮 input/output，范围 1–100 |

行为规则：

| 场景 | 行为 |
|---|---|
| `stateful=false` | 无状态模式，不读写会话历史 |
| `stateful=true` 且无 `conversation_id` | 自动创建会话，写入 `input` 事件，并在 SSE 首事件返回 `conversation_id`；后续每个 SSE 事件各自 INSERT 一行 |
| `stateful=true` 且有 `conversation_id` | 校验归属 → 加载历史 → 追加 input 事件，后续 SSE 事件各自 INSERT |
| `conversation_id` 不存在或无权限 | 404 / 403 |
| `conversation_id` 存在但 `agent_key` 不一致 | 409 Conflict |

`agent_key` 规则：

- 自动创建会话时，`conversations.agent_key` 写入当前请求解析后的 `agent_key`。
- 继续已有会话时，请求的 `agent_key` 必须与会话的 `agent_key` 一致，避免把 Agent A 的历史注入 Agent B。
- 前端切换 Agent 后，重新调用 `GET /conversations?agent_key=当前Agent`，只展示该 Agent 的会话。

流式响应保持后端现有 SSE `event` 结构；前端 service 层再映射为 UI 使用的 `kind`。

```json
{"event":"message_start","conversation_id":"...","task_id":"..."}
{"event":"skill","skills":["docx"]}
{"event":"tool_start","name":"...","input":{}}
{"event":"tool_end","name":"...","output":{}}
{"event":"message","content":"你好"}
{"event":"message_end","task_id":"...","status":"completed"}
```

## 6. 核心链路

```
POST /chat-messages
  │
  ├─ 1. 认证，得到 AuthPrincipal(user/api_key)
  │
  ├─ 2. 会话处理
  │     ├─ stateful=false → 不读写 DB
  │     ├─ 无 conversation_id → 创建 Conversation(agent_key=当前Agent)
  │     └─ 有 conversation_id → 校验归属与 agent_key，并读取历史 input/output
  │
  ├─ 3. 写入本轮持久化事件
  │     ├─ INSERT input 事件: {"type":"input", task_id, message, agent_key, ...}
  │     ├─ 后续每个 SSE 事件 INSERT 一行，纯追加，不 UPDATE
  │     └─ 更新 conversations.last_active_at
  │
  ├─ 4. 创建后台任务
  │     ├─ asyncio.create_task(...)
  │     ├─ TaskManager 记录 task_id → task/conversation/owner
  │     └─ Redis Pub/Sub channel = agent:task:{task_id}
  │
  ├─ 5. Agent 执行
  │     ├─ 技能选择 → skill SSE 事件
  │     ├─ LLM token → message/reasoning SSE 事件
  │     ├─ 工具调用 → tool_start/tool_end SSE 事件
  │     └─ 结束/异常/停止 → message_end/error/interrupted SSE 事件
  │
  └─ 6. SSE 订阅 Redis channel 转发实时事件
```

后台任务执行期间，每个实时 SSE 事件都会发布到 Redis Pub/Sub，同时 INSERT 一行到 `conversation_events`；客户端断开只会关闭 SSE 订阅，不影响后台任务继续 INSERT 事件到 DB。

## 7. 内存/缓存层

### 7.1 `TaskManager`

`src/core/task.py` 负责同进程后台任务生命周期：

```python
class RunningTask(BaseModel):
    task_id: str
    conversation_id: UUID | None
    owner_type: Literal["user", "api_key"]
    owner_id: UUID

class TaskManager:
    _tasks: dict[str, asyncio.Task]
    _meta: dict[str, RunningTask]

    async def create(self, meta: RunningTask, coro) -> None: ...
    async def cancel(self, task_id: str) -> bool: ...
    async def get(self, task_id: str) -> asyncio.Task | None: ...
    def channel(self, task_id: str) -> str: ...
```

MVP 限制：`asyncio.create_task` 只能保证客户端断开后同进程继续执行；服务重启、多 worker、滚动发布时，内存任务可能丢失。若后续要求跨进程可靠执行，应升级为 Celery/RQ/Arq。

### 7.2 Redis Pub/Sub

当前项目已存在 `RedisSettings` 和 `src/ext/redis.py`，复用现有 Redis 客户端。

频道：

```
agent:task:{task_id}
```

用途：

- 后台任务发布实时事件。
- SSE handler 订阅并转发事件。
- 可选：重连接口只订阅实时事件；历史事件仍从 DB 读取。

### 7.3 Redis 任务元信息（可选）

为了重连和 stop 能跨 handler 查询，可将任务元信息短期写入 Redis：

| Key | Value | TTL |
|---|---|---|
| `agent:task:{task_id}:meta` | `conversation_id`, `owner_type`, `owner_id`, `status` | 24h |

MVP 可以只用内存；如果部署可能多 worker，建议同时写 Redis meta。

## 8. 认证与授权

### 8.1 统一认证 Principal

当前 `get_current_user_or_api_key()` 在 API Key 认证成功时返回 `None`，无法绑定 `api_key_id`。需要改为统一身份对象：

```python
class AuthPrincipal(BaseModel):
    type: Literal["user", "api_key"]
    user: UserPublic | None = None
    api_key: ApiKeySummary | None = None
```

API Key 校验函数从 `validate_api_key(...) -> bool` 扩展为返回 `ApiKey | None`，用于绑定归属、展示名称和刷新 `last_used_at`。

### 8.2 权限表

| 接口 | 普通用户 | API Key | 管理员 |
|---|---|---|---|
| `GET /conversations` | 仅自己的 | 仅该 Key 的 | 仅自己的 |
| `GET /conversations/{id}` | 仅自己的 | 仅该 Key 的 | 仅自己的 |
| `DELETE /conversations/{id}` | 仅自己的 | 仅该 Key 的 | 仅自己的 |
| `POST /conversations/batch-delete` | 仅自己的 | 仅该 Key 的 | 仅自己的 |
| `GET /admin/conversations` | 禁止 | 禁止 | 全部 + 筛选 |
| `GET /admin/conversations/{id}` | 禁止 | 禁止 | 全部 |
| `POST /chat-messages/{task_id}/stop` | 仅自己的 task | 仅该 Key 的 task | 全部 |

## 9. 文件清单

### 新建

| 文件 | 说明 |
|---|---|
| `src/models/conversation.py` | `Conversation` / `ConversationEvent` ORM + Pydantic schema |
| `src/router/conversation.py` | 用户侧会话列表/详情/删除、管理员全局查询、stop/events 端点 |
| `src/core/conversation.py` | 事件追加、历史上下文构建 |
| `src/core/task.py` | 后台任务管理器 |
| `migrations/versions/202606260001_create_conversations.py` | 创建会话与事件表 |

### 修改

| 文件 | 说明 |
|---|---|
| `src/router/chat.py` | 增加 stateful/conversation_id、后台任务、事件持久化与 Pub/Sub |
| `src/models/llm.py` | 新增 `conversation_id`、`stateful`、`history_limit` 字段 |
| `src/core/agent.py` | 支持 `history_messages` 和事件回调 |
| `src/core/auth/user.py` | 返回 `AuthPrincipal` |
| `src/core/auth/api_key.py` | API Key 校验返回具体 `ApiKey` |
| `src/ext/redis.py` | 复用现有客户端，按需补 Pub/Sub helper |
| `src/router/__init__.py` | 注册 conversation 路由 |
| `migrations/env.py` | import 新模型，注册 metadata |
| `web/src/service/modules/chat.ts` | 请求携带 `conversation_id/stateful`，将后端 `event` 映射为 UI `kind` |

## 10. 实施步骤

| # | 步骤 | 内容 |
|---|---|---|
| 1 | 统一认证身份 | `AuthPrincipal` + API Key 返回记录 |
| 2 | 创建 ORM 和迁移 | `conversations` + `conversation_events` |
| 3 | 事件服务 | 事件流 INSERT、更新 `last_active_at`、从事件流按 `task_id` 归组构建 LLM history |
| 4 | TaskManager | 内存任务管理 + Redis Pub/Sub 发布 |
| 5 | 改造 Agent | 增加 `history_messages` 和事件回调 |
| 6 | 改造聊天接口 | stateful 会话创建、事件持久化、后台执行、SSE 转发 |
| 7 | 会话路由 | 用户侧列表/详情/删除、管理员全局查询、events 重连、stop |
| 8 | 前端适配 | 发送/保存 `conversation_id`，详情页回放 input/output |
| 9 | 验证 | 运行后端 lint、迁移和端到端手测 |

## 11. 测试计划

1. `stateful=false`：不创建会话、不写事件。
2. 首轮 `stateful=true` 且无 `conversation_id`：自动创建会话，首个 SSE `message_start` 含 `conversation_id`。
3. 第二轮携带同一 `conversation_id`：能加载上一轮上下文。
4. Session 用户创建会话：`user_id = 当前用户`，列表只看自己的。
5. API Key 创建会话：`api_key_id = 当前 Key`，列表只看该 Key 的。
6. Agent 隔离：`GET /conversations?agent_key=a` 只返回 Agent A 的会话，切换到 B 后只返回 B 的会话。
7. Agent 不匹配：用 Agent B 请求 Agent A 的 `conversation_id` 返回 409。
8. 管理员首页列表：`GET /conversations` 只返回管理员自己的会话。
9. 管理员全局查询：`GET /admin/conversations` 能查看全部会话并按用户/API Key/Agent/关键词筛选。
10. 事件回放：`GET /conversations/{id}` 返回平铺事件流，前端按 `type` 分发 + `task_id` 归组回放后显示一致。
11. 工具调用：`tool_start/tool_end` 各自单独一行，共享同一 `task_id`，前端按 `task_id` 归入同一 assistant 消息。
12. 技能选择：`skill` 事件单独一行，不污染 LLM 历史上下文。
13. SSE 断开：后台任务继续写事件，刷新详情能看到后续结果。
14. 停止任务：`POST /chat-messages/{task_id}/stop` 写入 `interrupted` 事件。
15. 异常任务：写入 `error` 事件，会话仍可打开。
16. 删除会话：级联删除事件。
17. 批量删除：只能删除自己有权限的会话，返回 `deleted/not_found/forbidden`。
18. 分页排序：按 `last_active_at DESC, id DESC` 稳定返回。

### 检查命令

```bash
pnpm run lint:backend
pnpm run db:migrate
```

## 12. 暂不做

- 软删除 / 归档
- 消息分支 / 重答
- Token / 费用统计
- 多模态附件持久化
- 会话摘要 / 自动压缩
- 跨进程可靠 worker（MVP 先用 `asyncio.create_task`）
