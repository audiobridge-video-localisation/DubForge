# DubForge

Video localisation SaaS MVP.

## Repository layout

- `apps/api` - FastAPI application and HTTP boundary
- `apps/web` - React/Vite web application
- `pipeline` - media and AI processing workers
- `packages/contracts` - shared Pydantic models and API contracts

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker Desktop (for PostgreSQL and Redis)
- FFmpeg available on the host when running media tooling locally

## Quick start

```bash
uv sync --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps pipeline packages
```

Frontend checks:

```bash
cd apps/web
npm ci
npm run lint
npm run format
npm run build
```

Install pre-commit and enable the hooks:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Pull requests and pushes to `main` run the same Python and frontend checks in
GitHub Actions.

Start local infrastructure:

```bash
mkdir -p media
docker compose up -d postgres redis pipeline
```

Apply database migrations:

```bash
uv run alembic -c apps/api/alembic.ini upgrade head
```

Run the API:

```bash
uv run uvicorn dubforge_api.main:app --app-dir apps/api/src --reload
```

The health endpoint is available at <http://localhost:8000/health>, and the
project CRUD endpoints are available at <http://localhost:8000/projects>.
Uploading a video via `POST /projects/{id}/media` saves it under `media/`,
queues a processing job on Redis, and the `pipeline` worker picks it up,
reporting progress back via `PATCH /internal/jobs/{id}`. Poll `GET
/jobs/{id}` for status, or `POST /jobs/{id}/retry` to re-queue a failed job.

Run the web app:

```bash
cd apps/web
cp .env.example .env
npm run dev
```

The web app is available at <http://localhost:5173>.

## Workspace commands

```bash
uv add --package dubforge-api fastapi
uv add --package dubforge-pipeline <provider-package>
uv lock
uv sync --all-packages
```

The shared contract carries `Media`/`Job` types now, since the api and
pipeline worker need to agree on a wire format to talk to each other over
Redis/HTTP. `Project`, `Segment`, and `Artifact` fields and state machines
are still pending agreement in the team change log.

## Environment

Copy `.env.example` to `.env` for local development. Never commit real
credentials or provider keys.

## STT providers & benchmarking

The pipeline's speech-to-text provider is selected at runtime via
`dubforge_pipeline.providers.registry.get_stt_provider()`, driven by env vars:

- `STT_PROVIDER` - `mock` (default) or `whisper`
- `WHISPER_MODEL` - faster-whisper model size (default `small.en`)
- `WHISPER_DEVICE` - `cpu` or `cuda` (default `cpu`)
- `WHISPER_COMPUTE_TYPE` - faster-whisper compute type, e.g. `int8`, `float16` (default `int8`)

The first transcription with `STT_PROVIDER=whisper` downloads the selected
model from Hugging Face (~500MB for `small.en`) and caches it locally.

Benchmark a provider against a video file:

```bash
uv run python scripts/benchmark_stt.py path/to/video.mp4 --provider whisper --model small.en
```

This extracts audio, transcribes it, and appends timing/memory/accuracy
metrics as a JSON line to `benchmarks/results.jsonl`, plus a plain-text
transcript under `benchmarks/` for manual review. The `benchmarks/` directory
is local-only and gitignored.
