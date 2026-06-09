from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_async_engine(settings.database_url, echo=False, connect_args=_connect_args)
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


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_match_calendar_columns)
        await conn.run_sync(_migrate_room_columns)
