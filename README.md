# Etsy AI Growth Agent

SaaS platform that helps Etsy sellers grow with AI: SEO analysis, listing optimization, and a daily growth agent.

**Stack:** FastAPI + PostgreSQL + Redis + Celery | Next.js 14 (App Router) + Tailwind + next-intl

## Repository layout

```
backend/    FastAPI app (auth, API, Celery tasks, Alembic migrations)
frontend/   Next.js 14 app (next-intl i18n: en / uk / pl, NextAuth)
specs/      Product and implementation specs
docker-compose.yml   PostgreSQL (pgvector) + Redis + pgAdmin for development
```

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node 20+ and pnpm (`npm install -g pnpm`)
- Docker Desktop

## Quick start

### 1. Start infrastructure

```bash
docker compose up -d
```

Postgres on `localhost:5432` (postgres/postgres, db `etsy_agent`), Redis on `localhost:6379`, pgAdmin on `localhost:5050`.

### 2. Backend

```bash
cd backend
cp .env.example .env          # adjust secrets if needed
uv sync
uv run alembic upgrade head   # creates users/sessions/oauth tables
uv run uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`. API docs at http://localhost:8000/docs.

Optional Celery worker:

```bash
uv run celery -A app.celery_app worker --loglevel=info
```

Run tests: `uv run pytest`

### 3. Frontend

```bash
cd frontend
cp .env.local.example .env.local   # set AUTH_SECRET to a random 32+ char string
pnpm install
pnpm dev
```

Open http://localhost:3000 — you are redirected to `/en`.

## Internationalization

The frontend supports **English (`/en`), Ukrainian (`/uk`), and Polish (`/pl`)** via [next-intl](https://next-intl.dev):

- Default locale: English; URLs are always locale-prefixed (`/en/login`, `/uk/dashboard`, ...)
- All UI text lives in translation files: `frontend/messages/{en,uk,pl}.json` — no hardcoded strings
- Language switcher in the header persists across navigation
- Adding a language: add the locale to `frontend/i18n/routing.ts` and create `frontend/messages/<locale>.json`

## Auth flow

1. `POST /v1/auth/register` — creates user (14-day trial, 30 credits), returns JWT access + refresh tokens
2. `POST /v1/auth/login` — verifies bcrypt password hash, returns tokens, records a session row
3. NextAuth (credentials provider) calls the FastAPI login endpoint and stores the access token in its JWT session
4. `GET /v1/auth/me` — protected route used by the dashboard; `POST /v1/auth/refresh` and `POST /v1/auth/logout` manage sessions

## API endpoints (current)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/v1/auth/register` | Create account, returns JWT |
| POST | `/v1/auth/login` | Login, returns JWT |
| POST | `/v1/auth/refresh` | New access token from refresh token |
| POST | `/v1/auth/logout` | Revoke sessions |
| GET | `/v1/auth/me` | Current user (requires Bearer token) |

See [specs/mvp-plan.md](specs/mvp-plan.md) for the full 4-week implementation plan.
