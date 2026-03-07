"""
bot/telegram_handler.py — Telegram interface for Vizzy.

Replaces the OpenClaw/WhatsApp handler described in the SDR.

Responsibilities:
- Registers python-telegram-bot (v20+) handlers with the Application object
- In GROUP CHATS: only processes messages that @mention the bot
  (Telegram delivers the bot's username in Message.entities with type MENTION)
- In PRIVATE CHATS (DMs): processes every message directly
- Extracts the command keyword and arguments from the message text
- Delegates to the appropriate function in bot/commands.py
- Sends the returned string back to the same chat as a reply
- Logs the event to the event_log table (command type only — never message content)

Key handlers to register (no implementation yet):
- CommandHandler("start")     — welcome message
- CommandHandler("help")      — show all commands
- MessageHandler(filters.TEXT) — catch-all for @mention routing in groups / all DMs

No logic implemented yet — this is a stub.
"""
