"""
scraper/vtu_scraper.py — Scrapes vtu.ac.in for circulars and announcements.

Called by the APScheduler job every SCRAPE_INTERVAL_MINUTES (default: 120 minutes).

Logic (no implementation yet):
1. HTTP GET vtu.ac.in/news and vtu.ac.in/academic-section using requests
2. On failure (non-200 or exception): log error to errors.log, return cached circulars from DB
3. Parse HTML with BeautifulSoup4 — extract title, date, URL for each circular/announcement
4. For each item: compute MD5 hash of (title + date)
5. Check circulars table — if hash already exists, skip (deduplication)
6. If hash is new: insert into circulars table, add to new_circulars list
7. Return list of new circulars (empty list if none)

scrape_and_broadcast():
    Wrapper called by scheduler. Calls scrape_circulars() and then broadcasts
    new items to all registered Telegram group chats via the bot's send_message API.

CRITICAL: All external calls wrapped in try-except. Scraper crash must never
crash the bot. Always save to DB before broadcasting.

No logic implemented yet — this is a stub.
"""
