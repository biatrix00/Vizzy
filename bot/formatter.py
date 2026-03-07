"""
bot/formatter.py — Formats bot replies as clean Telegram messages.

Telegram supports a subset of HTML and Markdown formatting.
All outbound message strings are assembled here for consistency.

Formatting conventions (no implementation yet):
- Use <b>bold</b> or *bold* for emphasis
- Use emojis sparingly: ✅ success, ❌ error, 📢 announcements, 📋 results
- Keep messages under 500 characters where possible
- Every command response ends with: "Type /help for all commands"

Functions to implement (stubs only):
- format_result(result_json, usn)      — formats VTU result data into readable text
- format_circulars(circulars_list)     — formats a list of circular dicts
- format_ia_summary(ia_records)        — formats IA marks and pass thresholds
- format_error(message)                — standard error reply template
- format_success(message)              — standard success reply template
- format_help()                        — full command list for /help

No logic implemented yet — this is a stub.
"""
