<div align="center">

<img src="docs/assets/hero-screenshot.png" alt="Consultaion — One question. Multiple AI perspectives. One decision report." width="900" />

<br/>

# Consultaion

**One question. Multiple AI perspectives. One decision report.**

Consultaion runs structured Arena and Debate workflows across multiple LLM
providers simultaneously, surfaces where models agree or disagree, and produces
a verified, structured decision report — not just a chatbot answer.

[![CI](https://github.com/kriptokasim/Consultaion/actions/workflows/ci.yml/badge.svg)](https://github.com/kriptokasim/Consultaion/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[**Live Demo**](https://consultaion.com/live) · [**Example Report**](https://consultaion.com) · [**API Docs**](docs/API.md)

</div>

---

## What is Consultaion?

> **Brand note:** The spelling *Consultaion* is intentional — it's the product
> name, not a typo.

Most AI tools give you one answer. Consultaion gives you a **structured
multi-model debate** — then synthesises it into a decision.

| Without Consultaion | With Consultaion |
|---|---|
| Ask one AI, get one opinion | Run 2–4 models in parallel |
| No way to know if the AI is overconfident | See where models agree and where they clash |
| Raw text you interpret yourself | Structured report: verdict, confidence, key findings, risks |
| Trust the black box | Auditable: every model's reasoning is preserved |

---

## Modes

| Mode | What it does |
|---|---|
| **Arena** | All selected models answer simultaneously; synthesis engine produces a PROCEED / INVESTIGATE / REJECT verdict |
| **Debate** | Parliamentary-style: models take positions, critique each other through rounds, judge panel scores |
| **Compare** | Side-by-side output from multiple models on the same prompt |
| **Oracle** | Single deep-reasoning model for research-grade synthesis |
| **RedTeam** | Adversarial challenge mode — one model argues against a draft decision |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Next.js 15 / React 19 frontend  (apps/web)             │
│  Tailwind · Zustand · TanStack Query · SSE streaming    │
└──────────────────────────┬──────────────────────────────┘
                           │  HTTP + Server-Sent Events
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI backend  (apps/api)                            │
│  SQLModel · PostgreSQL · Alembic migrations             │
│  Celery + Redis (async tasks, SSE broker)               │
│  LiteLLM adapter (OpenAI · Anthropic · Gemini · Groq…) │
│  BYOK encryption  (AES-256-GCM, per-user AAD)          │
└─────────────┬───────────────────────────┬───────────────┘
              │                           │
  ┌───────────▼───────┐       ┌───────────▼──────────┐
  │  Arena Engine     │       │  Reporting Engine     │
  │  asyncio.gather   │       │  Embedding cosine     │
  │  per-model SSE    │       │  G-Eval rubric        │
  │  delta streaming  │       │  Critique-revise loop │
  └───────────────────┘       └──────────────────────┘
```

**Tech stack:**

| Layer | Technology |
|---|---|
| Frontend | Next.js 15.5, React 19, Tailwind CSS, Radix UI, Zustand |
| Backend | FastAPI 0.138, Python 3.11, SQLModel, Alembic |
| Database | PostgreSQL (prod) · SQLite (CI) |
| Task queue | Celery 5.4, Redis |
| LLM routing | LiteLLM 1.84+ with OpenRouter fallback |
| Auth | PyJWT 2.13, bcrypt, Google OAuth, progressive account lockout |
| Observability | Sentry, PostHog, Prometheus, OpenTelemetry, Langfuse |
| CI | GitHub Actions — Bandit, pip-audit, npm audit, ruff, mypy, pytest (≥75% coverage) |

---

## Quick Start

### Prerequisites

- Python 3.11 (the backend **must** run on 3.11 — newer versions cause ASGI test hangs)
- Node.js 20+
- Docker + Docker Compose

### 1 — Clone and configure

```bash
git clone https://github.com/kriptokasim/Consultaion.git
cd Consultaion
cp apps/api/.env.example apps/api/.env
```

Edit `apps/api/.env` — the minimum required variables:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/consultaion_dev
JWT_SECRET=<random-32-char-string>
INTERNAL_SECRET=<same-32-char-string-in-vercel>
OPENROUTER_API_KEY=sk-or-...          # one key unlocks all models
STREAMING_RESPONSES_ENABLED=1         # stream tokens as they arrive
ARENA_MAX_TOKENS=800                  # faster responses
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

### 2 — Start infrastructure

```bash
cd infra && docker compose up -d db redis
```

### 3 — Backend

```bash
cd apps/api
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### 4 — Frontend

```bash
cd apps/web
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 5 — Run with mock LLMs (no API keys needed)

```bash
# In apps/api/.env:
USE_MOCK=1
STREAMING_RESPONSES_ENABLED=1
```

---

## Environment Variables Reference

### Backend (`apps/api/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `JWT_SECRET` | ✅ | — | 32+ char random secret for auth tokens |
| `INTERNAL_SECRET` | ✅ | — | Must match Vercel/frontend env var exactly |
| `OPENROUTER_API_KEY` | ✅* | — | One key gives access to all models via OpenRouter |
| `REDIS_URL` | ✅ | — | Required for SSE, task queue, and OAuth state |
| `RATE_LIMIT_BACKEND` | ✅ | `memory` | Set to `redis` in production |
| `STREAMING_RESPONSES_ENABLED` | ⚠️ | `False` | **Set to `1` for real-time token streaming** |
| `ARENA_MAX_TOKENS` | — | `1200` | Max tokens per model per run (800 = faster) |
| `ARENA_MODEL_TIMEOUT_SECONDS` | — | `45` | Per-model timeout before marking as failed |
| `GOOGLE_CLIENT_ID` | — | — | For Google OAuth sign-in |
| `GOOGLE_CLIENT_SECRET` | — | — | For Google OAuth sign-in |
| `GOOGLE_REDIRECT_URL` | — | — | Must be `https://your-frontend.vercel.app/api/auth/google/callback` |
| `REQUIRE_REAL_LLM` | — | `0` | Set `1` in production to reject mock mode |
| `USE_MOCK` | — | `0` | Set `1` for dev with no API keys |
| `ENV` | — | `development` | `production` / `staging` / `development` / `test` |
| `STRIPE_SECRET_KEY` | — | — | For billing integration |
| `STRIPE_WEBHOOK_SECRET` | — | — | For Stripe webhook signature verification |
| `SENTRY_DSN` | — | — | Error tracking |

\* Or set individual provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`

### Frontend (`apps/web/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL (e.g. `https://your-api.onrender.com`) |
| `INTERNAL_SECRET` | ✅ | Must match backend exactly (used for Google OAuth handoff) |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_REDIRECT_URL` | — | `https://your-frontend/api/auth/google/callback` |
| `NEXT_PUBLIC_POSTHOG_KEY` | — | Analytics |
| `NEXT_PUBLIC_SITE_URL` | — | Full frontend URL for OG tags |

---

## Google OAuth Setup

The OAuth state is stored in Redis on the backend. Both environments must be configured:

1. In **Google Cloud Console** → Credentials → add `https://your-frontend.vercel.app/api/auth/google/callback` as an Authorised redirect URI.
2. In **Render** (backend): set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URL`, `INTERNAL_SECRET`, `REDIS_URL`, `RATE_LIMIT_BACKEND=redis`.
3. In **Vercel** (frontend): set `INTERNAL_SECRET` to the **exact same string** as Render.

If you see `auth.invalid_state` — the most common cause is `INTERNAL_SECRET` mismatch or `RATE_LIMIT_BACKEND=memory` on Render (OAuth state is lost between dynos).

---

## Deployment (Render + Vercel)

### Backend (Render Web Service)

```
Build command:  pip install -r apps/api/requirements.txt
Start command:  cd apps/api && python scripts/migrate_database.py && uvicorn main:app --host 0.0.0.0 --port $PORT
Root directory: apps/api
```

**Required Render env vars:** `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `INTERNAL_SECRET`, `OPENROUTER_API_KEY`, `RATE_LIMIT_BACKEND=redis`, `STREAMING_RESPONSES_ENABLED=1`, `ENV=production`, `REQUIRE_REAL_LLM=1`

### Frontend (Vercel)

```
Framework:    Next.js
Root:         apps/web
Build cmd:    npm run build
Output dir:   .next
```

**Required Vercel env vars:** `NEXT_PUBLIC_API_URL`, `INTERNAL_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_REDIRECT_URL`

---

## BYOK (Bring Your Own Key)

Users can add their own provider API keys in **Settings → Provider Keys**. Keys are:
- Encrypted at rest with AES-256-GCM
- AAD-bound to `(user_id, provider)` — a stolen ciphertext cannot be decrypted under a different account
- Never logged or exposed in API responses
- Resolved at runtime per-request by the model gateway

---

## Development

### Run tests

```bash
# Backend (requires Python 3.11, Postgres running)
cd apps/api
pytest                          # full suite + coverage report
pytest -q --no-cov              # fast run, no coverage

# Frontend
cd apps/web
npx vitest run                  # unit tests
npm run test:e2e                # Playwright e2e (app must be running)
```

### Code quality

```bash
# From repo root:
ruff check apps/api             # lint
ruff check apps/api --fix       # lint + auto-fix
mypy apps/api                   # type check

# From apps/web:
npx tsc --noEmit                # TypeScript check
```

**CI gates:** ruff, mypy, pytest ≥75% coverage, Bandit (SAST), pip-audit, npm audit — all must pass on every PR.

### Project structure

```
Consultaion/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── arena/              # Arena mode engine (asyncio.gather fan-out)
│   │   ├── model_gateway/      # LiteLLM adapter, routing, BYOK resolution
│   │   ├── orchestration/      # Pipeline, checkpoints, finalization
│   │   ├── parliament/         # Model registry, router, debate engine
│   │   ├── reporting/          # Synthesizer, G-Eval, claim similarity
│   │   ├── routes/             # FastAPI route handlers
│   │   ├── security/           # Encryption, OAuth state store
│   │   ├── worker/             # Celery tasks (billing, arena, debate)
│   │   └── alembic/            # DB migrations
│   └── web/                    # Next.js 15 frontend
│       ├── app/                # App Router pages
│       ├── components/         # UI components (arena/, parliament/, report/…)
│       ├── hooks/              # React hooks (useRunWorkspace, usePromptHistory…)
│       └── lib/                # API client, types, utilities
├── infra/                      # Docker Compose (dev)
├── docs/                       # Architecture, API docs, diligence pack
└── scripts/                    # Migration, model freshness, audit tools
```

---

## Supported Models (via OpenRouter)

With a single `OPENROUTER_API_KEY` the following models are available:

| Model ID | Provider | Notes |
|---|---|---|
| `deepseek-r1` | DeepSeek | Best reasoning quality |
| `router-smart` | OpenRouter → GPT-4o-mini | Fast, cheap default |
| `router-deep` | OpenRouter → GPT-4o | Premium quality |
| `llama-3-free` | Meta via OpenRouter | Free tier, rate limited |
| `mimo-v2-free` | Xiaomi via OpenRouter | Free tier, rate limited |

Direct provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`) unlock those providers directly without OpenRouter.

Users can also add their own keys per-provider in Settings → Provider Keys (BYOK).

---

## Diligence & Trust

Consultaion is in pre-seed / internal beta. The repository includes a diligence pack:

| Document | Summary |
|---|---|
| [SECURITY.md](SECURITY.md) | Deployment security guidance |
| [SECURITY_OVERVIEW.md](docs/diligence/SECURITY_OVERVIEW.md) | Auth, encryption, secret management |
| [SOC2_READINESS.md](docs/diligence/SOC2_READINESS.md) | Planned compliance roadmap |
| [DATA_RETENTION.md](docs/diligence/DATA_RETENTION.md) | Data handling and deletion policies |
| [CI_OVERVIEW.md](docs/diligence/CI_OVERVIEW.md) | CI pipeline and gates |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

*These documents describe readiness work and roadmap; they are not compliance certifications.*

---

## Roadmap

- [x] SSE streaming, mock agents, final synthesis
- [x] Real LLM calls via LiteLLM
- [x] PostgreSQL schema + Alembic migrations
- [x] Arena mode with parallel fan-out
- [x] BYOK key encryption (AES-256-GCM)
- [x] Google OAuth + progressive account lockout
- [x] Stripe billing + webhook atomicity
- [x] Bandit / pip-audit / npm audit in CI
- [x] Mobile bottom navigation + swipe card UI
- [ ] SOC 2 Type I audit
- [ ] SSO / SAML for enterprise
- [ ] SCIM provisioning
- [ ] Async synthesis triggered before all models finish
- [ ] Per-model call timeout dashboard

---

## Contributing

This is a proprietary product. External contributions are not accepted at this time.
If you've found a security issue, please email the maintainer directly rather than opening a public issue.

---

## License

Proprietary and Confidential. All rights reserved. See [LICENSE](LICENSE).

---

<div align="center">

Built by [@kriptokasim](https://github.com/kriptokasim)

*"Consultaion" is intentional — it's the product name.*

</div>
