# KickOff26

An all-in-one fan companion for the **2026 World Cup** (48 teams across the United States, Canada, and Mexico). KickOff26 brings live scores, an interactive prediction bracket with a Monte Carlo simulator, a travel itinerary planner across the 16 host cities, and real-time watch-party rooms into a single, broadcast-grade web app.

> Looking for the deep technical breakdown - every module, the data pipeline, the real-time gateway, and the database strategy? See **[architecture.md](./architecture.md)**.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [How it fits together](#how-it-fits-together)
- [Quick start](#quick-start)
  - [Option A - Zero-config (SQLite)](#option-a--zero-config-sqlite)
  - [Option B - PostgreSQL (recommended)](#option-b--postgresql-recommended)
  - [Option C - Docker](#option-c--docker)
- [Database: why both SQLite and PostgreSQL?](#database-why-both-sqlite-and-postgresql)
- [Environment variables](#environment-variables)
- [Deployment / fresh database setup](#deployment--fresh-database-setup)
- [Project structure](#project-structure)
- [Live data architecture](#live-data-architecture)
- [Data sources & references](#data-sources--references)
- [WebSocket channels](#websocket-channels)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

> The in-app navigation uses friendly labels (the routes in parentheses are unchanged): **Live Matches** (`/matchday`), **Standings** (`/standings`), **Teams** (`/teams`), **Predictions** (`/bracket`), **Travel Planner** (`/fanplan`), **Following** (`/following`), **Fan Rooms** (`/watch`), **Resources** (`/resources`).

| Module | What it does |
|--------|--------------|
| **Live Matches** (`/matchday`) | Live scores dashboard backed by a Poisson/Elo win-probability engine, a personalized "following" feed, match detail pages with timelines, and momentum alerts pushed over WebSocket. |
| **Standings** (`/standings`) | Live group tables for all 12 groups with real tiebreakers (points, GD, GF). Top 2 of each group plus the 8 best third-placed teams are highlighted, and groups update in real time as scores change. |
| **Teams** (`/teams`) | All 48 nations grouped A-L with flags, team codes, and a per-team detail view (fixtures, venues, squads, coach, and player to watch). |
| **Predictions** (`/bracket`) | Build your group-stage and knockout picks by hand, or run a **Monte Carlo simulator** (1k / 10k / 50k runs) in a background process pool. Export your knockout bracket as a shareable **PNG or PDF**. |
| **Travel Planner** (`/fanplan`) | Itinerary optimizer that picks the best set of matches to attend across the 16 host cities given your followed teams, budget, and travel constraints - rendered on an interactive Leaflet map and **exportable to PDF**. |
| **Fan Rooms** (`/watch`) | Per-match real-time chat rooms with live presence, custom polls, and floating emoji reactions. **Viewing is open to everyone; sending messages and creating polls requires login.** |
| **Resources** (`/resources`) | Curated official links - tournament site, broadcasters, ticketing, host cities - plus the real data sources behind the app. |

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
| **Data sources** | [openfootball](https://github.com/openfootball/worldcup) (schedule, free) · [rezarahiminia World Cup 2026 API](https://github.com/rezarahiminia/worldcup2026) (live scores, `worldcup26.ir`) |
| **Exports** | html2canvas + jsPDF (bracket PNG/PDF, itinerary PDF) - all client-side |

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
     • worldcup_poller / matchday_demo  →  write scores+goal events to DB  →  broadcast over /ws
```

The frontend **never** talks to a football API directly. A single backend poller writes state to the database, and every client receives updates over the WebSocket gateway, so external API usage stays flat regardless of how many users are online.

---

## Quick start

**Prerequisites:** Python 3.11+, Node.js 18+. PostgreSQL 16 is recommended but optional (see Option A).

### Option A - Zero-config (SQLite)

The fastest way to run the app locally. If `DATABASE_URL` is not set, the backend defaults to a local SQLite file (`backend/kickoff26.db`) - no database server required.

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

### Option B - PostgreSQL (recommended)

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

# First run only - seed tables and fixtures:
#   cd backend; python scripts/init_db_data.py

# 4. Frontend
cd frontend
npm install
npm run dev
```

**Important:** always run Uvicorn from the `backend/` folder (not the repo root), and restart the backend after editing `.env`.

### Option C - Docker

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
| **When it's used** | When `DATABASE_URL` is unset - the default in [`app/config.py`](./backend/app/config.py) is `sqlite+aiosqlite:///./kickoff26.db`. Tests use a separate `test_kickoff26.db`. | When `DATABASE_URL` points at Postgres - set in `.env` for local dev and by `docker-compose.yml` for containers. |
| **Driver** | `aiosqlite` | `asyncpg` |
| **JSON columns** | stored as `JSON` | stored as `JSONB` (faster, indexable) |
| **Why** | No server to install - clone and run instantly; CI and `pytest` stay hermetic and fast. | Real concurrency, durability, JSONB, and parity with the deployed environment. |

This is wired up in two places:

- **Engine selection** - [`app/db/__init__.py`](./backend/app/db/__init__.py) inspects the URL and adds SQLite-only connect args (`check_same_thread=False`).
- **Column variants** - [`app/models/__init__.py`](./backend/app/models/__init__.py) defines `JsonField = JSON().with_variant(JSONB, "postgresql")`, so the same model is `JSON` on SQLite and `JSONB` on Postgres.

`kickoff26.db` and `test_kickoff26.db` are generated artifacts - safe to delete; they're recreated on the next run/test.

> **Rule of thumb:** use SQLite to try the app in seconds; use PostgreSQL for anything you'd ship or demo.

---

## Environment variables

Copy `.env.example` to `.env` and adjust as needed. Backend settings live in `.env`; frontend settings are the `NEXT_PUBLIC_*` entries.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy async connection string. Postgres (`postgresql+asyncpg://…` or Neon’s `postgresql://…?sslmode=require`) or SQLite (`sqlite+aiosqlite:///./kickoff26.db`). Read entirely from this env var — no hardcoded credentials. Neon SSL is enabled automatically. | SQLite if unset |
| `JWT_SECRET` | Signing secret for auth tokens - set to a long random string. | `change-me` |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | Token algorithm and lifetime. | `HS256` / `10080` (7 days) |
| `DATA_MODE` | `mock` = skip re-seed if DB already populated · `live` = force re-seed on startup. | `mock` (`live` in `.env`) |
| `LIVE_DATA_MODE` | `demo` = one simulated live match, **zero API calls** · `api` = real [rezarahiminia World Cup 2026 API](https://github.com/rezarahiminia/worldcup2026) poller. | `demo` |
| `WORLDCUP_API_TOKEN` | JWT bearer token for the rezarahiminia API (valid ~84 days) - **required** when `LIVE_DATA_MODE=api`. Obtain via `scripts/get_worldcup_token.py`. | empty |
| `WORLDCUP_API_BASE` | Base URL for the API (HTTPS). | `https://worldcup26.ir` |
| `WORLDCUP_API_EMAIL` / `WORLDCUP_API_PASSWORD` | Optional - only read by `scripts/get_worldcup_token.py` to register/authenticate. | empty |
| `API_FOOTBALL_KEY` / `RAPIDAPI_KEY` / `RAPIDAPI_HOST` | Legacy API-Football integration (no longer used by the live poller; kept for reference). | empty |
| `FOOTBALL_DATA_API_KEY` | Optional one-shot score merge from football-data.org at startup. | empty |
| `CACHE_TTL_TEAMS` / `_MATCHES` / `_STANDINGS` | TTLs (seconds) for the DB-backed `api_cache`. | `86400` / `300` / `600` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. | `http://localhost:3000,http://127.0.0.1:3000` |
| `ZAFRONIX_API_KEY` | Optional — kept for manual live re-fetch only; squads ship from bundled JSON | empty |
| `ZAFRONIX_LIVE_FETCH_ENABLED` | Set `true` only to enable live Zafronix HTTP fetches (default `false`) | `false` |
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_MAX_TOKENS` | AI tournament assistant ([Groq](https://console.groq.com)). | empty / `llama-3.3-70b-versatile` / `1024` |
| `NEXT_PUBLIC_API_URL` | Backend base URL used by the frontend. | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL used by the frontend. | `ws://localhost:8000/ws` |

Re-run `python -m app.setup` any time to re-apply schema migrations and re-sync tournament data (idempotent).

---

## Deployment / fresh database setup

Use this flow when deploying to a **new empty database** (e.g. [Neon](https://neon.tech) Postgres). The backend reads **`DATABASE_URL` only** — switch between local Postgres, Neon, or SQLite by changing that one variable.

### 1. Create the database

In Neon, create a project and copy the **pooled** connection string (hostname contains `-pooler`). It looks like:

```env
DATABASE_URL=postgresql://user:pass@ep-xxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

KickOff26 normalizes this to `postgresql+asyncpg://…` and enables TLS automatically (`sslmode=require` or any `*.neon.tech` host).

### 2. Set required environment variables

In your host’s env (Railway, Render, Fly, etc.) or `backend/.env`:

| Variable | Required for production | Notes |
|----------|-------------------------|-------|
| `DATABASE_URL` | Yes | Neon pooled connection string |
| `JWT_SECRET` | Yes | Long random string |
| `LIVE_DATA_MODE` | Yes | Set to `api` for real tournament data |
| `WORLDCUP_API_TOKEN` | Yes when `LIVE_DATA_MODE=api` | From `python scripts/get_worldcup_token.py` |
| `DATA_MODE` | Recommended | Use `mock` after initial setup so restarts don’t force re-seed |
| `ZAFRONIX_API_KEY` | Optional | Kept for manual live re-fetch only |
| `ZAFRONIX_LIVE_FETCH_ENABLED` | No | Leave `false` — squads come from bundled JSON |
| `GROQ_API_KEY` | Optional | AI assistant |
| `CORS_ORIGINS` | Yes | Your frontend URL(s), comma-separated |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` | Yes (frontend) | Public backend / WebSocket URLs |

### 3. One-command bootstrap

From `backend/`, with `DATABASE_URL` and API keys set:

```powershell
python -m app.setup
```

This single command is **idempotent** and safe to re-run. It:

1. **Creates the full schema** on an empty database (all tables, columns, foreign keys, API ID fields).
2. **Seeds fixtures** from the bundled openfootball schedule (teams + matches).
3. **Syncs WorldCup API data** — stadiums, team `api_object_id` / `api_seq_id`, game links, groups cache.
4. **Seeds bundled squads** from `backend/data/team_rosters_2026.json` (all 48 teams; no live Zafronix calls).

Options:

```powershell
python -m app.setup --schema-only      # migrations only, no data sync
python -m app.setup --skip-rosters     # skip bundled squad seed
python -m app.setup --skip-worldcup    # openfootball seed only (offline)
```

Legacy alias: `python scripts/init_db_data.py` runs the same setup.

### 4. What you get on a fresh production DB

- **Populated:** teams, fixtures, stadiums, group mappings, API ID links, optional squads.
- **Empty:** user accounts, bracket picks, watch-room messages, reactions, polls.
- User-generated content accumulates only after real users sign up and use the app.

### 5. Start the app

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify: `GET /health` should report `live_data_mode: api` and `worldcup_api_token_set: true`.

### Maintenance

| Task | Command |
|------|---------|
| Re-sync tournament reference data | `python scripts/sync_worldcup_api.py` or `POST /api/matchday/worldcup/sync` |
| Re-seed bundled squads | `python scripts/seed_team_rosters.py` or `POST /api/teams/rosters/resync` |
| Clear watch-room test content only | `python scripts/clear_room_content.py --confirm` |
| Check relational integrity | `python scripts/verify_db_integrity.py` |

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
│   │   ├── services/          # Business logic - incl. worldcup_api/_live/_sync/_poller, live_standings
│   │   └── websocket/         # /ws handler + shared channel gateway (ws_manager)
│   ├── data/                  # Cached openfootball schedule, ticket estimates (JSON)
│   ├── scripts/               # init_db_data.py, get_worldcup_token.py, build_fixtures_json.py
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

### Data sources

| Data | Source | API key? |
|------|--------|----------|
| Fixtures, groups, kickoff times, venues | [openfootball](https://github.com/openfootball/worldcup) (`backend/data/worldcup_2026.json`) | No |
| Live scores, goal scorers, match status, teams, groups, stadiums | [rezarahiminia World Cup 2026 API](https://github.com/rezarahiminia/worldcup2026) (`https://worldcup26.ir`) | Yes - `WORLDCUP_API_TOKEN` |

### `LIVE_DATA_MODE`

| Mode | Behavior |
|------|----------|
| **`demo`** (default) | One simulated live match (MEX vs RSA) with goals, cards, lineups, probabilities, and notifications. **Zero API calls.** Driven by `matchday_demo.py`. |
| **`api`** | A single backend poller calls `GET /get/games` on the rezarahiminia API during kickoff windows, writes to the DB, and fans out over WebSocket. Driven by `worldcup_poller.py`. |

### Setting up the rezarahiminia live API (`LIVE_DATA_MODE=api`)

1. **Register / authenticate** to get a JWT token (valid ~84 days). From `backend/`:
   ```powershell
   # Register a new account (first time)
   python scripts/get_worldcup_token.py --register --email you@example.com --password "your-password"

   # Or authenticate an existing account
   python scripts/get_worldcup_token.py --email you@example.com --password "your-password"
   ```
2. **Store the token** in `backend/.env` (never hardcode it):
   ```env
   LIVE_DATA_MODE=api
   WORLDCUP_API_TOKEN=eyJhbGciOi...        # printed by the script
   WORLDCUP_API_BASE=https://worldcup26.ir  # HTTPS, not the :3050 HTTP URL
   ```
3. **Restart the backend.** It sends the token as `Authorization: Bearer <token>` on every request. `/health` reports `live_source` and `worldcup_api_token_set`.

The token is read from settings only - it is never committed. Endpoints used: `/get/teams`, `/get/team/{_id}`, `/get/groups`, `/get/games`, `/get/game/{_id}`, `/get/stadiums`.

**Dual IDs (critical):** each API record has `_id` (Mongo object id - use in `/get/game/{_id}` and `/get/team/{_id}`) and `id` (sequential string - used in relational refs like `home_team_id`, `stadium_id`). The sync job stores both as `api_object_id` and `api_seq_id` on `teams`, `stadiums`, and `matches`.

**One-time / re-runnable sync:**

```powershell
cd backend
python scripts/sync_worldcup_api.py
# or POST http://localhost:8000/api/matchday/worldcup/sync
```

This upserts all teams (flags, `iso2`, team codes), stadiums (city/venue), and links all 104 group-stage fixtures to your openfootball schedule rows. Knockout placeholders (32 games without fixed teams yet) are skipped until the API assigns real team ids.

**Live status** is derived from the match payload: `notstarted` (not finished, no `time_elapsed`), `live` (`time_elapsed` present, not finished), `finished` (`finished` is true). **Goal events** come from `home_scorers` / `away_scorers` (scorer + timestamp) and drive notifications and live win-probability updates.

> **Not provided by this API (per the maintainer):** yellow/red cards, substitutions, squads/lineups, and any SSE/WebSocket. In `api` mode the app does **not** fabricate these - lineups show *"not yet available"* and card/substitution play-by-play remains a clearly-labeled feature of `demo` mode only.

### Why API usage stays flat

```
worldcup26.ir  →  backend poller     →  Database  →  WebSocket  →  all clients
 (1 req/poll)     (worldcup_poller.py)   (matches)    (ws_manager)   (any # of users)
```

Clients read DB state via WebSocket, so **API usage does not scale with user count** - only the poller calls the API. It makes one `GET /get/games` call per tick, polls every ~40 s while matches are live, ~60 s inside a kickoff window, and not at all when nothing is live or near kickoff - comfortably within the API's 500 req/60 s limit.

---

## Data sources & references

KickOff26 uses **real data only**, with anything estimated or simulated clearly labeled in the UI.

| Data | Source | Status |
|------|--------|--------|
| Tournament schedule, groups, kickoff times, venues | [openfootball / worldcup.json](https://github.com/openfootball/worldcup.json) | **Real** (open data) |
| Live scores, goal scorers, match status, teams, stadiums | [rezarahiminia World Cup 2026 API](https://github.com/rezarahiminia/worldcup2026) · [worldcup26.ir](https://worldcup26.ir) | **Real** (live, `api` mode) |
| Group standings | Computed on the backend from live match state (tiebreakers: pts, GD, GF) | **Real**, derived |
| Win probabilities | Poisson/Elo model in `app/models/win_probability.py` | **Model output** |
| Ticket-price ranges (Travel Planner) | Published 2026 ticket-pricing reporting (sports/business press) | **Estimated** - not official quotes |
| Team squads & rosters | [Zafronix API](https://api.zafronix.com) — fetched once, bundled as `backend/data/team_rosters_2026.json`; served from DB with **no live polling** (free tier 250 req/day) | **Real** (static bundle) |
| Head coaches & players to watch | [Bolavip](https://bolavip.com/en/world-cup/2026-world-cup-coaches-all-48-managers-of-the-qualified-national-teams) + local JSON | **Real** (curated) |
| Travel distances/times (Travel Planner) | Great-circle estimates between host cities | **Estimated** |
| Demo live match, cards, substitutions | `matchday_demo.py` simulation | **Demo/simulated** (only in `demo` mode) |
| Official info & broadcasters | [Official tournament site](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026), FOX, Telemundo (see in-app **Resources**) | **Real** (official links) |
| Country flags | [flag-icons](https://github.com/lipis/flag-icons) (MIT) | Asset |

Always confirm ticket prices and availability through the official 2026 ticketing channel - in-app figures are estimates.

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

The suite (win-probability, simulator, itinerary, live poller, match calendar/events/lineups, R32 seeding, bracket standings, rooms, sim jobs, and API integration) runs entirely on **SQLite** - no Postgres or Docker required.

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
| Backend won't pick up `.env` changes | Restart Uvicorn - settings load at startup. Run it from `backend/`, not the repo root. |
| `Address already in use` on :8000 | `scripts/dev-backend.ps1` detects this; free the port or stop the existing server. |
| Want a clean database | Drop/recreate the DB (or use a new Neon branch), then run `python -m app.setup`. For watch rooms only: `python scripts/clear_room_content.py --confirm`. |
| CORS errors in the browser | Ensure your frontend origin is in `CORS_ORIGINS` (localhost and 127.0.0.1 are treated as distinct). |

---

## License

MIT
