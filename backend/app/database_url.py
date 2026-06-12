"""Normalize DATABASE_URL for async SQLAlchemy (SQLite, local Postgres, Neon)."""

from __future__ import annotations

import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SSL_MODES_REQUIRING_TLS = frozenset({"require", "verify-ca", "verify-full", "prefer", "allow"})


def normalize_database_url(raw: str) -> str:
    """Return an async SQLAlchemy URL from DATABASE_URL (Neon, Postgres, or SQLite)."""
    url = str(raw).strip()
    if not url:
        return url

    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://") :]

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme.startswith("postgresql") and "+asyncpg" not in scheme:
        parsed = parsed._replace(scheme="postgresql+asyncpg")

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if not query_pairs:
        return urlunparse(parsed)

    filtered: list[tuple[str, str]] = []
    for key, value in query_pairs:
        # asyncpg uses connect_args["ssl"], not libpq query params
        if key.lower() in {"sslmode", "ssl", "channel_binding"}:
            continue
        filtered.append((key, value))

    parsed = parsed._replace(query=urlencode(filtered))
    return urlunparse(parsed)


def build_connect_args(database_url: str) -> dict:
    """Driver-specific connect_args (SQLite thread check, Postgres/Neon SSL)."""
    url = normalize_database_url(database_url)
    parsed = urlparse(url)

    if parsed.scheme.startswith("sqlite"):
        return {"check_same_thread": False}

    if not parsed.scheme.startswith("postgresql"):
        return {}

    # Read sslmode from the raw env string (may be stripped from the normalized URL).
    raw = os.environ.get("DATABASE_URL", database_url).strip()
    raw_query = dict(parse_qsl(urlparse(raw).query, keep_blank_values=True))
    sslmode = (raw_query.get("sslmode") or "").lower()
    if sslmode in _SSL_MODES_REQUIRING_TLS:
        return {"ssl": ssl.create_default_context()}

    host = (parsed.hostname or "").lower()
    if host.endswith(".neon.tech"):
        return {"ssl": ssl.create_default_context()}

    return {}


def database_url_label(database_url: str) -> str:
    """Safe host/db label for logs (no credentials)."""
    url = normalize_database_url(database_url)
    parsed = urlparse(url)
    if parsed.hostname:
        db = parsed.path.lstrip("/") or "postgres"
        return f"{parsed.hostname}/{db}"
    return url.split("?")[0]
