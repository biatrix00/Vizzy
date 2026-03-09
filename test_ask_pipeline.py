"""
test_ask_pipeline.py — Offline unit tests for the /ask command pipeline.

Tests the full cache + context + AI pipeline without a real Gemini API key.
Uses unittest.mock to patch ai.gemini.ask() so no network calls are made.

Run with:
    python test_ask_pipeline.py
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
os.environ["DB_PATH"] = "./test_run.db"

from db.database import init_db, get_connection

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(label, condition):
    print(f"  {PASS if condition else FAIL}  {label}")
    if not condition:
        raise AssertionError(f"FAILED: {label}")

print("\n=== Vizzy /ask Pipeline Test Suite ===\n")

# Initialise DB (creates response_cache table among others)
init_db()


# ── 1. Context builder ──────────────────────────────────────────────────────
print("1. Context builder (ai/context.py)")

from ai.context import build_prompt_context

ctx = build_prompt_context()
check("Returns a non-empty string", bool(ctx) and len(ctx) > 10)
check("Contains system preamble ('VTU student assistant')", "VTU student assistant" in ctx)
check("Contains 'Answer only VTU-related' instruction",     "Answer only VTU-related" in ctx)
check("Contains circular context header",
      "Here are the latest VTU circulars for context:" in ctx)
check("Contains VTU scheme info block", "VTU Scheme Info" in ctx)


# ── 2. Cache write / read ───────────────────────────────────────────────────
print("\n2. Cache read/write (db/cache.py)")

from db.cache import get_cached_response, save_response

TEST_HASH = "deadbeef" * 4   # 32-char fake MD5
TEST_RESP = "The VTU passing criteria is 40% in IA and 35% overall."

# Verify cache miss before inserting
check("Cache miss before save", get_cached_response(TEST_HASH) is None)

save_response(TEST_HASH, TEST_RESP)
cached = get_cached_response(TEST_HASH)
check("Cache hit after save",         cached == TEST_RESP)
check("Returned text matches exactly", cached == TEST_RESP)

# Cleanup
with get_connection() as conn:
    conn.execute("DELETE FROM response_cache WHERE query_hash = ?", (TEST_HASH,))
check("Cache miss after cleanup", get_cached_response(TEST_HASH) is None)


# ── 3. ask_gemini() cache-hit path (no API call) ────────────────────────────
print("\n3. ask_gemini() — cache-hit path (no API call)")

import hashlib, re

QUERY       = "What is the VTU passing criteria?"
normalised  = re.sub(r"\s+", " ", QUERY.strip().lower())
query_hash  = hashlib.md5(normalised.encode("utf-8")).hexdigest()

# Pre-seed the cache with a known answer
SEEDED_RESP = "Seeded: 40% in IA + 35% overall to pass VTU."
save_response(query_hash, SEEDED_RESP)

from ai.gemini import ask_gemini
result = ask_gemini(QUERY)
check("ask_gemini() returns cached answer without calling API", result == SEEDED_RESP)

# Cleanup
with get_connection() as conn:
    conn.execute("DELETE FROM response_cache WHERE query_hash = ?", (query_hash,))


# ── 4. ask_gemini() cache-miss path (mocked API) ────────────────────────────
print("\n4. ask_gemini() — cache-miss path (mocked API call)")

from unittest.mock import patch

MOCK_ANSWER = "Mocked Gemini answer: CBCS is the grading scheme used by VTU."

with patch("ai.gemini.ask", return_value=MOCK_ANSWER) as mock_ask:
    result2 = ask_gemini(QUERY)

check("ask_gemini() returns mocked API response", result2 == MOCK_ANSWER)
check("Low-level ask() was called exactly once",  mock_ask.call_count == 1)

# The response should now be cached
cached2 = get_cached_response(query_hash)
check("Fresh response was saved to cache", cached2 == MOCK_ANSWER)

# Cleanup
with get_connection() as conn:
    conn.execute("DELETE FROM response_cache WHERE query_hash = ?", (query_hash,))


# ── 5. ask_gemini() error handling ──────────────────────────────────────────
print("\n5. ask_gemini() — error handling (exception in API)")

from unittest.mock import patch as patch2

with patch2("ai.gemini.ask", side_effect=Exception("Network error")) as mock_err:
    err_result = ask_gemini("Some question?")

check("Returns friendly error string on exception",
      "Something went wrong" in err_result)
check("Does not raise exception to caller", True)  # test itself proves it


print("\n=== All pipeline tests passed! [ALL PASS] ===\n")
