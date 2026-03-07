"""
db/circulars.py — Circular storage and retrieval operations.

All operations on the circulars table are centralised here.

Functions to implement (stubs only):
- save_circular(title, url, content_hash, category, published_at) -> bool
    Inserts a new circular. Returns True if inserted, False if hash already exists (dedup).
- get_latest_circulars(limit=5) -> list[dict]
    Returns the most recent `limit` circulars ordered by scraped_at DESC.
    Used by the @bot updates command.
- circular_exists(content_hash) -> bool
    Returns True if a circular with this MD5 hash already exists in the DB.
- get_all_circulars() -> list[dict]
    Returns all stored circulars (used for Gemini context injection).

No logic implemented yet — this is a stub.
"""
