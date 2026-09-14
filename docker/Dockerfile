# 第一阶段：构建前端
FROM node:24-slim AS frontend-builder

RUN corepack enable

WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY web/package.json ./web/

RUN pnpm install --frozen-lockfile --filter foundry-agent...

COPY web/ ./web/

RUN pnpm build:web

# 第二阶段：后端运行镜像
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENV=production
ENV APP_PORT=9110
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/web/dist ./web/dist

# 复制后端应用代码
COPY main.py ./
COPY alembic.ini ./
COPY src/ ./src/

EXPOSE 9110

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9110/health', timeout=5)" || exit 1

CMD ["uv", "run", "main.py"]
