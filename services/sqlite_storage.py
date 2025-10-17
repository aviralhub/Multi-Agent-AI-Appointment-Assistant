import os
import uuid
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path(os.getcwd()) / "data"


class SQLiteStorageService:
    """Minimal SQLite-backed storage with a compatible API to the JSON StorageService.

    This implementation is intentionally small and synchronous. It uses a table
    `appointments` with columns matching keys used elsewhere in the project.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_path = db_path or os.getenv("SQLITE_DB_PATH") or str(DATA_DIR / "appointments.db")
        self.db_path = Path(db_path)
        self._lock = RLock()
        # Use check_same_thread=False since we protect with a lock
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS appointments (
                    Id TEXT PRIMARY KEY,
                    Date TEXT,
                    Day TEXT,
                    Time TEXT,
                    Mode TEXT,
                    Notes TEXT,
                    UserID TEXT
                )
                """
            )

    def list_appointments(self, user_id: Optional[str] = None) -> List[Dict]:
        with self._lock:
            cur = self.conn.cursor()
            if user_id:
                cur.execute("SELECT * FROM appointments WHERE UserID = ?", (user_id,))
            else:
                cur.execute("SELECT * FROM appointments")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def add_appointment(self, appt: Dict) -> bool:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO appointments(Id, Date, Day, Time, Mode, Notes, UserID) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    appt.get("Id"),
                    appt.get("Date"),
                    appt.get("Day"),
                    appt.get("Time"),
                    appt.get("Mode"),
                    appt.get("Notes"),
                    appt.get("UserID"),
                ),
            )
            return True

    def _get_latest_for_user(self, user_id: str) -> Optional[Dict]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM appointments WHERE UserID = ? ORDER BY rowid DESC LIMIT 1", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_latest_for_user(self, user_id: str, updater) -> Optional[Dict]:
        latest = self._get_latest_for_user(user_id)
        if not latest:
            return None
        updated = updater(dict(latest))
        with self._lock, self.conn:
            self.conn.execute(
                "UPDATE appointments SET Date=?, Day=?, Time=?, Mode=?, Notes=?, UserID=? WHERE Id=?",
                (
                    updated.get("Date"),
                    updated.get("Day"),
                    updated.get("Time"),
                    updated.get("Mode"),
                    updated.get("Notes"),
                    updated.get("UserID"),
                    updated.get("Id"),
                ),
            )
        return updated

    def delete_latest_for_user(self, user_id: str) -> bool:
        latest = self._get_latest_for_user(user_id)
        if not latest:
            return False
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM appointments WHERE Id = ?", (latest.get("Id"),))
        return True

    def find_conflicts(self, date: str, time: str, user_id: str) -> List[Dict]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT * FROM appointments WHERE Date = ? AND Time = ? AND UserID = ?",
                (date, time, user_id),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def has_time_slot_taken(self, date: str, time: str) -> bool:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM appointments WHERE Date = ? AND Time = ? LIMIT 1", (date, time))
            return cur.fetchone() is not None

    def save_appointment(self, date: str, day: Optional[str], time: str, mode: str, notes: str, user_id: str) -> Dict:
        appt = {
            "Id": str(uuid.uuid4()),
            "Date": date,
            "Day": day,
            "Time": time,
            "Mode": mode,
            "Notes": notes,
            "UserID": user_id,
        }
        ok = self.add_appointment(appt)
        if not ok:
            raise RuntimeError("Failed to persist appointment")
        return appt
