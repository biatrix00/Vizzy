"""
ai/gemini.py — Gemini API wrapper with rate-limit handling.

Uses the google-generativeai library to call Gemini 1.5 Flash (not Pro).
Flash is used because it has higher free-tier rate limits than Pro.

Functions to implement (stubs only):
- init_gemini() -> None
    Configures the google-generativeai client using GEMINI_API_KEY from .env.
    Called once on startup from main.py.
- ask(prompt: str) -> str
    Sends a single prompt string to Gemini 1.5 Flash and returns the response text.
    Raises RateLimitError if the API responds with a 429.
    Raises NetworkError if the request cannot be completed.
    All other exceptions are re-raised so bot/queue.py can handle them.
- ask_with_vision(prompt: str, image_bytes: bytes) -> str
    Sends a multimodal prompt (text + image) to Gemini Vision.
    Used by scraper/pdf_parser.py for timetable OCR.

Note: This module does NOT handle rate-limit queuing or caching.
That is the responsibility of bot/queue.py.

No logic implemented yet — this is a stub.
"""
