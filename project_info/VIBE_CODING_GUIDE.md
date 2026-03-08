# VIBE CODING INSTRUCTIONS
## VTU WhatsApp Assistant Bot
### Read the PDR and SDR first. Then follow these instructions every session.

---

## HOW TO USE THESE DOCUMENTS

Before writing any code in a new session, paste this into the AI:

> "I am building a VTU WhatsApp assistant bot. Here is my PDR: [paste PDR]. Here is my SDR: [paste SDR]. Follow these documents exactly. Do not introduce tools or patterns not mentioned in the SDR. Ask me if anything is unclear before writing code."

---

## PHASE-BY-PHASE BUILD ORDER

### PHASE 0 — Setup (Do this first, today)
Ask AI: *"Set up the project folder structure exactly as defined in the SDR. Create all files as empty stubs with docstrings. Create requirements.txt with all listed packages. Create .env.example. Do not write any logic yet."*

Then manually:
- Install OpenClaw from openclaw.dev
- Scan QR code to link a spare WhatsApp number
- Run `pip install -r requirements.txt` in virtual environment
- Get Gemini API key from aistudio.google.com
- Fill in .env file

### PHASE 1 — Database + Registration (Days 1–2)
Ask AI: *"Implement db/database.py — create all tables from the SDR schema on startup. Then implement the USN registration flow in bot/commands.py exactly as described in the SDR. Include consent message. Include USN validation regex."*

Test: register yourself with your own USN in a test WhatsApp group.

### PHASE 2 — Result Fetching (Day 3)
Ask AI: *"Implement the result fetching command using python-vtu-api as described in the SDR. Include 24-hour cache in results_cache table. Handle VTU site being down gracefully."*

Test: fetch your own real VTU result via the bot.

### PHASE 3 — Gemini Q&A (Day 4)
Ask AI: *"Implement bot/queue.py with the rate-limited Gemini request queue as described in the SDR. Implement the ask command. Include 6-hour response cache. Handle rate limit errors with user-friendly messages."*

Test: ask the bot 5 different VTU questions back to back.

### PHASE 4 — Scraper (Days 5–7)
Ask AI: *"Implement scraper/vtu_scraper.py as described in the SDR. Scrape vtu.ac.in for circulars. Use content hash deduplication. Save everything to SQLite before broadcasting. Wrap entirely in try-except — a broken VTU site must never crash the bot."*

Test: run scraper manually, check that circulars appear in the database.

### PHASE 5 — Scheduler + Full Integration (Days 8–10)
Ask AI: *"Implement scheduler/jobs.py with APScheduler jobs as defined in the SDR. Wire everything together in main.py. Bot should start, connect to OpenClaw, start the scheduler, and be ready to handle messages."*

Test: leave bot running for 24 hours, check it is still alive.

---

## KEY INSTRUCTIONS TO GIVE THE AI AT ANY TIME

**When starting a new feature:**
> "Follow the SDR exactly. Use only the tools listed in the tech stack. If you are about to add a library not in requirements.txt, ask me first."

**When debugging a scraper issue:**
> "The scraper must never crash the bot. If it fails, log the error and return cached data. Fix this without removing the try-except blocks."

**When the AI wants to add complexity:**
> "Keep it simple. We are in prototype phase. If it works, that is enough. We can improve it later."

**When writing any database code:**
> "Always use context managers for SQLite connections. Always create tables if they don't exist on startup. Never drop tables."

**When writing any external API call:**
> "Wrap this in try-except. Return a user-friendly string on failure. Log the actual error to errors.log."

---

## THINGS TO WATCH OUT FOR

If the AI does any of these, stop it and redirect:

- Suggests using Flask, FastAPI, or any web server → say "No web server needed, remove it"
- Suggests Docker → say "No Docker, this runs directly on my laptop"
- Suggests PostgreSQL or MongoDB → say "SQLite only, as per SDR"
- Adds new commands not in the PDR → say "Stick to the PDR command list"
- Writes Gemini calls without a queue → say "All Gemini calls must go through bot/queue.py"
- Stores raw message content in DB → say "Never store message content, only event types"
- Stores raw phone numbers → say "Phone numbers must be SHA-256 hashed before storing"
