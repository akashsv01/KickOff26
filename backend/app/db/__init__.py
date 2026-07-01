from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.database_url import build_connect_args, normalize_database_url

_db_url = normalize_database_url(settings.database_url)
_connect_args = build_connect_args(settings.database_url)
engine = create_async_engine(_db_url, echo=False, connect_args=_connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _migrate_match_calendar_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "matches" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("matches")}
    if "local_date" not in cols:
        sync_conn.execute(text("ALTER TABLE matches ADD COLUMN local_date VARCHAR(10)"))
    if "kickoff_timezone" not in cols:
        sync_conn.execute(text("ALTER TABLE matches ADD COLUMN kickoff_timezone VARCHAR(64)"))
    if "api_fixture_id" not in cols:
        sync_conn.execute(text("ALTER TABLE matches ADD COLUMN api_fixture_id INTEGER"))
    if "brackets" in insp.get_table_names():
        bracket_cols = {c["name"] for c in insp.get_columns("brackets")}
        if "updated_at" not in bracket_cols:
            if sync_conn.dialect.name == "postgresql":
                sync_conn.execute(
                    text(
                        "ALTER TABLE brackets ADD COLUMN updated_at "
                        "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
                    )
                )
            else:
                sync_conn.execute(
                    text(
                        "ALTER TABLE brackets ADD COLUMN updated_at "
                        "DATETIME DEFAULT CURRENT_TIMESTAMP"
                    )
                )


def _migrate_room_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "rooms" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("rooms")}
    if "polls" not in cols:
        sync_conn.execute(text("ALTER TABLE rooms ADD COLUMN polls JSON"))


def _migrate_worldcup_api_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())

    if "teams" in tables:
        cols = {c["name"] for c in insp.get_columns("teams")}
        for col, ddl in (
            ("api_object_id", "VARCHAR(32)"),
            ("api_seq_id", "VARCHAR(16)"),
            ("iso2", "VARCHAR(4)"),
        ):
            if col not in cols:
                sync_conn.execute(text(f"ALTER TABLE teams ADD COLUMN {col} {ddl}"))

    if "matches" in tables:
        cols = {c["name"] for c in insp.get_columns("matches")}
        for col, ddl in (
            ("api_object_id", "VARCHAR(32)"),
            ("api_seq_id", "VARCHAR(16)"),
            ("stadium_id", "INTEGER"),
            ("matchday", "VARCHAR(8)"),
            ("wc_match_type", "VARCHAR(32)"),
        ):
            if col not in cols:
                sync_conn.execute(text(f"ALTER TABLE matches ADD COLUMN {col} {ddl}"))


def _migrate_user_profile_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    added: set[str] = set()
    for col, ddl in (
        ("favorite_team_id", "INTEGER"),
        ("country_region", "VARCHAR(64)"),
        ("preferred_language", "VARCHAR(16)"),
        ("timezone", "VARCHAR(64)"),
        ("daily_digest_opt_in", "BOOLEAN DEFAULT FALSE NOT NULL"),
        ("last_digest_sent_date", "DATE"),
    ):
        if col not in cols:
            sync_conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
            added.add(col)

    # Backfill timezone from the country map where we can, only for rows that
    # don't have one yet. Idempotent: the WHERE timezone IS NULL guard means
    # re-runs and user-set values are never overwritten.
    if "timezone" in added or "country_region" in (cols | added):
        from app.data.country_timezones import COUNTRY_TIMEZONE

        for country, tz in COUNTRY_TIMEZONE.items():
            sync_conn.execute(
                text(
                    "UPDATE users SET timezone = :tz "
                    "WHERE country_region = :country AND (timezone IS NULL OR timezone = '')"
                ),
                {"tz": tz, "country": country},
            )


def _migrate_team_roster_table(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "team_rosters" in insp.get_table_names():
        return
    sync_conn.execute(
        text(
            """
            CREATE TABLE team_rosters (
                team_id INTEGER PRIMARY KEY,
                zafronix_slug VARCHAR(120),
                players JSON,
                coach VARCHAR(120),
                fetch_status VARCHAR(16) DEFAULT 'pending',
                error_message VARCHAR(255),
                fetched_at TIMESTAMP,
                retry_after TIMESTAMP,
                FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
            )
            """
        )
    )


def _migrate_match_event_minute_nullable(sync_conn) -> None:
    """Drop NOT NULL on match_events.minute so unknown goal minutes store NULL.

    Postgres only - SQLite recreates the table from the (now nullable) model.
    """
    from sqlalchemy import inspect, text

    if sync_conn.dialect.name != "postgresql":
        return
    insp = inspect(sync_conn)
    if "match_events" not in insp.get_table_names():
        return
    for col in insp.get_columns("match_events"):
        if col["name"] == "minute" and col.get("nullable") is False:
            sync_conn.execute(text("ALTER TABLE match_events ALTER COLUMN minute DROP NOT NULL"))


def _migrate_match_event_added_time(sync_conn) -> None:
    """Add match_events.added_time and widen the dedup constraint to include it.

    Works on SQLite (tests recreate from the model) and Postgres (local + Neon).
    """
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "match_events" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("match_events")}
    if "added_time" not in cols:
        sync_conn.execute(text("ALTER TABLE match_events ADD COLUMN added_time INTEGER"))
    # The dedup constraint must include added_time so e.g. a 45' and a 45+5' goal
    # by the same player can coexist. Postgres only; SQLite rebuilds from the model.
    if sync_conn.dialect.name == "postgresql":
        sync_conn.execute(
            text("ALTER TABLE match_events DROP CONSTRAINT IF EXISTS uq_match_event_dedup")
        )
        sync_conn.execute(
            text(
                "ALTER TABLE match_events ADD CONSTRAINT uq_match_event_dedup UNIQUE "
                "(match_id, event_type, minute, added_time, team_side, player_name, detail)"
            )
        )


def _migrate_match_scorers_reconciled(sync_conn) -> None:
    """Add matches.scorers_reconciled + reconcile_attempted (idempotent, dialect-aware)."""
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "matches" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("matches")}
    default_false = "FALSE" if sync_conn.dialect.name == "postgresql" else "0"
    for col in ("scorers_reconciled", "reconcile_attempted"):
        if col not in cols:
            sync_conn.execute(
                text(f"ALTER TABLE matches ADD COLUMN {col} BOOLEAN NOT NULL DEFAULT {default_false}")
            )


def _migrate_password_reset_columns(sync_conn) -> None:
    """Add users.password_reset_token_hash + password_reset_expires_at (idempotent)."""
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "password_reset_token_hash" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(64)"))
    if "password_reset_expires_at" not in cols:
        ddl = (
            "TIMESTAMP WITH TIME ZONE" if sync_conn.dialect.name == "postgresql" else "DATETIME"
        )
        sync_conn.execute(
            text(f"ALTER TABLE users ADD COLUMN password_reset_expires_at {ddl}")
        )


def _migrate_poll_tables(sync_conn) -> None:
    """Create the durable polls + poll_votes tables (idempotent, dialect-aware).

    Base.metadata.create_all already creates these from the models on both fresh
    and existing databases (it only adds missing tables); this explicit migration
    is the documented schema + a safety net, mirroring _migrate_team_roster_table.

    Votes live in poll_votes, so they survive a user leaving and rejoining a room.
    UNIQUE(poll_id, user_id) gives each user at most one vote per poll, and the
    ON DELETE CASCADE foreign keys drop a poll's votes when the poll (or its room)
    is removed.
    """
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    pg = sync_conn.dialect.name == "postgresql"
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = "TIMESTAMP WITH TIME ZONE" if pg else "DATETIME"
    now = "NOW()" if pg else "CURRENT_TIMESTAMP"
    json_type = "JSONB" if pg else "JSON"
    bool_false = "BOOLEAN NOT NULL DEFAULT FALSE" if pg else "BOOLEAN NOT NULL DEFAULT 0"

    if "polls" not in tables:
        sync_conn.execute(
            text(
                f"""
                CREATE TABLE polls (
                    id {pk},
                    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                    question VARCHAR(300) NOT NULL,
                    options {json_type} NOT NULL,
                    created_by VARCHAR(100) NOT NULL DEFAULT '',
                    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    closes_at {ts},
                    closed {bool_false},
                    created_at {ts} DEFAULT {now}
                )
                """
            )
        )
        sync_conn.execute(text("CREATE INDEX ix_polls_room_id ON polls (room_id)"))

    if "poll_votes" not in tables:
        sync_conn.execute(
            text(
                f"""
                CREATE TABLE poll_votes (
                    id {pk},
                    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    option_index INTEGER NOT NULL,
                    created_at {ts} DEFAULT {now},
                    updated_at {ts} DEFAULT {now},
                    CONSTRAINT uq_poll_vote_user UNIQUE (poll_id, user_id)
                )
                """
            )
        )
        sync_conn.execute(text("CREATE INDEX ix_poll_votes_poll_id ON poll_votes (poll_id)"))
        sync_conn.execute(text("CREATE INDEX ix_poll_votes_user_id ON poll_votes (user_id)"))


def _migrate_match_penalty_columns(sync_conn) -> None:
    """Add matches penalty-shootout columns (idempotent, dialect-aware).

    Knockout matches decided on penalties carry a shootout tally plus the
    scorers/misses lists; group matches leave these null/empty.
    """
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "matches" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("matches")}
    json_type = "JSONB" if sync_conn.dialect.name == "postgresql" else "JSON"
    for col, ddl in (
        ("home_penalty_score", "INTEGER"),
        ("away_penalty_score", "INTEGER"),
        ("home_penalty_scorers", json_type),
        ("away_penalty_scorers", json_type),
        ("home_penalty_misses", json_type),
        ("away_penalty_misses", json_type),
    ):
        if col not in cols:
            sync_conn.execute(text(f"ALTER TABLE matches ADD COLUMN {col} {ddl}"))


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_match_calendar_columns)
        await conn.run_sync(_migrate_room_columns)
        await conn.run_sync(_migrate_worldcup_api_columns)
        await conn.run_sync(_migrate_user_profile_columns)
        await conn.run_sync(_migrate_team_roster_table)
        await conn.run_sync(_migrate_match_event_minute_nullable)
        await conn.run_sync(_migrate_match_event_added_time)
        await conn.run_sync(_migrate_match_scorers_reconciled)
        await conn.run_sync(_migrate_password_reset_columns)
        await conn.run_sync(_migrate_poll_tables)
        await conn.run_sync(_migrate_match_penalty_columns)
