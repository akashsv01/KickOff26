"""Obtain a rezarahiminia World Cup 2026 API token (valid ~84 days).

Usage (from backend/):
    python scripts/get_worldcup_token.py --register --email you@example.com --password 'secret'
    python scripts/get_worldcup_token.py --email you@example.com --password 'secret'

Or set WORLDCUP_API_EMAIL / WORLDCUP_API_PASSWORD in .env and run with no args.
Copy the printed token into .env as WORLDCUP_API_TOKEN, then set LIVE_DATA_MODE=api.
The token is sent as `Authorization: Bearer <token>` on all API requests.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.worldcup_api import WorldCupApiClient


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a World Cup 2026 API token")
    parser.add_argument("--register", action="store_true", help="register a new account")
    parser.add_argument("--email", default=settings.worldcup_api_email)
    parser.add_argument("--password", default=settings.worldcup_api_password)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error("email and password are required (flags or WORLDCUP_API_EMAIL/PASSWORD)")

    client = WorldCupApiClient(token="placeholder")  # token not needed for auth endpoints
    if args.register:
        token = await client.register(args.email, args.password, args.name)
    else:
        token = await client.authenticate(args.email, args.password)

    if not token:
        print("Failed to obtain token - check credentials and base URL.", file=sys.stderr)
        sys.exit(1)

    print("\nToken obtained. Add this line to backend/.env:\n")
    print(f"WORLDCUP_API_TOKEN={token}\n")


if __name__ == "__main__":
    asyncio.run(main())
