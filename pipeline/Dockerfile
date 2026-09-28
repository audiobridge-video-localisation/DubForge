# Build context must be the repo root (monorepo uv workspace), e.g.:
#   docker build -f pipeline/Dockerfile -t dubforge-pipeline .
FROM python:3.12-slim

# ffmpeg is a hard runtime dependency of dubforge_pipeline.audio.extract_audio
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY pipeline ./pipeline
COPY packages ./packages

RUN uv sync --frozen --package dubforge-pipeline

CMD ["uv", "run", "--package", "dubforge-pipeline", "dubforge-worker"]
