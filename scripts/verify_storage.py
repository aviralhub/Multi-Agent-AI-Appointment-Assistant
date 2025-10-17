"""Small non-destructive verification for StorageService

This script runs basic CRUD and conflict checks against the project's
StorageService in two modes:
 1. Default (JSON storage)
 2. SQLite storage (using a temporary DB file via SQLITE_DB_PATH)

It attempts to avoid touching or deleting existing data by using a unique
user id for tests and a temporary sqlite path.

Run from project root (in your activated venv):
  python scripts\verify_storage.py

No changes to project files are made except adding a test appointment for a
unique user id which is then removed at the end of each test step.
"""

import os
import importlib
import uuid
import tempfile
import pprint

from datetime import datetime

pp = pprint.PrettyPrinter(indent=2)


def run_smoke(storage_cls, label: str):
    print(f"\n--- Running storage smoke tests: {label} ---")
    storage = storage_cls()
    user_id = f"test-{uuid.uuid4()}"
    date = datetime.now().strftime("%Y-%m-%d")
    time = "15:00"

    print("Saving appointment...")
    appt = storage.save_appointment(date=date, day=None, time=time, mode="virtual", notes="verify", user_id=user_id)
    pp.pprint(appt)

    print("Listing appointments for user...")
    items = storage.list_appointments(user_id=user_id)
    pp.pprint(items)

    if not items:
        raise RuntimeError("Saved appointment not listed")

    print("Checking has_time_slot_taken (global check)...")
    taken = storage.has_time_slot_taken(date, time)
    print("has_time_slot_taken:", taken)

    print("Finding conflicts for this user...")
    conflicts = storage.find_conflicts(date, time, user_id)
    pp.pprint(conflicts)

    print("Updating latest for user (add note)...")

    def updater(it):
        it["Notes"] = "updated-note"
        return it

    updated = storage.update_latest_for_user(user_id, updater)
    pp.pprint(updated)

    print("Deleting latest for user...")
    ok = storage.delete_latest_for_user(user_id)
    print("deleted:", ok)

    print("Confirm deletion (should be empty list):")
    items_after = storage.list_appointments(user_id=user_id)
    pp.pprint(items_after)

    print(f"--- Finished tests for {label} ---\n")


def main():
    # Ensure we import a fresh module based on env var state
    # 1) Test JSON/default storage
    if "USE_SQLITE" in os.environ:
        del os.environ["USE_SQLITE"]
    import services.storage as storage_mod
    importlib.reload(storage_mod)
    Storage = storage_mod.StorageService
    run_smoke(Storage, "JSON (default)")

    # 2) Test SQLite storage using a temp DB path
    tmp_db = tempfile.NamedTemporaryFile(prefix="appt-test-", suffix=".db", delete=False)
    tmp_db.close()
    os.environ["USE_SQLITE"] = "1"
    os.environ["SQLITE_DB_PATH"] = tmp_db.name
    importlib.reload(storage_mod)
    StorageSqlite = storage_mod.StorageService
    try:
        run_smoke(StorageSqlite, f"SQLite (temp) {tmp_db.name}")
    finally:
        # Do not delete the DB automatically so you can inspect it if wanted
        print("SQLite DB path (left for inspection):", tmp_db.name)


if __name__ == "__main__":
    main()
