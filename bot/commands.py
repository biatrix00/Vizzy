"""
bot/commands.py — Bot command implementations for Vizzy.

All functions are called from bot/telegram_handler.py after mention/command detection.
Each function is async (python-telegram-bot v20+ uses asyncio throughout).

Registration flow (two-step with mandatory consent):
  1. User sends /register (or @vizzy register)
  2. Bot asks for USN
  3. User replies with USN
  4. Bot validates USN format, extracts fields, sends CONSENT message
  5. User replies AGREE → data saved, confirmed
     User replies CANCEL (or anything else) → data discarded

Pending state between steps 3 and 5 is stored in the pending_consent table
so the bot survives restarts mid-flow.
"""

import re
import hashlib
import logging
from datetime import datetime

from db import users as db_users
from db.database import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# USN format: 1RV21CS045  →  ^[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$
USN_REGEX = re.compile(r"^[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$")

CONSENT_MESSAGE = (
    "📋 *Before I save anything, please read this:*\n\n"
    "I will store the following data about you:\n"
    "• Your USN: *{usn}*\n"
    "• Branch: *{branch}*\n"
    "• Estimated semester: *{semester}*\n"
    "• A one-way hash of your Telegram user ID (your number is never stored in plain text)\n\n"
    "This data is used only to personalise VTU updates and result lookups.\n"
    "You can delete all your data at any time with /delete.\n\n"
    "Reply *AGREE* to confirm, or *CANCEL* to stop. No data is saved until you reply AGREE."
)

HELP_TEXT = (
    "🤖 *Vizzy — VTU Assistant Bot*\n\n"
    "/register — Register your USN for personalised updates\n"
    "/result — Fetch your exam result (uses registered USN)\n"
    "/result [USN] — Fetch result for any USN\n"
    "/updates — Get last 5 VTU circulars\n"
    "/ask [question] — Ask Gemini any VTU-related question\n"
    "/ia [subject] [marks] — Log an IA marks entry\n"
    "/ia summary — View IA marks and pass thresholds\n"
    "/delete — Delete all your data from the system\n"
    "/help — Show this message\n\n"
    "_In groups: mention @vizzy before any command._"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_user_id(telegram_user_id: int) -> str:
    """Return SHA-256 hex digest of the Telegram user ID (integer → str → bytes)."""
    raw = str(telegram_user_id).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_usn(usn: str) -> bool:
    """Return True if the USN matches the VTU format."""
    return bool(USN_REGEX.match(usn.strip().upper()))


def _parse_usn(usn: str) -> dict:
    """Extract structured fields from a valid USN string.

    USN layout (1-indexed):
        Pos 1       : digit (scheme/prefix)
        Pos 2-3     : 2-letter college code prefix  → part of college_code
        Pos 4-5     : 2-digit year of joining
        Pos 6-7     : 2-letter branch code
        Pos 8-10    : 3-digit roll number

    Example: 1RV21CS045
        college_code    = "1RV"  (first 3 chars)
        year_of_joining = 2021
        branch          = "CS"
        roll            = "045"
    """
    usn = usn.strip().upper()
    college_code = usn[:3]
    year_suffix = int(usn[3:5])
    year_of_joining = 2000 + year_suffix
    branch = usn[5:7]

    # Estimate current semester based on academic calendar.
    # VTU runs two semesters per year: odd (Aug–Dec) and even (Jan–May).
    now = datetime.now()
    years_elapsed = now.year - year_of_joining
    # Odd semester months: Aug (8) – Dec (12)
    sem_offset = 1 if now.month >= 8 else 0
    estimated_semester = min(max(years_elapsed * 2 + sem_offset, 1), 8)

    return {
        "college_code": college_code,
        "year_of_joining": year_of_joining,
        "branch": branch,
        "estimated_semester": estimated_semester,
    }


def _fmt_date(raw: str) -> str:
    """Reformat an ISO-8601 date string as 'D Mon YYYY'. Returns raw string on failure.

    Examples:
        '2026-02-19T04:36:38+00:00'  ->  '19 Feb 2026'
        '2026-01-06'                 ->  '6 Jan 2026'
    """
    if not raw:
        return "Date unknown"
    try:
        d = datetime.fromisoformat(raw[:19])
        return d.strftime("%d %b %Y").lstrip("0")
    except Exception:
        return raw


def _log_event(event_type: str, command: str | None, group_id_hash: str | None) -> None:
    """Write a row to event_log. NEVER logs message content."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO event_log (event_type, command, group_id_hash)
                VALUES (?, ?, ?)
                """,
                (event_type, command, group_id_hash),
            )
    except Exception:
        logger.exception("Failed to write event_log row")


# ---------------------------------------------------------------------------
# /register  — Step 1: ask for USN
# ---------------------------------------------------------------------------

async def register(update, context) -> str:
    """Step 1 of registration: prompt the user to send their USN.

    If the user is already registered (and consented), acknowledge that.
    Stores nothing yet — merely prompts.
    """
    user = update.effective_user
    phone_hash = _hash_user_id(user.id)

    existing = db_users.get_user_by_phone_hash(phone_hash)
    if existing and existing["consent_given"] == 1:
        return (
            f"✅ You are already registered!\n"
            f"USN: *{existing['usn']}*  |  Branch: *{existing['branch']}*  |  "
            f"Semester: *{existing['semester']}*\n\n"
            "To update your registration, first run /delete and then /register again."
        )

    # Store that we are waiting for a USN from this user.
    context.user_data["awaiting_usn"] = True

    _log_event("command", "register", None)
    return (
        "📝 Please send me your VTU USN.\n\n"
        "Example format: *1RV21CS045*\n"
        "_(College code + year + branch + roll number)_"
    )


# ---------------------------------------------------------------------------
# /register  — Step 2: receive USN, validate, send consent
# ---------------------------------------------------------------------------

async def handle_usn_input(update, context) -> str:
    """Step 2: called when the user sends a message while awaiting_usn=True.

    Validates the USN, extracts fields, persists to pending_consent, and
    sends the mandatory consent message. No data written to users table yet.
    """
    user = update.effective_user
    phone_hash = _hash_user_id(user.id)
    raw_text = update.message.text.strip()

    usn = raw_text.upper()
    if not _validate_usn(usn):
        return (
            "❌ That doesn't look like a valid VTU USN.\n\n"
            "Expected format: *1RV21CS045*\n"
            "• 1 digit + 2 letters (college) + 2 digits (year) + 2 letters (branch) + 3 digits (roll)\n\n"
            "Please try again, or type /help for all commands."
        )

    parsed = _parse_usn(usn)

    # Check if this USN is already registered by someone else.
    existing_usn = db_users.get_user_by_usn(usn)
    if existing_usn:
        return (
            "❌ This USN is already registered.\n"
            "If this is your USN and you've lost access, please contact the group admin."
        )

    # Save to staging table — NOT users table yet.
    db_users.save_pending_consent(
        phone_hash=phone_hash,
        usn=usn,
        branch=parsed["branch"],
        semester=parsed["estimated_semester"],
        college_code=parsed["college_code"],
    )

    # Clear awaiting-USN flag; now waiting for AGREE/CANCEL.
    context.user_data.pop("awaiting_usn", None)
    context.user_data["awaiting_consent"] = True

    _log_event("command", "register_usn_received", None)
    return CONSENT_MESSAGE.format(
        usn=usn,
        branch=parsed["branch"],
        semester=parsed["estimated_semester"],
    )


# ---------------------------------------------------------------------------
# /register  — Step 3: handle AGREE / CANCEL
# ---------------------------------------------------------------------------

async def handle_consent_reply(update, context) -> str:
    """Step 3: finalise or abort registration based on user's AGREE/CANCEL reply."""
    user = update.effective_user
    phone_hash = _hash_user_id(user.id)
    reply = update.message.text.strip().upper()

    pending = db_users.get_pending_consent(phone_hash)
    if not pending:
        context.user_data.pop("awaiting_consent", None)
        return (
            "⚠️ Your registration session has expired. Please start again with /register."
        )

    if reply == "AGREE":
        try:
            db_users.create_user(
                phone_hash=phone_hash,
                usn=pending["usn"],
                branch=pending["branch"],
                semester=pending["semester"],
                college_code=pending["college_code"],
            )
            db_users.set_consent(phone_hash, agreed=True)
        except Exception:
            logger.exception("Failed to create user during consent confirmation")
            db_users.delete_pending_consent(phone_hash)
            context.user_data.pop("awaiting_consent", None)
            return "❌ Something went wrong while saving your data. Please try /register again."

        db_users.delete_pending_consent(phone_hash)
        context.user_data.pop("awaiting_consent", None)
        _log_event("registration", "register_agreed", None)
        return (
            f"✅ *Registration complete!*\n\n"
            f"USN: *{pending['usn']}*\n"
            f"Branch: *{pending['branch']}*\n"
            f"Estimated Semester: *{pending['semester']}*\n\n"
            "You'll now receive personalised VTU updates.\n"
            "Type /help for all commands."
        )

    else:
        # CANCEL or anything else — discard everything.
        db_users.delete_pending_consent(phone_hash)
        context.user_data.pop("awaiting_consent", None)
        _log_event("registration", "register_cancelled", None)
        return (
            "🚫 Registration cancelled. No data has been saved.\n\n"
            "You can register anytime with /register."
        )


# ---------------------------------------------------------------------------
# /delete — erase all user data
# ---------------------------------------------------------------------------

async def delete_user(update, context) -> str:
    """Delete all personal data for the requesting user from the database."""
    user = update.effective_user
    phone_hash = _hash_user_id(user.id)

    existing = db_users.get_user_by_phone_hash(phone_hash)
    if not existing:
        return "ℹ️ You don't have any data registered with Vizzy."

    try:
        db_users.delete_user(phone_hash)
        db_users.delete_pending_consent(phone_hash)
    except Exception:
        logger.exception("Failed to delete user data")
        return "❌ Something went wrong while deleting your data. Please try again."

    _log_event("command", "delete", None)
    return (
        "✅ All your data has been permanently deleted.\n\n"
        "You can re-register anytime with /register."
    )


# ---------------------------------------------------------------------------
# /result — stub (to be implemented in next phase)
# ---------------------------------------------------------------------------

async def get_result(update, context) -> str:
    """Fetch VTU exam result. Stub — to be implemented."""
    return (
        "📋 Result fetching is coming soon!\n"
        "Type /help for currently available commands."
    )


# ---------------------------------------------------------------------------
# /updates — stub (to be implemented in next phase)
# ---------------------------------------------------------------------------

async def get_updates(update, context) -> str:
    """Return the last 5 VTU circulars from the local database.

    Always works even when VTU site is down — data is served from local DB.
    """
    from db.circulars import get_recent_circulars

    _log_event("command", "updates", None)
    try:
        circulars = get_recent_circulars(limit=5)
    except Exception:
        logger.exception("Failed to fetch circulars from DB")
        return "❌ Could not retrieve circulars. Please try again."

    if not circulars:
        return (
            "📢 No circulars stored yet.\n\n"
            "The bot scrapes VTU every 2 hours automatically.\n"
            "Type /help for all commands."
        )

    lines = ["📢 *Latest VTU Announcements*\n"]
    for i, c in enumerate(circulars, 1):
        title = c.get("title", "Untitled")
        date  = _fmt_date(c.get("published_at") or "")
        url   = c.get("url", "")

        # Truncate very long titles for readability
        if len(title) > 80:
            title = title[:77] + "…"

        if url:
            lines.append(f"*{i}.* [{title}]({url})\n    📅 {date}")
        else:
            lines.append(f"*{i}.* {title}\n    📅 {date}")

    lines.append("\nType /help for all commands.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /ask — stub (to be implemented in next phase)
# ---------------------------------------------------------------------------

async def ask_gemini(update, context) -> str:
    """Route a VTU question through the Gemini rate-limit queue."""
    import asyncio
    from bot.queue import ask_via_queue

    # Extract everything after the command as the query.
    # Supports both '/ask <question>' and '@vizzy ask <question>' via args.
    args = context.args or []
    query = " ".join(args).strip()

    # Fall back: try to get query from raw message text after 'ask'
    if not query and update.effective_message:
        text = update.effective_message.text or ""
        # Remove everything up to and including 'ask' keyword
        import re
        m = re.search(r'\bask\b(.+)', text, re.IGNORECASE)
        if m:
            query = m.group(1).strip()

    if not query:
        return (
            "Please include your question.\n"
            "Example: /ask What is the VTU passing criteria?\n\n"
            "Type /help for all commands."
        )

    _log_event("command", "ask", None)

    # Run the blocking queue call in a thread executor so the async bot loop
    # isn't blocked while waiting for Gemini.
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, ask_via_queue, query)
    except Exception:
        logger.exception("Error routing question to Gemini queue")
        return "Something went wrong. Please try again."

    return f"🤖 {response}\n\nType /help for all commands."


# ---------------------------------------------------------------------------
# /ia — stub (to be implemented in next phase)
# ---------------------------------------------------------------------------

async def ia_tracker(update, context) -> str:
    """Log or summarise IA marks. Stub — to be implemented."""
    return (
        "📊 IA marks tracker is coming soon!\n"
        "Type /help for currently available commands."
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def help_command(update, context) -> str:
    """Return the full command list."""
    _log_event("command", "help", None)
    return HELP_TEXT
