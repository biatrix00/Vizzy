"""
bot/queue.py — Rate-limited Gemini request queue for Vizzy.

Implements the SDR design exactly:
  - Uses queue.Queue() — thread-safe FIFO, single worker thread
  - Max 4 Gemini API calls per minute (free tier)
  - Enforces a minimum 15-second gap between consecutive API calls
  - Checks response_cache before every API call (CACHE_TTL_HOURS TTL)
  - On RateLimitError: waits 15s, retries once
  - On second failure: returns a user-friendly busy message
  - Saves all successful responses to response_cache

Usage:
    from bot.queue import ask_via_queue
    response = ask_via_queue(query_text)   # blocking, safe to call from any thread
"""

import hashlib
import logging
import queue
import re
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (from SDR)
# ---------------------------------------------------------------------------

MIN_SECONDS_BETWEEN_CALLS = 15   # enforces max ~4 calls/min on free tier
RETRY_WAIT_SECONDS        = 15
BUSY_MESSAGE = (
    "I'm getting too many questions right now. "
    "Please try again in 2 minutes."
)

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_request_queue: queue.Queue  = queue.Queue()
_worker_thread: Optional[threading.Thread] = None
_last_call_time: float = 0.0
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(query: str) -> str:
    """Lowercase and collapse whitespace for consistent cache keys."""
    return re.sub(r"\s+", " ", query.strip().lower())


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _do_gemini_call(prompt: str) -> str:
    """Make one Gemini API call with a single retry on rate-limit failure."""
    from ai.gemini import ask as gemini_ask

    global _last_call_time

    # Throttle: wait until 15s have elapsed since the last call.
    with _lock:
        elapsed = time.monotonic() - _last_call_time
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
        _last_call_time = time.monotonic()

    try:
        return gemini_ask(prompt)
    except Exception as first_err:
        err_str = str(first_err).lower()
        if "429" in err_str or "quota" in err_str or "rate" in err_str:
            logger.warning("Gemini rate limit hit — waiting %ds and retrying.", RETRY_WAIT_SECONDS)
            time.sleep(RETRY_WAIT_SECONDS)
            with _lock:
                _last_call_time = time.monotonic()
            try:
                return gemini_ask(prompt)
            except Exception as retry_err:
                logger.error("Gemini retry also failed: %s", retry_err)
                return BUSY_MESSAGE
        else:
            logger.exception("Gemini call failed with non-rate-limit error.")
            return "Something went wrong with the AI. Please try again."


def _worker() -> None:
    """Background worker thread — processes queue items one at a time."""
    from db.cache import get_cached_response, save_response
    from ai.context import build_prompt_context

    logger.info("Gemini queue worker started.")
    while True:
        item = _request_queue.get()
        if item is None:   # Poison pill — shut down worker
            logger.info("Gemini queue worker shutting down.")
            break

        query_text, result_holder, event = item

        try:
            normalised  = _normalise(query_text)
            query_hash  = _md5(normalised)

            # --- Cache check ---
            cached = get_cached_response(query_hash)
            if cached:
                logger.debug("Cache hit for query hash %s", query_hash[:8])
                result_holder["response"] = cached
                event.set()
                continue

            # --- Build contextualised prompt ---
            context_block = build_prompt_context()
            full_prompt   = f"{context_block}\n\nStudent question: {query_text}"

            # --- API call (with rate limiting and retry) ---
            response = _do_gemini_call(full_prompt)

            # --- Cache the fresh response (don't cache busy/error messages) ---
            if response not in (BUSY_MESSAGE, "Something went wrong with the AI. Please try again."):
                save_response(query_hash, response)

            result_holder["response"] = response

        except Exception:
            logger.exception("Unexpected error in queue worker for query: %s", query_text[:60])
            result_holder["response"] = "Something went wrong. Please try again."
        finally:
            event.set()

        _request_queue.task_done()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_queue_worker() -> None:
    """Start the background worker thread. Call once from main.py on startup."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="gemini-queue-worker")
    _worker_thread.start()
    logger.info("Gemini queue worker thread started.")


def stop_queue_worker() -> None:
    """Gracefully stop the worker by sending the poison pill."""
    _request_queue.put(None)


def ask_via_queue(query_text: str, timeout: int = 60) -> str:
    """Submit a query to the Gemini queue and block until the response arrives.

    Args:
        query_text : The raw user question (not yet normalised).
        timeout    : Max seconds to wait for a response (default 60).

    Returns:
        The AI response string, or a friendly error message on timeout/failure.
    """
    result_holder: dict = {}
    done_event    = threading.Event()

    _request_queue.put((query_text, result_holder, done_event))

    if not done_event.wait(timeout=timeout):
        logger.warning("Gemini queue timed out after %ds for query: %s", timeout, query_text[:60])
        return "The request timed out. Please try again."

    return result_holder.get("response", "No response received.")
