"""Read-only backend helpers for the Doser dashboard plugin."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any


def _state_db_path() -> Path:
    configured = (os.environ.get("CHIHIROS_STATE_DB") or "").strip()
    return Path(configured) if configured else Path("/config/.chihiros/chihiros_state.sqlite3")


def read_schedule(data: dict[str, Any]) -> dict[str, Any]:
    """Return one schedule selected by exact device MAC and one-based channel."""
    address = str(data.get("address") or "").strip().upper()
    normalized_address = re.sub(r"[^0-9A-F]", "", address)
    if len(normalized_address) != 12:
        raise ValueError("Ungueltige Doser-MAC-Adresse")

    channel = int(data.get("channel") or 0)
    if channel < 1 or channel > 4:
        raise ValueError("Doser-Kanal muss zwischen 1 und 4 liegen")

    database = _state_db_path()
    if not database.is_file():
        return {"found": False, "address": address, "channel": channel, "timer_entries": []}

    query = """
        SELECT schedule_kind, schedule_type_id, schedule_time, weekdays_mask,
               dose_ml, entries_json, enabled, valid_from_tomorrow
        FROM doser_schedules
        WHERE REPLACE(REPLACE(UPPER(device_key), ':', ''), '-', '') = ?
          AND channel = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query, (normalized_address, channel - 1)).fetchone()

    if row is None:
        return {"found": False, "address": address, "channel": channel, "timer_entries": []}

    entries: list[Any]
    try:
        entries = json.loads(str(row["entries_json"] or "[]"))
    except (json.JSONDecodeError, TypeError):
        entries = []
    timer_entries = [
        {
            "time": f"{int(entry.get('hour') or 0):02d}:{int(entry.get('minute') or 0):02d}",
            "ml": round(float(entry.get("ml") or 0.0), 1),
        }
        for entry in entries
        if isinstance(entry, dict) and str(row["schedule_kind"] or "") == "timer"
    ]
    window_entries = [
        {
            "start": f"{int(entry.get('start_hour') or 0):02d}:{int(entry.get('start_minute') or 0):02d}",
            "end": f"{int(entry.get('end_hour') or 0):02d}:{int(entry.get('end_minute') or 0):02d}",
            "doses": int(entry.get("value") or 1),
        }
        for entry in entries
        if isinstance(entry, dict) and str(row["schedule_kind"] or "") == "window"
    ]
    return {
        "found": True,
        "address": address,
        "channel": channel,
        "schedule_kind": str(row["schedule_kind"] or ""),
        "schedule_type_id": int(row["schedule_type_id"] or 0),
        "schedule_time": str(row["schedule_time"] or "00:00"),
        "weekdays_mask": int(row["weekdays_mask"] or 0),
        "dose_ml": round(float(row["dose_ml"] or 0.0), 1),
        "enabled": bool(int(row["enabled"] or 0)),
        "valid_from_tomorrow": bool(int(row["valid_from_tomorrow"] or 0)),
        "timer_entries": timer_entries,
        "window_entries": window_entries,
    }
