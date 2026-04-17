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
_conn_ok = False


def _get_conn():
    """Return a reusable database connection, creating it and the table on first call."""
    global _conn, _conn_ok
    if _conn is not None and _conn_ok:
        return _conn

    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            _conn_ok = True
            return _conn
        except Exception:
            _conn = None
            _conn_ok = False

    import psycopg2
    url = os.environ.get("DATABASE_URL", "")
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
    _conn_ok = True
    return _conn


def is_db_enabled() -> bool:
    """Check whether database storage is configured."""
    return bool(os.environ.get("DATABASE_URL"))


def db_put(key: str, value: dict):
    """Upsert a JSON value by key."""
    global _conn_ok
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


def db_get_many(keys: list[str]) -> dict[str, dict]:
    """Retrieve multiple keys in a single query. Returns {key: value} for found keys."""
    if not keys:
        return {}
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, value FROM health_data WHERE key = ANY(%s)",
            (keys,),
        )
        result = {}
        for row in cur.fetchall():
            v = row[1]
            result[row[0]] = v if isinstance(v, dict) else json.loads(v)
        return result


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
