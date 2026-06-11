# KickOff26 - Architecture

This document explains how KickOff26 is built: every layer, what each module is responsible for, how data flows from the source feeds to the browser in real time, and why the project uses **both SQLite and PostgreSQL**.

For setup and day-to-day commands, see [README.md](./README.md).

---

## 1. Design principles

1. **One source of truth.** All clients read state from the database; nothing in the browser calls a football API directly.
2. **Fan-out, don't fan-in.** A single backend poller fetches live data; the WebSocket gateway broadcasts it to every connected client, so external API cost is independent of user count.
3. **Engine-agnostic persistence.** The same async SQLAlchemy code runs on SQLite (frictionless dev/tests) and PostgreSQL (production), selected purely by `DATABASE_URL`.
4. **Thin routers, fat services.** HTTP routers validate and delegate; all domain logic lives in `app/services/`.
5. **Free-tier friendly.** Static schedule data is bundled (openfootball); the paid live feed (API-Football) is optional and quota-budgeted.

---

## 2. System overview

```
                         ┌───────────────────────────────────────────────┐
                         │                Next.js (App Router)            │
                         │                                                │
   Browser  ◄───────────►│  Pages: /matchday /bracket /fanplan /watch …   │
        HTTP + WebSocket │  lib/api.ts (REST)   lib/websocket.ts (WS)     │
                         └───────────────┬───────────────────────────────┘
                                         │  HTTP /api/*        │ WS /ws
                                         ▼                     ▼
        ┌────────────────────────────────────────────────────────────────────────┐
        │                              FastAPI (app.main)                          │
        │                                                                          │
        │   api/ (routers) ──► services/ (domain logic) ──► models/ (ORM)          │
        │        auth  teams  matchday  bracket  rooms  fanplan                    │
        │                                                                          │
        │   websocket/handler ──► websocket/gateway (ws_manager: channel pub/sub)  │
        │                                                                          │
        │   Background asyncio tasks (started in lifespan):                        │
        │     • worldcup_poller  OR  matchday_demo                               │
        │   Background processes:                                                  │
        │     • sim_job_manager → ProcessPoolExecutor (Monte Carlo)               │
        └───────────────────────────────────┬──────────────────────────────────────┘
                                             │  async SQLAlchemy (asyncpg / aiosqlite)
                                             ▼
                ┌───────────────────────────────────────────────────────┐
                │   PostgreSQL  (prod / recommended)                      │
                │   SQLite kickoff26.db  (zero-config dev + tests)        │
                └───────────────────────────────────────────────────────┘

   External feeds:
     openfootball/worldcup.json  →  bundled in backend/data (no key)   → seeds schedule
     API-Football (RapidAPI)     →  live_poller only (optional key)     → live scores/events
```

---

## 3. Lifecycles

### HTTP request
1. Browser calls `lib/api.ts` → `GET/POST /api/<feature>/…`.
2. The matching router in `app/api/` validates input with a Pydantic schema and obtains a DB session via the `get_db` dependency.
3. The router calls a service in `app/services/`, which performs the work and returns ORM/data objects.
4. The router serializes via a response schema and returns JSON.

### Real-time update (e.g. a goal)
1. `live_poller` (api mode) or `matchday_demo` (demo mode) detects a score/event change and writes it to the `matches` / `match_events` tables.
2. The same loop computes alerts/probabilities and calls `ws_manager.broadcast("matches:alerts", …)`, `match:{id}`, `matches:live`.
3. Every connection subscribed to those channels receives the JSON frame instantly - no client polling.

### App startup (`lifespan` in [`app/main.py`](./backend/app/main.py))
1. `init_db()` creates tables and runs lightweight column migrations.
2. `DataIngestionService.sync_all(force=…)` seeds teams + fixtures (forced unless `DATA_MODE=mock`).
3. Depending on `LIVE_DATA_MODE`, it either seeds demo lineups + a live match, or links API fixture IDs.
4. Unless `TESTING` is set, it spawns the background tasks: the live/demo loop and (in api mode) the lineup fetcher.
5. On shutdown it cancels tasks and shuts down the simulation process pool.

---

## 4. Backend layers

### 4.1 Application core
| File | Responsibility |
|------|----------------|
| [`app/main.py`](./backend/app/main.py) | Creates the FastAPI app, configures CORS, mounts routers under `/api` and the `/ws` router, defines the `lifespan` (startup seeding + background tasks), and exposes `/health` (reports `data_mode`, `live_data_mode`, and `api_quota` in api mode). |
| [`app/config.py`](./backend/app/config.py) | Pydantic-settings `Settings` loaded from `.env`. Holds `database_url` (**defaults to SQLite**), JWT config, `data_mode`, `live_data_mode`, API keys, cache TTLs, and CORS. Convenience props: `is_mock`, `is_demo_live`, `is_api_live`, `effective_api_football_key`, `cors_origin_list`. |

### 4.2 Persistence
| File | Responsibility |
|------|----------------|
| [`app/db/__init__.py`](./backend/app/db/__init__.py) | Builds the async engine + `async_sessionmaker`, adds SQLite-only connect args, defines the `Base` declarative class and the `get_db` dependency (commit-on-success, rollback-on-error). `init_db()` runs `create_all` plus idempotent migrations (`_migrate_match_calendar_columns`, `_migrate_room_columns`) that add later columns to existing tables on both dialects. |
| [`app/models/__init__.py`](./backend/app/models/__init__.py) | All ORM models (see schema below). Defines `JsonField = JSON().with_variant(JSONB, "postgresql")` so JSON columns are `JSON` on SQLite and `JSONB` on Postgres. |
| `app/schemas/` | Pydantic request/response models used by the routers. |

### 4.3 Authentication ([`app/auth/__init__.py`](./backend/app/auth/__init__.py))
- `hash_password` / `verify_password` - bcrypt via passlib (passwords are **never** stored in plaintext).
- `create_access_token` / `decode_token` - HS256 JWT with `sub = user_id` and an expiry.
- `get_user_by_email/username/id`, `create_user` - async user lookups.
- Used by the auth router and by the WebSocket handler (to resolve a user from a `?token=` query param).

### 4.4 HTTP API (`app/api/`, all mounted under `/api`)
| Router | Prefix | Key endpoints |
|--------|--------|---------------|
| `auth.py` | `/api/auth` | `POST /register`, `POST /login`, `GET /me` |
| `teams.py` | `/api/teams` | `GET ""` (list), `POST /follow` |
| `matchday.py` | `/api/matchday` | `GET /matches`, `GET /matches/{id}`, `GET /days`, `GET /following`, `GET /live` |
| `bracket.py` | `/api/bracket` | `GET /structure`, `GET /groups`, `GET /odds/{home}/{away}`, `POST /save[/groups|/knockout]`, `GET/DELETE /picks…`, `GET /mine`, `GET/POST /leaderboard…`, `POST /simulate[/quick|/sync]`, `GET /simulate/jobs/{id}`, `GET /poster/{team_code}` |
| `rooms.py` | `/api/rooms` | `GET /summary`, `POST ""`, `GET /match/{id}`, `GET /{id}`, `GET/POST /{id}/messages`, `POST /{id}/poll`, `POST /{id}/poll/vote`, `POST /{id}/reactions` |
| `fanplan.py` | `/api/fanplan` | `GET /cities`, `POST /itinerary` |

`app/api/deps.py` holds shared dependencies (DB session, current user from JWT).

### 4.5 Real-time layer (`app/websocket/`)
| File | Responsibility |
|------|----------------|
| [`gateway.py`](./backend/app/websocket/gateway.py) | The singleton `ws_manager` (`WebSocketManager`). Tracks connections and channel subscriptions under an `asyncio.Lock`; provides `subscribe`/`unsubscribe`, `broadcast(channel)`, `broadcast_all`, `send_to`, room presence (`room_participants`, `room_watcher_count`), and channel-name helpers (`match:`, `room:`, `user:`, `sim:`). |
| [`handler.py`](./backend/app/websocket/handler.py) | The `/ws` endpoint. Accepts the socket, resolves the user from an optional `token`, and runs a receive loop handling `subscribe` / `unsubscribe` / `ping`. Subscribing/leaving a `room:{id}` triggers presence + join/leave system messages via `room_live`. Cleans up presence on disconnect. |

### 4.6 Services (`app/services/`) - grouped by domain

**Static tournament data**
| Module | Purpose |
|--------|---------|
| `tournament_2026.py` | Official 2026 tournament data (teams, groups, Elo seeds). |
| `r32_seeding.py` | Official Round-of-32 seeding map. |
| `ticket_estimates.py` | Estimated ticket price ranges (USD) per stage. |
| `mock_data.py` | Offline mock fixtures/teams for demos and tests. |

**Schedule loading & seeding**
| Module | Purpose |
|--------|---------|
| `openfootball.py` | Load the real 2026 schedule from the cached `worldcup.json`. |
| `fixtures_loader.py` | Parse cached fixtures into normalized rows. |
| `fixture_seed.py` | Seed teams + fixtures from the cached schedule. |

**Ingestion & external APIs**
| Module | Purpose |
|--------|---------|
| `data_ingestion.py` | Orchestrates seeding/sync: API-Football (primary) with football-data.org (fallback); called at startup and by `init_db_data.py`. |
| `data_sync.py` | Sync teams/fixtures from published JSON plus optional live API scores. |
| `api_football.py` | API-Football (RapidAPI) client with **daily quota tracking** and a DB-backed cache. |

**MatchDay & live data**
| Module | Purpose |
|--------|---------|
| `matchday.py` | MatchDay companion: live scores, win probabilities, following feed, alerts. |
| `match_calendar.py` | Buckets matches into calendar days (Eastern Time) for the schedule view. |
| `match_events.py` | Persist/load per-match event timelines (source of truth for match detail). |
| `match_lineups.py` | Durable per-match lineups (fetch-once ~10 min pre-kickoff). |
| `matchday_alerts.py` | Canonical alert/event types (goal, card, kickoff, full-time, momentum). |
| `matchday_live.py` | Apply API-Football live snapshots to the DB and fan out WebSocket updates. |
| `matchday_demo.py` | The **demo** live loop - simulated scores/events, zero API calls. |
| `worldcup_poller.py` | The **api-mode** poller: rezarahiminia API → DB → WebSocket. |
| `live_poller.py` | Shared polling-window helpers (`compute_polling_window`). |

**Win probability & simulation**
| Module | Purpose |
|--------|---------|
| `app/models/win_probability.py` | The Poisson/Elo win-probability engine (home/draw/away). |
| `match_resolver.py` | Resolve a single match outcome using the win-probability engine. |
| `simulator.py` | Monte Carlo tournament simulator (group stage → knockouts → champion odds). |
| `sim_job_manager.py` | Manages background Monte Carlo jobs: a `ProcessPoolExecutor`, progress streaming over `sim:{task_id}`, and guardrails. |
| `sim_worker.py` | Picklable worker entry point executed inside the process pool. |

**Bracket, FanPlan, rooms, presentation**
| Module | Purpose |
|--------|---------|
| `bracket_standings.py` | Compute group standings + knockout seeding from user-entered results. |
| `leaderboard.py` | Score manual brackets against finished match results. |
| `itinerary.py` | FanPlan optimizer across the 16 host cities (real fixtures, estimated costs). |
| `room_live.py` | WatchTogether presence broadcasts and join/leave system messages. |
| `squads.py` | Squad names + demo lineup packages for match detail. |
| `poster.py` | Server-side champion poster image (Pillow). |

---

## 5. Database schema

All tables are defined in [`app/models/__init__.py`](./backend/app/models/__init__.py). JSON columns use `JsonField` (`JSON` on SQLite, `JSONB` on Postgres).

| Table | Purpose | Notable columns |
|-------|---------|-----------------|
| `users` | Accounts | `email`, `username` (unique), `hashed_password` (bcrypt), `followed_team_ids` (JSON) |
| `teams` | 48 nations | `code`, `group_letter`, `elo_rating`, `flag_url`, `external_id` |
| `matches` | Fixtures + live state | `home/away_team_id`, `home/away_score`, `minute`, `status` (enum), `stage`, `kickoff_at`, `local_date`, `kickoff_timezone`, venue/city/geo, `events` (JSON), `win_prob_home/draw/away`, `api_fixture_id` |
| `match_lineups` | Fetch-once XI/bench | `home/away_formation`, `home/away_coach`, `home/away_xi/bench` (JSON), `fetch_status`, `retry_after` |
| `match_events` | Durable timeline | `event_type`, `minute`, `team_side`, `player_name`, `detail` + a uniqueness constraint to dedupe |
| `brackets` | Saved predictions | `mode` (`manual`/`monte_carlo`), `picks` (JSON), `champion_team_id`, `accuracy_score` |
| `rooms` | Watch parties | `match_id`, `active_poll` (JSON), `polls` (JSON), `reactions` (JSON) |
| `messages` | Chat | `room_id`, `user_id`, `username`, `content`, `message_type` (`chat`/`system`) |
| `api_cache` | Cached API payloads | `cache_key` (unique), `payload` (JSON), `expires_at` |

---

## 6. Why SQLite **and** PostgreSQL

KickOff26 deliberately supports two engines through one codebase. The choice is made by `DATABASE_URL`; no code changes are needed to switch.

### SQLite (`kickoff26.db`)
- **What it is:** a single local file created in `backend/`. The default in `app/config.py` is `sqlite+aiosqlite:///./kickoff26.db`, so if `DATABASE_URL` is unset, the app uses it automatically.
- **Where it's used:**
  - **Zero-config local runs** - clone, install, run; no database server.
  - **The test suite** - `pytest` runs against a throwaway `test_kickoff26.db`, keeping CI fast and hermetic with no external services.
- **Trade-offs:** great for a single process and demos; not built for high concurrency, and it stores JSON as plain `JSON` (no JSONB indexing).

### PostgreSQL
- **What it is:** the primary, production-grade datastore via the `asyncpg` driver.
- **Where it's used:**
  - **Local development** - `.env` ships with `DATABASE_URL=postgresql+asyncpg://postgres:admin123@localhost:5432/kickoff26`, created by `scripts/setup-postgres.ps1`.
  - **Containers / production** - `docker-compose.yml` runs a `postgres:16-alpine` service and injects an asyncpg `DATABASE_URL` into the backend.
- **Why:** real concurrency, durability, and `JSONB` columns (faster, indexable) - and parity with the deployed environment.

### How one codebase targets both
- **Engine + connect args** - `app/db/__init__.py` detects a `sqlite` URL and adds `check_same_thread=False`; otherwise it uses Postgres defaults.
- **Dialect-aware columns** - `JsonField = JSON().with_variant(JSONB, "postgresql")` resolves to the right type per dialect.
- **Dialect-aware migrations** - `_migrate_*` helpers in `init_db()` branch on `sync_conn.dialect.name` (e.g. `TIMESTAMP WITH TIME ZONE` on Postgres vs `DATETIME` on SQLite).

> `kickoff26.db` / `test_kickoff26.db` are generated artifacts - delete them anytime; they're recreated on the next run/test.

---

## 7. Data pipeline

### Seeding (static, no key)
```
backend/data/worldcup_2026.json   (openfootball cache; refresh via scripts/fetch_worldcup.py)
        │
        ▼  openfootball.py / fixtures_loader.py / fixture_seed.py
DataIngestionService.sync_all()    (app startup, or scripts/init_db_data.py)
        │
        ▼
teams + matches tables  (48 teams, full 104-match schedule, venues, kickoff times)
```

### Live updates (optional key, `LIVE_DATA_MODE=api`)
```
API-Football  ── fixtures?live=all ──►  live_poller.py
        │                                   │ writes scores/events, computes win prob + alerts
        ▼                                   ▼
   api_cache (quota-tracked)          matches / match_events
                                            │
                                            ▼  ws_manager.broadcast(...)
                       match:{id} · matches:live · matches:alerts  ──►  all clients
```
In `LIVE_DATA_MODE=demo`, `matchday_demo.py` produces the same DB writes and broadcasts for one simulated match - with **zero** API calls. The two paths never mix.

**Quota budgeting (api mode):** one call per poll for all live matches; poll only inside kickoff windows; adaptive interval (5 min while live, 90 s for ~5 min after a goal/red card); event detail fetched only on score change/bursts; polling halts when the rate-limit remaining header drops below the safety threshold. A typical 6-match day stays within the 100 req/day free tier.

---

## 8. Monte Carlo simulator

The bracket simulator runs off the request thread so large runs don't block the API:

1. `POST /api/bracket/simulate` (or `/simulate/quick`) creates a job in `sim_job_manager`.
2. The manager submits work to a `ProcessPoolExecutor`; `sim_worker.py` is the picklable entry point.
3. `simulator.py` plays the tournament many times (1k/10k/50k) using `match_resolver` + the Poisson/Elo `win_probability` engine, accumulating advancement and champion odds.
4. Progress streams to the client over the `sim:{task_id}` WebSocket channel; results are polled via `GET /api/bracket/simulate/jobs/{id}`.
5. A synchronous `/simulate/sync` variant exists for small runs/tests. The pool is shut down cleanly on app shutdown.

---

## 9. Frontend architecture

Next.js 14 App Router (`frontend/`), TypeScript, Tailwind.

| Area | Contents |
|------|----------|
| `app/` | Route segments: `page.tsx` (home), `matchday/`, `matchday/[id]/`, `bracket/`, `fanplan/`, `watch/`, `following/`, `auth/`, plus `layout.tsx` and icon/manifest routes. |
| `components/` | Feature UI: `matchday/`, `bracket/`, `watch/`, `FanPlanMap`, `Nav`, `TeamFlag`, `Atmosphere`, `TrophyIcon`, etc. |
| `lib/` | Data + helpers: `api.ts` (REST client using `NEXT_PUBLIC_API_URL`), `websocket.ts` (subscribes to channels via `NEXT_PUBLIC_WS_URL`), and domain modules (`matchday.ts`, `watch.ts`, `bracketGroups.ts`, `knockoutBracket.ts`, `r32Seeding.ts`, `fanplan.ts`, `flags.ts`, `simResults.ts`). |
| `styles/` | Theme tokens + per-feature CSS (`theme.css`, `atmosphere.css`, `home.css`, `matchday.css`, `watch.css`). |

**Data flow:** pages fetch via `lib/api.ts` for initial state, then open a WebSocket through `lib/websocket.ts` and subscribe to the relevant channels (`matches:live`, `match:{id}`, `matches:alerts`, `room:{id}`, `sim:{task_id}`) for live updates. The client never contacts a football API.

---

## 10. Configuration & environments

| Concern | Local (SQLite) | Local (Postgres) | Docker |
|---------|----------------|------------------|--------|
| `DATABASE_URL` | unset → SQLite default | `postgresql+asyncpg://…@localhost` | injected to the `postgres` service |
| `DATA_MODE` | `live` (seed) | `live` | from `.env` |
| `LIVE_DATA_MODE` | `demo` | `demo` or `api` | from `.env` |
| Seeding | `scripts/init_db_data.py` | `scripts/init_db_data.py` | runs at startup via lifespan |

Settings load once at startup, so **restart the backend after editing `.env`**.

---

## 11. Testing

- **Backend** (`backend/tests/`): `pytest` against SQLite - unit tests for win-probability, simulator, itinerary, live poller, match calendar/events/lineups, R32 seeding, bracket standings, rooms, and sim jobs, plus API integration tests. `conftest.py` provides a test DB/session and sets `TESTING` so background loops don't start.
- **Frontend** (`frontend/lib/*.test.mjs`): Node test runner for calendar/navigation helpers (`npm run test:matchday`).

---

## 12. Deployment notes

- `docker-compose.yml` builds the backend image (`backend/Dockerfile`) and runs it alongside `postgres:16-alpine` with a health-gated dependency.
- For production, set a strong `JWT_SECRET`, use `LIVE_DATA_MODE=api` with a real `API_FOOTBALL_KEY`, and front the app with a TLS-terminating reverse proxy (the WebSocket endpoint is `/ws`).
- The frontend is a standard Next.js build (`npm run build && npm start`) pointed at the backend via `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`.
