"""
ai/context.py — Builds the context block prepended to every Gemini prompt.

Keeps Gemini answers grounded in up-to-date VTU data from the local database.
"""

import logging

logger = logging.getLogger(__name__)

_SYSTEM_PREAMBLE = (
    "You are Vizzy, a helpful assistant for VTU (Visvesvaraya Technological University) "
    "students in Karnataka, India. Answer questions clearly and concisely. "
    "If you don't know something specific about VTU, say so rather than guessing. "
    "Keep responses under 300 words."
)

_VTU_SCHEME_INFO = (
    "VTU uses the CBCS (Choice Based Credit System) scheme for students admitted from 2015 onwards. "
    "Each semester has Internal Assessment (IA) worth 40 marks and a final exam worth 60 marks. "
    "Minimum to pass: 40% in IA + 35% overall. "
    "Grading: O (90+), A+ (80-89), A (70-79), B+ (60-69), B (55-59), C (50-54), P (40-49), F (<40)."
)


def build_prompt_context() -> str:
    """Assemble the context block injected before every Gemini prompt.

    Includes:
      1. System role description
      2. Latest 5 VTU circulars from local DB
      3. Static VTU scheme info
    """
    lines = [_SYSTEM_PREAMBLE, "", "--- Latest VTU Updates ---"]

    try:
        from db.circulars import get_recent_circulars
        circulars = get_recent_circulars(limit=5)
        if circulars:
            for c in circulars:
                date  = c.get("published_at", "")[:10]   # just the date part
                title = c.get("title", "")[:120]
                lines.append(f"• [{date}] {title}")
        else:
            lines.append("• No recent circulars available.")
    except Exception:
        logger.warning("Could not load circulars for Gemini context.")
        lines.append("• Circular data unavailable.")

    lines += ["", "--- VTU Scheme Info ---", _VTU_SCHEME_INFO, ""]
    return "\n".join(lines)
