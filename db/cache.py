"""
db/cache.py — Response cache for Gemini answers and VTU result data.

Manages both the response_cache and results_cache tables.

Functions to implement (stubs only):
- get_cached_response(query_hash) -> str | None
    Returns a cached Gemini response if it exists and is within CACHE_TTL_HOURS.
    Returns None if expired or not found.
- save_response(query_hash, response_text) -> None
    Inserts or replaces a Gemini response in response_cache.
- get_cached_result(usn, semester_label) -> dict | None
    Returns cached result JSON if it exists and is within RESULT_CACHE_TTL_HOURS (24h).
    Returns None if expired or not found.
- save_result(usn, semester_label, data_json) -> None
    Inserts or replaces a result entry in results_cache.
- clear_expired_entries() -> None
    Deletes rows from response_cache and results_cache that have exceeded their TTL.
    Called once daily at 03:00 by the scheduler.

No logic implemented yet — this is a stub.
"""
