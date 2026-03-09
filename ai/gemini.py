"""
ai/gemini.py — Gemini API wrapper for Vizzy using the google-genai SDK.

Uses google.genai (the new unified SDK) instead of the deprecated google-generativeai.
Model: gemini-1.5-flash (higher free-tier rate limits vs Pro).

Functions:
  init_gemini()                          — configure client once on startup
  ask_gemini(query)                      — high-level: cache check → context → API → save
  ask(prompt)                            — low-level text-only generation (used by queue)
  ask_with_vision(prompt, image_bytes)   — multimodal (for timetable OCR)
"""

import hashlib
import logging
import os
import re

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.0-flash"

_client = None   # google.genai.Client instance (lazy init)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def init_gemini() -> None:
    """Configure the Gemini client. Call once from main.py on startup."""
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    from google import genai
    _client = genai.Client(api_key=api_key)
    logger.info("Gemini client initialised (%s).", MODEL_NAME)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(query: str) -> str:
    """Lowercase and collapse whitespace for a consistent cache key."""
    return re.sub(r"\s+", " ", query.strip().lower())


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# High-level: ask_gemini (cache-aware, context-injected)
# ---------------------------------------------------------------------------

def ask_gemini(query: str) -> str:
    """Ask Vizzy a VTU question with full cache + context pipeline.

    Steps:
      1. Normalise query and compute MD5 hash.
      2. Return cached response immediately if hit and within CACHE_TTL_HOURS.
      3. Build the context-aware prompt (last 5 circulars + scheme info).
      4. Call Gemini 1.5 Flash.
      5. Save fresh response to cache.
      6. Return response text.

    All exceptions are caught and a friendly error string is returned instead
    of propagating — bot/queue.py only adds rate-limiting and retry on top.
    """
    try:
        from db.cache import get_cached_response, save_response, CACHE_TTL_HOURS  # noqa: F401
        from ai.context import build_prompt_context

        normalised  = _normalise(query)
        query_hash  = _md5(normalised)

        # --- 1. Cache check ---
        cached = get_cached_response(query_hash)
        if cached:
            logger.debug("Cache hit for query hash %s", query_hash[:8])
            return cached

        # --- 2. Build context-aware prompt ---
        context_block = build_prompt_context()
        full_prompt   = f"{context_block}\n\nStudent question: {query}"

        # --- 3. Call Gemini ---
        response_text = ask(full_prompt)

        # --- 4. Persist to cache ---
        save_response(query_hash, response_text)
        logger.debug("Cached response for query hash %s", query_hash[:8])

        return response_text

    except Exception:
        logger.exception("ask_gemini() failed for query: %s", query[:60])
        return "Something went wrong with the AI. Please try again."


# ---------------------------------------------------------------------------
# Low-level: ask / ask_with_vision
# ---------------------------------------------------------------------------

def ask(prompt: str) -> str:
    """Send a text prompt to Gemini 1.5 Flash and return the response text.

    Raises RuntimeError if init_gemini() was not called first.
    All other exceptions propagate to the caller (bot/queue.py handles them).
    """
    if _client is None:
        raise RuntimeError("Gemini not initialised — call init_gemini() first.")

    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text.strip()


def ask_with_vision(prompt: str, image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Send a multimodal (text + image) prompt to Gemini Vision.

    Used by scraper/pdf_parser.py for timetable OCR.
    """
    if _client is None:
        raise RuntimeError("Gemini not initialised — call init_gemini() first.")

    from google.genai import types
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, image_part],
    )
    return response.text.strip()
