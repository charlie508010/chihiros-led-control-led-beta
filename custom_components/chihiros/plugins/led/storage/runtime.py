"""Storage helpers for LED schedules."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from ....core.storage import state_db_path
from ..const import (
    ATTR_ACTIVE,
    ATTR_BRIGHTNESS,
    ATTR_END,
    ATTR_LEVELS,
    ATTR_RAMP_UP_MINUTES,
    ATTR_START,
    ATTR_WEEKDAYS,
)
from ..models import ChihirosData
from ..vendor.chihiros_led_control.weekday_encoding import WeekdaySelect
from .history import record_led_schedule_verification

_LOGGER = logging.getLogger(__name__)

LedScheduleSetting = tuple[datetime, datetime, dict[str, int], int, list[WeekdaySelect]]


def _schedule_signature(
    start: str,
    end: str,
    levels: dict[str, Any],
    ramp: int,
    weekdays: list[Any],
) -> str:
    """Return a stable identity for one complete schedule row."""
    payload = {
        "start": start,
        "end": end,
        "levels": {str(key): int(value) for key, value in sorted(levels.items())},
        "ramp": int(ramp),
        "weekdays": sorted(str(value) for value in weekdays),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_led_schedule_rows(chihiros_data: ChihirosData, periods: list[dict[str, Any]], *, sent: bool) -> None:
    """Persist LED schedule rows and whether they were sent to the device."""
    path = state_db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now().isoformat()
        device_key = str(chihiros_data.device.address or chihiros_data.title)
        with sqlite3.connect(path) as conn:
            ensure_led_schedule_table(conn)
            previous = {
                str(row[0]): (str(row[1]), str(row[2]))
                for row in conn.execute(
                    "SELECT schedule_signature, verification_status, verified_at FROM led_schedules WHERE device_key=?",
                    (device_key,),
                ).fetchall()
            }
            conn.execute("DELETE FROM led_schedules WHERE device_key=?", (device_key,))
            for index, period in enumerate(periods):
                levels = period.get(ATTR_LEVELS, period.get(ATTR_BRIGHTNESS, {}))
                stored_ramp_up_minutes = max(1, int(period.get(ATTR_RAMP_UP_MINUTES, 1)))
                weekdays = period.get(ATTR_WEEKDAYS) or ["everyday"]
                signature = _schedule_signature(
                    str(period.get(ATTR_START, "")),
                    str(period.get(ATTR_END, "")),
                    levels,
                    stored_ramp_up_minutes,
                    weekdays,
                )
                verification_status, verified_at = ("pending", "") if sent else previous.get(signature, ("pending", ""))
                conn.execute(
                    """
                    INSERT INTO led_schedules(
                        device_key, schedule_index, start_time, end_time, levels_json,
                        ramp_up_minutes, weekdays_json, active, sent, source, updated_at,
                        schedule_signature, verification_status, verified_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_key,
                        index,
                        str(period.get(ATTR_START, "")),
                        str(period.get(ATTR_END, "")),
                        json.dumps(levels, ensure_ascii=False),
                        stored_ramp_up_minutes,
                        json.dumps(weekdays, ensure_ascii=False),
                        1 if bool(period.get(ATTR_ACTIVE, True)) else 0,
                        1 if sent else 0,
                        "homeassistant",
                        now,
                        signature,
                        verification_status,
                        verified_at,
                    ),
                )
    except (OSError, sqlite3.Error) as ex:
        raise HomeAssistantError(f"LED schedule DB write failed: {ex}") from ex


def ensure_led_schedule_table(conn: sqlite3.Connection) -> None:
    """Create or migrate the LED schedule table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS led_schedules (
            device_key TEXT NOT NULL,
            schedule_index INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            levels_json TEXT NOT NULL DEFAULT '{}',
            ramp_up_minutes INTEGER NOT NULL DEFAULT 1,
            weekdays_json TEXT NOT NULL DEFAULT '[]',
            active INTEGER NOT NULL DEFAULT 1,
            sent INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'homeassistant',
            updated_at TEXT NOT NULL,
            schedule_signature TEXT NOT NULL DEFAULT '',
            verification_status TEXT NOT NULL DEFAULT 'pending',
            verified_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (device_key, schedule_index)
        )
        """
    )
    columns = {str(row[1]).lower(): row for row in conn.execute("PRAGMA table_info(led_schedules)").fetchall()}
    if "weekdays_json" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN weekdays_json TEXT NOT NULL DEFAULT '[]'")
    if "active" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "sent" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN sent INTEGER NOT NULL DEFAULT 0")
    if "source" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN source TEXT NOT NULL DEFAULT 'homeassistant'")
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    if "schedule_signature" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN schedule_signature TEXT NOT NULL DEFAULT ''")
    if "verification_status" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending'")
    if "verified_at" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN verified_at TEXT NOT NULL DEFAULT ''")
    job_columns = {
        str(row[1]).lower(): row for row in conn.execute("PRAGMA table_info(led_schedule_verification_jobs)").fetchall()
    }
    legacy_jobs: list[tuple[Any, ...]] = []
    if job_columns and "schedule_signature" not in job_columns:
        legacy_jobs = conn.execute(
            "SELECT device_key, target_json, restore_json, due_at, created_at FROM led_schedule_verification_jobs"
        ).fetchall()
        conn.execute("DROP TABLE led_schedule_verification_jobs")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS led_schedule_verification_jobs (
            device_key TEXT NOT NULL,
            schedule_signature TEXT NOT NULL,
            target_json TEXT NOT NULL,
            restore_json TEXT NOT NULL DEFAULT '[]',
            due_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (device_key, schedule_signature)
        )
        """
    )
    for device_key, target_json, restore_json, due_at, created_at in legacy_jobs:
        target = json.loads(str(target_json))
        signature = _schedule_signature(
            str(target["start"]), str(target["end"]), target["levels"], int(target["ramp"]), target["weekdays"]
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO led_schedule_verification_jobs(
                device_key, schedule_signature, target_json, restore_json, due_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (device_key, signature, target_json, restore_json, due_at, created_at),
        )


def initialize_led_schedule_storage() -> None:
    """Create and migrate LED schedule storage before the first service call."""
    path = state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        ensure_led_schedule_table(conn)


def load_led_schedule_rows(device_key: str) -> list[dict[str, Any]]:
    """Load complete active schedule rows for delayed verification and restore."""
    path = state_db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        ensure_led_schedule_table(conn)
        rows = conn.execute(
            """
            SELECT start_time, end_time, levels_json, ramp_up_minutes, weekdays_json
            FROM led_schedules WHERE UPPER(device_key)=UPPER(?) AND active=1 ORDER BY schedule_index
            """,
            (device_key,),
        ).fetchall()
    return [
        {
            "start": str(start),
            "end": str(end),
            "levels": json.loads(str(levels_json)),
            "ramp": max(1, int(ramp)),
            "weekdays": json.loads(str(weekdays_json)) or ["everyday"],
        }
        for start, end, levels_json, ramp, weekdays_json in rows
    ]


def save_led_schedule_verification_job(device_key: str, target: dict[str, Any], restore: list[dict[str, Any]]) -> None:
    """Persist a delayed schedule verification job and mark its target pending."""
    path = state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    signature = _schedule_signature(
        str(target["start"]), str(target["end"]), target["levels"], int(target["ramp"]), target["weekdays"]
    )
    with sqlite3.connect(path) as conn:
        ensure_led_schedule_table(conn)
        # Re-sending an edited row keeps its time slot but changes its full
        # signature. Remove the superseded job before inserting the new one.
        for old_signature, old_target_json in conn.execute(
            """
            SELECT schedule_signature, target_json FROM led_schedule_verification_jobs
            WHERE UPPER(device_key)=UPPER(?)
            """,
            (device_key,),
        ).fetchall():
            old_target = json.loads(str(old_target_json))
            if old_target.get("start") == target["start"] and old_target.get("end") == target["end"]:
                conn.execute(
                    """
                    DELETE FROM led_schedule_verification_jobs
                    WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?
                    """,
                    (device_key, old_signature),
                )
        conn.execute(
            """
            INSERT INTO led_schedule_verification_jobs(
                device_key, schedule_signature, target_json, restore_json, due_at, created_at
            )
            VALUES (?, ?, ?, ?, datetime(?, '+60 seconds'), ?)
            ON CONFLICT(device_key, schedule_signature) DO UPDATE SET target_json=excluded.target_json,
                restore_json=excluded.restore_json, due_at=excluded.due_at, created_at=excluded.created_at
            """,
            (
                device_key,
                signature,
                json.dumps(target, ensure_ascii=False),
                json.dumps(restore, ensure_ascii=False),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        conn.execute(
            """
            UPDATE led_schedules SET verification_status='pending', verified_at=''
            WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?
            """,
            (device_key, signature),
        )


def finish_led_schedule_verification(device_key: str, target: dict[str, Any], status: str) -> None:
    """Persist one final verification result and remove its temporary job."""
    signature = _schedule_signature(
        str(target["start"]), str(target["end"]), target["levels"], int(target["ramp"]), target["weekdays"]
    )
    with sqlite3.connect(state_db_path()) as conn:
        ensure_led_schedule_table(conn)
        conn.execute(
            """
            UPDATE led_schedules SET verification_status=?, verified_at=?
            WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?
            """,
            (status, datetime.now(timezone.utc).isoformat(), device_key, signature),
        )
        conn.execute(
            """
            DELETE FROM led_schedule_verification_jobs
            WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?
            """,
            (device_key, signature),
        )
    record_led_schedule_verification(device_key, target, status)


def reset_led_schedule_verifications(device_key: str, targets: list[dict[str, Any]]) -> None:
    """Mark schedule rows as pending without scheduling a device check."""
    if not targets:
        return
    with sqlite3.connect(state_db_path()) as conn:
        ensure_led_schedule_table(conn)
        for target in targets:
            signature = _schedule_signature(
                str(target["start"]), str(target["end"]), target["levels"], int(target["ramp"]), target["weekdays"]
            )
            conn.execute(
                """
                UPDATE led_schedules SET verification_status='pending', verified_at=''
                WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?
                """,
                (device_key, signature),
            )


def delete_led_schedule_rows(chihiros_data: ChihirosData) -> int:
    """Delete persisted LED schedule rows for one device."""
    path = state_db_path()
    try:
        device_key = str(chihiros_data.device.address or chihiros_data.title)
        with sqlite3.connect(path) as conn:
            cur = conn.execute("DELETE FROM led_schedules WHERE device_key=?", (device_key,))
            return int(cur.rowcount or 0)
    except (OSError, sqlite3.Error):
        _LOGGER.debug("Failed to delete persisted LED schedule rows", exc_info=True)
        return 0


def load_active_led_schedule_settings(device_key: str) -> list[LedScheduleSetting]:
    """Load active schedules for restoring automatic mode on one device."""
    path = state_db_path()
    if not path.exists():
        return []
    try:
        with sqlite3.connect(path) as conn:
            ensure_led_schedule_table(conn)
            rows = conn.execute(
                """
                SELECT start_time, end_time, levels_json, ramp_up_minutes, weekdays_json
                FROM led_schedules
                WHERE device_key=? AND active=1
                ORDER BY schedule_index
                """,
                (device_key,),
            ).fetchall()
        settings: list[LedScheduleSetting] = []
        for start_value, end_value, levels_json, ramp_value, weekdays_json in rows:
            start = datetime.combine(date.today(), datetime.strptime(str(start_value), "%H:%M").time())
            end = datetime.combine(date.today(), datetime.strptime(str(end_value), "%H:%M").time())
            levels = {str(key): int(value) for key, value in json.loads(str(levels_json)).items()}
            weekdays = [WeekdaySelect(value) for value in json.loads(str(weekdays_json)) or ["everyday"]]
            ramp = max(1, int(ramp_value))
            settings.append((start, end, levels, ramp, weekdays))
        return settings
    except (OSError, sqlite3.Error, TypeError, ValueError):
        _LOGGER.warning("Failed to load persisted LED schedule rows for %s", device_key, exc_info=True)
        return []
