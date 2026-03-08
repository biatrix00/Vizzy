"""
db/users.py — CRUD operations for the users and pending_consent tables.

All user-related database operations are centralised here.
Raw phone numbers are NEVER stored — only SHA-256 hashes.
All operations use context managers via get_connection().
"""

import logging
from .database import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confirmed users
# ---------------------------------------------------------------------------

def create_user(phone_hash: str, usn: str, branch: str,
                semester: int, college_code: str) -> int:
    """Insert a new user row with consent_given=0. Returns the new row ID."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (phone_hash, usn, branch, semester, college_code, consent_given)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (phone_hash, usn.upper(), branch.upper(), semester, college_code.upper()),
        )
        return cur.lastrowid


def get_user_by_phone_hash(phone_hash: str) -> dict | None:
    """Return the user row as a plain dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone_hash = ?", (phone_hash,)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_usn(usn: str) -> dict | None:
    """Return the user row as a plain dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE usn = ?", (usn.upper(),)
        ).fetchone()
    return dict(row) if row else None


def set_consent(phone_hash: str, agreed: bool) -> None:
    """Set consent_given = 1 (agreed) or 0 (denied/pending)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET consent_given = ? WHERE phone_hash = ?",
            (1 if agreed else 0, phone_hash),
        )


def delete_user(phone_hash: str) -> None:
    """Delete the user row and all associated ia_marks (CASCADE handles ia_marks).
    This is the /delete command — complete erasure of all personal data.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE phone_hash = ?", (phone_hash,))
    logger.info("Deleted user data for phone_hash=%s…", phone_hash[:8])


def update_semester(phone_hash: str, semester: int) -> None:
    """Update the estimated semester for a registered user."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET semester = ? WHERE phone_hash = ?",
            (semester, phone_hash),
        )


# ---------------------------------------------------------------------------
# Pending-consent staging (used during the two-step registration flow)
# ---------------------------------------------------------------------------

def save_pending_consent(phone_hash: str, usn: str, branch: str,
                         semester: int, college_code: str) -> None:
    """Upsert a pending registration record while we wait for AGREE/CANCEL."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_consent
                (phone_hash, usn, branch, semester, college_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (phone_hash, usn.upper(), branch.upper(), semester, college_code.upper()),
        )


def get_pending_consent(phone_hash: str) -> dict | None:
    """Return the pending-consent record for this user, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pending_consent WHERE phone_hash = ?", (phone_hash,)
        ).fetchone()
    return dict(row) if row else None


def delete_pending_consent(phone_hash: str) -> None:
    """Remove the staging record once the user has accepted or declined."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM pending_consent WHERE phone_hash = ?", (phone_hash,)
        )
