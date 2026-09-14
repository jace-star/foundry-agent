# foundry-agent

FastAPI 后端服务，当前保留 AI Agent 相关基础能力：

- `langchain` / `langchain-openai`：OpenAI-compatible 模型调用
- `langgraph`：有状态多步 Agent 编排
- `langfuse`：LLM 追踪客户端初始化
- `opendal`：统一对象存储
- `fastapi`：HTTP API
- `loguru`：日志

## 项目结构

```text
.
├── main.py
├── pyproject.toml
├── src/
│   ├── app.py
│   ├── config.py
│   ├── router/
│   ├── core/
│   ├── ext/
│   └── models/
└── docker/
```

## 开发

安装依赖：

```bash
uv sync
```

启动后端：

```bash
uv run main.py
```

检查代码：

```bash
uv run ruff check main.py src
```

执行数据库迁移：

```bash
uv run alembic upgrade head
```

## 接口

MCP server 配置通过 OpenDAL 持久化到对象存储。

- `POST /agent/v1/chat-messages`：模型聊天
- `POST /agent/v1/mcp/servers`：新增并校验外部 MCP server
- `GET /agent/v1/mcp/servers`：查询已接入的 MCP server 配置
- `GET /agent/v1/mcp/servers/{name}`：查询单个 MCP server 的工具信息
- `DELETE /agent/v1/mcp/servers/{name}`：删除已接入的 MCP server

## 环境变量

参考 `.env.example`。Langfuse 的 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 留空时不会启用追踪。
