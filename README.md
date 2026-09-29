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
docker compose up -d postgres redis
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

The shared contract is intentionally empty apart from a package marker until the
Project, Media, Segment, Job, and Artifact fields and state machines are agreed
in the team change log.

## Environment

Copy `.env.example` to `.env` for local development. Never commit real
credentials or provider keys.
