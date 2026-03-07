# PRODUCT DESIGN REQUIREMENTS (PDR)
## VTU WhatsApp Assistant Bot
### Feed this entire document to the AI before starting any code

---

## WHAT WE ARE BUILDING

A WhatsApp bot for VTU (Visvesvaraya Technological University) students in India.

The bot:
- Lives inside existing WhatsApp groups that students already use
- Only responds when tagged/mentioned with @bot — it stays silent otherwise
- Scrapes VTU's official website automatically and posts new circulars and updates to groups
- Lets students fetch their own exam results by typing their USN
- Answers VTU-related questions using Gemini AI
- Personalizes updates per student based on their registered USN, branch, and semester

The core problem we are solving: VTU students miss important updates because information is scattered across multiple websites, teachers aren't available 24/7, and there is no central real-time notification system. Students already live in WhatsApp groups — we bring the information to them there.

---

## WHO THE USERS ARE

- VTU undergraduate students, semester 1 to 8, all branches (CS, EC, ME, CV, IS, etc.)
- Affiliated colleges across Karnataka — VTU has 200+ colleges and ~500,000 students
- Class Representatives (CRs) who manage WhatsApp groups will be the first adopters
- Bot is added to existing class WhatsApp groups by the CR or admin

---

## FEATURES — WHAT THE BOT MUST DO

### MUST HAVE (build these first, nothing else matters until these work)

**1. Mention-triggered responses**
- Bot only activates when a message contains @bot
- All other group messages are completely ignored
- This is critical — bot must never spam the group

**2. USN Registration**
- Student sends @bot register
- Bot asks for their USN (example format: 1RV21CS045)
- Bot validates the USN format using regex
- Bot extracts and confirms: college code, year of joining, branch, semester estimate
- Stores phone number hash (not raw number), USN, branch, semester in SQLite
- Sends consent message before storing: "I will store your USN and branch to personalize updates. Reply AGREE to confirm or CANCEL to stop."
- User can delete all their data anytime with @bot delete

**3. Result Fetching**
- @bot result → fetches result for the student's registered USN
- @bot result 1RV21CS045 → fetches result for any specific USN
- Uses the open source library python-vtu-api (already handles CAPTCHA bypass)
- Returns: student name, subject-wise marks, grades, result status (pass/fail), total percentage
- Caches result in SQLite for 24 hours to avoid hammering VTU servers

**4. Auto Circular Updates**
- Scraper runs every 2 hours using APScheduler
- Scrapes vtu.ac.in for new circulars, notifications, and academic announcements
- Detects new content using content hash comparison against what's already stored
- Only broadcasts to groups when genuinely new content is found
- Message format: circular title + date + direct link
- All circulars saved to local SQLite — never depend on live VTU site being up

**5. Gemini AI Q&A**
- @bot ask [any VTU related question] → Gemini answers it
- Questions are queued — processed one at a time (rate limit: 4 calls per minute on free tier)
- Identical questions within 6 hours are answered from cache (no API call consumed)
- Context injected into every Gemini prompt: latest circulars, VTU scheme info
- If Gemini is rate limited, bot replies: "I'm getting too many questions right now, try again in 2 minutes"

**6. Manual Updates on Demand**
- @bot updates → returns the last 5 circulars from local database
- Works even when VTU website is down because data is cached locally

### SHOULD HAVE (build after the must-haves are stable)

**7. IA Marks Tracker**
- @bot ia [subject name] [marks] → logs internal assessment marks
- @bot ia summary → shows all logged subjects and minimum marks needed to pass finals
- Formula: minimum finals = (35 - IA_average * 0.4) / 0.6, rounded up

**8. Result Drop Alert**
- Separate background job polls results.vtu.ac.in every 15 minutes
- When new semester results go live, immediately alerts all registered groups
- Message: "VTU Results are LIVE! Type @bot result to check yours"

### NICE TO HAVE (only if everything else is solid)

**9. Timetable Parsing**
- When VTU releases exam timetable PDF, admin can send it to bot
- Bot uses Gemini Vision to OCR the scanned PDF
- Extracts subject names, dates, times
- Sends personalized exam schedule to each registered student based on their branch/sem

---

## BOT COMMANDS — COMPLETE LIST

| Command | What happens |
|---|---|
| @bot register | Starts USN registration flow |
| @bot result | Fetch your result using registered USN |
| @bot result [USN] | Fetch result for any USN |
| @bot updates | Get last 5 VTU circulars |
| @bot ask [question] | Ask Gemini any VTU question |
| @bot ia [subject] [marks] | Log IA marks |
| @bot ia summary | View IA tracker and pass thresholds |
| @bot delete | Delete all your data from the system |
| @bot help | Show all available commands |

---

## WHAT THE BOT MUST NEVER DO

- Never respond to messages that don't mention @bot
- Never store raw message content — only log @bot events
- Never store raw phone numbers — only store SHA-256 hash of phone number
- Never share one student's data with another student
- Never continue if user does not send AGREE to the consent message
- Never crash silently — all errors must be caught and return a friendly message

---

## PRIVACY REQUIREMENTS

This is a student project but must be treated seriously:
- Only data stored: USN, phone_number_hash, branch, semester, registered_at
- Consent is mandatory before any data is saved
- Users can delete all their data with one command
- SQLite database must be encrypted (use SQLCipher or at minimum AES encryption on the file)
- Never log the content of group messages — only log when @bot was mentioned and what command was used
- Must comply with India's Digital Personal Data Protection Act (DPDPA) 2023

---

## KNOWN CONSTRAINTS

- Gemini API: free tier = 4 calls per minute. Must use request queue + response cache
- WhatsApp interface: using OpenClaw (formerly MoltBot/Clawdbot) which uses Baileys protocol — unofficial API, ban risk exists, acceptable for prototype
- Server: running on a local laptop for prototype phase. Must handle being restarted without losing data
- VTU website: unreliable, goes down during peak times. Everything scraped must be cached locally
- PDF problem: most VTU timetables are scanned image PDFs, not text PDFs — need OCR

---

## SUCCESS CRITERIA FOR MVP

The MVP is successful when:
1. Bot is live in one real WhatsApp group with 30+ students
2. It auto-posts at least one new VTU circular without being asked
3. At least 10 students have registered their USN
4. At least 5 students have fetched their result using the bot
5. Bot has been running for 48 hours straight without crashing
