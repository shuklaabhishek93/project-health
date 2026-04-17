"""Database-backed storage using PostgreSQL (key-value with JSON).

When DATABASE_URL is set, all data is stored in PostgreSQL so it
persists across Render free-tier restarts.  Falls back to the JSON
file storage when DATABASE_URL is not set (local development).
"""

import json
import os
from typing import Optional

_db_url: str | None = os.environ.get("DATABASE_URL")
_conn = None


def _get_conn():
    """Return a reusable database connection, creating it and the table on first call."""
    global _conn
    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            _conn = None

    import psycopg2
    url = os.environ.get("DATABASE_URL", "")
    # Render uses postgres:// but psycopg2 needs postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    _conn = psycopg2.connect(url)
    _conn.autocommit = True
    with _conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_data (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL
            )
        """)
    return _conn


def is_db_enabled() -> bool:
    """Check whether database storage is configured."""
    return bool(os.environ.get("DATABASE_URL"))


def db_put(key: str, value: dict):
    """Upsert a JSON value by key."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO health_data (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
            (key, json.dumps(value)),
        )


def db_get(key: str) -> Optional[dict]:
    """Retrieve a JSON value by key, or None."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM health_data WHERE key = %s", (key,))
        row = cur.fetchone()
        if row:
            v = row[0]
            return v if isinstance(v, dict) else json.loads(v)
    return None


def db_delete(key: str):
    """Remove a key."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM health_data WHERE key = %s", (key,))


def db_list_keys(prefix: str) -> list[str]:
    """List all keys matching a prefix, sorted."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key FROM health_data WHERE key LIKE %s ORDER BY key",
            (prefix + "%",),
        )
        return [row[0] for row in cur.fetchall()]
