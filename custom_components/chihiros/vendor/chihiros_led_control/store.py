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

DEVICE_KINDS = ("led",)

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
        return Path("/config/.chihiros_led_core/chihiros_led_core.sqlite3")
    return Path.home() / ".chihiros_led_core" / "chihiros_led_core.sqlite3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()




def _db_connect() -> sqlite3.Connection:
    path = state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_state_db() -> None:
    """Create local LED state tables."""
    with _db_connect() as conn:
        conn.executescript(
            """
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
        _ensure_default_standard_templates(conn)


def state_db_info() -> dict[str, Any]:
    """Return local LED state database table counts."""
    init_state_db()
    with _db_connect() as conn:
        tables = {}
        for table in (
            "led_schedules",
            "ctl_devices",
            "ctl_settings",
            "ctl_standard_templates",
            "ctl_device_templates",
            "ctl_led_on_presets",
        ):
            tables[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return {"path": str(state_db_path()), "tables": tables}
















def _state_key(device: str) -> str:
    """Return the normalized key used by device-scoped LED settings."""
    return resolve_device_address(device).upper()


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
    aliases = {"light": "led", "licht": "led"}
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
    """Resolve an LED alias to a stored MAC address."""
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
