# KickOff26

An all-in-one fan companion for the **2026 FIFA World Cup** (48 teams across the United States, Canada, and Mexico). KickOff26 brings live scores, an interactive prediction bracket with a Monte Carlo simulator, a travel itinerary planner across the 16 host cities, and real-time watch-party rooms into a single, broadcast-grade web app.

> Looking for the deep technical breakdown — every module, the data pipeline, the real-time gateway, and the database strategy? See **[architecture.md](./architecture.md)**.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [How it fits together](#how-it-fits-together)
- [Quick start](#quick-start)
  - [Option A — Zero-config (SQLite)](#option-a--zero-config-sqlite)
  - [Option B — PostgreSQL (recommended)](#option-b--postgresql-recommended)
  - [Option C — Docker](#option-c--docker)
- [Database: why both SQLite and PostgreSQL?](#database-why-both-sqlite-and-postgresql)
- [Environment variables](#environment-variables)
- [Project structure](#project-structure)
- [Live data architecture](#live-data-architecture)
- [WebSocket channels](#websocket-channels)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

| Module | What it does |
|--------|--------------|
| **MatchDay Companion** | Live scores dashboard backed by a Poisson/Elo win-probability engine, a personalized "following" feed, match detail pages with lineups and timelines, and momentum alerts pushed over WebSocket. |
| **Bracket Predictor** | Build your group-stage and knockout picks by hand, or run a **Monte Carlo simulator** (1k / 10k / 50k runs) in a background process pool, then export a shareable champion poster. |
| **FanPlan** | Itinerary optimizer that picks the best set of matches to attend across the 16 host cities given your followed teams, budget, and travel constraints — rendered on an interactive Leaflet map. |
| **WatchTogether** | Per-match real-time chat rooms with live presence, custom polls, and floating emoji reactions — all synced through the shared WebSocket gateway. |

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Leaflet, native WebSocket client |
| **Backend** | FastAPI, async SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| **Database** | PostgreSQL (primary) · SQLite (zero-config fallback + tests) |
| **Real-time** | A single in-process WebSocket gateway (`ws_manager`) with channel pub/sub |
| **Auth** | JWT (python-jose) + bcrypt password hashing (passlib) |
| **Compute** | NumPy-powered Monte Carlo simulator on a `ProcessPoolExecutor` |
| **Data sources** | [openfootball](https://github.com/openfootball/worldcup) (schedule, free) · [API-Football](https://rapidapi.com/api-sports/api/api-football) (optional live scores) |

---

## How it fits together

```
┌──────────────────────────────┐         ┌────────────────────────────────────────┐
│   Next.js frontend (3000)     │         │            FastAPI backend (8000)         │
│                               │  HTTP   │                                          │
│  MatchDay · Bracket · FanPlan │ ──────► │  /api/*  routers ─► services ─► models   │
│  WatchTogether · Following    │         │                       │                   │
│                               │   WS    │  /ws  ◄────► ws_manager (channel fanout)  │
│  lib/api.ts · lib/websocket.ts│ ◄─────► │                       │                   │
└──────────────────────────────┘         │            ┌──────────▼──────────┐        │
                                          │            │  SQLAlchemy (async) │        │
                                          │            └──────────┬──────────┘        │
                                          └───────────────────────┼───────────────────┘
                                                                  │
                                  ┌───────────────────────────────▼───────────────────────────────┐
                                  │  PostgreSQL (prod / recommended)  ·  SQLite kickoff26.db (dev)  │
                                  └─────────────────────────────────────────────────────────────────┘

   Background loops (started in app lifespan):
     • live_poller / matchday_demo  →  write scores+events to DB  →  broadcast over /ws
     • lineup_fetcher               →  fetch-once lineups near kickoff
```

The frontend **never** talks to a football API directly. A single backend poller writes state to the database, and every client receives updates over the WebSocket gateway, so external API usage stays flat regardless of how many users are online.

---

## Quick start

**Prerequisites:** Python 3.11+, Node.js 18+. PostgreSQL 16 is recommended but optional (see Option A).

### Option A — Zero-config (SQLite)

The fastest way to run the app locally. If `DATABASE_URL` is not set, the backend defaults to a local SQLite file (`backend/kickoff26.db`) — no database server required.

```powershell
# 1. Backend (from backend/, with NO DATABASE_URL in the environment)
cd backend
pip install -r requirements.txt
python scripts/init_db_data.py        # create tables + seed 48 teams & full schedule
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- API health check: <http://localhost:8000/health>
- App: <http://localhost:3000>

> Note: the repo `.env` ships with a PostgreSQL `DATABASE_URL`. To use the SQLite fallback, comment out/remove `DATABASE_URL` (or run in an environment where it is unset).

### Option B — PostgreSQL (recommended)

Mirrors production (JSONB columns, real concurrency, durability).

```powershell
# 1. Create the database (uses postgres / admin123 by default)
.\scripts\setup-postgres.ps1

# 2. Point the backend at Postgres (already the default in .env)
#    DATABASE_URL=postgresql+asyncpg://postgres:admin123@localhost:5432/kickoff26

# 3. Seed + run the backend (handles cwd + port checks for you)
cd backend
pip install -r requirements.txt
cd ..
.\scripts\dev-backend.ps1

# First run only — seed tables and fixtures:
#   cd backend; python scripts/init_db_data.py

# 4. Frontend
cd frontend
npm install
npm run dev
```

**Important:** always run Uvicorn from the `backend/` folder (not the repo root), and restart the backend after editing `.env`.

### Option C — Docker

Brings up PostgreSQL + the backend together. The compose file injects an asyncpg `DATABASE_URL` pointing at the `postgres` service.

```bash
cp .env.example .env
docker compose up -d
# Backend: http://localhost:8000  ·  Postgres: localhost:5432
```

Run the frontend separately with `npm run dev` (or add it to compose). See [`docker-compose.yml`](./docker-compose.yml).

---

## Database: why both SQLite and PostgreSQL?

KickOff26 runs the **same** async SQLAlchemy models and queries against either engine. The driver is chosen entirely by `DATABASE_URL`:

| | **SQLite (`kickoff26.db`)** | **PostgreSQL** |
|---|---|---|
| **Role** | Zero-config fallback + automated tests | Primary datastore for dev & production |
| **When it's used** | When `DATABASE_URL` is unset — the default in [`app/config.py`](./backend/app/config.py) is `sqlite+aiosqlite:///./kickoff26.db`. Tests use a separate `test_kickoff26.db`. | When `DATABASE_URL` points at Postgres — set in `.env` for local dev and by `docker-compose.yml` for containers. |
| **Driver** | `aiosqlite` | `asyncpg` |
| **JSON columns** | stored as `JSON` | stored as `JSONB` (faster, indexable) |
| **Why** | No server to install — clone and run instantly; CI and `pytest` stay hermetic and fast. | Real concurrency, durability, JSONB, and parity with the deployed environment. |

This is wired up in two places:

- **Engine selection** — [`app/db/__init__.py`](./backend/app/db/__init__.py) inspects the URL and adds SQLite-only connect args (`check_same_thread=False`).
- **Column variants** — [`app/models/__init__.py`](./backend/app/models/__init__.py) defines `JsonField = JSON().with_variant(JSONB, "postgresql")`, so the same model is `JSON` on SQLite and `JSONB` on Postgres.

`kickoff26.db` and `test_kickoff26.db` are generated artifacts — safe to delete; they're recreated on the next run/test.

> **Rule of thumb:** use SQLite to try the app in seconds; use PostgreSQL for anything you'd ship or demo.

---

## Environment variables

Copy `.env.example` to `.env` and adjust as needed. Backend settings live in `.env`; frontend settings are the `NEXT_PUBLIC_*` entries.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy async connection string. Postgres (`postgresql+asyncpg://…`) or SQLite (`sqlite+aiosqlite:///./kickoff26.db`). | SQLite if unset |
| `JWT_SECRET` | Signing secret for auth tokens — set to a long random string. | `change-me` |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | Token algorithm and lifetime. | `HS256` / `10080` (7 days) |
| `DATA_MODE` | `mock` = skip re-seed if DB already populated · `live` = force re-seed on startup. | `mock` (`live` in `.env`) |
| `LIVE_DATA_MODE` | `demo` = one simulated live match, **zero API calls** · `api` = real API-Football poller. | `demo` |
| `API_FOOTBALL_KEY` | RapidAPI key for API-Football — required only when `LIVE_DATA_MODE=api`. | empty |
| `RAPIDAPI_KEY` / `RAPIDAPI_HOST` | Legacy alias for the key / API host. | empty / `v3.football.api-sports.io` |
| `FOOTBALL_DATA_API_KEY` | Optional one-shot score merge from football-data.org at startup. | empty |
| `CACHE_TTL_TEAMS` / `_MATCHES` / `_STANDINGS` | TTLs (seconds) for the DB-backed `api_cache`. | `86400` / `300` / `600` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. | `http://localhost:3000,http://127.0.0.1:3000` |
| `NEXT_PUBLIC_API_URL` | Backend base URL used by the frontend. | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL used by the frontend. | `ws://localhost:8000/ws` |

Re-run `python scripts/init_db_data.py` any time to re-seed fixtures.

---

## Project structure

```
KickOff26/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, CORS, router mounting, /health
│   │   ├── config.py          # Pydantic settings (DATABASE_URL default = SQLite)
│   │   ├── db/__init__.py     # Async engine, session, init_db + lightweight migrations
│   │   ├── models/__init__.py # SQLAlchemy ORM models (JSON/JSONB variant)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── auth/              # JWT + bcrypt helpers, user lookups
│   │   ├── api/               # HTTP routers: auth, teams, matchday, bracket, rooms, fanplan
│   │   ├── services/          # Business logic (see architecture.md for each module)
│   │   └── websocket/         # /ws handler + shared channel gateway (ws_manager)
│   ├── data/                  # Cached openfootball schedule, ticket estimates (JSON)
│   ├── scripts/               # init_db_data.py, fetch_worldcup.py, build_fixtures_json.py
│   └── tests/                 # pytest suite (runs on SQLite)
├── frontend/
│   ├── app/                   # Next.js App Router pages (matchday, bracket, fanplan, watch, …)
│   ├── components/            # React UI components (per feature)
│   ├── lib/                   # api.ts, websocket.ts, domain helpers (matchday, watch, bracket…)
│   └── styles/                # Theme tokens + per-feature CSS (atmosphere, watch, home, …)
├── scripts/                   # setup-postgres.ps1, dev-backend.ps1
├── docker-compose.yml         # Postgres + backend services
└── architecture.md            # Full architecture reference
```

---

## Live data architecture

### Data sources (free-tier friendly)

| Data | Source | API key? |
|------|--------|----------|
| Fixtures, groups, kickoff times, venues | [openfootball](https://github.com/openfootball/worldcup) (`backend/data/worldcup_2026.json`) | No |
| Live scores, events, status | [API-Football](https://rapidapi.com/api-sports/api/api-football) via RapidAPI | Yes — `API_FOOTBALL_KEY` |

### `LIVE_DATA_MODE`

| Mode | Behavior |
|------|----------|
| **`demo`** (default) | One simulated live match (MEX vs RSA) with goals, cards, probabilities, and notifications. **Zero API calls.** Driven by `matchday_demo.py`. |
| **`api`** | A single backend poller calls `fixtures?live=all` during kickoff windows; real events drive notifications. Driven by `live_poller.py`. |

```env
# Local dev — live card without consuming any quota
LIVE_DATA_MODE=demo

# Tournament day — real live data
LIVE_DATA_MODE=api
API_FOOTBALL_KEY=your-rapidapi-key
```

### Why API usage stays flat

```
API-Football  →  backend poller  →  Database  →  WebSocket  →  all clients
 (1 req/poll)     (live_poller.py)   (matches)    (ws_manager)   (any # of users)
```

Clients read DB state via WebSocket, so **API usage does not scale with user count** — only the poller calls the API. The poller uses one `fixtures?live=all` call per tick, only polls inside kickoff windows, runs an adaptive interval (5 min idle-live, 90 s for ~5 min after a goal/red card), and halts when the rate-limit header drops below a safety threshold (serving last-known DB state). On `LIVE_DATA_MODE=api`, `/health` reports `api_quota`.

---

## WebSocket channels

Connect to `/ws` and subscribe with `{ "type": "subscribe", "channel": "<name>" }`:

| Channel | Payload |
|---------|---------|
| `match:{id}` | Live updates for a single match |
| `matches:live` | Feed of all live matches |
| `matches:alerts` | Goals, cards, kickoff, full time, momentum swings |
| `sim:{task_id}` | Monte Carlo simulation progress |
| `room:{id}` | WatchTogether chat, polls, reactions, presence |

The client also sends `ping` (gets `pong`) and `unsubscribe`. Subscribing to a `room:{id}` channel automatically registers presence and a join system message.

---

## Testing

```powershell
cd backend
pytest -v
```

The suite (win-probability, simulator, itinerary, live poller, match calendar/events/lineups, R32 seeding, bracket standings, rooms, sim jobs, and API integration) runs entirely on **SQLite** — no Postgres or Docker required.

Frontend logic tests:

```powershell
cd frontend
npm run test:matchday
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `PageNotFoundError` / stale build in Next.js | Stop dev/build, remove `frontend/.next`, then rebuild. |
| Backend won't pick up `.env` changes | Restart Uvicorn — settings load at startup. Run it from `backend/`, not the repo root. |
| `Address already in use` on :8000 | `scripts/dev-backend.ps1` detects this; free the port or stop the existing server. |
| Want a clean database | Delete `backend/kickoff26.db` (SQLite) or drop/recreate the Postgres DB, then re-run `python scripts/init_db_data.py`. |
| CORS errors in the browser | Ensure your frontend origin is in `CORS_ORIGINS` (localhost and 127.0.0.1 are treated as distinct). |

---

## License

MIT
