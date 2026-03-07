# SYSTEM DESIGN REQUIREMENTS (SDR)
## VTU WhatsApp Assistant Bot
### Feed this entire document to the AI alongside the PDR before writing any code

---

## TECH STACK — USE EXACTLY THESE TOOLS

| Layer | Tool | Version / Notes |
|---|---|---|
| WhatsApp interface | OpenClaw (self-hosted) | Uses Baileys under the hood. Custom skills written in Python |
| AI model | Google Gemini 1.5 Flash | Use Flash not Pro — higher free tier rate limits |
| Scraping | Python + BeautifulSoup4 + Requests | Standard scraping stack |
| Result fetching | python-vtu-api | Open source PyPI package. Already handles CAPTCHA. Returns clean JSON |
| Scheduling | APScheduler (Python) | Background jobs for scraper and result-drop polling |
| Database | SQLite | Single file, zero setup. Use sqlite3 standard library |
| Environment | Python 3.11+ virtual environment | All dependencies in requirements.txt |
| Prototype server | Local laptop | Acceptable. Must survive restarts without data loss |

Do NOT introduce any other tools, frameworks, or databases unless explicitly asked. No Docker, no Redis, no PostgreSQL, no FastAPI server — keep it simple.

---

## PROJECT FOLDER STRUCTURE

Create exactly this structure:

```
vtu-bot/
├── main.py                  # Entry point — starts OpenClaw skill + scheduler
├── requirements.txt         # All Python dependencies
├── .env                     # API keys and config (never commit this)
├── .env.example             # Template showing what keys are needed
│
├── bot/
│   ├── __init__.py
│   ├── handler.py           # Routes incoming @bot commands to correct function
│   ├── commands.py          # All command implementations (result, updates, ask, register, delete)
│   ├── queue.py             # Gemini request queue (max 4/min rate limit handler)
│   └── formatter.py         # Formats bot replies as clean WhatsApp messages
│
├── scraper/
│   ├── __init__.py
│   ├── vtu_scraper.py       # Scrapes vtu.ac.in for circulars and announcements
│   ├── result_monitor.py    # Polls results.vtu.ac.in for new semester result drops
│   └── pdf_parser.py        # OCR for scanned timetable PDFs using Gemini Vision
│
├── db/
│   ├── __init__.py
│   ├── database.py          # SQLite connection, table creation, migrations
│   ├── users.py             # All user CRUD operations
│   ├── circulars.py         # Circular storage and retrieval
│   └── cache.py             # Response cache for Gemini answers and result data
│
├── ai/
│   ├── __init__.py
│   ├── gemini.py            # Gemini API wrapper with rate limit handling
│   └── context.py           # Builds context string injected into every Gemini prompt
│
└── scheduler/
    ├── __init__.py
    └── jobs.py              # APScheduler job definitions
```

---

## DATABASE SCHEMA

Use SQLite. Create all tables on startup if they don't exist. Never drop tables on restart.

```sql
-- Student profiles
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_hash TEXT NOT NULL UNIQUE,    -- SHA-256 of phone number, never raw number
    usn TEXT NOT NULL UNIQUE,
    branch TEXT NOT NULL,               -- e.g. "CS", "EC", "ME"
    semester INTEGER NOT NULL,          -- estimated from USN year
    college_code TEXT,                  -- extracted from USN
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consent_given INTEGER DEFAULT 0     -- 1 = agreed, 0 = pending
);

-- Scraped VTU circulars and announcements
CREATE TABLE IF NOT EXISTS circulars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    content_hash TEXT NOT NULL UNIQUE,  -- MD5 of title+date, used for dedup
    category TEXT,                      -- "academic", "exam", "results", "general"
    published_at TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cached result data per USN
CREATE TABLE IF NOT EXISTS results_cache (
    usn TEXT NOT NULL,
    semester_label TEXT NOT NULL,       -- e.g. "Jan 2024"
    data_json TEXT NOT NULL,            -- Full result JSON from python-vtu-api
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usn, semester_label)
);

-- Cached Gemini responses (to avoid burning rate limit on repeat questions)
CREATE TABLE IF NOT EXISTS response_cache (
    query_hash TEXT PRIMARY KEY,        -- MD5 of normalized query string
    response TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bot event log (NEVER store message content — only events)
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,           -- "command", "registration", "circular_posted", "error"
    command TEXT,                       -- e.g. "result", "ask", "updates"
    group_id_hash TEXT,                 -- hashed group ID
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IA marks tracker
CREATE TABLE IF NOT EXISTS ia_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    subject TEXT NOT NULL,
    ia1 REAL,
    ia2 REAL,
    ia3 REAL,
    semester INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## ENVIRONMENT VARIABLES

.env file must contain:

```
GEMINI_API_KEY=your_key_here
DB_PATH=./vtu_bot.db
SCRAPE_INTERVAL_MINUTES=120
RESULT_POLL_INTERVAL_MINUTES=15
CACHE_TTL_HOURS=6
RESULT_CACHE_TTL_HOURS=24
BOT_MENTION_TRIGGER=@bot
```

Always load these with python-dotenv. Never hardcode keys.

---

## CORE LOGIC — IMPLEMENT EXACTLY AS DESCRIBED

### Message Handler (bot/handler.py)

Every message received by OpenClaw passes through this function:

```
function handle_message(message, group_id, sender_phone):
    1. Check if BOT_MENTION_TRIGGER (@bot) is in message — if not, return immediately, do nothing
    2. Extract the command part: everything after @bot, stripped and lowercased
    3. Log the event to event_log table (event_type="command", no message content)
    4. Route to correct command function based on first word:
       - "register" → commands.register(sender_phone, group_id)
       - "result" → commands.get_result(sender_phone, args)
       - "updates" → commands.get_updates(group_id)
       - "ask" → commands.ask_gemini(query, sender_phone)
       - "ia" → commands.ia_tracker(sender_phone, args)
       - "delete" → commands.delete_user(sender_phone)
       - "help" → commands.help()
       - anything else → "Command not recognised. Type @bot help to see all commands."
    5. Send returned string back to group as bot reply
```

### Gemini Queue (bot/queue.py)

Rate limit is 4 calls per minute on free tier. Implement a simple queue:

```
- Use Python queue.Queue() — thread-safe
- Single worker thread processes queue items one at a time
- Before making API call: check response_cache table with MD5 of normalized query
- If cached and created_at < CACHE_TTL_HOURS ago: return cached response (no API call)
- If not cached: make Gemini API call, save response to cache, return response
- If API call fails with rate limit error: wait 15 seconds, retry once
- If retry also fails: return "Too busy right now, please try again in 2 minutes"
- Track last API call timestamp — if less than 15 seconds ago, wait before calling
```

### VTU Scraper (scraper/vtu_scraper.py)

```
function scrape_circulars():
    1. Try to fetch vtu.ac.in/news and vtu.ac.in/academic-section
    2. If request fails or returns non-200: log error, return cached circulars from DB, do not crash
    3. Parse HTML with BeautifulSoup — extract: title, date, URL for each item
    4. For each item: compute MD5 hash of (title + date)
    5. Check if hash exists in circulars table — if yes, skip (already seen)
    6. If hash is new: save to circulars table, add to "new_circulars" list
    7. Return list of new circulars found (empty list if none)
    8. Caller broadcasts new circulars to all registered groups

CRITICAL: Wrap everything in try-except. A scraper crash must never crash the whole bot.
CRITICAL: Always save to DB before broadcasting. If broadcast fails, data is still saved.
```

### Result Fetcher (bot/commands.py)

```
function get_result(sender_phone, args):
    1. Determine USN: if args contains a USN pattern, use that. Otherwise look up registered USN for sender_phone_hash.
    2. If no USN found: return "Please register first with @bot register, or provide your USN: @bot result 1RV21CS045"
    3. Check results_cache table — if entry exists and fetched_at < 24 hours ago: return cached data
    4. If not cached: call python-vtu-api to fetch result
    5. If fetch fails (VTU site down): return "VTU results portal is currently down. Try again later."
    6. Save result JSON to results_cache
    7. Format result as readable WhatsApp message and return
```

### USN Validation

```
USN format: [4 digits][2 letter college code][2 digit year][2 letter branch][3 digit roll]
Example: 1RV21CS045

Regex: ^[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$

From USN extract:
- college_code = characters 1-3
- year_of_joining = 2000 + int(characters 4-5)
- branch = characters 6-7
- estimated_semester = (current_year - year_of_joining) * 2 + current_sem_offset
```

---

## ERROR HANDLING RULES — FOLLOW THESE EVERYWHERE

1. Every function that calls an external API (Gemini, VTU scraper, result fetch) must be wrapped in try-except
2. On exception: log the error with timestamp to a local errors.log file, return a user-friendly string
3. Never let an exception propagate up and crash the bot process
4. Database operations: always use context managers (with sqlite3.connect() as conn)
5. If DB file doesn't exist on startup: create it and run all CREATE TABLE statements
6. Every scraper function must work without internet and return cached data if network fails

Example pattern to follow everywhere:
```python
try:
    result = external_api_call()
    return format_result(result)
except RateLimitError:
    return "Too many requests right now. Please try again in 2 minutes."
except NetworkError:
    return "Could not reach VTU servers. Showing last cached data instead."
except Exception as e:
    log_error(e)
    return "Something went wrong. Please try again."
```

---

## WHATSAPP MESSAGE FORMATTING

WhatsApp supports basic formatting. Use these in all bot replies:

- *bold text* → wrap in single asterisks
- Use emojis sparingly for clarity: ✅ for success, ❌ for error, 📢 for announcements, 📋 for results
- Keep messages under 500 characters where possible
- For result data, format as a clean list
- Always end command responses with: "Type @bot help for all commands"

Example result message format:
```
📋 *Result — 1RV21CS045*
Name: Ravi Kumar
Semester: 5th Sem (Jan 2024)

DBMS: 78 (Pass) ✅
OS: 62 (Pass) ✅  
CN: 45 (Pass) ✅
Maths: 38 (Fail) ❌

Total: 74.2% | Status: *Result Withheld*
```

---

## SCHEDULER JOBS (scheduler/jobs.py)

Set up these APScheduler jobs on startup:

| Job | Function | Interval |
|---|---|---|
| Scrape circulars | scraper.vtu_scraper.scrape_and_broadcast | Every 2 hours |
| Poll result drops | scraper.result_monitor.check_for_new_results | Every 15 minutes |
| Clean expired cache | db.cache.clear_expired_entries | Once daily at 3am |

All jobs must be wrapped in try-except. A failing job must log the error and reschedule — never crash the scheduler.

---

## OPEN SOURCE LIBRARIES TO USE

Install all of these. Do not reinvent what already exists:

```
# requirements.txt
google-generativeai      # Gemini API
python-vtu-api           # VTU result scraping with CAPTCHA handling
beautifulsoup4           # HTML scraping
requests                 # HTTP requests
apscheduler              # Background job scheduling
python-dotenv            # Load .env variables
hashlib                  # Built-in, for MD5/SHA-256 hashing
sqlite3                  # Built-in, for database
```

---

## WHAT NOT TO BUILD

Do not build any of these — they are out of scope and will be added later:

- No web dashboard or frontend
- No REST API or Flask/FastAPI server
- No Docker container
- No teacher-side portal
- No multi-university support
- No payment or subscription system
- No analytics
- No WhatsApp Business API integration (prototype uses OpenClaw only)
