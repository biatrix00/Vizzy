"""
scheduler/jobs.py — APScheduler job definitions for Vizzy.

Configures and registers all background jobs using APScheduler's
BackgroundScheduler. Started from main.py after the bot is initialised.

Jobs to register (no implementation yet):

| Job name              | Function                                      | Interval                     |
|-----------------------|-----------------------------------------------|------------------------------|
| scrape_circulars      | scraper.vtu_scraper.scrape_and_broadcast      | Every SCRAPE_INTERVAL_MINUTES (default 120 min) |
| poll_result_drops     | scraper.result_monitor.check_for_new_results  | Every RESULT_POLL_INTERVAL_MINUTES (default 15 min) |
| clean_expired_cache   | db.cache.clear_expired_entries                | Daily at 03:00               |

Rules (from SDR error handling section):
- Every job function must be wrapped in its own try-except
- A failing job must log the error to errors.log and reschedule normally
- A job crash must NEVER crash the scheduler or the bot process

Functions to implement (stubs only):
- start_scheduler(app) -> None
    Creates and starts the BackgroundScheduler, registers all jobs,
    and stores the scheduler reference for clean shutdown.
- stop_scheduler() -> None
    Gracefully shuts down the scheduler (called on SIGTERM/SIGINT).

No logic implemented yet — this is a stub.
"""
