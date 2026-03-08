"""
db/database.py — SQLite connection management and schema initialisation for Vizzy.

Provides:
- init_db()         : Called once on startup. Creates the DB file and all tables.
- get_connection()  : Returns a sqlite3.Connection for use in context managers.

Rules:
- Tables are created with IF NOT EXISTS — never dropped on restart.
- All callers must use:  with get_connection() as conn:
  (sqlite3 context manager commits on exit, rolls back on exception)
"""

import sqlite3
import os
import logging
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "./vtu_bot.db")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema — verbatim from the SDR
# ---------------------------------------------------------------------------

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_hash      TEXT    NOT NULL UNIQUE,
    usn             TEXT    NOT NULL UNIQUE,
    branch          TEXT    NOT NULL,
    semester        INTEGER NOT NULL,
    college_code    TEXT,
    registered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consent_given   INTEGER DEFAULT 0
);
"""

_CREATE_CIRCULARS = """
CREATE TABLE IF NOT EXISTS circulars (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    url             TEXT,
    content_hash    TEXT    NOT NULL UNIQUE,
    category        TEXT,
    published_at    TEXT,
    scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_RESULTS_CACHE = """
CREATE TABLE IF NOT EXISTS results_cache (
    usn             TEXT    NOT NULL,
    semester_label  TEXT    NOT NULL,
    data_json       TEXT    NOT NULL,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usn, semester_label)
);
"""

_CREATE_RESPONSE_CACHE = """
CREATE TABLE IF NOT EXISTS response_cache (
    query_hash      TEXT    PRIMARY KEY,
    response        TEXT    NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_EVENT_LOG = """
CREATE TABLE IF NOT EXISTS event_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT    NOT NULL,
    command         TEXT,
    group_id_hash   TEXT,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_IA_MARKS = """
CREATE TABLE IF NOT EXISTS ia_marks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    ia1         REAL,
    ia2         REAL,
    ia3         REAL,
    semester    INTEGER,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Pending-consent staging table.
# Stores USN registration info while we wait for the user to type AGREE/CANCEL.
# Deleted immediately after consent decision is recorded.
_CREATE_PENDING_CONSENT = """
CREATE TABLE IF NOT EXISTS pending_consent (
    phone_hash      TEXT    PRIMARY KEY,
    usn             TEXT    NOT NULL,
    branch          TEXT    NOT NULL,
    semester        INTEGER NOT NULL,
    college_code    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_ALL_TABLES = [
    _CREATE_USERS,
    _CREATE_CIRCULARS,
    _CREATE_RESULTS_CACHE,
    _CREATE_RESPONSE_CACHE,
    _CREATE_EVENT_LOG,
    _CREATE_IA_MARKS,
    _CREATE_PENDING_CONSENT,
]


def get_connection() -> sqlite3.Connection:
    """Return a sqlite3.Connection to the configured DB_PATH.

    Always use inside a ``with`` block so the connection commits on clean
    exit and rolls back on exception::

        with get_connection() as conn:
            conn.execute("SELECT 1")
    """
    conn = sqlite3.connect(DB_PATH)
    # Return rows as dict-like objects (access columns by name).
    conn.row_factory = sqlite3.Row
    # Enforce foreign-key constraints (OFF by default in SQLite).
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create all tables on startup if they don't exist.

    Safe to call on every restart — uses CREATE TABLE IF NOT EXISTS throughout.
    Never drops or truncates any existing table.
    """
    logger.info("Initialising database at %s", DB_PATH)
    try:
        with get_connection() as conn:
            for ddl in _ALL_TABLES:
                conn.execute(ddl)
        logger.info("Database ready — all tables exist.")
    except Exception:
        logger.exception("FATAL: could not initialise the database.")
        raise
