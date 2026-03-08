"""
db/circulars.py — Circular storage and retrieval operations.

All operations on the circulars table are centralised here.
Uses get_connection() from db/database.py — all callers must use context managers.
"""

import logging
from .database import get_connection

logger = logging.getLogger(__name__)


def save_circular(
    title: str,
    url: str,
    content_hash: str,
    category: str,
    published_at: str,
) -> bool:
    """Insert a new circular into the database.

    Returns True if the circular was inserted (new), False if the hash already
    existed (duplicate — silently skipped).
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO circulars (title, url, content_hash, category, published_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title.strip(), url.strip(), content_hash, category, published_at),
            )
        return True
    except Exception as e:
        # UNIQUE constraint on content_hash → duplicate; anything else is a real error.
        if "UNIQUE" in str(e).upper():
            return False
        logger.exception("Unexpected error saving circular: %s", title[:60])
        return False


def circular_exists(content_hash: str) -> bool:
    """Return True if a circular with this MD5 hash is already in the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM circulars WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
    return row is not None


def get_recent_circulars(limit: int = 5) -> list[dict]:
    """Return the most recent `limit` circulars ordered by scraped_at DESC.

    Used by the /updates command. Works even when VTU site is down — pulls
    purely from local database.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT title, url, category, published_at, scraped_at
            FROM circulars
            ORDER BY scraped_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_circulars() -> list[dict]:
    """Return all stored circulars. Used for injecting context into Gemini prompts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT title, url, published_at FROM circulars ORDER BY scraped_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
