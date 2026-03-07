"""
scraper/result_monitor.py — Polls results.vtu.ac.in for new semester result drops.

Called by the APScheduler job every RESULT_POLL_INTERVAL_MINUTES (default: 15 minutes).

Logic (no implementation yet):
1. Poll results.vtu.ac.in to check if a new semester result has been published
2. Compare against the last known state stored in the local DB
3. If a new result semester is detected:
   - Save the new state to DB
   - Send an alert message to all registered Telegram group chats:
     "🔔 VTU Results are LIVE! Type /result to check yours"
4. On failure: log error, do not crash — results will be re-checked next interval

check_for_new_results():
    Main function called by the scheduler. Wraps all logic in try-except.

No logic implemented yet — this is a stub.
"""
