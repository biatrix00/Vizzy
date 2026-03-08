"""
bot/telegram_handler.py — Telegram interface layer for Vizzy.

Registers all handlers with the python-telegram-bot Application object.
Routes every incoming event to the correct function in bot/commands.py.
Contains NO business logic — this file is wiring only.

Group chat behaviour:
    Only responds when the bot is @mentioned in the message text.
    Uses Message.entities to detect MENTION type pointing at the bot's username.

DM (private chat) behaviour:
    Responds to every message — no mention check needed.

Two-step registration state is tracked via context.user_data:
    "awaiting_usn"     : True  → next text message = USN input
    "awaiting_consent" : True  → next text message = AGREE / CANCEL reply
"""

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from bot import commands

logger = logging.getLogger(__name__)

BOT_USERNAME: str | None = None   # Set after Application is built (via bot.username)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bot_mentioned(update: Update) -> bool:
    """Return True if the message is a DM or if the bot is @mentioned in a group."""
    message = update.effective_message
    if message is None:
        return False

    # Private chat: always respond.
    if update.effective_chat.type == "private":
        return True

    # Group / supergroup: only respond if @botusername is in entities.
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mentioned = message.text[entity.offset: entity.offset + entity.length]
                if BOT_USERNAME and mentioned.lower() == f"@{BOT_USERNAME.lower()}":
                    return True
    return False


async def _send(update: Update, text: str) -> None:
    """Reply to the current message with Markdown formatting."""
    await update.effective_message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Command handlers — each delegates immediately to bot/commands.py
# ---------------------------------------------------------------------------

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — welcome message, same content as /help."""
    if not _bot_mentioned(update):
        return
    text = (
        "👋 *Hi! I'm Vizzy, your VTU student assistant.*\n\n"
        "I can help you with:\n"
        "• Exam results • VTU circulars • AI-powered Q&A • IA marks tracking\n\n"
        "Type /register to get started, or /help for all commands."
    )
    await _send(update, text)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — show full command list."""
    if not _bot_mentioned(update):
        return
    reply = await commands.help_command(update, context)
    await _send(update, reply)


async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/register — step 1: prompt for USN."""
    if not _bot_mentioned(update):
        return
    reply = await commands.register(update, context)
    await _send(update, reply)


async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delete — erase all personal data for this user."""
    if not _bot_mentioned(update):
        return
    reply = await commands.delete_user(update, context)
    await _send(update, reply)


async def handle_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/result — stub, delegates to commands.get_result."""
    if not _bot_mentioned(update):
        return
    reply = await commands.get_result(update, context)
    await _send(update, reply)


async def handle_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/updates — stub, delegates to commands.get_updates."""
    if not _bot_mentioned(update):
        return
    reply = await commands.get_updates(update, context)
    await _send(update, reply)


async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ask — stub, delegates to commands.ask_gemini."""
    if not _bot_mentioned(update):
        return
    reply = await commands.ask_gemini(update, context)
    await _send(update, reply)


async def handle_ia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ia — stub, delegates to commands.ia_tracker."""
    if not _bot_mentioned(update):
        return
    reply = await commands.ia_tracker(update, context)
    await _send(update, reply)


# ---------------------------------------------------------------------------
# Plain-text message handler — drives the multi-step registration flow
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for plain text messages.

    Routes mid-flow registration replies (USN input, AGREE/CANCEL) regardless
    of @mention so users can reply naturally during the conversation.
    For all other plain text in groups, requires an @mention.
    """
    # Mid-flow messages are always processed (user is replying to a bot prompt).
    in_registration_flow = (
        context.user_data.get("awaiting_usn")
        or context.user_data.get("awaiting_consent")
    )

    if in_registration_flow:
        if context.user_data.get("awaiting_usn"):
            reply = await commands.handle_usn_input(update, context)
        else:
            reply = await commands.handle_consent_reply(update, context)
        await _send(update, reply)
        return

    # Outside registration flow: require @mention in groups.
    if not _bot_mentioned(update):
        return

    # Unknown plain text with @mention — nudge towards commands.
    await _send(
        update,
        "I didn't understand that. Type /help to see all available commands."
    )


# ---------------------------------------------------------------------------
# Registration function — called from main.py
# ---------------------------------------------------------------------------

def register_handlers(app: Application, bot_username: str) -> None:
    """Register all handlers with the Application. Called once from main.py."""
    global BOT_USERNAME
    BOT_USERNAME = bot_username

    # Command handlers
    app.add_handler(CommandHandler("start",   handle_start))
    app.add_handler(CommandHandler("help",    handle_help))
    app.add_handler(CommandHandler("register", handle_register))
    app.add_handler(CommandHandler("delete",  handle_delete))
    app.add_handler(CommandHandler("result",  handle_result))
    app.add_handler(CommandHandler("updates", handle_updates))
    app.add_handler(CommandHandler("ask",     handle_ask))
    app.add_handler(CommandHandler("ia",      handle_ia))

    # Plain text — must come AFTER command handlers so commands take priority.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("All handlers registered for @%s", bot_username)
