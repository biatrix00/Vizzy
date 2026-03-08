"""
ai/gemini.py — Gemini API wrapper for Vizzy using the google-genai SDK.

Uses google.genai (the new unified SDK) instead of the deprecated google-generativeai.
Model: gemini-1.5-flash (higher free-tier rate limits vs Pro).

Functions:
  init_gemini()                          — configure client once on startup
  ask(prompt)                            — text-only generation
  ask_with_vision(prompt, image_bytes)   — multimodal (for timetable OCR)

No caching or rate-limit handling here — that's bot/queue.py's job.
"""

import logging
import os

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-1.5-flash"

_client = None   # google.genai.Client instance (lazy init)


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
