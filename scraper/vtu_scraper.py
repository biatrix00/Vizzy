"""
scraper/vtu_scraper.py — Scrapes vtu.ac.in for announcements and circulars.

Called by the APScheduler job every SCRAPE_INTERVAL_MINUTES (default: 120 min).
Also callable manually via /updates for an immediate refresh.

Scraping strategy:
  - Primary target: https://vtu.ac.in/en/ (main homepage announcements block)
  - Parses all <article> elements or announcement <h3> links within the page
  - Extracts: title, URL (permalink), date text
  - Computes MD5(title + date) for deduplication
  - Saves new circulars to DB, skips known hashes
  - Returns list of newly saved circular dicts

CRITICAL: Every external call is wrapped in try-except.
          A scraper failure must NEVER crash the bot or the scheduler.
          If VTU site is down: log error, return empty list.
"""

import hashlib
import logging
import re
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from db.circulars import save_circular, circular_exists, get_recent_circulars

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VTU_BASE      = "https://vtu.ac.in/en/"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5(text: str) -> str:
    """Return an MD5 hex digest of the given string."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _clean(text: str) -> str:
    """Collapse whitespace and strip a string."""
    return re.sub(r"\s+", " ", text).strip()


def _classify(title: str) -> str:
    """Guess a category from the title text."""
    t = title.lower()
    if any(k in t for k in ("result", "results")):
        return "results"
    if any(k in t for k in ("exam", "examination", "timetable", "schedule")):
        return "exam"
    if any(k in t for k in ("academic", "calendar", "semester", "scheme")):
        return "academic"
    return "general"


def _fetch_html(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching %s", url)
    except requests.exceptions.ConnectionError:
        logger.error("Connection error fetching %s — VTU site may be down", url)
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP %s from %s", e.response.status_code, url)
    except Exception:
        logger.exception("Unexpected error fetching %s", url)
    return None


def _parse_announcements(soup: BeautifulSoup) -> list[dict]:
    """
    Extract announcement items from the parsed VTU homepage HTML.

    The VTU site renders announcements as WordPress blog posts.
    Each post is an <article> tag (or inside a div.post-content / div.entry-content).
    The title is in an <h2> or <h3> with a permalink <a>.
    The date is in a <time> element (datetime attribute) or a <span class="...date...">.

    We try multiple strategies in order, stopping at the first that yields results.
    """
    items = []

    # ── Strategy 1: standard WordPress <article> loop ──
    articles = soup.find_all("article")
    if articles:
        for article in articles:
            # Title: first h1/h2/h3/h4 with an <a> inside
            heading = article.find(["h1", "h2", "h3", "h4"])
            if not heading:
                continue
            a_tag = heading.find("a", href=True)
            if not a_tag:
                continue
            title = _clean(a_tag.get_text())
            url   = a_tag["href"].strip()

            # Date: prefer <time datetime="YYYY-MM-DD">, fall back to text
            time_el = article.find("time")
            if time_el:
                date_str = time_el.get("datetime", time_el.get_text())
            else:
                # Try common date class names
                date_span = article.find(
                    class_=re.compile(r"date|published|entry-date", re.I)
                )
                date_str = _clean(date_span.get_text()) if date_span else ""

            if title:
                items.append({"title": title, "url": url, "date": _clean(date_str)})
        if items:
            return items

    # ── Strategy 2: announcement <h3> links (seen on vtu.ac.in/en/ homepage) ──
    # The homepage wraps announcements in a widget/section; each entry is an <h3><a>.
    # Date appears as a sibling <a> link to the same permalink.
    for h3 in soup.find_all("h3"):
        a_tag = h3.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        # Only VTU permalinks — filter out nav/menu links.
        if "vtu.ac.in" not in href and not href.startswith("/"):
            continue
        title = _clean(a_tag.get_text())
        if not title:
            continue

        # Look for a date: the next sibling or parent's next sibling often has
        # the date as a <a> or <span> with parseable date text.
        date_str = ""
        parent = h3.parent
        if parent:
            # Find any element near this h3 that contains a date pattern
            date_pattern = re.compile(
                r"\b(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                re.IGNORECASE,
            )
            for sib in h3.next_siblings:
                sib_text = sib.get_text() if hasattr(sib, "get_text") else str(sib)
                m = date_pattern.search(sib_text)
                if m:
                    date_str = m.group(0)
                    break

        items.append({"title": title, "url": href, "date": date_str})

    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_circulars() -> list[dict]:
    """Scrape VTU site and save new circulars to the database.

    Returns a list of newly found circular dicts (empty list = nothing new or site down).
    Never raises — all exceptions are caught and logged.
    """
    logger.info("Scraping VTU announcements from %s", VTU_BASE)
    new_circulars: list[dict] = []

    try:
        soup = _fetch_html(VTU_BASE)
        if soup is None:
            logger.warning("Could not fetch VTU page — returning empty list.")
            return []

        items = _parse_announcements(soup)
        logger.info("Parsed %d announcement items from VTU page.", len(items))

        for item in items:
            title      = item.get("title", "").strip()
            url        = item.get("url", "").strip()
            date_str   = item.get("date", "").strip()

            if not title:
                continue

            content_hash = _md5(title + date_str)

            # Dedup check before DB write.
            if circular_exists(content_hash):
                continue

            category = _classify(title)
            inserted = save_circular(
                title        = title,
                url          = url,
                content_hash = content_hash,
                category     = category,
                published_at = date_str,
            )
            if inserted:
                new_circulars.append({
                    "title"       : title,
                    "url"         : url,
                    "published_at": date_str,
                    "category"    : category,
                })
                logger.info("New circular saved: %s", title[:70])

    except Exception:
        logger.exception("Unexpected error in scrape_circulars — returning empty list")
        return []

    logger.info(
        "Scrape complete. %d new circular(s) found.", len(new_circulars)
    )
    return new_circulars


def scrape_and_broadcast(app=None) -> None:
    """Scheduler entry point: scrape then broadcast new circulars to all groups.

    `app` is the python-telegram-bot Application object, passed by the scheduler.
    Broadcasting is a placeholder until group tracking is implemented.
    """
    try:
        new_circulars = scrape_circulars()
        if not new_circulars:
            return

        logger.info(
            "Broadcasting %d new circular(s) to registered groups (placeholder).",
            len(new_circulars),
        )
        # TODO: when group tracking is implemented, iterate registered group_ids
        # and call app.bot.send_message(chat_id=group_id, text=...) here.

    except Exception:
        logger.exception("Error in scrape_and_broadcast — scheduler will retry next interval")
