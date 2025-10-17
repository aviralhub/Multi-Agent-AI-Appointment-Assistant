import os
import json
import uuid
from typing import Dict, List, Optional, Callable, Tuple
from pathlib import Path
import pandas as pd
import tempfile
import shutil
from threading import RLock
from .logger import setup_logger

logger = setup_logger("storage")

DATA_DIR = Path(os.getcwd()) / "data"
JSON_PATH = DATA_DIR / "appointments.json"
XLSX_PATH = DATA_DIR / "appointments.xlsx"

_lock = RLock()


def _atomic_write_json(path: Path, data: List[Dict]) -> Tuple[bool, Optional[str]]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(str(tmp_path), str(path))
        # Validate by re-open
        with path.open("r", encoding="utf-8") as f:
            json.load(f)
        return True, None
    except Exception as e:
        logger.error(f"Atomic write failed: {e}")
        return False, str(e)
    finally:
        try:
            if "tmp_path" in locals() and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


class StorageService:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not JSON_PATH.exists():
            success, err = _atomic_write_json(JSON_PATH, [])
            if not success:
                raise RuntimeError(f"Failed initializing storage: {err}")

    def _load_json(self) -> List[Dict]:
        with _lock:
            try:
                with JSON_PATH.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except FileNotFoundError:
                return []

    def _save_json(self, items: List[Dict]) -> bool:
        with _lock:
            ok, err = _atomic_write_json(JSON_PATH, items)
            if not ok:
                logger.error(f"Failed to save JSON: {err}")
                return False
            try:
                df = pd.DataFrame(items)
                df.to_excel(str(XLSX_PATH), index=False)
            except Exception as e:
                logger.warning(f"Failed to write Excel: {e}")
            return True

    # CRUD operations
    def list_appointments(self, user_id: Optional[str] = None) -> List[Dict]:
        items = self._load_json()
        if user_id:
            items = [it for it in items if it.get("UserID") == user_id]
        return items

    def add_appointment(self, appt: Dict) -> bool:
        items = self._load_json()
        items.append(appt)
        ok = self._save_json(items)
        if ok:
            logger.info(f"wrote appointment id={appt.get('Id')} to {JSON_PATH}")
        return ok

    def update_latest_for_user(self, user_id: str, updater: Callable[[Dict], Dict]) -> Optional[Dict]:
        items = self._load_json()
        idx = None
        for i in range(len(items) - 1, -1, -1):
            if items[i].get("UserID") == user_id:
                idx = i
                break
        if idx is None:
            return None
        updated = updater(dict(items[idx]))
        items[idx] = updated
        ok = self._save_json(items)
        if ok:
            logger.info(f"updated appointment id={updated.get('Id')} for user={user_id}")
        return updated if ok else None

    def delete_latest_for_user(self, user_id: str) -> bool:
        items = self._load_json()
        idx = None
        for i in range(len(items) - 1, -1, -1):
            if items[i].get("UserID") == user_id:
                idx = i
                break
        if idx is None:
            return False
        deleted = items[idx]
        ok = self._save_json(items[:idx] + items[idx + 1 :])
        if ok:
            logger.info(f"deleted appointment id={deleted.get('Id')} for user={user_id}")
        return ok

    # Conflict detection
    def find_conflicts(self, date: str, time: str, user_id: str) -> List[Dict]:
        items = self._load_json()
        return [
            it for it in items if it.get("Date") == date and it.get("Time") == time and it.get("UserID") == user_id
        ]

    def has_time_slot_taken(self, date: str, time: str) -> bool:
        items = self._load_json()
        return any(it.get("Date") == date and it.get("Time") == time for it in items)

    def save_appointment(
        self,
        date: str,
        day: Optional[str],
        time: str,
        mode: str,
        notes: str,
        user_id: str,
    ) -> Dict:
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


# Optional SQLite-backed storage. When USE_SQLITE env var is set to a truthy value,
# create an alias `StorageService` that wraps the SQLite implementation so existing
# code continues to work without changes.
try:
    if os.getenv("USE_SQLITE", "0") in {"1", "true", "True"}:
        from .sqlite_storage import SQLiteStorageService  # type: ignore

        class StorageService(SQLiteStorageService):
            """Drop-in subclass to preserve the name `StorageService` used across the project."""

            pass
except Exception:
    # If sqlite module or file missing, keep the JSON-based StorageService above.
    pass
