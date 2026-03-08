"""
db/cache.py — Response cache for Gemini answers and VTU result data.

Manages response_cache (Gemini answers) and results_cache (VTU result JSON).
All TTLs are loaded from .env via python-dotenv.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from .database import get_connection

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS        = int(os.getenv("CACHE_TTL_HOURS", "6"))
RESULT_CACHE_TTL_HOURS = int(os.getenv("RESULT_CACHE_TTL_HOURS", "24"))


# ---------------------------------------------------------------------------
# Gemini response cache
# ---------------------------------------------------------------------------

def get_cached_response(query_hash: str) -> str | None:
    """Return a cached Gemini response if it exists and is within TTL, else None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT response, created_at FROM response_cache WHERE query_hash = ?",
            (query_hash,),
        ).fetchone()

    if not row:
        return None

    created_at = datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc)
    if datetime.now(tz=timezone.utc) - created_at > timedelta(hours=CACHE_TTL_HOURS):
        return None  # Expired — caller will fetch fresh from Gemini

    return row["response"]


def save_response(query_hash: str, response_text: str) -> None:
    """Insert or replace a Gemini response in response_cache."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO response_cache (query_hash, response, created_at)
            VALUES (?, ?, ?)
            """,
            (query_hash, response_text, datetime.now(tz=timezone.utc).isoformat()),
        )


# ---------------------------------------------------------------------------
# VTU result cache
# ---------------------------------------------------------------------------

def get_cached_result(usn: str, semester_label: str) -> dict | None:
    """Return cached result JSON if within RESULT_CACHE_TTL_HOURS, else None."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT data_json, fetched_at FROM results_cache
            WHERE usn = ? AND semester_label = ?
            """,
            (usn.upper(), semester_label),
        ).fetchone()

    if not row:
        return None

    fetched_at = datetime.fromisoformat(row["fetched_at"]).replace(tzinfo=timezone.utc)
    if datetime.now(tz=timezone.utc) - fetched_at > timedelta(hours=RESULT_CACHE_TTL_HOURS):
        return None

    try:
        return json.loads(row["data_json"])
    except json.JSONDecodeError:
        return None


def save_result(usn: str, semester_label: str, data_json: dict) -> None:
    """Insert or replace a result entry in results_cache."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO results_cache
                (usn, semester_label, data_json, fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                usn.upper(),
                semester_label,
                json.dumps(data_json),
                datetime.now(tz=timezone.utc).isoformat(),
            ),
        )


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def clear_expired_entries() -> None:
    """Delete expired rows from both cache tables. Called daily at 03:00 by scheduler."""
    try:
        now = datetime.now(tz=timezone.utc)
        response_cutoff = (now - timedelta(hours=CACHE_TTL_HOURS)).isoformat()
        result_cutoff   = (now - timedelta(hours=RESULT_CACHE_TTL_HOURS)).isoformat()

        with get_connection() as conn:
            r1 = conn.execute(
                "DELETE FROM response_cache WHERE created_at < ?", (response_cutoff,)
            ).rowcount
            r2 = conn.execute(
                "DELETE FROM results_cache WHERE fetched_at < ?", (result_cutoff,)
            ).rowcount

        logger.info("Cache cleanup: removed %d response(s) and %d result(s).", r1, r2)
    except Exception:
        logger.exception("Error during cache cleanup")
