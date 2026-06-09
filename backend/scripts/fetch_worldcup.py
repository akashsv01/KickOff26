"""Fetch and cache the openfootball 2026 World Cup schedule."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.openfootball import CACHE_PATH, ensure_worldcup_cache, parse_fixtures


def main() -> None:
    force = "--force" in sys.argv
    path = ensure_worldcup_cache(force=force)
    fixtures = parse_fixtures()
    group = sum(1 for f in fixtures if f["stage"] == "group")
    print(f"Cached openfootball schedule to {path}")
    print(f"Parsed {len(fixtures)} fixtures ({group} group-stage)")


if __name__ == "__main__":
    main()
