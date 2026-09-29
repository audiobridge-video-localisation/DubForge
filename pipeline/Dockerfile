# Build from repo root:  docker build -f pipeline/Dockerfile -t dubforge-pipeline .
FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /usr/local/bin/

# ffmpeg: hard runtime dependency of dubforge_pipeline.audio
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=0 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

# 1) Workspace metadata only -> dependency layer stays cached until the lockfile changes
COPY pyproject.toml uv.lock ./
COPY pipeline/pyproject.toml pipeline/pyproject.toml
COPY packages/contracts/pyproject.toml packages/contracts/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package dubforge-pipeline

# 2) Source code -> install workspace packages (fast, deps already cached)
COPY packages/contracts/src packages/contracts/src
COPY pipeline/src pipeline/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package dubforge-pipeline

# Writable dir for job media; everything else stays read-only and root-owned
RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser

CMD ["dubforge-worker"]
