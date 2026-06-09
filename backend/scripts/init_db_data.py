"""Create tables and seed official tournament data into PostgreSQL/SQLite."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import async_session, init_db
from app.services.data_ingestion import DataIngestionService


async def main() -> None:
    print(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    print(f"Data mode: {settings.data_mode}")
    await init_db()
    async with async_session() as db:
        result = await DataIngestionService(db).sync_all(force=True)  # openfootball schedule
        await db.commit()
    print("Init complete:", result)


if __name__ == "__main__":
    asyncio.run(main())
