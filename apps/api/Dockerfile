# Build from the repo root:  docker build -f apps/api/Dockerfile -t dubforge-api .
FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

# ---- build stage: resolve + install dependencies into /app/.venv ------------------------
FROM python:3.12-slim AS build

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 1) Workspace metadata only -> this layer stays cached until the lockfile changes
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/contracts/pyproject.toml packages/contracts/pyproject.toml
COPY pipeline/pyproject.toml pipeline/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package dubforge-api

# 2) Source code -> install the workspace packages (fast, dependencies already cached)
COPY packages/contracts/src packages/contracts/src
COPY apps/api/src apps/api/src
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/alembic apps/api/alembic

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package dubforge-api

# ---- runtime stage: no uv, no build tools -----------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data

COPY --from=build /app /app

USER appuser

EXPOSE 8000

# python is already here, so the check needs no curl
HEALTHCHECK --interval=10s --timeout=4s --start-period=10s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "dubforge_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
