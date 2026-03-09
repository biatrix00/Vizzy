"""
bot/queue.py — Rate-limited Gemini request queue for Vizzy.

  - Thread-safe FIFO queue, single worker thread
  - Max 4 Gemini API calls per minute (free tier, 15-sec min gap)
  - On RateLimitError (429): waits 15s, retries once
  - On second failure: returns a friendly busy message
  - Cache check, context injection, and cache save are handled inside
    ai.gemini.ask_gemini() — this module owns only rate-limiting + retry.

Usage:
    from bot.queue import ask_via_queue
    response = ask_via_queue(query_text)   # blocking, safe from any thread
"""

import logging
import queue
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

def _do_gemini_call_via_gemini(query_text: str) -> str:
    """Rate-throttle, then delegate to ask_gemini() with a single 429 retry.

    ask_gemini() handles cache check, context injection, API call, and
    saving to cache. This function only adds:
      - A 15-second minimum gap between API calls (max ~4/min on free tier)
      - One retry after a 15-second wait on rate-limit errors (429/quota)
    """
    from ai.gemini import ask_gemini

    global _last_call_time

    # Throttle: wait until 15s have elapsed since the last call.
    with _lock:
        elapsed = time.monotonic() - _last_call_time
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
        _last_call_time = time.monotonic()

    try:
        return ask_gemini(query_text)
    except Exception as first_err:
        err_str = str(first_err).lower()
        if "429" in err_str or "quota" in err_str or "rate" in err_str:
            logger.warning("Rate limit hit — waiting %ds before retry.", RETRY_WAIT_SECONDS)
            time.sleep(RETRY_WAIT_SECONDS)
            with _lock:
                _last_call_time = time.monotonic()
            try:
                return ask_gemini(query_text)
            except Exception as retry_err:
                logger.error("Gemini retry also failed: %s", retry_err)
                return BUSY_MESSAGE
        else:
            logger.exception("Gemini call failed (non-rate-limit error).")
            return "Something went wrong with the AI. Please try again."


def _worker() -> None:
    """Background worker thread — processes queue items one at a time."""
    logger.info("Gemini queue worker started.")
    while True:
        item = _request_queue.get()
        if item is None:   # Poison pill — shut down worker
            logger.info("Gemini queue worker shutting down.")
            break

        query_text, result_holder, event = item

        try:
            # ask_gemini() handles cache check, context injection, API call,
            # and saving to cache — all in one place (ai/gemini.py).
            # _do_gemini_call() here only adds the rate-limit gap + 429 retry.
            response = _do_gemini_call_via_gemini(query_text)
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
