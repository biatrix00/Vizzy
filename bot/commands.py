"""
bot/commands.py — All bot command implementations for Vizzy.

Each function corresponds to one user-facing command as defined in the PDR/SDR.
All functions receive the Telegram Update and Context objects (python-telegram-bot v20+)
and return a string that telegram_handler.py sends back to the chat.

Commands implemented here (stubs only):
- register(update, context)      — starts the USN registration conversation flow
- get_result(update, context)    — fetches VTU exam result for a USN
- get_updates(update, context)   — returns the last 5 circulars from local DB
- ask_gemini(update, context)    — queues a question for the Gemini AI via bot/queue.py
- ia_tracker(update, context)    — logs or summarises IA marks
- delete_user(update, context)   — deletes all data for the requesting user
- help_command(update, context)  — returns the full command list

USN validation regex (to be used inside register and get_result):
    ^[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$

Extraction from USN:
    college_code       = characters 1-3
    year_of_joining    = 2000 + int(characters 4-5)
    branch             = characters 6-7
    estimated_semester = derived from year_of_joining and current date

No logic implemented yet — this is a stub.
"""
