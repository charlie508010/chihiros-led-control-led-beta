"""Persist LED notification and schedule-verification history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ....core.storage import state_db_path


def record_led_notification_poll(
    device_address: str,
    device_alias: str,
    status: str,
    output: str,
    notifications: int = 0,
) -> None:
    """Persist one active LED notification poll in the shared add-on history."""
    database = state_db_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              device_alias TEXT DEFAULT '',
              device_address TEXT DEFAULT '',
              action TEXT NOT NULL,
              channel INTEGER,
              params_json TEXT DEFAULT '{}',
              status TEXT DEFAULT '',
              output TEXT DEFAULT ''
            )
            """
        )
        params: dict[str, Any] = {
            "scope": "led",
            "source": "notification_poll",
            "notifications": max(0, int(notifications)),
        }
        connection.execute(
            """
            INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                str(device_alias or device_address),
                str(device_address),
                "LED notification fetch",
                json.dumps(params, ensure_ascii=False),
                str(status),
                str(output),
            ),
        )


def record_led_schedule_verification(
    device_address: str,
    target: dict[str, Any],
    status: str,
) -> None:
    """Persist the final result of one delayed LED schedule verification."""
    database = state_db_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    normalized_status = "ok" if status == "verified" else "fail"
    start = str(target.get("start") or "")
    end = str(target.get("end") or "")
    with sqlite3.connect(database, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              device_alias TEXT DEFAULT '',
              device_address TEXT DEFAULT '',
              action TEXT NOT NULL,
              channel INTEGER,
              params_json TEXT DEFAULT '{}',
              status TEXT DEFAULT '',
              output TEXT DEFAULT ''
            )
            """
        )
        params = {
            "scope": "led",
            "source": "schedule_verification",
            "verification_status": status,
            "start": start,
            "end": end,
        }
        connection.execute(
            """
            INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                str(device_address),
                str(device_address),
                "LED schedule verification",
                json.dumps(params, ensure_ascii=False),
                normalized_status,
                f"{start}-{end}: {status}",
            ),
        )
