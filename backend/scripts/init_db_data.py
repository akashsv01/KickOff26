"""Create tables and seed official tournament data (delegates to app.setup)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.setup import main


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
