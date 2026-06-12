# ⚽ KickOff26

**A full-stack companion web app for the 2026 World Cup** - 48 teams across the United States, Canada, and Mexico, all in one broadcast-grade app. Live scores with a win-probability model, an interactive prediction bracket with a Monte Carlo simulator, a multi-city travel planner, and real-time fan rooms.

### 🔴 Live

- **App:** https://kickoff2026.tech  (also https://kick-off26.vercel.app)
- **API:** https://kickoff26-backend-vknuo.ondigitalocean.app
- **API docs:** https://kickoff26-backend-vknuo.ondigitalocean.app/docs

> For the deep technical breakdown - every module, the data pipeline, the real-time gateway, and the deployment topology - see **[architecture.md](./architecture.md)**.

---

## 🗂️ Table of contents

- [Features](#-features)
- [Tech stack](#-tech-stack)
- [Live URLs](#-live-urls)
- [How it fits together](#-how-it-fits-together)
- [Local setup](#-local-setup)
- [Environment variables](#-environment-variables)
- [Deployment](#-deployment)
- [Project structure](#-project-structure)
- [Data sources & references](#-data-sources--references)
- [WebSocket channels](#-websocket-channels)
- [Testing](#-testing)
- [Principles](#-principles)
- [Contributing & contact](#-contributing--contact)
- [License](#-license)

---

## ✨ Features

> The in-app navigation uses friendly labels (routes in parentheses): **Live Matches** (`/matchday`), **Standings** (`/standings`), **Teams** (`/teams`), **Predictions** (`/bracket`), **Travel Planner** (`/fanplan`), **Following** (`/following`), **Fan Rooms** (`/watch`), **Resources** (`/resources`).

| Module | What it does |
|--------|--------------|
| 🔴 **Live Matches** (`/matchday`) | Live scores dashboard backed by a self-built Poisson/Elo win-probability model, a personalized following feed, match detail pages with event timelines, and momentum alerts pushed over WebSocket. |
| 🏆 **Predictions / Bracket** (`/bracket`) | Build group-stage and knockout picks by hand, or run a **Monte Carlo simulator** (1k / 10k / 50k runs) in a background process pool for advancement and champion odds. Export your knockout bracket as a shareable PNG or PDF. |
| ✈️ **Travel Planner** (`/fanplan`) | A multi-city itinerary optimizer that picks the best set of matches to attend across the 16 host cities given your followed teams, budget, and travel constraints - with estimated ticket and travel costs, rendered on an interactive Leaflet map and exportable to PDF. |
| 💬 **Fan Rooms** (`/watch`) | Per-match real-time chat rooms with live presence, custom polls, and floating emoji reactions. Viewing is open to everyone; sending messages and creating polls requires login. |
| **Teams** (`/teams`) | All 48 nations grouped A-L with flags and team codes, plus a per-team view: squads, coaches, fixtures, venues, and a player to watch. |
| **Standings** (`/standings`) | Live group tables for all 12 groups with real tiebreakers (points, GD, GF). Top 2 of each group plus the 8 best third-placed teams are highlighted, updating in real time as scores change. |
| **AI tournament assistant** | A Groq-powered assistant that answers tournament questions grounded in the app's own data. |
| **Resources** (`/resources`) | Curated official links - tournament site, broadcasters, ticketing, host cities - plus the real data sources behind the app. |
| **Following** (`/following`) | A personalized feed for the teams you follow across matches, alerts, and standings. |

---

## 🛠️ Tech stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router) + TypeScript + Tailwind CSS, Leaflet, native WebSocket client |
| **Backend** | FastAPI + Python, async SQLAlchemy 2.0, Pydantic v2, Uvicorn, WebSockets |
| **Database** | PostgreSQL (Neon in production, local Postgres in dev) |
| **Real-time** | A single in-process WebSocket gateway (`ws_manager`) with channel pub/sub |
| **Auth** | JWT (python-jose) + bcrypt password hashing (passlib) |
| **Compute** | NumPy-powered Monte Carlo simulator on a `ProcessPoolExecutor` |
| **AI** | Groq (Llama 3.3 70B) tournament assistant |

> The backend also runs on SQLite with zero config (it is the automatic fallback when `DATABASE_URL` is unset, and the engine the test suite uses) - but PostgreSQL is the database for dev and production. See [Testing](#testing).

---

## 🌐 Live URLs

| What | URL |
|------|-----|
| App (primary) | https://kickoff2026.tech |
| App (Vercel) | https://kick-off26.vercel.app |
| API | https://kickoff26-backend-vknuo.ondigitalocean.app |
| API docs (Swagger) | https://kickoff26-backend-vknuo.ondigitalocean.app/docs |

---

## 🧩 How it fits together

```
┌──────────────────────────────┐         ┌────────────────────────────────────────┐
│   Next.js frontend (Vercel)   │         │       FastAPI backend (DigitalOcean)     │
│                               │  HTTP   │                                          │
│  Live Matches · Bracket ·     │ ──────► │  /api/*  routers ─► services ─► models    │
│  Travel Planner · Fan Rooms   │         │                       │                   │
│                               │   WS    │  /ws  ◄────► ws_manager (channel fanout)  │
│  lib/api.ts · lib/websocket   │ ◄─────► │                       │                   │
└──────────────────────────────┘         │            ┌──────────▼──────────┐        │
                                          │            │  SQLAlchemy (async) │        │
                                          │            └──────────┬──────────┘        │
                                          └───────────────────────┼───────────────────┘
                                                                  │
                                              ┌───────────────────▼───────────────────┐
                                              │      PostgreSQL  (Neon, production)     │
                                              └─────────────────────────────────────────┘

   Background loops (started in app lifespan):
     • worldcup_poller / matchday_demo  →  write scores + goal events to DB  →  broadcast over /ws
```

The frontend **never** talks to a football API directly. A single backend poller writes state to the database, and every client receives updates over the WebSocket gateway, so external API usage stays flat regardless of how many users are online.

---

## 💻 Local setup

**Prerequisites:** Python 3.11+, Node.js 18+, and a local PostgreSQL 16 (or Docker - see [`docker-compose.yml`](./docker-compose.yml)).

```powershell
# 1. Clone
git clone <repo-url> KickOff26
cd KickOff26

# 2. Configure environment
cp .env.example .env
#   Edit .env: set DATABASE_URL to your local Postgres, JWT_SECRET, and any API keys.
#   scripts/setup-postgres.ps1 creates a local DB with the default credentials.

# 3. Backend: install deps, then migrate + seed in one idempotent command
cd backend
pip install -r requirements.txt
python -m app.setup            # creates schema, seeds teams/fixtures/squads
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000
- API health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs

`python -m app.setup` is idempotent and safe to re-run; it re-applies schema migrations and re-syncs tournament data. Useful variants:

```powershell
python -m app.setup --schema-only      # migrations only, no data sync
python -m app.setup --skip-rosters     # skip bundled squad seed
python -m app.setup --skip-worldcup    # openfootball seed only (offline)
```

> Always run Uvicorn from the `backend/` folder (not the repo root), and restart the backend after editing `.env` - settings load once at startup.

---

## 🔑 Environment variables

Copy `.env.example` to `.env` and fill in values. Backend settings live in `.env`; the frontend reads the `NEXT_PUBLIC_*` entries. Production values (Neon DB, DigitalOcean/Vercel URLs, `wss://`) belong in the hosting dashboards, not in the committed file.

| Variable | Description | Local vs production |
|----------|-------------|---------------------|
| `DATABASE_URL` | Async SQLAlchemy connection string, read entirely from this one var (no hardcoded credentials). Falls back to local SQLite if unset. | Local: `postgresql+asyncpg://postgres:password@localhost:5432/kickoff26`. Production: Neon pooled string (`postgresql://...?sslmode=require`; TLS handled automatically). |
| `LIVE_DATA_MODE` | `demo` = one simulated live match, zero API calls. `api` = real rezarahiminia poller + WebSocket fan-out. | Local: `demo`. Production: `api`. |
| `WORLDCUP_API_TOKEN` | Bearer token for the rezarahiminia API (valid ~84 days). Required when `LIVE_DATA_MODE=api`. Obtain via `scripts/get_worldcup_token.py`. | Production (when `api`). |
| `WORLDCUP_API_BASE` | Base URL for the live API. | `https://worldcup26.ir` (both). |
| `WORLDCUP_POLL_*` | Live poller cadence in seconds (`LIVE` / `PRE_KICKOFF` / `IDLE_MAX`). | Same defaults both. |
| `WORLDCUP_API_EMAIL` / `WORLDCUP_API_PASSWORD` | Optional - only read by `scripts/get_worldcup_token.py` to register/authenticate. | Optional. |
| `ZAFRONIX_API_KEY` | Optional - kept only for a manual squad re-fetch; squads ship as bundled JSON. | Optional. |
| `ZAFRONIX_API_BASE` | Base URL for the Zafronix API. | `https://api.zafronix.com` (both). |
| `ZAFRONIX_LIVE_FETCH_ENABLED` | Set `true` only to allow live Zafronix HTTP fetches. | `false` (both). |
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_MAX_TOKENS` | AI tournament assistant ([Groq](https://console.groq.com), free tier). | Same both; key required for the assistant. |
| `JWT_SECRET` | Signing secret for auth tokens - set to a long random string. | Use a strong, unique value in production. |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | Token algorithm and lifetime. | `HS256` / `10080` (7 days). |
| `DATA_MODE` | `mock` = skip re-seed if DB already populated. `live` = force re-seed on startup. | `mock` after initial setup so restarts do not force a re-seed. |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. | Local: `http://localhost:3000,http://127.0.0.1:3000`. Production: add `https://kickoff2026.tech`, `https://www.kickoff2026.tech`, `https://kick-off26.vercel.app`. |
| `NEXT_PUBLIC_API_URL` | Backend base URL used by the frontend. | Local: `http://localhost:8000`. Production: `https://kickoff26-backend-vknuo.ondigitalocean.app`. |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL used by the frontend. | Local: `ws://localhost:8000/ws`. Production: `wss://kickoff26-backend-vknuo.ondigitalocean.app/ws`. |
| `CACHE_TTL_TEAMS` / `_MATCHES` / `_STANDINGS` | TTLs (seconds) for the DB-backed `api_cache`. | `86400` / `300` / `600`. |

---

## 🚀 Deployment

| Tier | Host |
|------|------|
| **Frontend** | [Vercel](https://vercel.com) - standard Next.js build, pointed at the backend via `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`. |
| **Backend** | [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform) - built from [`backend/Dockerfile`](./backend/Dockerfile), serving HTTP and the `/ws` WebSocket endpoint. |
| **Database** | [Neon](https://neon.tech) Postgres - use the pooled connection string; `sslmode=require` is enabled automatically. |

**Fresh database bootstrap.** Point the backend at the new (empty) `DATABASE_URL`, set `JWT_SECRET`, `LIVE_DATA_MODE=api` and `WORLDCUP_API_TOKEN`, then run `python -m app.setup` once. It creates the full schema, seeds teams + the openfootball schedule, syncs WorldCup reference data (stadiums, group/game links), and seeds the bundled squads. It is idempotent and safe to re-run. After the first run, set `DATA_MODE=mock` so restarts do not force a re-seed.

Maintenance:

| Task | Command |
|------|---------|
| Re-sync tournament reference data | `python scripts/sync_worldcup_api.py` or `POST /api/matchday/worldcup/sync` |
| Re-seed bundled squads | `python scripts/seed_team_rosters.py` or `POST /api/teams/rosters/resync` |
| Clear watch-room content only | `python scripts/clear_room_content.py --confirm` |
| Check relational integrity | `python scripts/verify_db_integrity.py` |

---

## 📁 Project structure

```
KickOff26/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, CORS, router mounting, /health
│   │   ├── config.py          # Pydantic settings loaded from .env
│   │   ├── database_url.py    # DATABASE_URL normalization + driver connect args
│   │   ├── db/__init__.py     # Async engine, session, init_db + lightweight migrations
│   │   ├── models/__init__.py # SQLAlchemy ORM models (JSON/JSONB variant)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── auth/              # JWT + bcrypt helpers, user lookups
│   │   ├── api/               # HTTP routers: auth, teams, matchday, bracket, rooms, fanplan
│   │   ├── services/          # Business logic (worldcup poller/sync, live standings, simulator, ...)
│   │   └── websocket/         # /ws handler + shared channel gateway (ws_manager)
│   ├── data/                  # Bundled openfootball schedule, squads, ticket estimates (JSON)
│   ├── scripts/               # setup helpers, get_worldcup_token.py, sync/seed scripts
│   ├── Dockerfile             # Backend image (used by DigitalOcean App Platform)
│   └── tests/                 # pytest suite
├── frontend/
│   ├── app/                   # Next.js App Router pages (matchday, bracket, fanplan, watch, ...)
│   ├── components/            # React UI components (per feature)
│   ├── lib/                   # api.ts, websocket.tsx, domain helpers
│   └── styles/                # Theme tokens + per-feature CSS
├── scripts/                   # setup-postgres.ps1, dev-backend.ps1
├── docker-compose.yml         # Local Postgres + backend services
└── architecture.md            # Full architecture reference
```

---

## 📊 Data sources & references

KickOff26 uses **real data only**, with anything estimated or simulated clearly labeled in the UI.

| Data | Source | Status |
|------|--------|--------|
| Live scores, goal scorers, match status, teams, stadiums | [rezarahiminia World Cup 2026 API](https://github.com/rezarahiminia/worldcup2026) · [worldcup26.ir](https://worldcup26.ir) | **Real** (live, `api` mode) |
| Tournament schedule, groups, kickoff times, venues | [openfootball / worldcup.json](https://github.com/openfootball/worldcup.json) | **Real** (open data, schedule seed) |
| Team squads & rosters | [Zafronix API](https://api.zafronix.com) - fetched once and bundled as `backend/data/team_rosters_2026.json`; served from the DB with **no live polling** (free tier 250 req/day) | **Real** (static bundle) |
| Head coaches | [Bolavip](https://bolavip.com/en/world-cup/2026-world-cup-coaches-all-48-managers-of-the-qualified-national-teams) + curated JSON | **Real** (curated) |
| Group standings | Computed on the backend from live match state (tiebreakers: pts, GD, GF) | **Real**, derived |
| Win probabilities | Self-built Poisson/Elo model in `app/models/win_probability.py` | **Model output** |
| Ticket-price ranges (Travel Planner) | Publicly reported 2026 ticket-price information (price tiers/categories in sports/business press), mapped to match stage (see note below) | **Estimated** - not official quotes |
| Travel distances/times (Travel Planner) | Great-circle estimates between host cities | **Estimated** |
| Demo live match, cards, substitutions | `matchday_demo.py` simulation | **Demo/simulated** (only in `demo` mode) |
| Official info & broadcasters | [Official 2026 tournament site](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026) and broadcasters (see in-app **Resources**) | **Real** (official links) |
| Country flags | [flag-icons](https://github.com/lipis/flag-icons) (MIT) | Asset |

**How ticket estimates are derived.** The Travel Planner's ticket-price ranges are built from publicly reported 2026 ticket-price information (the price tiers and categories described in sports and business press), mapped to match stage: group-stage matches are estimated toward the lower end of the range, host-nation and knockout matches higher, and the final at the top. These are clearly-labeled planning estimates, not official quotes - actual pricing is dynamic and demand-based, so always confirm prices and availability through the official 2026 ticketing channel.

---

## 🔌 WebSocket channels

Connect to `/ws` and subscribe with `{ "type": "subscribe", "channel": "<name>" }`:

| Channel | Payload |
|---------|---------|
| `match:{id}` | Live updates for a single match |
| `matches:live` | Feed of all live matches |
| `matches:alerts` | Goals, cards, kickoff, full time, momentum swings |
| `sim:{task_id}` | Monte Carlo simulation progress |
| `room:{id}` | Fan-room chat, polls, reactions, presence |

The client also sends `ping` (gets `pong`) and `unsubscribe`. Subscribing to a `room:{id}` channel automatically registers presence and a join system message.

---

## 🧪 Testing

```powershell
cd backend
pytest -v
```

The suite (win-probability, simulator, itinerary, live poller, match calendar/events/lineups, R32 seeding, bracket standings, rooms, sim jobs, and API integration) runs on **SQLite** for speed and isolation - no Postgres or Docker required. `conftest.py` points `DATABASE_URL` at a throwaway `test_kickoff26.db` and sets `TESTING` so background loops do not start. The same async SQLAlchemy models run on both engines (`JsonField = JSON().with_variant(JSONB, "postgresql")`), so SQLite tests exercise the same code paths that run on Postgres in production.

Frontend logic tests:

```powershell
cd frontend
npm run test:matchday
```

---

## 📜 Principles

- **Real data only.** Live scores, schedule, squads, coaches, and standings come from real sources; nothing is fabricated.
- **Estimates clearly labeled.** Travel-planner ticket and travel costs are estimates (published price reporting and great-circle distances), and the simulated `demo` match is always labeled as such in the UI.
- **No "FIFA" mark** except where linking to the official tournament site.

---

## 🤝 Contributing & contact

KickOff26 is an actively-built project, and it is far from finished - new ideas are always on the table. If there is a feature you would love to see, a tweak that would make the app better, or something you think is missing, your input is genuinely welcome. Open an issue or reach out, and let's talk about it.

- **Have an idea or feature request?** Suggestions and feature requests are welcome - if you would like to see something implemented or have improvements in mind, open an issue or get in touch.
- **Want to contribute?** Pull requests are welcome. Feel free to fork the repo, build on it, and submit improvements - all contributions are appreciated.
- **Questions or feedback?** Any comments, feedback, or questions are welcome too. Please do not hesitate to reach out.

Find me here:

- **GitHub:** [github.com/akashsv01](https://github.com/akashsv01)
- **Portfolio:** [akashsvora.dev](https://akashsvora.dev)
- **LinkedIn:** [linkedin.com/in/akash-s-vora](https://linkedin.com/in/akash-s-vora)

Built with love ⚽💛 by **Akash Vora** - here's to a summer of unforgettable football. See you at the 2026 World Cup.

---

## 📄 License

MIT
