"""
main.py — Entry point for Vizzy, the VTU Telegram Assistant Bot.

Responsibilities:
- Loads environment variables from .env using python-dotenv
- Initialises the SQLite database (creates tables if they don't exist)
- Starts the APScheduler background jobs (circulars scraper, result monitor, cache cleaner)
- Starts the python-telegram-bot Application in polling mode
- Registers the Telegram command and message handlers from bot/telegram_handler.py

No logic implemented yet — this is a stub.
"""
