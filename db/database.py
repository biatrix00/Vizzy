"""
db/database.py — SQLite connection management and schema initialisation.

Responsibilities:
- On startup: open (or create) the SQLite database file at DB_PATH from .env
- Create all tables using CREATE TABLE IF NOT EXISTS — never DROP on restart
- Expose a get_connection() helper used by all other db modules

Schema (all tables defined here; no logic yet):

    users           — student profiles (phone_hash, USN, branch, semester, consent)
    circulars       — scraped VTU circulars (title, url, content_hash, category, dates)
    results_cache   — cached VTU result JSON per USN (24h TTL)
    response_cache  — cached Gemini AI responses (CACHE_TTL_HOURS TTL)
    event_log       — bot event log (command type + group hash only, never message content)
    ia_marks        — internal assessment marks tracker per student/subject

Full CREATE TABLE SQL is defined in the SDR — implement it verbatim.

Rules (from SDR error handling section):
- Always use context managers: with sqlite3.connect(DB_PATH) as conn
- If DB file does not exist on startup, create it and run all CREATE TABLE statements

No logic implemented yet — this is a stub.
"""
