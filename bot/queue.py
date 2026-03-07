"""
bot/queue.py — Gemini request queue with rate-limit handling.

Implements a thread-safe queue for all Gemini API calls, as required by the SDR.

Design (no implementation yet):
- Uses Python's built-in queue.Queue() — thread-safe FIFO
- A single background worker thread processes items one at a time
- Before every API call:
    1. Normalise the query string (lowercase, strip whitespace)
    2. Compute MD5 hash of the normalised query
    3. Check response_cache table — if a fresh entry exists (within CACHE_TTL_HOURS), return it
- If not cached:
    - Enforce a minimum 15-second gap between consecutive API calls
    - Call ai/gemini.py to make the Gemini API request
    - On RateLimitError: wait 15 seconds, retry once
    - On second failure: return "Too busy right now, please try again in 2 minutes"
    - Save successful response to response_cache table
- Rate limit target: max 4 calls per minute (Gemini free tier)

No logic implemented yet — this is a stub.
"""
