"""Local Chihiros CTL storage.

This module stores CLI-only configuration such as device aliases and LED
templates. It intentionally has no Home Assistant dependency.
"""

from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEVICE_KINDS = ("led", "doser", "ruehrer", "heizer")

DEFAULT_STANDARD_TEMPLATES: dict[str, list[int]] = {
    "ALL": [100, 100, 100, 100],
    "Bukeland": [100, 85, 100, 78],
    "freshwater": [80, 100, 100, 100],
    "nature": [100, 80, 100, 90],
    "radiant": [100, 85, 100, 78],
    "RGB": [100, 100, 100, 0],
}


def state_db_path() -> Path:
    """Return the local CTL/state database path."""
    configured = (os.environ.get("CHIHIROS_STATE_DB") or "").strip()
    if configured:
        return Path(configured)
    if Path("/config").exists():
        return Path("/config/.chihiros/chihiros_state.sqlite3")
    return Path.home() / ".chihiros" / "chihiros_state.sqlite3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now().date().isoformat()


def _db_connect() -> sqlite3.Connection:
    path = state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_state_db() -> None:
    """Create local Doser state tables."""
    with _db_connect() as conn:
        conn.executescript(
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
            );

            CREATE TABLE IF NOT EXISTS containers (
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                volume_ml REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, channel)
            );

            CREATE TABLE IF NOT EXISTS manual_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                ml REAL NOT NULL,
                ts TEXT NOT NULL,
                day TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS manual_daily (
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                day TEXT NOT NULL,
                ml REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (device_key, channel, day)
            );

            CREATE TABLE IF NOT EXISTS doser_schedules (
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                schedule_kind TEXT NOT NULL DEFAULT 'single_dose',
                schedule_type_id INTEGER NOT NULL DEFAULT 1,
                schedule_time TEXT NOT NULL,
                weekdays_mask INTEGER NOT NULL,
                dose_ml REAL NOT NULL,
                timer_type INTEGER NOT NULL DEFAULT 0,
                entries_json TEXT NOT NULL DEFAULT '[]',
                enabled INTEGER NOT NULL DEFAULT 1,
                source TEXT DEFAULT 'ble',
                not_before_date TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, channel, schedule_time, weekdays_mask)
            );

            CREATE TABLE IF NOT EXISTS doser_auto_totals (
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                day TEXT NOT NULL,
                mode INTEGER NOT NULL,
                ml REAL NOT NULL DEFAULT 0,
                raw_json TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, channel, day, mode)
            );

            CREATE TABLE IF NOT EXISTS magstirrer_schedules (
                device_key TEXT NOT NULL,
                channel INTEGER NOT NULL,
                schedule_kind TEXT NOT NULL,
                weekdays_mask INTEGER NOT NULL,
                timer_type INTEGER NOT NULL DEFAULT 0,
                schedule_value INTEGER NOT NULL DEFAULT 0,
                catch_up INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                entries_json TEXT NOT NULL DEFAULT '[]',
                source TEXT DEFAULT 'ble',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, channel, schedule_kind, weekdays_mask)
            );

            CREATE TABLE IF NOT EXISTS led_schedules (
                device_key TEXT NOT NULL,
                schedule_index INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                levels_json TEXT NOT NULL DEFAULT '{}',
                ramp_up_minutes INTEGER NOT NULL DEFAULT 1,
                weekdays_json TEXT NOT NULL DEFAULT '[]',
                sent INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'homeassistant',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, schedule_index)
            );

            CREATE TABLE IF NOT EXISTS ctl_devices (
                kind TEXT NOT NULL,
                alias TEXT NOT NULL,
                address TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (kind, alias)
            );

            CREATE TABLE IF NOT EXISTS ctl_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ctl_standard_templates (
                name TEXT PRIMARY KEY,
                values_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ctl_device_templates (
                device_key TEXT NOT NULL,
                name TEXT NOT NULL,
                values_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (device_key, name)
            );

            CREATE TABLE IF NOT EXISTS ctl_led_on_presets (
                device_key TEXT PRIMARY KEY,
                values_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_doser_schedule_columns(conn)
        _ensure_default_standard_templates(conn)


def state_db_info() -> dict[str, Any]:
    """Return local Doser state database table counts."""
    init_state_db()
    with _db_connect() as conn:
        tables = {}
        for table in (
            "actions",
            "containers",
            "manual_history",
            "manual_daily",
            "doser_schedules",
            "doser_auto_totals",
            "magstirrer_schedules",
            "led_schedules",
            "ctl_devices",
            "ctl_settings",
            "ctl_standard_templates",
            "ctl_device_templates",
            "ctl_led_on_presets",
        ):
            tables[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return {"path": str(state_db_path()), "tables": tables}


def record_action(
    action: str,
    *,
    device_alias: str = "",
    device_address: str = "",
    channel: int | None = None,
    params: dict[str, Any] | None = None,
    status: str = "",
    output: str = "",
) -> None:
    """Record a local Doser/CTL action."""
    init_state_db()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                device_alias,
                device_address,
                action,
                channel,
                json.dumps(params or {}, ensure_ascii=False),
                status,
                output,
            ),
        )


def _empty_channels() -> dict[str, float]:
    return {str(index): 0.0 for index in range(4)}


def _state_key(device: str) -> str:
    return resolve_device_address(device).upper()


def ensure_device_containers(device: str) -> None:
    """Ensure local container rows exist for one Doser."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        for channel in range(4):
            conn.execute(
                """
                INSERT OR IGNORE INTO containers(device_key, channel, volume_ml, updated_at)
                VALUES (?, ?, 0, ?)
                """,
                (key, channel, _utc_now()),
            )


def set_container(device: str, channel: int, ml: float) -> None:
    """Set one local container volume."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO containers(device_key, channel, volume_ml, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_key, channel) DO UPDATE SET
                volume_ml=excluded.volume_ml,
                updated_at=excluded.updated_at
            """,
            (key, int(channel), max(0.0, float(ml)), _utc_now()),
        )


def adjust_container(device: str, channel: int, delta_ml: float) -> None:
    """Adjust one local container volume."""
    current = get_containers(device).get(str(int(channel)), 0.0)
    set_container(device, channel, current + float(delta_ml))


def get_containers(device: str) -> dict[str, float]:
    """Return local container volumes."""
    ensure_device_containers(device)
    key = _state_key(device)
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT channel, volume_ml FROM containers WHERE device_key=? ORDER BY channel", (key,)
        ).fetchall()
    values = _empty_channels()
    for row in rows:
        values[str(int(row["channel"]))] = float(row["volume_ml"])
    return values


def record_manual(device: str, channel: int, ml: float) -> None:
    """Record a local manual Doser amount."""
    init_state_db()
    key = _state_key(device)
    day = _today()
    with _db_connect() as conn:
        conn.execute(
            "INSERT INTO manual_history(device_key, channel, ml, ts, day) VALUES (?, ?, ?, ?, ?)",
            (key, int(channel), float(ml), _utc_now(), day),
        )
        conn.execute(
            """
            INSERT INTO manual_daily(device_key, channel, day, ml)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_key, channel, day) DO UPDATE SET
                ml=round(manual_daily.ml + excluded.ml, 3)
            """,
            (key, int(channel), day, float(ml)),
        )


def get_history(device: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent local manual Doser history."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT ts, channel AS ch, ml FROM manual_history WHERE device_key=? ORDER BY id DESC LIMIT ?",
            (key, int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_history(device: str) -> None:
    """Clear local manual Doser history."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        conn.execute("DELETE FROM manual_history WHERE device_key=?", (key,))
        conn.execute("DELETE FROM manual_daily WHERE device_key=?", (key,))


def get_manual_daily_totals(device: str) -> list[float]:
    """Return today's local manual Doser totals."""
    init_state_db()
    key = _state_key(device)
    totals = [0.0, 0.0, 0.0, 0.0]
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT channel, ml FROM manual_daily WHERE device_key=? AND day=?",
            (key, _today()),
        ).fetchall()
    for row in rows:
        channel = int(row["channel"])
        if 0 <= channel < 4:
            totals[channel] = float(row["ml"])
    return totals


def _ensure_doser_schedule_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(doser_schedules)").fetchall()}
    if not columns:
        return
    if "schedule_kind" not in columns:
        conn.execute("ALTER TABLE doser_schedules ADD COLUMN schedule_kind TEXT NOT NULL DEFAULT 'single_dose'")
    if "schedule_type_id" not in columns:
        conn.execute("ALTER TABLE doser_schedules ADD COLUMN schedule_type_id INTEGER NOT NULL DEFAULT 1")
    if "timer_type" not in columns:
        conn.execute("ALTER TABLE doser_schedules ADD COLUMN timer_type INTEGER NOT NULL DEFAULT 0")
    if "entries_json" not in columns:
        conn.execute("ALTER TABLE doser_schedules ADD COLUMN entries_json TEXT NOT NULL DEFAULT '[]'")
    if "not_before_date" not in columns:
        conn.execute("ALTER TABLE doser_schedules ADD COLUMN not_before_date TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        UPDATE doser_schedules
        SET schedule_type_id = CASE schedule_kind
            WHEN 'interval' THEN 2
            WHEN 'timer' THEN 3
            WHEN 'window' THEN 4
            ELSE 1
        END
        """
    )


def upsert_doser_schedule(
    device: str,
    channel: int,
    schedule_time: str,
    weekdays_mask: int,
    dose_ml: float,
    *,
    schedule_kind: str = "single_dose",
    timer_type: int = 0,
    entries: list[dict[str, Any]] | None = None,
    enabled: bool = True,
    source: str = "ble",
    not_before_date: str | None = "",
) -> None:
    """Store one local Doser schedule."""
    init_state_db()
    key = _state_key(device)
    schedule_type_id = {"single_dose": 1, "interval": 2, "timer": 3, "window": 4}.get(str(schedule_kind), 1)
    with _db_connect() as conn:
        conn.execute("DELETE FROM doser_schedules WHERE device_key=? AND channel=?", (key, int(channel)))
        conn.execute(
            """
            INSERT INTO doser_schedules(
                device_key, channel, schedule_kind, schedule_type_id, schedule_time, weekdays_mask, dose_ml,
                timer_type, entries_json, enabled, source, not_before_date, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                int(channel),
                str(schedule_kind),
                schedule_type_id,
                str(schedule_time),
                int(weekdays_mask),
                float(dose_ml),
                int(timer_type),
                json.dumps(entries or [], ensure_ascii=False),
                1 if enabled else 0,
                source,
                str(not_before_date or ""),
                _utc_now(),
            ),
        )


def list_doser_schedules(device: str) -> list[dict[str, Any]]:
    """List current local Doser schedules."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        _ensure_doser_schedule_columns(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM doser_schedules
            WHERE device_key=?
            ORDER BY channel, schedule_time, weekdays_mask
            """,
            (key,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["entries"] = json.loads(item.get("entries_json") or "[]")
        except json.JSONDecodeError:
            item["entries"] = []
        out.append(item)
    return out


def set_doser_schedule_enabled(device: str, channel: int, enabled: bool) -> int:
    """Set local Doser schedule enabled flag for a channel."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        cur = conn.execute(
            "UPDATE doser_schedules SET enabled=?, updated_at=? WHERE device_key=? AND channel=?",
            (1 if enabled else 0, _utc_now(), key, int(channel)),
        )
        return int(cur.rowcount)


def delete_doser_schedule(device: str, channel: int, kind: str | None = None) -> int:
    """Delete local Doser schedule rows."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        if kind:
            cur = conn.execute(
                "DELETE FROM doser_schedules WHERE device_key=? AND channel=? AND schedule_kind=?",
                (key, int(channel), str(kind)),
            )
        else:
            cur = conn.execute("DELETE FROM doser_schedules WHERE device_key=? AND channel=?", (key, int(channel)))
        return int(cur.rowcount)


def set_doser_auto_total(device: str, channel: int, mode: int, ml: float, day: str | None = None) -> None:
    """Set one local Doser auto total value."""
    init_state_db()
    key = _state_key(device)
    selected_day = day or _today()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO doser_auto_totals(device_key, channel, day, mode, ml, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, '{}', ?)
            ON CONFLICT(device_key, channel, day, mode) DO UPDATE SET
                ml=excluded.ml,
                updated_at=excluded.updated_at
            """,
            (key, int(channel), selected_day, int(mode), float(ml), _utc_now()),
        )


def record_doser_auto_totals(device: str, mode: int, values: list[float], day: str | None = None) -> None:
    """Store four local Doser auto totals."""
    for channel, ml in enumerate(values[:4]):
        set_doser_auto_total(device, channel, mode, float(ml), day)


def get_doser_auto_totals(device: str, mode: int | None = None, day: str | None = None) -> list[dict[str, Any]]:
    """Return local Doser auto totals."""
    init_state_db()
    key = _state_key(device)
    clauses = ["device_key=?"]
    params: list[Any] = [key]
    if mode is not None:
        clauses.append("mode=?")
        params.append(int(mode))
    if day is not None:
        clauses.append("day=?")
        params.append(str(day))
    where = " AND ".join(clauses)
    with _db_connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM doser_auto_totals WHERE {where} ORDER BY day DESC, mode, channel",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def clear_doser_auto_totals(device: str, mode: int | None = None, day: str | None = None) -> int:
    """Clear local Doser auto totals."""
    init_state_db()
    key = _state_key(device)
    clauses = ["device_key=?"]
    params: list[Any] = [key]
    if mode is not None:
        clauses.append("mode=?")
        params.append(int(mode))
    if day is not None:
        clauses.append("day=?")
        params.append(str(day))
    with _db_connect() as conn:
        cur = conn.execute(f"DELETE FROM doser_auto_totals WHERE {' AND '.join(clauses)}", params)
        return int(cur.rowcount)


def set_channel_name(kind: str, device: str, channel: int, name: str) -> None:
    """Store one local channel name."""
    set_setting(f"channel_name.{normalize_kind(kind)}.{_state_key(device)}.{int(channel)}", name.strip())


def list_channel_names(kind: str, device: str) -> dict[int, str]:
    """Return local channel names by zero-based channel."""
    prefix = f"channel_name.{normalize_kind(kind)}.{_state_key(device)}."
    names: dict[int, str] = {}
    for key, value in list_settings(prefix):
        suffix = key.removeprefix(prefix)
        if suffix.isdigit():
            names[int(suffix)] = value
    return names


def upsert_magstirrer_schedule(
    device: str,
    channel: int,
    schedule_kind: str,
    weekdays_mask: int,
    entries: list[dict[str, Any]],
    *,
    timer_type: int = 0,
    schedule_value: int = 0,
    catch_up: int = 0,
    enabled: bool = True,
    source: str = "ble",
) -> None:
    """Store one local MagStirrer schedule."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO magstirrer_schedules(
                device_key, channel, schedule_kind, weekdays_mask, timer_type,
                schedule_value, catch_up, enabled, entries_json, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_key, channel, schedule_kind, weekdays_mask) DO UPDATE SET
                timer_type=excluded.timer_type,
                schedule_value=excluded.schedule_value,
                catch_up=excluded.catch_up,
                enabled=excluded.enabled,
                entries_json=excluded.entries_json,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            (
                key,
                int(channel),
                str(schedule_kind),
                int(weekdays_mask),
                int(timer_type),
                int(schedule_value),
                int(catch_up),
                1 if enabled else 0,
                json.dumps(entries, ensure_ascii=False),
                str(source),
                _utc_now(),
            ),
        )


def list_magstirrer_schedules(device: str) -> list[dict[str, Any]]:
    """List local MagStirrer schedules."""
    init_state_db()
    key = _state_key(device)
    with _db_connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM magstirrer_schedules
            WHERE device_key=?
            ORDER BY channel, schedule_kind, weekdays_mask
            """,
            (key,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["entries"] = json.loads(item.get("entries_json") or "[]")
        except json.JSONDecodeError:
            item["entries"] = []
        out.append(item)
    return out


def delete_magstirrer_schedule(
    device: str,
    channel: int,
    schedule_kind: str | None = None,
    weekdays_mask: int | None = None,
) -> int:
    """Delete local MagStirrer schedule rows."""
    init_state_db()
    key = _state_key(device)
    clauses = ["device_key=?", "channel=?"]
    params: list[Any] = [key, int(channel)]
    if schedule_kind is not None:
        clauses.append("schedule_kind=?")
        params.append(str(schedule_kind))
    if weekdays_mask is not None:
        clauses.append("weekdays_mask=?")
        params.append(int(weekdays_mask))
    with _db_connect() as conn:
        cur = conn.execute(f"DELETE FROM magstirrer_schedules WHERE {' AND '.join(clauses)}", params)
        return int(cur.rowcount)


def _empty_store() -> dict[str, Any]:
    return {
        "devices": {kind: {} for kind in DEVICE_KINDS},
        "settings": {},
        "templates": {
            "standard": deepcopy(DEFAULT_STANDARD_TEMPLATES),
            "devices": {},
        },
        "led_on_presets": {},
    }


def _ensure_default_standard_templates(conn: sqlite3.Connection) -> None:
    for name, values in DEFAULT_STANDARD_TEMPLATES.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO ctl_standard_templates(name, values_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (name, json.dumps(_validate_brightness(values)), _utc_now()),
        )


def _store_from_conn(conn: sqlite3.Connection) -> dict[str, Any]:
    store = _empty_store()
    for row in conn.execute("SELECT kind, alias, address, label, model FROM ctl_devices ORDER BY kind, alias"):
        kind = normalize_kind(str(row["kind"]))
        store["devices"][kind][str(row["alias"])] = {
            "alias": str(row["alias"]),
            "address": str(row["address"]),
            "label": str(row["label"] or ""),
            "model": str(row["model"] or ""),
        }
    for row in conn.execute("SELECT key, value FROM ctl_settings ORDER BY key"):
        store["settings"][str(row["key"])] = str(row["value"])
    store["templates"]["standard"] = {}
    for row in conn.execute("SELECT name, values_json FROM ctl_standard_templates ORDER BY name"):
        store["templates"]["standard"][str(row["name"])] = _normalize_stored_brightness(json.loads(row["values_json"]))
    for row in conn.execute("SELECT device_key, name, values_json FROM ctl_device_templates ORDER BY device_key, name"):
        key = str(row["device_key"])
        store["templates"]["devices"].setdefault(key, {})
        store["templates"]["devices"][key][str(row["name"])] = _normalize_stored_brightness(
            json.loads(row["values_json"])
        )
    for row in conn.execute("SELECT device_key, values_json, updated_at FROM ctl_led_on_presets ORDER BY device_key"):
        store["led_on_presets"][str(row["device_key"])] = {
            "values": _normalize_stored_brightness(json.loads(row["values_json"])),
            "updated_at": str(row["updated_at"] or ""),
        }
    return store


def _save_store_to_conn(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    store = _empty_store()
    if isinstance(data, dict):
        store.update(data)
    now = _utc_now()
    conn.execute("DELETE FROM ctl_devices")
    conn.execute("DELETE FROM ctl_settings")
    conn.execute("DELETE FROM ctl_standard_templates")
    conn.execute("DELETE FROM ctl_device_templates")
    conn.execute("DELETE FROM ctl_led_on_presets")
    for kind in DEVICE_KINDS:
        for alias, row in (store.get("devices", {}).get(kind, {}) or {}).items():
            if not isinstance(row, dict):
                continue
            conn.execute(
                """
                INSERT INTO ctl_devices(kind, alias, address, label, model, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    kind,
                    str(row.get("alias") or alias),
                    str(row.get("address") or "").upper(),
                    str(row.get("label") or ""),
                    str(row.get("model") or ""),
                    now,
                ),
            )
    for key, value in (store.get("settings", {}) or {}).items():
        conn.execute(
            "INSERT INTO ctl_settings(key, value, updated_at) VALUES (?, ?, ?)",
            (str(key), str(value), now),
        )
    for name, values in (store.get("templates", {}).get("standard", {}) or {}).items():
        conn.execute(
            "INSERT INTO ctl_standard_templates(name, values_json, updated_at) VALUES (?, ?, ?)",
            (str(name), json.dumps(_validate_brightness(values)), now),
        )
    for device_key, templates in (store.get("templates", {}).get("devices", {}) or {}).items():
        for name, values in (templates or {}).items():
            conn.execute(
                "INSERT INTO ctl_device_templates(device_key, name, values_json, updated_at) VALUES (?, ?, ?, ?)",
                (str(device_key).upper(), str(name), json.dumps(_validate_brightness(values)), now),
            )
    for device_key, item in (store.get("led_on_presets", {}) or {}).items():
        values = item.get("values", item) if isinstance(item, dict) else item
        updated = str(item.get("updated_at") or now) if isinstance(item, dict) else now
        conn.execute(
            "INSERT INTO ctl_led_on_presets(device_key, values_json, updated_at) VALUES (?, ?, ?)",
            (str(device_key).upper(), json.dumps(_validate_brightness(values)), updated),
        )


def load_store() -> dict[str, Any]:
    """Load local CTL store data."""
    init_state_db()
    with _db_connect() as conn:
        return _store_from_conn(conn)


def save_store(data: dict[str, Any]) -> None:
    """Persist local CTL store data."""
    init_state_db()
    with _db_connect() as conn:
        _save_store_to_conn(conn, data)


def normalize_kind(kind: str) -> str:
    """Normalize a user-facing device kind."""
    normalized = kind.strip().lower()
    aliases = {
        "light": "led",
        "licht": "led",
        "dose": "doser",
        "mag": "ruehrer",
        "magstirrer": "ruehrer",
        "rührer": "ruehrer",
        "stirrer": "ruehrer",
        "heater": "heizer",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in DEVICE_KINDS:
        raise ValueError(f"Unknown device kind: {kind}")
    return normalized


def default_alias(kind: str, index: int) -> str:
    """Return the default alias for a device kind/index."""
    return f"{normalize_kind(kind)}_{int(index)}"


def set_device(
    kind: str,
    index: int,
    address: str,
    *,
    alias: str | None = None,
    label: str = "",
    model: str = "",
) -> dict[str, str]:
    """Store a device alias."""
    data = load_store()
    normalized = normalize_kind(kind)
    device_alias = alias.strip() if alias else default_alias(normalized, index)
    row = {
        "alias": device_alias,
        "address": address.strip().upper(),
        "label": label.strip(),
        "model": model.strip(),
    }
    data["devices"][normalized][device_alias] = row
    save_store(data)
    return row


def update_device_fields(kind: str, alias_or_index: str, *, label: str | None = None, model: str | None = None) -> bool:
    """Update optional metadata for a stored device alias."""
    data = load_store()
    normalized = normalize_kind(kind)
    alias = alias_or_index if not alias_or_index.isdigit() else default_alias(normalized, int(alias_or_index))
    row = data["devices"][normalized].get(alias)
    if not row:
        return False
    if label is not None:
        row["label"] = label.strip()
    if model is not None:
        row["model"] = model.strip()
    save_store(data)
    return True


def delete_device(kind: str, alias_or_index: str) -> bool:
    """Delete a stored device alias."""
    data = load_store()
    normalized = normalize_kind(kind)
    alias = alias_or_index if not alias_or_index.isdigit() else default_alias(normalized, int(alias_or_index))
    existed = alias in data["devices"][normalized]
    data["devices"][normalized].pop(alias, None)
    save_store(data)
    return existed


def list_devices(kind: str | None = None) -> list[dict[str, str]]:
    """List stored device aliases."""
    data = load_store()
    kinds = [normalize_kind(kind)] if kind else list(DEVICE_KINDS)
    rows: list[dict[str, str]] = []
    for current_kind in kinds:
        for row in data["devices"].get(current_kind, {}).values():
            item = dict(row)
            item["kind"] = current_kind
            rows.append(item)
    return rows


def resolve_device_address(value: str) -> str:
    """Resolve an alias such as doser_1 to a stored MAC address."""
    wanted = value.strip()
    data = load_store()
    for devices in data["devices"].values():
        row = devices.get(wanted)
        if row and row.get("address"):
            return str(row["address"])
        for item in devices.values():
            if str(item.get("address", "")).lower() == wanted.lower():
                return str(item["address"])
    return wanted


def set_setting(key: str, value: str) -> None:
    """Set one string setting."""
    data = load_store()
    data["settings"][key] = value
    save_store(data)


def get_setting(key: str, default: str | None = None) -> str | None:
    """Get one string setting."""
    value = load_store()["settings"].get(key, default)
    return None if value is None else str(value)


def list_settings(prefix: str = "") -> list[tuple[str, str]]:
    """List settings, optionally filtered by prefix."""
    settings = load_store()["settings"]
    return [(str(key), str(value)) for key, value in sorted(settings.items()) if str(key).startswith(prefix)]


def delete_setting(key: str) -> bool:
    """Delete one setting."""
    data = load_store()
    existed = key in data["settings"]
    data["settings"].pop(key, None)
    save_store(data)
    return existed


def set_led_on_preset(device: str, brightness: list[int]) -> None:
    """Store brightness values used as a local LED turn-on preset."""
    data = load_store()
    device_key = resolve_device_address(device).upper()
    data["led_on_presets"][device_key] = {
        "values": _validate_brightness(brightness),
        "updated_at": _utc_now(),
    }
    save_store(data)


def list_led_on_presets(device: str | None = None) -> list[dict[str, Any]]:
    """List stored LED turn-on presets."""
    presets = load_store().get("led_on_presets", {})
    device_key = resolve_device_address(device).upper() if device else None
    rows: list[dict[str, Any]] = []
    for key, value in sorted(presets.items()):
        if device_key and str(key).upper() != device_key:
            continue
        item = value if isinstance(value, dict) else {"values": value}
        rows.append(
            {
                "device_key": str(key),
                "values": [int(entry) for entry in item.get("values", [])],
                "updated_at": str(item.get("updated_at", "")),
            }
        )
    return rows


def delete_led_on_preset(device: str) -> bool:
    """Delete one LED turn-on preset."""
    data = load_store()
    device_key = resolve_device_address(device).upper()
    existed = device_key in data["led_on_presets"]
    data["led_on_presets"].pop(device_key, None)
    save_store(data)
    return existed


def _validate_brightness(values: list[int]) -> list[int]:
    cleaned = [int(value) for value in values]
    if len(cleaned) not in (1, 3, 4):
        raise ValueError("Brightness must have 1, 3 or 4 values")
    for value in cleaned:
        if not 0 <= value <= 100:
            raise ValueError("Brightness values must be 0..100")
    return cleaned


def _normalize_stored_brightness(values: list[int]) -> list[int]:
    """Clamp legacy persisted LED values to the current 0..100 range."""
    return [max(0, min(100, int(value))) for value in values]


def set_standard_template(name: str, brightness: list[int]) -> None:
    """Store a standard template."""
    data = load_store()
    data["templates"]["standard"][name] = _validate_brightness(brightness)
    save_store(data)


def get_standard_template(name: str) -> list[int] | None:
    """Return a standard template."""
    values = load_store()["templates"]["standard"].get(name)
    return None if values is None else [int(value) for value in values]


def delete_standard_template(name: str) -> bool:
    """Delete a standard template."""
    data = load_store()
    existed = name in data["templates"]["standard"]
    data["templates"]["standard"].pop(name, None)
    save_store(data)
    return existed


def list_standard_templates() -> list[tuple[str, list[int]]]:
    """List standard templates."""
    templates = load_store()["templates"]["standard"]
    return [(str(name), [int(value) for value in values]) for name, values in sorted(templates.items())]


def set_device_template(device: str, name: str, brightness: list[int]) -> None:
    """Store a device-specific template."""
    data = load_store()
    device_key = resolve_device_address(device).upper()
    data["templates"]["devices"].setdefault(device_key, {})
    data["templates"]["devices"][device_key][name] = _validate_brightness(brightness)
    save_store(data)


def get_device_template(device: str, name: str) -> list[int] | None:
    """Return a device-specific template."""
    device_key = resolve_device_address(device).upper()
    values = load_store()["templates"]["devices"].get(device_key, {}).get(name)
    return None if values is None else [int(value) for value in values]


def delete_device_template(device: str, name: str) -> bool:
    """Delete a device-specific template."""
    data = load_store()
    device_key = resolve_device_address(device).upper()
    templates = data["templates"]["devices"].setdefault(device_key, {})
    existed = name in templates
    templates.pop(name, None)
    save_store(data)
    return existed


def list_device_templates(device: str) -> list[tuple[str, list[int]]]:
    """List device-specific templates."""
    device_key = resolve_device_address(device).upper()
    templates = load_store()["templates"]["devices"].get(device_key, {})
    return [(str(name), [int(value) for value in values]) for name, values in sorted(templates.items())]
