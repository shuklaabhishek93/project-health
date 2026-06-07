"""Database-backed storage using PostgreSQL (key-value with JSON).

When DATABASE_URL is set, all data is stored in PostgreSQL so it
persists across deployments.  Falls back to the JSON file storage
when DATABASE_URL is not set (local development).

Supports Neon (serverless, requires SSL), Supabase, Render,
and any standard PostgreSQL provider.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("db_storage")

_conn = None
_conn_ok = False


def _prepare_url(url: str) -> str:
    """Normalize the DATABASE_URL for psycopg2 compatibility."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url += sep + "sslmode=require"
    return url


def _get_conn():
    """Return a reusable database connection, creating it and the table on first call."""
    global _conn, _conn_ok
    if _conn is not None and _conn_ok:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            _conn_ok = False
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None

    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            _conn_ok = True
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
            _conn_ok = False

    import psycopg2
    url = _prepare_url(os.environ.get("DATABASE_URL", ""))
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
    logger.info("Database connected")
    return _conn


def _safe_execute(fn):
    """Retry once on connection failure (handles Neon serverless wake-up)."""
    global _conn_ok
    try:
        return fn()
    except Exception:
        _conn_ok = False
        try:
            conn = _get_conn()
            return fn()
        except Exception:
            raise


def is_db_enabled() -> bool:
    """Check whether database storage is configured."""
    return bool(os.environ.get("DATABASE_URL"))


def db_put(key: str, value: dict):
    """Upsert a JSON value by key."""
    def _do():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO health_data (key, value) VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                (key, json.dumps(value)),
            )
    _safe_execute(_do)


def db_get(key: str) -> Optional[dict]:
    """Retrieve a JSON value by key, or None."""
    def _do():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM health_data WHERE key = %s", (key,))
            row = cur.fetchone()
            if row:
                v = row[0]
                return v if isinstance(v, dict) else json.loads(v)
        return None
    return _safe_execute(_do)


def db_get_many(keys: list[str]) -> dict[str, dict]:
    """Retrieve multiple keys in a single query. Returns {key: value} for found keys."""
    if not keys:
        return {}
    def _do():
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
    return _safe_execute(_do)


def db_delete(key: str):
    """Remove a key."""
    def _do():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM health_data WHERE key = %s", (key,))
    _safe_execute(_do)


def db_list_keys(prefix: str) -> list[str]:
    """List all keys matching a prefix, sorted."""
    def _do():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key FROM health_data WHERE key LIKE %s ORDER BY key",
                (prefix + "%",),
            )
            return [row[0] for row in cur.fetchall()]
    return _safe_execute(_do)


def db_export_all() -> dict[str, dict]:
    """Export all data for migration purposes."""
    def _do():
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM health_data ORDER BY key")
            result = {}
            for row in cur.fetchall():
                v = row[1]
                result[row[0]] = v if isinstance(v, dict) else json.loads(v)
            return result
    return _safe_execute(_do)


def db_import_all(data: dict[str, dict]):
    """Import data from a migration export."""
    conn = _get_conn()
    with conn.cursor() as cur:
        for key, value in data.items():
            cur.execute(
                """INSERT INTO health_data (key, value) VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                (key, json.dumps(value)),
            )
    logger.info(f"Imported {len(data)} records")
