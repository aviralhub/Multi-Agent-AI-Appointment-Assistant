from __future__ import annotations
from typing import Any, Dict, Callable, Optional
import re
import json
import datetime as _dt
import dateparser

LocalTask = Callable[[Dict[str, Any]], Dict[str, Any]]


def task_intent(payload: Dict[str, Any]) -> Dict[str, Any]:
    labels = payload.get("labels", [])
    text = (payload.get("text") or "").lower()
    mapping = {
        "book": ["book", "schedule", "reserve", "set up"],
        "cancel": ["cancel", "drop"],
        "reschedule": ["reschedule", "move", "change", "shift"],
        "query": ["available", "availability", "when", "slots", "time?"],
    }
    for label, keys in mapping.items():
        if any(k in text for k in keys) and label in labels:
            return {"intent": label}
    if "other" in labels:
        return {"intent": "other"}
    return {"intent": labels[0] if labels else "other"}


def _parse_time_from_range(text: str) -> Optional[_dt.time]:
    # Prefer the destination time if pattern "from X to Y" exists
    m = re.search(r"from\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\s+to\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)",
                  text, flags=re.IGNORECASE)
    if not m:
        return None
    dest = m.group(2)
    # normalize like '5am' -> '5 am'
    dest = re.sub(r"(\d)(am|pm)\b", r"\1 \2", dest, flags=re.IGNORECASE)
    t = dateparser.parse(dest)
    return t.time() if t else None


def _extract_explicit_time(text: str) -> Optional[_dt.time]:
    # Normalize '5am' -> '5 am', '5:30pm' -> '5:30 pm'
    norm = re.sub(r"(\d)(am|pm)\b", r"\1 \2", text, flags=re.IGNORECASE)
    # Accept formats like '5 am', '05:00', '5:30 pm'
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", norm, flags=re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = m.group(3).lower() if m.group(3) else None
    if ampm == "am":
        if hour == 12:
            hour = 0
    elif ampm == "pm":
        if hour != 12:
            hour += 12
    if 0 <= hour < 24 and 0 <= minute < 60:
        return _dt.time(hour=hour, minute=minute)
    return None


def task_datetime(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = (payload.get("text") or "").strip()
    # Clean noisy characters but keep digits, letters, spaces, colon
    lt = re.sub(r"[^a-z0-9:\s]", " ", raw.lower())
    lt = re.sub(r"\s+", " ", lt).strip()

    dest_time = _parse_time_from_range(lt)

    now = _dt.datetime.now()
    base_date: Optional[_dt.date] = None
    if "today" in lt:
        base_date = now.date()
    elif "tomorrow" in lt:
        base_date = (now + _dt.timedelta(days=1)).date()

    # Try explicit time first (more reliable with noisy text)
    explicit_time = dest_time or _extract_explicit_time(lt)

    # Determine date
    chosen_date: Optional[_dt.date] = base_date
    if chosen_date is None:
        # Try detect a date with preference to future
        dt_try = dateparser.parse(lt, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False})
        if dt_try:
            chosen_date = dt_try.date()
        else:
            chosen_date = now.date()

    if explicit_time is None:
        # Try parse any time token separately
        t_try = dateparser.parse(lt)
        if t_try:
            explicit_time = t_try.time()

    if explicit_time is None:
        # Last resort: keep user's hour if present like '5 am' in noisy text; otherwise default 09:00
        explicit_time = _dt.time(hour=9, minute=0)

    dt = _dt.datetime.combine(chosen_date, explicit_time)
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "day": dt.strftime("%A"),
        "time": dt.strftime("%H:%M"),
    }


def task_mode(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = (payload.get("text") or "").lower()
    if any(k in text for k in ["virtual", "video", "online"]):
        return {"mode": "virtual"}
    if any(k in text for k in ["tele", "phone", "call", "telephonic"]):
        return {"mode": "telephonic"}
    return {"mode": "virtual"}


def task_confirmation(payload: Dict[str, Any]) -> Dict[str, Any]:
    date = payload.get("date")
    day = payload.get("day")
    time = payload.get("time")
    mode = payload.get("mode")
    return {"text": f"Your {mode} appointment is booked for {day}, {date} at {time}."}


REGISTRY: Dict[str, LocalTask] = {
    "intent.classify_intent": task_intent,
    "datetime.extract_datetime": task_datetime,
    "mode.infer_mode": task_mode,
    "confirmation.generate_confirmation": task_confirmation,
}


def run_local(agent: str, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    fn = REGISTRY.get(f"{agent}.{task}")
    if not fn:
        return {}
    return fn(payload)
