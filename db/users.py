"""
db/users.py — CRUD operations for the users table.

All operations on the users table are centralised here.

Functions to implement (stubs only):
- create_user(phone_hash, usn, branch, semester, college_code) -> int
    Inserts a new user row with consent_given=0. Returns new user ID.
- get_user_by_phone_hash(phone_hash) -> dict | None
    Returns the user row as a dict, or None if not found.
- get_user_by_usn(usn) -> dict | None
    Returns the user row as a dict, or None if not found.
- set_consent(phone_hash, agreed: bool) -> None
    Sets consent_given=1 (agreed) or 0 (denied/pending).
- delete_user(phone_hash) -> None
    Deletes the user row and all associated ia_marks rows.
    This is the @bot delete command implementation — complete data removal.
- update_semester(phone_hash, semester) -> None
    Updates the estimated semester for a registered user.

Privacy note: raw phone numbers are NEVER stored. Only SHA-256 hashes.

No logic implemented yet — this is a stub.
"""
