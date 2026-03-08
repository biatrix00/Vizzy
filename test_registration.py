"""
test_registration.py — Manually exercises the database and USN registration logic
without needing Telegram running. Run with: python test_registration.py

Tests:
  1. init_db() creates all tables
  2. USN validation regex
  3. USN parsing (extracts college_code, branch, semester)
  4. Full registration flow: pending_consent → AGREE → users table
  5. Duplicate USN rejection
  6. User deletion
"""

import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
os.environ["DB_PATH"] = "./test_run.db"   # Use a throwaway test database

from db.database import init_db, get_connection
from db import users as db_users
from bot.commands import _validate_usn, _parse_usn, _hash_user_id

PASS = "[PASS]"
FAIL = "[FAIL]"

def check(label, condition):
    print(f"  {PASS if condition else FAIL}  {label}")
    if not condition:
        raise AssertionError(f"FAILED: {label}")

print("\n=== Vizzy Local Test Suite ===\n")

# ── 1. Database init ────────────────────────────────────────────────
print("1. Database initialisation")
init_db()
with get_connection() as conn:
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

for t in ["users", "circulars", "results_cache", "response_cache",
          "event_log", "ia_marks", "pending_consent"]:
    check(f"Table '{t}' exists", t in tables)

# ── 2. USN validation ───────────────────────────────────────────────
print("\n2. USN validation regex")
check("1RV21CS045 -> valid",   _validate_usn("1RV21CS045"))
check("4JC22EC101 -> valid",   _validate_usn("4JC22EC101"))
check("1RV21CS04  -> invalid (short)",  not _validate_usn("1RV21CS04"))
check("RV21CS045  -> invalid (no leading digit)", not _validate_usn("RV21CS045"))
check("1rv21cs045 -> valid (case insensitive)", _validate_usn("1rv21cs045"))
check("ABCDEFGHIJ -> invalid", not _validate_usn("ABCDEFGHIJ"))

# ── 3. USN parsing  ─────────────────────────────────────────────────
print("\n3. USN field extraction")
p = _parse_usn("1RV21CS045")


check(f"college_code = '1RV' (got '{p['college_code']}')",   p["college_code"] == "1RV")
check(f"branch       = 'CS'  (got '{p['branch']}')",          p["branch"] == "CS")
check(f"year_of_join = 2021  (got {p['year_of_joining']})",   p["year_of_joining"] == 2021)
check(f"semester     >= 1    (got {p['estimated_semester']})", p["estimated_semester"] >= 1)
check(f"semester     <= 8    (got {p['estimated_semester']})", p["estimated_semester"] <= 8)

# ── 4. Full registration flow ───────────────────────────────────────
print("\n4. Registration flow (pending -> AGREE -> users table)")

FAKE_TG_ID   = 123456789
phone_hash   = _hash_user_id(FAKE_TG_ID)
usn          = "1RV21CS045"
parsed       = _parse_usn(usn)

# Step 1: save to pending_consent (no data yet in users)
db_users.save_pending_consent(phone_hash, usn, parsed["branch"],
                              parsed["estimated_semester"], parsed["college_code"])
pending = db_users.get_pending_consent(phone_hash)
check("Pending consent record saved",        pending is not None)
check("Pending USN matches",                 pending["usn"] == usn)
check("Users table still empty at this point",
      db_users.get_user_by_phone_hash(phone_hash) is None)

# Step 2: user replies AGREE → move to users table
db_users.create_user(phone_hash, usn, parsed["branch"],
                     parsed["estimated_semester"], parsed["college_code"])
db_users.set_consent(phone_hash, agreed=True)
db_users.delete_pending_consent(phone_hash)

user = db_users.get_user_by_phone_hash(phone_hash)
check("User row created",                    user is not None)
check("consent_given = 1",                   user["consent_given"] == 1)
check("USN stored correctly",                user["usn"] == usn)
check("Branch stored correctly",             user["branch"] == "CS")
check("Pending record cleaned up",
      db_users.get_pending_consent(phone_hash) is None)

# ── 5. Duplicate USN rejection ──────────────────────────────────────
print("\n5. Duplicate USN rejection")
try:
    db_users.create_user("different_hash", usn, "CS", 5, "1RV")
    check("Duplicate USN should raise IntegrityError", False)
except Exception as e:
    check(f"IntegrityError raised for duplicate USN ({type(e).__name__})", True)

# ── 6. User deletion ────────────────────────────────────────────────
print("\n6. User deletion (/delete command)")
db_users.delete_user(phone_hash)
check("User row deleted",
      db_users.get_user_by_phone_hash(phone_hash) is None)
check("USN lookup also gone",
      db_users.get_user_by_usn(usn) is None)

# test_run.db is left behind — delete it manually if needed.
print("\n=== All tests passed! [ALL PASS] ===\n")
