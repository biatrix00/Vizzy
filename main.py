"""
main.py — Entry point for Vizzy, the VTU Telegram Assistant Bot.

Start order:
  1. Load .env
  2. Configure logging
  3. init_db()           — create all SQLite tables
  4. init_gemini()       — configure Gemini API client
  5. start_queue_worker()— start background Gemini request queue thread
  6. Build Telegram Application
  7. post_init: fetch bot username, register handlers, kick off startup scrape
  8. run_polling()       — blocks until Ctrl-C / SIGTERM
"""

import logging
import os
import threading

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from db.database import init_db
from bot.telegram_handler import register_handlers

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("errors.log"),
    ],
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Copy .env.example to .env and fill in your token."
        )

    # 1. Database — create all tables, safe on every restart.
    logger.info("Initialising database ...")
    init_db()

    # 2. Gemini — configure API key. Skip gracefully if key not set.
    try:
        from ai.gemini import init_gemini
        init_gemini()
    except RuntimeError as e:
        logger.warning("Gemini not configured: %s — /ask will be unavailable.", e)
    except Exception:
        logger.exception("Failed to initialise Gemini — /ask will be unavailable.")

    # 3. Gemini queue worker thread (daemon — lives for the lifetime of the process).
    from bot.queue import start_queue_worker
    start_queue_worker()

    # 4. Telegram Application.
    async def post_init(application) -> None:
        bot_info = await application.bot.get_me()
        username = bot_info.username
        logger.info("Bot username: @%s", username)
        register_handlers(application, username)

        # Startup scrape in a plain daemon thread — avoids asyncio future-cancellation
        # warnings that occur when using loop.run_in_executor inside post_init.
        def _startup_scrape():
            try:
                from scraper.vtu_scraper import scrape_circulars
                new = scrape_circulars()
                logger.info("Startup scrape complete: %d new circular(s).", len(new))
            except Exception:
                logger.exception("Startup scrape failed — bot continues normally.")

        t = threading.Thread(target=_startup_scrape, daemon=True, name="startup-scrape")
        t.start()

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # 5. Scheduler placeholder (uncomment when scheduler/jobs.py is implemented).
    # from scheduler.jobs import start_scheduler
    # start_scheduler(app)

    logger.info("Vizzy is running. Press Ctrl-C to stop.")
    app.run_polling(
        allowed_updates=["message", "edited_message"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
