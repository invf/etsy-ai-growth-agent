# Etsy AI Growth Agent — MVP Implementation Plan

> Start coding today. Every task has a clear output and acceptance criterion.
> Stack: FastAPI + PostgreSQL + Redis + Celery | Next.js 14 App Router + shadcn/ui

---

## Table of Contents

1. [What to Build First (Week 1–4)](#1-what-to-build-first-week-14)
2. [Project File & Folder Structure](#2-project-file--folder-structure)
3. [Setup Instructions](#3-setup-instructions)
4. [First 3 API Endpoints](#4-first-3-api-endpoints)
5. [First Dashboard Page](#5-first-dashboard-page)

---

## 1. What to Build First (Week 1–4)

### Guiding Principle

Build the **smallest loop that delivers value**: user signs up → connects Etsy store → agent analyzes one listing → user sees SEO recommendation → user approves it → it goes live on Etsy.

Everything outside that loop is deferred.

---

### Week 1: Foundation (Days 1–7)

**Goal:** Running app with auth, database, and Docker. Zero features — just a skeleton you can ship code into.

| Day | Task | Output / Acceptance Criterion |
|---|---|---|
| 1 | Project scaffolding (monorepo, Docker Compose) | `docker compose up` starts postgres + redis |
| 1 | Backend: FastAPI skeleton + health endpoint | `GET /health` returns `{"status":"ok"}` |
| 1 | Frontend: Next.js 14 with App Router + shadcn/ui | `pnpm dev` loads at localhost:3000 |
| 2 | Alembic setup + first 4 migrations | `users`, `sessions`, `password_reset_tokens`, `oauth_accounts` tables exist |
| 2 | `POST /auth/register` endpoint | Creates user row, returns JWT |
| 3 | `POST /auth/login` endpoint | Returns JWT on valid credentials |
| 3 | `GET /auth/me` endpoint | Returns user object for valid token |
| 3 | `POST /auth/logout` + `POST /auth/refresh` | Session revoked; refresh returns new token |
| 4 | NextAuth.js with credentials provider | Login form works end-to-end |
| 4 | Register page + login page (basic forms) | Can create account, log in, see `/dashboard` |
| 5 | Auth middleware (`get_current_user` FastAPI dep) | Unauthenticated requests get 401 |
| 5 | JWT + password hashing (`bcrypt`, `python-jose`) | Tested with `pytest` |
| 6 | Celery + Redis connected | `celery -A app.celery_app worker` starts clean |
| 6 | First Celery task: `tasks.health.ping` | `ping.delay()` returns `"pong"` |
| 7 | GitHub Actions: lint (ruff) + type check (mypy) + `pytest` | CI green on push |

**End of Week 1 checkpoint:** Auth works end-to-end. You can register, log in, get a JWT, and hit a protected route.

---

### Week 2: Store Connection & Listing Sync (Days 8–14)

**Goal:** User can connect their Etsy store and see their listings in the dashboard.

| Day | Task | Output / Acceptance Criterion |
|---|---|---|
| 8 | `stores` + `listings` + `listing_metrics_history` migrations | Tables exist with correct schema |
| 8 | Etsy OAuth initiate: `POST /stores/connect/initiate` | Returns Etsy OAuth URL with PKCE params |
| 9 | Etsy OAuth callback: `GET /stores/connect/callback` | Stores encrypted tokens, redirects to dashboard |
| 9 | AES-256-GCM token encryption service | Raw token never hits DB |
| 10 | `GET /stores` + `GET /stores/{id}` endpoints | Returns connected stores |
| 10 | Celery task: `tasks.sync.sync_store_listings` | Fetches from Etsy API, upserts `listings` table |
| 11 | `POST /stores/{id}/sync` endpoint | Queues Celery task, returns `{job_id}` |
| 11 | Etsy rate limiter (Redis Lua token bucket, 10 req/s) | No 429s from Etsy during sync |
| 12 | `GET /stores/{id}/listings` endpoint (paginated) | Returns listing list with scores |
| 12 | `GET /stores/{id}/listings/{id}` endpoint | Returns full listing detail |
| 13 | Dashboard: Store selector + listing table | User can see their listings after connecting store |
| 13 | Store connection flow (UI: "Connect Etsy Store") | End-to-end OAuth flow works in browser |
| 14 | `content_hash` computation on upsert | Changed listings detectable for re-embedding |
| 14 | Error handling: Etsy token expiry + refresh | Expired tokens auto-refresh before API calls |

**End of Week 2 checkpoint:** User can connect Etsy, sync listings, and see them in a table. The app is genuinely useful for the first time.

---

### Week 3: SEO Analysis — The Core Value Prop (Days 15–21)

**Goal:** User can run an AI SEO analysis on any listing and see structured recommendations.

| Day | Task | Output / Acceptance Criterion |
|---|---|---|
| 15 | `seo_analyses` + `agent_runs` + `agent_run_logs` migrations | Tables exist |
| 15 | `AIService` wrapper + `call_with_structured_output` | Returns Pydantic model, never free text |
| 15 | SEO Analyzer prompt + tool schema (from ai-agent-spec.md §3.1) | Returns valid `SeoAnalysis` object |
| 16 | Celery task: `tasks.seo.analyze_single` | Calls Claude, writes `seo_analyses` row |
| 16 | `POST /listings/{id}/seo/analyze` endpoint | Queues task, returns `{run_id}` |
| 16 | `GET /listings/{id}/seo` endpoint | Returns latest analysis |
| 17 | `listing_optimizations` migration | Table exists with correct state machine fields |
| 17 | `POST /listings/{id}/seo/apply` | Creates `listing_optimizations` rows with `status=pending` |
| 17 | `POST /optimizations/{id}/approve` + `reject` | Status transitions work |
| 18 | `POST /optimizations/{id}/apply` | Writes to Etsy API via `PUT /application/listings/{id}` |
| 18 | Etsy tag validation before write (`len ≤ 13`, each `≤ 20` chars) | Constraint errors caught before API call |
| 19 | SSE progress endpoint: `GET /agent/runs/{id}/stream` | Browser EventSource receives phase events |
| 19 | Credit reservation + settlement (`CreditService`) | Credits reserved at start, settled on completion |
| 20 | Listing detail page with SEO score + analysis | Shows score, title/tag recommendations |
| 20 | OptimizationCard component (pending → approve → apply) | State machine works in UI |
| 21 | End-to-end test: connect store → analyze → approve → apply | Listing on Etsy updated |

**End of Week 3 checkpoint:** The core value loop is complete. User can run SEO analysis and apply one change to their live Etsy listing.

---

### Week 4: Billing, Polish & Deploy (Days 22–28)

**Goal:** Paying users. Deployed to production. Ready to onboard beta users.

| Day | Task | Output / Acceptance Criterion |
|---|---|---|
| 22 | `subscription_plans` seed + `credit_transactions` + `paddle_events` migrations | Tables exist |
| 22 | Paddle.js checkout on pricing page | Can complete a test payment in Sandbox |
| 23 | `POST /webhooks/paddle` handler (sig verification + 7 events) | `subscription.created` allocates credits |
| 23 | `GET /billing/subscription` + `GET /billing/credits` endpoints | Returns correct data |
| 24 | Daily credit cap enforcement in `CreditService` | Can't burn >30 credits/day on Starter |
| 24 | Low-credit notification (in-app + email via SendGrid) | Email sent when <20 credits remain |
| 24 | Pricing page (3 tiers, Paddle checkout) | End-to-end subscribe flow works |
| 25 | Celery Beat: `daily_agent_fan_out` at 07:00 UTC | Scheduled task fires and queues per-store jobs |
| 25 | Daily agent chord: sync → SEO → synthesis → notify | Complete pipeline runs for 1 test store |
| 26 | Render deployment (backend + frontend + workers + beat) | `curl https://api.etsyagent.com/health` returns 200 |
| 26 | Environment secrets in Render dashboard | No secrets in git |
| 27 | Onboarding flow: welcome → connect store → first analysis | New user reaches first recommendation in <5 min |
| 27 | Sentry error tracking (frontend + backend) | Errors appear in Sentry on throw |
| 28 | Smoke test on production with real Etsy store | Full loop works in prod |
| 28 | Invite 5 beta users | First paying customers |

**End of Week 4 checkpoint:** Production app, paying users, daily agent running. MVP is live.

---

### Post-MVP Backlog (Week 5+, prioritized)

```
Priority 1 (Week 5–6):
  - Competitor analysis (second most valuable AI feature)
  - Trend intelligence (third)
  - Notifications panel (in-app)
  - Store health score

Priority 2 (Week 7–8):
  - Content generator
  - Image analysis
  - Weekly report

Priority 3 (Month 3):
  - Pricing intelligence
  - Audience discovery
  - Monthly strategic plan
  - A/B test tracking

Priority 4 (Month 4+):
  - Pro/Agency tier features (bulk, API keys, webhooks)
  - White-label
  - RAG pipeline (pgvector embeddings)
```

---

## 2. Project File & Folder Structure

```
etsy-ai-growth-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  ← FastAPI app factory
│   │   ├── celery_app.py            ← Celery app + beat schedule
│   │   │
│   │   ├── api/                     ← All HTTP routes
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py      ← get_current_user, get_db, rate_limiter
│   │   │   ├── middleware.py        ← CreditBalanceMiddleware, RequestIdMiddleware
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── stores.py
│   │   │       ├── listings.py
│   │   │       ├── seo.py
│   │   │       ├── competitors.py
│   │   │       ├── trends.py
│   │   │       ├── audience.py
│   │   │       ├── content.py
│   │   │       ├── pricing.py
│   │   │       ├── images.py
│   │   │       ├── optimizations.py
│   │   │       ├── agent.py
│   │   │       ├── reports.py
│   │   │       ├── notifications.py
│   │   │       ├── billing.py
│   │   │       ├── webhooks.py
│   │   │       ├── api_keys.py
│   │   │       └── admin.py
│   │   │
│   │   ├── core/                    ← App-wide config + utilities
│   │   │   ├── config.py            ← Settings (pydantic BaseSettings)
│   │   │   ├── security.py          ← JWT create/decode, bcrypt
│   │   │   ├── encryption.py        ← AES-256-GCM for Etsy tokens
│   │   │   └── exceptions.py        ← Custom HTTP exceptions
│   │   │
│   │   ├── db/                      ← Database layer
│   │   │   ├── base.py              ← SQLAlchemy declarative base
│   │   │   ├── session.py           ← get_db_session context manager
│   │   │   └── models/              ← One file per domain
│   │   │       ├── user.py
│   │   │       ├── store.py
│   │   │       ├── listing.py
│   │   │       ├── analysis.py      ← seo_analyses, competitor_analyses, etc.
│   │   │       ├── agent.py         ← agent_runs, agent_tasks, agent_run_logs
│   │   │       ├── billing.py
│   │   │       └── system.py
│   │   │
│   │   ├── schemas/                 ← Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── store.py
│   │   │   ├── listing.py
│   │   │   ├── seo.py
│   │   │   ├── optimization.py
│   │   │   ├── agent.py
│   │   │   └── billing.py
│   │   │
│   │   ├── services/                ← Business logic (no HTTP, no Celery)
│   │   │   ├── auth_service.py
│   │   │   ├── credit_service.py    ← CreditService (reserve/settle)
│   │   │   ├── etsy_client.py       ← Etsy API wrapper + rate limiter
│   │   │   ├── ai_service.py        ← call_with_structured_output wrapper
│   │   │   ├── paddle_service.py    ← PaddleWebhookService
│   │   │   ├── email_service.py     ← SendGrid wrapper
│   │   │   └── lock_service.py      ← AcquireDistributedLock
│   │   │
│   │   ├── tasks/                   ← Celery tasks
│   │   │   ├── sync.py              ← sync_store_listings, sync_single_listing
│   │   │   ├── seo.py               ← analyze_single, analyze_batch
│   │   │   ├── competitors.py
│   │   │   ├── trends.py
│   │   │   ├── content.py
│   │   │   ├── images.py
│   │   │   ├── pricing.py
│   │   │   ├── agent.py             ← run_daily_agent, daily_agent_fan_out
│   │   │   ├── embeddings.py
│   │   │   ├── notifications.py
│   │   │   ├── billing.py
│   │   │   ├── maintenance.py
│   │   │   └── base.py              ← AgentTask base class
│   │   │
│   │   └── prompts/                 ← AI prompt templates + tool schemas
│   │       ├── seo_analyzer.py
│   │       ├── competitor_analyzer.py
│   │       ├── trend_synthesizer.py
│   │       ├── content_generator.py
│   │       ├── image_analyzer.py
│   │       ├── pricing_advisor.py
│   │       ├── audience_discovery.py
│   │       └── daily_synthesizer.py
│   │
│   ├── migrations/
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 0001_extensions.py
│   │       ├── 0002_users_auth.py
│   │       ├── 0003_stores.py
│   │       ├── 0004_listings.py
│   │       ├── 0005_analysis.py
│   │       ├── 0006_trends_audience.py
│   │       ├── 0007_content_optimizations.py
│   │       ├── 0008_agent_runs.py
│   │       ├── 0009_billing.py
│   │       ├── 0010_system.py
│   │       ├── 0011_embeddings.py
│   │       ├── 0012_indexes.py
│   │       └── 0014_seed_plans.py
│   │
│   ├── tests/
│   │   ├── conftest.py              ← pytest fixtures (test DB, test client)
│   │   ├── test_auth.py
│   │   ├── test_stores.py
│   │   ├── test_listings.py
│   │   ├── test_seo.py
│   │   ├── test_optimizations.py
│   │   └── test_billing.py
│   │
│   ├── pyproject.toml               ← uv-managed deps + ruff + mypy config
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx               ← Root layout (fonts, providers)
│   │   ├── globals.css
│   │   │
│   │   ├── (auth)/                  ← Route group: no dashboard nav
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── register/
│   │   │   │   └── page.tsx
│   │   │   ├── forgot-password/
│   │   │   │   └── page.tsx
│   │   │   └── reset-password/
│   │   │       └── page.tsx
│   │   │
│   │   ├── (dashboard)/             ← Route group: with sidebar nav
│   │   │   ├── layout.tsx           ← DashboardLayout (sidebar + topbar)
│   │   │   ├── page.tsx             ← Redirects to /dashboard
│   │   │   └── dashboard/
│   │   │       ├── page.tsx         ← Store overview (FIRST PAGE TO BUILD)
│   │   │       ├── listings/
│   │   │       │   ├── page.tsx
│   │   │       │   └── [listingId]/
│   │   │       │       └── page.tsx
│   │   │       ├── seo/
│   │   │       │   └── page.tsx
│   │   │       ├── competitors/
│   │   │       │   └── page.tsx
│   │   │       ├── trends/
│   │   │       │   └── page.tsx
│   │   │       ├── audience/
│   │   │       │   └── page.tsx
│   │   │       ├── content/
│   │   │       │   └── page.tsx
│   │   │       ├── optimizations/
│   │   │       │   └── page.tsx
│   │   │       ├── reports/
│   │   │       │   └── page.tsx
│   │   │       └── settings/
│   │   │           └── page.tsx
│   │   │
│   │   └── api/                     ← Next.js route handlers
│   │       └── auth/
│   │           └── [...nextauth]/
│   │               └── route.ts
│   │
│   ├── components/
│   │   ├── ui/                      ← shadcn/ui components (auto-generated)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── table.tsx
│   │   │   └── toast.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── StoreSelector.tsx
│   │   │   └── CreditsDisplay.tsx
│   │   │
│   │   ├── dashboard/
│   │   │   ├── HealthScoreCard.tsx
│   │   │   ├── InsightCard.tsx
│   │   │   ├── AgentRunStatus.tsx
│   │   │   ├── OptimizationPreview.tsx
│   │   │   └── TodaysSummary.tsx
│   │   │
│   │   ├── listings/
│   │   │   ├── ListingTable.tsx
│   │   │   ├── ListingCard.tsx
│   │   │   └── SeoScoreBadge.tsx
│   │   │
│   │   ├── optimizations/
│   │   │   ├── OptimizationCard.tsx
│   │   │   ├── OptimizationDiff.tsx
│   │   │   └── ApproveRejectButtons.tsx
│   │   │
│   │   ├── agent/
│   │   │   ├── AgentProgressBar.tsx
│   │   │   └── PhaseIndicator.tsx
│   │   │
│   │   └── billing/
│   │       ├── PricingCard.tsx
│   │       ├── CreditsWidget.tsx
│   │       └── TopUpModal.tsx
│   │
│   ├── hooks/
│   │   ├── useCurrentStore.ts       ← Zustand store selector
│   │   ├── useAgentStream.ts        ← SSE hook
│   │   ├── useCredits.ts
│   │   ├── useListings.ts
│   │   ├── useOptimizations.ts
│   │   └── useHealthScore.ts
│   │
│   ├── lib/
│   │   ├── api.ts                   ← Typed API client (fetch wrapper)
│   │   ├── auth.ts                  ← NextAuth config
│   │   ├── store.ts                 ← Zustand global state
│   │   ├── utils.ts                 ← cn(), formatCredits(), etc.
│   │   └── constants.ts
│   │
│   ├── types/
│   │   └── index.ts                 ← Shared TypeScript types
│   │
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── Dockerfile
│   └── .env.local.example
│
├── docker-compose.yml               ← postgres + redis + pgadmin for dev
├── docker-compose.prod.yml          ← production overrides
├── .github/
│   └── workflows/
│       ├── ci.yml                   ← lint + test on PR
│       └── deploy.yml               ← deploy to Render on main push
├── scripts/
│   ├── setup.sh                     ← one-command dev setup
│   └── seed_db.py                   ← insert test user + test store
├── .gitignore
└── README.md
```

---

## 3. Setup Instructions

### Prerequisites

```
Python 3.12+    (pyenv recommended: pyenv install 3.12.4)
Node 20+        (nvm recommended: nvm install 20)
Docker Desktop  (for postgres + redis)
uv              (pip install uv  — fast Python package manager)
pnpm            (npm install -g pnpm)
```

### Step 1: Clone and Bootstrap

```bash
# Create project
mkdir etsy-ai-growth-agent && cd etsy-ai-growth-agent
git init
git remote add origin https://github.com/your-org/etsy-ai-growth-agent.git

# Copy the folder structure
mkdir -p backend/app/{api/routes,core,db/models,schemas,services,tasks,prompts}
mkdir -p backend/{migrations/versions,tests}
mkdir -p frontend/{app/{(auth),(dashboard)/dashboard},components/{ui,layout,dashboard,listings,optimizations,agent,billing},hooks,lib,types}
mkdir -p scripts .github/workflows
```

### Step 2: Backend Setup

```bash
cd backend

# Create pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "etsy-ai-growth-agent-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.36",
    "alembic>=1.14.0",
    "asyncpg>=0.30.0",          # async postgres driver
    "psycopg2-binary>=2.9.10",  # sync driver for alembic
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "httpx>=0.28.0",
    "anthropic>=0.42.0",
    "voyageai>=0.3.2",
    "redis>=5.2.0",
    "celery[redis]>=5.4.0",
    "redbeat>=2.2.0",            # redis-backed celery beat
    "cryptography>=44.0.0",
    "python-multipart>=0.0.12",
    "sentry-sdk[fastapi]>=2.19.0",
]

[tool.uv.dev-dependencies]
pytest = ">=8.3.0"
pytest-asyncio = ">=0.24.0"
httpx = ">=0.28.0"
ruff = ">=0.8.0"
mypy = ">=1.13.0"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true
EOF

# Install dependencies
uv sync

# Copy .env
cat > .env.example << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/etsy_agent
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/etsy_agent

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
SECRET_KEY=your-secret-key-min-32-chars-change-in-production
ETSY_TOKEN_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Voyage AI (embeddings)
VOYAGE_API_KEY=pa-...

# Etsy OAuth
ETSY_CLIENT_ID=
ETSY_CLIENT_SECRET=
ETSY_REDIRECT_URI=http://localhost:8000/v1/stores/connect/callback

# Paddle (billing)
PADDLE_API_KEY=
PADDLE_CLIENT_TOKEN=
PADDLE_WEBHOOK_SECRET=
PADDLE_ENVIRONMENT=sandbox

# SendGrid
SENDGRID_API_KEY=
FROM_EMAIL=hello@etsyagent.com

# App
APP_ENV=development
FRONTEND_URL=http://localhost:3000
EOF

cp .env.example .env
```

### Step 3: Frontend Setup

```bash
cd ../frontend

# Create Next.js app
pnpm create next-app@latest . --typescript --tailwind --eslint --app --src-dir=no --import-alias="@/*"

# Install dependencies
pnpm add \
  next-auth@beta \
  @tanstack/react-query \
  zustand \
  @radix-ui/react-dialog \
  @radix-ui/react-dropdown-menu \
  @radix-ui/react-progress \
  @radix-ui/react-tooltip \
  recharts \
  clsx \
  tailwind-merge \
  lucide-react \
  date-fns

# Install shadcn/ui
pnpm dlx shadcn@latest init
# Choose: New York style, Zinc base color, CSS variables: yes

# Add required shadcn components
pnpm dlx shadcn@latest add button card badge dialog input progress skeleton table toast alert

# Copy .env.local
cat > .env.local.example << 'EOF'
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret-min-32-chars

NEXT_PUBLIC_API_URL=http://localhost:8000/v1
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=
EOF

cp .env.local.example .env.local
```

### Step 4: Docker Compose (Development Services)

```yaml
# docker-compose.yml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: etsy_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@local.dev
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Step 5: Alembic Setup

```bash
cd backend

# Initialize alembic
uv run alembic init migrations

# Edit migrations/env.py — replace the target_metadata block:
```

```python
# migrations/env.py  (key section to replace)
from app.db.base import Base
from app.core.config import settings

# Import all models so Alembic sees them
from app.db.models import user, store, listing, analysis, agent, billing, system  # noqa

target_metadata = Base.metadata

def get_url():
    return settings.DATABASE_URL_SYNC
```

```bash
# Create and apply first migration
uv run alembic revision --autogenerate -m "initial_schema"
uv run alembic upgrade head

# Verify
uv run python -c "from app.db.session import get_db_session; print('DB connected')"
```

### Step 6: Start Everything

```bash
# Terminal 1: Start Docker services
docker compose up -d

# Terminal 2: Backend API server
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery worker
cd backend
uv run celery -A app.celery_app worker --loglevel=info -Q critical,high,default

# Terminal 4: Celery Beat (scheduler)
cd backend
uv run celery -A app.celery_app beat -S redbeat.RedBeatScheduler --loglevel=info

# Terminal 5: Frontend
cd frontend
pnpm dev

# Verify everything is running:
curl http://localhost:8000/health        # → {"status":"ok","version":"0.1.0"}
curl http://localhost:3000               # → Next.js app
```

### Step 7: Seed Data for Development

```python
# scripts/seed_db.py
"""Run: cd backend && uv run python ../scripts/seed_db.py"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.db.session import get_db_session
from app.core.security import hash_password
from app.db.models.user import User, SubscriptionTier, SubscriptionStatus
from datetime import datetime, timezone, timedelta

async def seed():
    with get_db_session() as db:
        # Test user: trial account
        trial_user = User(
            email="test@example.com",
            name="Test Seller",
            password_hash=hash_password("TestPass123!"),
            subscription_status=SubscriptionStatus.TRIAL,
            subscription_tier=SubscriptionTier.TRIAL,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            credits_balance=30,
        )
        db.add(trial_user)

        # Test user: paid Growth account
        paid_user = User(
            email="paid@example.com",
            name="Paid Seller",
            password_hash=hash_password("TestPass123!"),
            subscription_status=SubscriptionStatus.ACTIVE,
            subscription_tier=SubscriptionTier.GROWTH,
            credits_balance=247,
        )
        db.add(paid_user)
        db.flush()
        print(f"Created users: {trial_user.id}, {paid_user.id}")

asyncio.run(seed())
```

---

## 4. First 3 API Endpoints

### Endpoint 1: `POST /auth/register`

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str
    SECRET_KEY: str
    ETSY_TOKEN_ENCRYPTION_KEY: str
    ANTHROPIC_API_KEY: str
    VOYAGE_API_KEY: str = ""
    ETSY_CLIENT_ID: str = ""
    ETSY_CLIENT_SECRET: str = ""
    ETSY_REDIRECT_URI: str = ""
    PADDLE_API_KEY: str = ""
    PADDLE_CLIENT_TOKEN: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_ENVIRONMENT: str = "sandbox"
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "hello@etsyagent.com"
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

settings = Settings()
```

```python
# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expires, "type": "access"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {"sub": user_id, "exp": expires, "type": "refresh"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return {}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

```python
# backend/app/db/models/user.py
from sqlalchemy import Column, String, Boolean, Integer, SmallInteger
from sqlalchemy import DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from datetime import datetime, timezone
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255))
    password_hash = Column(String(255))
    avatar_url = Column(String)
    timezone = Column(String(100), nullable=False, default="UTC")

    subscription_status = Column(String(20), nullable=False, default="trial")
    subscription_tier = Column(String(20), nullable=False, default="trial")
    billing_interval = Column(String(10), nullable=False, default="monthly")
    trial_ends_at = Column(DateTime(timezone=True))
    subscription_started_at = Column(DateTime(timezone=True))
    subscription_cancelled_at = Column(DateTime(timezone=True))
    subscription_current_period_end = Column(DateTime(timezone=True))

    paddle_customer_id = Column(String(100), unique=True)
    paddle_subscription_id = Column(String(100), unique=True)

    credits_balance = Column(Integer, nullable=False, default=30)
    credits_reserved = Column(Integer, nullable=False, default=0)

    email_notifications = Column(Boolean, nullable=False, default=True)
    email_digest_frequency = Column(String(10), nullable=False, default="daily")
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_step = Column(SmallInteger, nullable=False, default=0)

    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("credits_balance >= 0", name="chk_credits_non_negative"),
        CheckConstraint("credits_reserved >= 0", name="chk_credits_reserved_non_negative"),
        CheckConstraint(
            "subscription_status IN ('trial','active','past_due','cancelling','cancelled','paused')",
            name="chk_subscription_status"
        ),
        CheckConstraint(
            "subscription_tier IN ('trial','starter','growth','pro','agency')",
            name="chk_subscription_tier"
        ),
    )
```

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr, field_validator
import re


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    timezone: str = "UTC"

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Name must be 2–100 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    subscription_tier: str
    subscription_status: str
    credits_balance: int
    credits_available: int
    trial_ends_at: str | None
    onboarding_completed: bool
    store_count: int = 0

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    refresh_token: str
    expires_in: int = 86400


class RefreshRequest(BaseModel):
    refresh_token: str
```

```python
# backend/app/db/session.py
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# FastAPI dependency
def get_db():
    with get_db_session() as session:
        yield session
```

```python
# backend/app/api/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.session import UserSession
from app.schemas.auth import (
    RegisterRequest, LoginRequest, AuthResponse, UserOut, RefreshRequest
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, hash_token
)
from app.api.dependencies import get_current_user
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_out(user: User, db: Session) -> UserOut:
    store_count = db.query(
        __import__("app.db.models.store", fromlist=["Store"]).Store
    ).filter_by(user_id=user.id).count()
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        credits_balance=user.credits_balance,
        credits_available=user.credits_balance - user.credits_reserved,
        trial_ends_at=user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        onboarding_completed=user.onboarding_completed,
        store_count=store_count,
    )


def _create_session(db: Session, user: User, token: str) -> None:
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=dict)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        User.email == body.email.lower(),
        User.deleted_at.is_(None)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "EMAIL_ALREADY_EXISTS", "message": "Email already registered"}
        )

    user = User(
        email=body.email.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        timezone=body.timezone,
        subscription_status="trial",
        subscription_tier="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        credits_balance=30,
    )
    db.add(user)
    db.flush()  # get user.id without committing

    access_token, _ = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    _create_session(db, user, refresh_token)

    return {
        "data": AuthResponse(
            user=_user_to_out(user, db),
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump()
    }


@router.post("/login", response_model=dict)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == body.email.lower(),
        User.deleted_at.is_(None)
    ).first()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
        )

    user.last_login_at = datetime.now(timezone.utc)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    _create_session(db, user, refresh_token)

    return {
        "data": AuthResponse(
            user=_user_to_out(user, db),
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump()
    }


@router.post("/refresh", response_model=dict)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_INVALID", "message": "Invalid refresh token"}
        )

    token_hash = hash_token(body.refresh_token)
    session_row = db.query(
        __import__("app.db.models.session", fromlist=["UserSession"]).UserSession
    ).filter(
        __import__("app.db.models.session", fromlist=["UserSession"]).UserSession.token_hash == token_hash,
        __import__("app.db.models.session", fromlist=["UserSession"]).UserSession.is_revoked == False,
    ).first()

    if not session_row or session_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_EXPIRED", "message": "Refresh token expired"}
        )

    new_access, _ = create_access_token(payload["sub"])
    return {"data": {"access_token": new_access, "expires_in": 86400}}


@router.post("/logout", response_model=dict)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Revoke all non-expired sessions for this user
    # (in production: revoke only the current token by passing it in the request)
    from app.db.models.session import UserSession
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True})
    return {"data": {"success": True}}


@router.get("/me", response_model=dict)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"data": _user_to_out(current_user, db).model_dump()}
```

```python
# backend/app/api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.user import User
from app.core.security import decode_token

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "Invalid or expired token"}
        )

    user = db.query(User).filter(
        User.id == payload["sub"],
        User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "User not found"}
        )

    return user


def require_tier(required: str):
    TIER_RANK = {"trial": 0, "starter": 1, "growth": 2, "pro": 3, "agency": 4}

    def check(current_user: User = Depends(get_current_user)):
        user_rank = TIER_RANK.get(current_user.subscription_tier, 0)
        required_rank = TIER_RANK.get(required, 0)
        if user_rank < required_rank:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UPGRADE_REQUIRED",
                    "message": f"This feature requires {required} plan or higher.",
                    "details": {
                        "required_tier": required,
                        "current_tier": current_user.subscription_tier,
                        "upgrade_url": "/billing/upgrade",
                    }
                }
            )
        return current_user
    return check
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, stores, listings, seo, optimizations, agent, billing, webhooks
from app.core.config import settings
import sentry_sdk

if settings.APP_ENV == "production":
    sentry_sdk.init(dsn=settings.SENTRY_DSN)

app = FastAPI(
    title="Etsy AI Growth Agent API",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Credits-Available", "X-Credits-Balance", "X-Request-Id"],
)

# Register routers
app.include_router(auth.router, prefix="/v1")
app.include_router(stores.router, prefix="/v1")
app.include_router(listings.router, prefix="/v1")
app.include_router(seo.router, prefix="/v1")
app.include_router(optimizations.router, prefix="/v1")
app.include_router(agent.router, prefix="/v1")
app.include_router(billing.router, prefix="/v1")
app.include_router(webhooks.router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
```

---

### Endpoint 2: `GET /stores` + `POST /stores/connect/initiate`

```python
# backend/app/api/routes/stores.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.store import Store
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.services.etsy_client import build_etsy_oauth_url
import secrets
import redis as redis_module
import json

router = APIRouter(prefix="/stores", tags=["stores"])
r = redis_module.from_url(settings.REDIS_URL)


def _store_to_dict(store: Store) -> dict:
    return {
        "id": str(store.id),
        "etsy_shop_id": store.etsy_shop_id,
        "shop_name": store.shop_name,
        "shop_url": store.shop_url,
        "icon_url": store.icon_url,
        "currency_code": store.currency_code,
        "status": store.status,
        "sync_status": store.sync_status,
        "listing_count": store.listing_count,
        "health_score": store.health_score,
        "health_computed_at": store.health_computed_at.isoformat() if store.health_computed_at else None,
        "agent_enabled": store.agent_enabled,
        "agent_last_run_at": store.agent_last_run_at.isoformat() if store.agent_last_run_at else None,
        "last_synced_at": store.last_synced_at.isoformat() if store.last_synced_at else None,
        "created_at": store.created_at.isoformat(),
    }


@router.get("", response_model=dict)
def list_stores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stores = db.query(Store).filter_by(user_id=current_user.id).all()
    return {"data": [_store_to_dict(s) for s in stores]}


@router.post("/connect/initiate", response_model=dict)
def initiate_etsy_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check store limit for tier
    STORE_LIMITS = {"trial": 1, "starter": 1, "growth": 2, "pro": 5, "agency": 20}
    max_stores = STORE_LIMITS.get(current_user.subscription_tier, 1)
    current_count = db.query(Store).filter_by(user_id=current_user.id).count()

    if current_count >= max_stores:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_LIMIT_REACHED",
                "message": f"Your {current_user.subscription_tier} plan supports {max_stores} store(s).",
                "details": {"max_stores": max_stores, "upgrade_url": "/billing/upgrade"}
            }
        )

    # PKCE + CSRF state
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    # Store in Redis for 10 min
    r.setex(
        f"oauth:state:{state}",
        600,
        json.dumps({"user_id": str(current_user.id), "code_verifier": code_verifier})
    )

    oauth_url = build_etsy_oauth_url(state, code_verifier)
    return {"data": {"oauth_url": oauth_url, "state": state, "expires_in": 600}}


@router.get("/connect/callback")
def etsy_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    # Verify state
    cached = r.get(f"oauth:state:{state}")
    if not cached:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard/stores?error=OAUTH_STATE_MISMATCH")

    state_data = json.loads(cached)
    r.delete(f"oauth:state:{state}")

    # Exchange code for tokens
    from app.services.etsy_client import exchange_oauth_code
    from app.core.encryption import encrypt
    from fastapi.responses import RedirectResponse
    import httpx

    try:
        tokens = exchange_oauth_code(code, state_data["code_verifier"])
    except Exception as e:
        return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard/stores?error=OAUTH_FAILED")

    # Fetch shop info
    shop = _fetch_etsy_shop(tokens["access_token"])

    # Upsert store
    store = db.query(Store).filter_by(etsy_shop_id=str(shop["shop_id"])).first()
    if not store:
        store = Store(
            user_id=state_data["user_id"],
            etsy_shop_id=str(shop["shop_id"]),
            shop_name=shop["shop_name"],
            shop_url=shop.get("url"),
            icon_url=shop.get("icon", {}).get("url_fullxfull"),
        )
        db.add(store)
    else:
        store.user_id = state_data["user_id"]

    # Encrypt and store tokens
    from datetime import datetime, timezone, timedelta
    store.etsy_access_token = encrypt(tokens["access_token"])
    store.etsy_refresh_token = encrypt(tokens["refresh_token"])
    store.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
    store.token_scope = tokens.get("token_type")
    db.flush()

    # Kick off first sync
    from app.tasks.sync import sync_store_listings
    sync_store_listings.delay(str(store.id))

    return RedirectResponse(
        f"{settings.FRONTEND_URL}/dashboard/stores?connected=true&shop_name={shop['shop_name']}"
    )


def _fetch_etsy_shop(access_token: str) -> dict:
    import httpx
    resp = httpx.get(
        "https://openapi.etsy.com/v3/application/users/me/shops",
        headers={
            "x-api-key": settings.ETSY_CLIENT_ID,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]
```

---

### Endpoint 3: `POST /listings/{id}/seo/analyze`

```python
# backend/app/api/routes/seo.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.listing import Listing
from app.db.models.analysis import SeoAnalysis
from app.api.dependencies import get_current_user
from app.services.credit_service import CreditService
from app.core.config import settings
import redis as redis_module

router = APIRouter(tags=["seo"])
r = redis_module.from_url(settings.REDIS_URL)
credit_service = CreditService(r)

SEO_ANALYSIS_COST = 2   # credits


def _verify_listing_ownership(listing_id: str, user: User, db: Session) -> Listing:
    listing = db.query(Listing).filter_by(id=listing_id).first()
    if not listing:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Listing not found"})

    from app.db.models.store import Store
    store = db.query(Store).filter_by(id=listing.store_id, user_id=user.id).first()
    if not store:
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})

    return listing


@router.get("/listings/{listing_id}/seo", response_model=dict)
def get_seo_analysis(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _verify_listing_ownership(listing_id, current_user, db)
    analysis = (
        db.query(SeoAnalysis)
        .filter_by(listing_id=listing.id)
        .order_by(SeoAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            404,
            detail={
                "code": "NO_ANALYSIS_FOUND",
                "message": "No SEO analysis found. Trigger one with POST /listings/{id}/seo/analyze"
            }
        )

    return {
        "data": {
            "id": str(analysis.id),
            "overall_score": analysis.overall_score,
            "title_score": analysis.title_score,
            "tags_score": analysis.tags_score,
            "description_score": analysis.description_score,
            "priority": analysis.priority,
            "title_analysis": {
                "current_title": analysis.current_title,
                "optimized_title": analysis.optimized_title,
                "primary_keyword": analysis.title_primary_keyword,
                "keyword_position": analysis.title_keyword_position,
                "issues": analysis.title_issues or [],
                "change_rationale": analysis.title_change_rationale,
            },
            "tags_analysis": {
                "current_tags": analysis.current_tags or [],
                "optimized_tags": analysis.optimized_tags or [],
                "weak_tags": analysis.weak_tags or [],
                "missing_high_value_tags": analysis.missing_high_value_tags or [],
            },
            "description_analysis": {
                "issues": analysis.description_issues or [],
                "recommended_additions": analysis.recommended_additions or [],
            },
            "estimated_traffic_lift_pct": analysis.estimated_traffic_lift,
            "competitor_gap_summary": analysis.competitor_gap_summary,
            "from_cache": analysis.from_cache,
            "model_used": analysis.model_used,
            "cost_usd": float(analysis.cost_usd) if analysis.cost_usd else None,
            "created_at": analysis.created_at.isoformat(),
        }
    }


@router.post("/listings/{listing_id}/seo/analyze", response_model=dict, status_code=202)
def trigger_seo_analysis(
    listing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _verify_listing_ownership(listing_id, current_user, db)

    # Check credits (free if covered by active daily run — skip charge for now)
    available = credit_service.get_balance(str(current_user.id))["available"]
    if available < SEO_ANALYSIS_COST:
        raise HTTPException(
            402,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": f"Need {SEO_ANALYSIS_COST} credits; you have {available}.",
                "details": {"required": SEO_ANALYSIS_COST, "available": available}
            }
        )

    # Check not already running
    from app.db.models.agent import AgentRun
    running = db.query(AgentRun).filter(
        AgentRun.store_id == listing.store_id,
        AgentRun.run_type == "seo_analysis",
        AgentRun.status.in_(["pending", "running"]),
    ).first()
    if running:
        raise HTTPException(
            409,
            detail={"code": "ANALYSIS_IN_PROGRESS", "message": "SEO analysis already running"}
        )

    # Create agent_run record
    from app.db.models.agent import AgentRun, AgentRunStatus
    from uuid import uuid4
    run = AgentRun(
        store_id=listing.store_id,
        user_id=current_user.id,
        run_type="seo_analysis",
        status="pending",
        triggered_by="user",
        credits_reserved=SEO_ANALYSIS_COST,
    )
    db.add(run)
    db.flush()
    run_id = str(run.id)

    # Reserve credits
    credit_service.reserve(str(current_user.id), SEO_ANALYSIS_COST, run_id)

    # Queue Celery task
    from app.tasks.seo import analyze_single_listing
    analyze_single_listing.apply_async(
        args=[listing_id, run_id],
        queue="critical",
        task_id=run_id,
    )

    return {
        "data": {
            "run_id": run_id,
            "status": "pending",
            "estimated_seconds": 20,
        }
    }


@router.post("/listings/{listing_id}/seo/apply", response_model=dict, status_code=201)
def apply_seo_analysis(
    listing_id: str,
    body: dict = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _verify_listing_ownership(listing_id, current_user, db)
    analysis = (
        db.query(SeoAnalysis)
        .filter_by(listing_id=listing.id)
        .order_by(SeoAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(404, detail={"code": "NO_ANALYSIS_FOUND", "message": "Run analysis first"})

    fields = (body or {}).get("fields", ["title", "tags", "description"])
    created_ids = []

    from app.db.models.analysis import ListingOptimization
    import json

    if "title" in fields and analysis.optimized_title:
        opt = ListingOptimization(
            listing_id=listing.id,
            optimization_type="title",
            old_value=listing.title,
            new_value=analysis.optimized_title,
            change_summary=analysis.title_change_rationale,
            impact_estimate={"seo_score_delta": analysis.title_score},
            status="pending",
        )
        db.add(opt)
        db.flush()
        created_ids.append(str(opt.id))

    if "tags" in fields and analysis.optimized_tags:
        opt = ListingOptimization(
            listing_id=listing.id,
            optimization_type="tags",
            old_value=json.dumps(listing.tags or []),
            new_value=json.dumps(analysis.optimized_tags),
            change_summary=f"Replaced {len(analysis.weak_tags or [])} weak tags, added {len(analysis.missing_high_value_tags or [])} high-value tags",
            impact_estimate={"seo_score_delta": analysis.tags_score},
            status="pending",
        )
        db.add(opt)
        db.flush()
        created_ids.append(str(opt.id))

    return {
        "data": {
            "optimization_ids": created_ids,
            "message": f"{len(created_ids)} optimization(s) created. Review and approve in the Optimizations tab."
        }
    }
```

---

## 5. First Dashboard Page

The **store overview page** (`/dashboard`) — shows health score, today's insights, pending optimizations, and agent run status.

### 5.1 API Client

```typescript
// frontend/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/v1'

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<{ data: T; meta?: Record<string, number> }> {
  const { token, ...fetchOptions } = options
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers as Record<string, string> ?? {}),
  }

  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw Object.assign(new Error(body?.error?.message ?? 'API error'), {
      code: body?.error?.code,
      status: res.status,
    })
  }

  return res.json()
}

export const api = {
  auth: {
    me: (token: string) => apiFetch<UserProfile>('/auth/me', { token }),
    login: (email: string, password: string) =>
      apiFetch<AuthResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (data: RegisterData) =>
      apiFetch<AuthResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  stores: {
    list: (token: string) => apiFetch<Store[]>('/stores', { token }),
    get: (storeId: string, token: string) =>
      apiFetch<Store>(`/stores/${storeId}`, { token }),
    dashboard: (storeId: string, token: string) =>
      apiFetch<StoreDashboard>(`/stores/${storeId}/dashboard`, { token }),
    health: (storeId: string, token: string) =>
      apiFetch<StoreHealth>(`/stores/${storeId}/health`, { token }),
    sync: (storeId: string, token: string) =>
      apiFetch<{ job_id: string }>(`/stores/${storeId}/sync`, { method: 'POST', token }),
    initiateConnect: (token: string) =>
      apiFetch<{ oauth_url: string }>('/stores/connect/initiate', { method: 'POST', token }),
  },
  optimizations: {
    list: (storeId: string, token: string, status = 'pending') =>
      apiFetch<Optimization[]>(`/stores/${storeId}/optimizations?status=${status}`, { token }),
    approve: (id: string, token: string) =>
      apiFetch<Optimization>(`/optimizations/${id}/approve`, { method: 'POST', token }),
    reject: (id: string, reason: string, token: string) =>
      apiFetch<Optimization>(`/optimizations/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
        token,
      }),
    apply: (id: string, token: string) =>
      apiFetch<Optimization>(`/optimizations/${id}/apply`, { method: 'POST', token }),
  },
  agent: {
    runs: (storeId: string, token: string) =>
      apiFetch<AgentRun[]>(`/stores/${storeId}/agent/runs`, { token }),
    trigger: (storeId: string, runType: string, token: string) =>
      apiFetch<{ run_id: string }>(`/stores/${storeId}/agent/run`, {
        method: 'POST',
        body: JSON.stringify({ run_type: runType }),
        token,
      }),
  },
}
```

### 5.2 Zustand Store

```typescript
// frontend/lib/store.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  activeStoreId: string | null
  stores: Store[]
  setActiveStoreId: (id: string) => void
  setStores: (stores: Store[]) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activeStoreId: null,
      stores: [],
      setActiveStoreId: (id) => set({ activeStoreId: id }),
      setStores: (stores) => {
        set({ stores })
        // Auto-select first store if none active
        set((state) => ({
          activeStoreId: state.activeStoreId ?? stores[0]?.id ?? null,
        }))
      },
    }),
    { name: 'app-store' }
  )
)
```

### 5.3 Dashboard Layout

```tsx
// frontend/app/(dashboard)/layout.tsx
import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')

  return (
    <div className="flex h-screen bg-zinc-50 overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
```

### 5.4 Dashboard Page (Store Overview)

```tsx
// frontend/app/(dashboard)/dashboard/page.tsx
'use client'

import { useSession } from 'next-auth/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAppStore } from '@/lib/store'
import { api } from '@/lib/api'
import { HealthScoreCard } from '@/components/dashboard/HealthScoreCard'
import { TodaysSummary } from '@/components/dashboard/TodaysSummary'
import { AgentRunStatus } from '@/components/dashboard/AgentRunStatus'
import { OptimizationPreview } from '@/components/dashboard/OptimizationPreview'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, Zap } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'

export default function DashboardPage() {
  const { data: session } = useSession()
  const { activeStoreId } = useAppStore()
  const queryClient = useQueryClient()
  const token = session?.accessToken as string

  const {
    data: dashboard,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['dashboard', activeStoreId],
    queryFn: () => api.stores.dashboard(activeStoreId!, token),
    enabled: !!activeStoreId && !!token,
    refetchInterval: 60_000,    // refresh every minute
    select: (res) => res.data,
  })

  const { data: optimizations } = useQuery({
    queryKey: ['optimizations', activeStoreId, 'pending'],
    queryFn: () => api.optimizations.list(activeStoreId!, token),
    enabled: !!activeStoreId && !!token,
    select: (res) => res.data,
  })

  const triggerAgent = useMutation({
    mutationFn: () => api.agent.trigger(activeStoreId!, 'daily', token),
    onSuccess: () => {
      toast({ title: 'Daily analysis started', description: 'Results in ~5 minutes.' })
      queryClient.invalidateQueries({ queryKey: ['dashboard', activeStoreId] })
    },
    onError: (err: any) => {
      toast({
        variant: 'destructive',
        title: 'Could not start analysis',
        description: err.message,
      })
    },
  })

  if (!activeStoreId) return <NoStoreConnected />

  if (isLoading) return <DashboardSkeleton />

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Failed to load dashboard. Please refresh.
      </div>
    )
  }

  if (!dashboard) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">
            {dashboard.store.shop_name}
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {dashboard.store.listing_count} active listings ·{' '}
            Last analyzed {formatRelativeTime(dashboard.agent_runs.last_run?.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['dashboard'] })}
          >
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => triggerAgent.mutate()}
            disabled={triggerAgent.isPending}
          >
            <Zap className="h-4 w-4 mr-1.5" />
            {triggerAgent.isPending ? 'Running...' : 'Run Analysis'}
          </Button>
        </div>
      </div>

      {/* Top row: health + insights + agent status */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <HealthScoreCard
          score={dashboard.health.overall_score}
          breakdown={dashboard.health.breakdown}
          trend={dashboard.health.trend_vs_yesterday}
        />
        <TodaysSummary
          headline={dashboard.today_insights.headline}
          newOptimizations={dashboard.today_insights.new_optimizations}
          trendingKeywords={dashboard.today_insights.trending_keywords}
        />
        <AgentRunStatus
          lastRun={dashboard.agent_runs.last_run}
          nextScheduled={dashboard.agent_runs.next_scheduled}
          storeId={activeStoreId}
        />
      </div>

      {/* Pending optimizations */}
      {optimizations && optimizations.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-zinc-900">
              Pending Optimizations
              <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
                {optimizations.length}
              </span>
            </h2>
            <Button variant="ghost" size="sm" asChild>
              <a href="/dashboard/optimizations">View all →</a>
            </Button>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {optimizations.slice(0, 4).map((opt) => (
              <OptimizationPreview key={opt.id} optimization={opt} token={token} />
            ))}
          </div>
        </div>
      )}

      {/* Top listings */}
      {dashboard.top_listings.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-zinc-900">Top Listings</h2>
            <Button variant="ghost" size="sm" asChild>
              <a href="/dashboard/listings">View all →</a>
            </Button>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-100 bg-zinc-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-zinc-500">Listing</th>
                  <th className="px-4 py-3 text-right font-medium text-zinc-500">Views</th>
                  <th className="px-4 py-3 text-right font-medium text-zinc-500">SEO Score</th>
                  <th className="px-4 py-3 text-right font-medium text-zinc-500">Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {dashboard.top_listings.map((listing) => (
                  <tr key={listing.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3">
                      <a
                        href={`/dashboard/listings/${listing.id}`}
                        className="font-medium text-zinc-900 hover:text-indigo-600 truncate block max-w-xs"
                      >
                        {listing.title}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-600">
                      {listing.views.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <SeoScorePill score={listing.seo_score} />
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-600">
                      ${listing.price_usd?.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SeoScorePill({ score }: { score: number | null }) {
  if (score === null) return <span className="text-zinc-400 text-xs">–</span>
  const color =
    score >= 80 ? 'bg-green-100 text-green-700' :
    score >= 60 ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {score}
    </span>
  )
}

function NoStoreConnected() {
  return (
    <div className="flex flex-col items-center justify-center h-96 text-center space-y-4">
      <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center">
        <Zap className="w-8 h-8 text-indigo-600" />
      </div>
      <div>
        <h2 className="text-xl font-semibold text-zinc-900">Connect your Etsy store</h2>
        <p className="text-zinc-500 mt-1 max-w-sm">
          Connect your store to start getting AI-powered recommendations.
        </p>
      </div>
      <Button asChild>
        <a href="/dashboard/stores">Connect Etsy Store</a>
      </Button>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-9 w-32" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-36 rounded-lg" />
        <Skeleton className="h-36 rounded-lg" />
        <Skeleton className="h-36 rounded-lg" />
      </div>
      <Skeleton className="h-64 rounded-lg" />
    </div>
  )
}

function formatRelativeTime(iso: string | undefined): string {
  if (!iso) return 'never'
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
```

### 5.5 HealthScoreCard Component

```tsx
// frontend/components/dashboard/HealthScoreCard.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface HealthBreakdown {
  seo: number
  pricing: number
  images: number
  trends: number
  reviews: number
}

interface Props {
  score: number
  breakdown: HealthBreakdown
  trend: 'up' | 'down' | 'stable'
}

export function HealthScoreCard({ score, breakdown, trend }: Props) {
  const color =
    score >= 80 ? 'text-green-600' :
    score >= 60 ? 'text-yellow-600' :
                  'text-red-600'

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-zinc-400'

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-zinc-500">Store Health Score</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between mb-4">
          <span className={`text-5xl font-bold tabular-nums ${color}`}>{score}</span>
          <div className={`flex items-center gap-1 text-sm ${trendColor}`}>
            <TrendIcon className="h-4 w-4" />
            <span className="capitalize">{trend}</span>
          </div>
        </div>
        <div className="space-y-1.5">
          {(Object.entries(breakdown) as [string, number][]).map(([key, val]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-xs text-zinc-500 w-16 capitalize">{key}</span>
              <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    val >= 80 ? 'bg-green-500' : val >= 60 ? 'bg-yellow-400' : 'bg-red-400'
                  }`}
                  style={{ width: `${val}%` }}
                />
              </div>
              <span className="text-xs font-medium text-zinc-700 w-6 text-right">{val}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
```

### 5.6 OptimizationPreview Component

```tsx
// frontend/components/dashboard/OptimizationPreview.tsx
'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { toast } from '@/components/ui/use-toast'
import { Check, X, Tag, Type, FileText } from 'lucide-react'

const TYPE_ICONS = { title: Type, tags: Tag, description: FileText, price: Type, images: FileText }
const TYPE_LABELS = { title: 'Title', tags: 'Tags', description: 'Description', price: 'Price', images: 'Images' }

interface Props {
  optimization: Optimization
  token: string
}

export function OptimizationPreview({ optimization, token }: Props) {
  const [status, setStatus] = useState(optimization.status)
  const queryClient = useQueryClient()
  const Icon = TYPE_ICONS[optimization.optimization_type as keyof typeof TYPE_ICONS] ?? Tag

  const approve = useMutation({
    mutationFn: () => api.optimizations.approve(optimization.id, token),
    onSuccess: () => {
      setStatus('approved')
      toast({ title: 'Approved', description: 'Ready to apply to Etsy.' })
    },
  })

  const reject = useMutation({
    mutationFn: () => api.optimizations.reject(optimization.id, '', token),
    onSuccess: () => {
      setStatus('rejected')
      queryClient.invalidateQueries({ queryKey: ['optimizations'] })
    },
  })

  const apply = useMutation({
    mutationFn: () => api.optimizations.apply(optimization.id, token),
    onSuccess: () => {
      setStatus('applied')
      toast({ title: 'Applied to Etsy!', description: 'Your listing has been updated.' })
      queryClient.invalidateQueries({ queryKey: ['optimizations'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err: any) => {
      setStatus('failed')
      toast({ variant: 'destructive', title: 'Failed to apply', description: err.message })
    },
  })

  const isPending = approve.isPending || reject.isPending || apply.isPending

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-indigo-50 rounded">
              <Icon className="h-3.5 w-3.5 text-indigo-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-500">
                {TYPE_LABELS[optimization.optimization_type as keyof typeof TYPE_LABELS]}
              </p>
              <p className="text-sm font-medium text-zinc-900 truncate max-w-[180px]">
                {optimization.listing_title}
              </p>
            </div>
          </div>
          {optimization.impact_estimate?.seo_score_delta && (
            <Badge variant="secondary" className="text-xs shrink-0">
              +{optimization.impact_estimate.seo_score_delta} SEO
            </Badge>
          )}
        </div>

        {/* Change preview */}
        {optimization.optimization_type === 'title' && (
          <div className="space-y-1 text-xs">
            <p className="line-through text-zinc-400 truncate">{optimization.old_value}</p>
            <p className="text-zinc-900 font-medium truncate">{optimization.new_value}</p>
          </div>
        )}

        {optimization.optimization_type === 'tags' && (
          <div className="space-y-1 text-xs">
            <p className="text-zinc-400 line-clamp-1">
              {JSON.parse(optimization.old_value || '[]').slice(0, 4).join(', ')}
            </p>
            <p className="text-zinc-900">
              {JSON.parse(optimization.new_value || '[]').slice(0, 4).join(', ')}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2 pt-1">
          {status === 'pending' && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-8 text-xs"
                onClick={() => reject.mutate()}
                disabled={isPending}
              >
                <X className="h-3 w-3 mr-1" />
                Skip
              </Button>
              <Button
                size="sm"
                className="flex-1 h-8 text-xs"
                onClick={() => approve.mutate()}
                disabled={isPending}
              >
                <Check className="h-3 w-3 mr-1" />
                Approve
              </Button>
            </>
          )}

          {status === 'approved' && (
            <Button
              size="sm"
              className="w-full h-8 text-xs bg-green-600 hover:bg-green-700"
              onClick={() => apply.mutate()}
              disabled={isPending}
            >
              {apply.isPending ? 'Applying...' : 'Apply to Etsy'}
            </Button>
          )}

          {status === 'applied' && (
            <p className="text-xs text-green-600 font-medium w-full text-center py-1">
              ✓ Live on Etsy
            </p>
          )}

          {status === 'rejected' && (
            <p className="text-xs text-zinc-400 w-full text-center py-1">Skipped</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
```

### 5.7 Types

```typescript
// frontend/types/index.ts

export interface UserProfile {
  id: string
  email: string
  name: string | null
  subscription_tier: 'trial' | 'starter' | 'growth' | 'pro' | 'agency'
  subscription_status: 'trial' | 'active' | 'past_due' | 'cancelling' | 'cancelled'
  credits_balance: number
  credits_available: number
  trial_ends_at: string | null
  onboarding_completed: boolean
  store_count: number
}

export interface Store {
  id: string
  etsy_shop_id: string
  shop_name: string
  shop_url: string | null
  icon_url: string | null
  status: 'active' | 'paused' | 'disconnected' | 'error'
  sync_status: 'idle' | 'syncing' | 'error'
  listing_count: number
  health_score: number | null
  health_computed_at: string | null
  agent_enabled: boolean
  agent_last_run_at: string | null
  last_synced_at: string | null
}

export interface StoreHealth {
  overall_score: number
  breakdown: {
    seo: number
    pricing: number
    images: number
    trends: number
    reviews: number
  }
  top_issues: string[]
  trend_vs_yesterday: 'up' | 'down' | 'stable'
  computed_at: string
}

export interface StoreDashboard {
  store: Store
  health: StoreHealth
  pending_optimizations_count: number
  agent_runs: {
    last_run: AgentRun | null
    next_scheduled: string
  }
  top_listings: ListingSummary[]
  today_insights: {
    headline: string
    new_optimizations: number
    trending_keywords: string[]
  }
  credits: {
    available: number
    balance: number
    next_renewal: string
  }
}

export interface Optimization {
  id: string
  listing_id: string
  listing_title: string
  optimization_type: 'title' | 'tags' | 'description' | 'price' | 'images'
  old_value: string | null
  new_value: string
  change_summary: string | null
  impact_estimate: {
    seo_score_delta?: number
    estimated_views_lift_pct?: number
  } | null
  status: 'pending' | 'approved' | 'rejected' | 'applying' | 'applied' | 'failed'
  created_at: string
}

export interface AgentRun {
  id: string
  run_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress_pct: number
  credits_used: number
  total_cost_usd: number
  result_summary: {
    headline_insight?: string
    new_optimizations_count?: number
    store_health_score?: number
  } | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface ListingSummary {
  id: string
  title: string
  views: number
  seo_score: number | null
  price_usd: number | null
}

export interface AuthResponse {
  user: UserProfile
  access_token: string
  refresh_token: string
  expires_in: number
}

export interface RegisterData {
  email: string
  name: string
  password: string
  timezone?: string
}
```
