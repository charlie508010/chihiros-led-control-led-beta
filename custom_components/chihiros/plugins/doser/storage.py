"""Home Assistant Store-backed state for the optional Doser plugin."""

# ruff: noqa: D107,E501

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ...common.storage import state_db_path
from ...const import DOMAIN
from .types import DoserSchedule

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_doser_ext"
DEFAULT_CONTAINER_ML = 500.0
LOW_CONTAINER_THRESHOLD_PERCENT = 10.0
MAX_ACTION_LOG_ENTRIES = 80
DEFAULT_MAX_AUTO_ML = 50.0
DEFAULT_MAX_MANUAL_ML = 50.0
DEFAULT_MAX_DAILY_ML = 250.0
DEFAULT_CALIBRATION_REMINDER_DAYS = 30
DEFAULT_LOW_CONTAINER_PUSH_MESSAGE = (
    "{ch} {channel}: nur noch {remaining} mL im Behaelter. Schwellwert: {threshold} mL."
)
DEFAULT_CHANNEL_NAMES = ("Nitrat", "Phosphat", "Eisen", "Kalium")
SIGNAL_DOSER_EXT_UPDATED = f"{DOMAIN}_doser_ext_updated"
SCHEDULE_KIND_IDS = {
    "single_dose": 1,
    "interval": 2,
    "timer": 3,
    "window": 4,
}
SCHEDULE_ID_KINDS = {value: key for key, value in SCHEDULE_KIND_IDS.items()}


def update_signal(address: str) -> str:
    """Return dispatcher signal for one dosing device."""
    return f"{SIGNAL_DOSER_EXT_UPDATED}_{address.lower()}"


def schedule_type_id(kind: str) -> int:
    """Return the stable database id for one scheduler type."""
    return SCHEDULE_KIND_IDS.get(str(kind or "single_dose"), 1)


def schedule_kind_from_id(type_id: int | None, fallback: str = "single_dose") -> str:
    """Return scheduler kind from the stable database id."""
    try:
        value = int(type_id) if type_id is not None else 0
    except (TypeError, ValueError):
        value = 0
    return SCHEDULE_ID_KINDS.get(value, str(fallback or "single_dose"))


def _state_db_path() -> Path:
    """Return the shared Chihiros SQLite state database path."""
    return state_db_path()


def _today() -> str:
    """Return the Home Assistant local date."""
    return dt_util.now().date().isoformat()


def _utc_now() -> str:
    """Return a SQLite-compatible UTC timestamp."""
    return dt_util.utcnow().replace(tzinfo=UTC).isoformat()


def _split_history_ts(value: str) -> tuple[str, str]:
    """Return local-ish date and time strings from a stored timestamp."""
    try:
        parsed = dt_util.parse_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        return "", ""
    local = dt_util.as_local(parsed)
    return local.date().isoformat(), local.strftime("%H:%M:%S")


class DoserExtStore:
    """Small JSON store for local dosing metadata."""

    def __init__(self, hass: HomeAssistant, address: str, pump_count: int = 4) -> None:
        self.hass = hass
        self.address = address.upper()
        self.pump_count = pump_count
        key = f"{STORE_KEY}_{self.address.lower().replace(':', '_')}"
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, key)
        self.data: dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load the store and ensure default channel rows exist."""
        loaded = await self._store.async_load()
        self.data = loaded if isinstance(loaded, dict) else {}
        self.data.setdefault("containers_ml", {})
        self.data.setdefault("schedules", {})
        self.data.setdefault("action_log", [])
        self.data.setdefault("doser_safety", {})
        self.data.setdefault("low_container_notified", {})
        self.data.setdefault("low_container_notification_enabled", True)
        self.data.setdefault("low_container_notify_targets", [])
        self.data.setdefault("low_container_push_message", DEFAULT_LOW_CONTAINER_PUSH_MESSAGE)
        self.data.setdefault("calibrations", {})
        self._ensure_today()
        for pump_idx in range(self.pump_count):
            self.data["containers_ml"].setdefault(str(pump_idx), DEFAULT_CONTAINER_ML)

    def _ensure_today(self) -> None:
        """Reset local daily counters when the HA local date changes."""
        today = dt_util.now().date().isoformat()
        if self.data.get("manual_daily_date") == today:
            return
        self.data["manual_daily_date"] = today
        self.data["manual_daily_ml"] = {}

    async def async_save(self) -> None:
        """Persist the current state."""
        await self._store.async_save(self.data)
        async_dispatcher_send(self.hass, update_signal(self.address))

    async def async_add_log(self, action: str, pump_idx: int | None = None, detail: str = "") -> None:
        """Append one dosing action to the local action log."""
        now = dt_util.now()
        entry = {
            "ts": now.isoformat(),
            "time": now.strftime("%H:%M:%S"),
            "date": now.date().isoformat(),
            "action": action,
            "detail": detail,
        }
        if pump_idx is not None:
            entry["pump"] = int(pump_idx) + 1
        log = self.data.setdefault("action_log", [])
        if not isinstance(log, list):
            log = []
            self.data["action_log"] = log
        dedupe_actions = {"Scheduler erfolgreich", "Tageswerte vom Geraet", "Auto-Differenz"}
        if action in dedupe_actions:
            entry_pump = entry.get("pump")
            for existing in log[:MAX_ACTION_LOG_ENTRIES]:
                if not isinstance(existing, dict):
                    continue
                if (
                    existing.get("action") == action
                    and existing.get("pump") == entry_pump
                    and existing.get("detail") == detail
                ):
                    return
        log.insert(0, entry)
        del log[MAX_ACTION_LOG_ENTRIES:]
        await self.async_save()

    def _sqlite_rows(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        """Read rows from the shared SQLite state database if it exists."""
        path = _state_db_path()
        if not path.exists():
            return []
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(row) for row in conn.execute(query, params).fetchall()]
        except sqlite3.Error:
            return []

    def _sqlite_execute(self, statements: list[tuple[str, tuple[Any, ...]]]) -> bool:
        """Write statements to the shared SQLite state database if it exists."""
        path = _state_db_path()
        if not path.exists():
            return False
        try:
            with sqlite3.connect(path) as conn:
                self._ensure_doser_schedule_type_column(conn)
                for query, params in statements:
                    conn.execute(query, params)
            return True
        except sqlite3.Error:
            return False

    def _ensure_doser_schedule_type_column(self, conn: sqlite3.Connection) -> None:
        """Ensure the stable scheduler type id exists in SQLite."""
        rows = conn.execute("PRAGMA table_info(doser_schedules)").fetchall()
        columns = {str(row[1]) for row in rows}
        if "schedule_type_id" not in columns:
            conn.execute("ALTER TABLE doser_schedules ADD COLUMN schedule_type_id INTEGER NOT NULL DEFAULT 1")
        if "valid_from_tomorrow" not in columns:
            conn.execute("ALTER TABLE doser_schedules ADD COLUMN valid_from_tomorrow INTEGER NOT NULL DEFAULT 0")
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

    def _sqlite_record_action(
        self,
        action: str,
        pump_idx: int | None,
        params: dict[str, Any],
        status: str,
        output: str = "",
    ) -> bool:
        """Write one audit row to the shared SQLite actions table if available."""
        return self._sqlite_execute(
            [
                (
                    """
                    INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now(),
                        "",
                        self.address,
                        str(action),
                        None if pump_idx is None else int(pump_idx),
                        json.dumps(params, ensure_ascii=False),
                        str(status),
                        str(output),
                    ),
                )
            ]
        )

    def _sqlite_schedule_row(self, pump_idx: int) -> dict[str, Any] | None:
        """Return the newest SQLite schedule row for one pump."""
        rows = self._sqlite_rows(
            """
            SELECT *
            FROM doser_schedules
            WHERE device_key=? AND channel=?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (self.address, int(pump_idx)),
        )
        return rows[0] if rows else None

    def schedule_rows(self) -> list[dict[str, Any]]:
        """Return enabled schedule rows with decoded entries for background watching."""
        rows = self._sqlite_rows(
            """
            SELECT *
            FROM doser_schedules
            WHERE device_key=?
            ORDER BY channel, schedule_time, weekdays_mask
            """,
            (self.address,),
        )
        for row in rows:
            try:
                row["entries"] = json.loads(str(row.get("entries_json") or "[]"))
            except json.JSONDecodeError:
                row["entries"] = []
        return rows

    def _weekdays_mask(self, weekdays: tuple[str, ...]) -> int:
        """Convert schedule weekdays to the local SQLite bit mask."""
        if not weekdays or "everyday" in weekdays:
            return 127
        bits = {
            "monday": 1 << 0,
            "tuesday": 1 << 1,
            "wednesday": 1 << 2,
            "thursday": 1 << 3,
            "friday": 1 << 4,
            "saturday": 1 << 5,
            "sunday": 1 << 6,
        }
        mask = 0
        for day in weekdays:
            mask |= bits.get(str(day).lower(), 0)
        return mask or 127

    def _weekdays_from_mask(self, mask: int) -> tuple[str, ...]:
        """Convert the stored SQLite weekday mask back to service names."""
        value = int(mask) & 0x7F
        if value == 0x7F or value == 0:
            return ("everyday",)
        days = (
            ("monday", 1 << 0),
            ("tuesday", 1 << 1),
            ("wednesday", 1 << 2),
            ("thursday", 1 << 3),
            ("friday", 1 << 4),
            ("saturday", 1 << 5),
            ("sunday", 1 << 6),
        )
        return tuple(day for day, bit in days if value & bit) or ("everyday",)

    def action_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent dosing action log entries."""
        entries: list[dict[str, Any]] = []
        for row in self._sqlite_rows(
            """
            SELECT ts, action, channel, params_json, status, output
            FROM actions
            WHERE UPPER(device_address)=UPPER(?) OR UPPER(device_alias)=UPPER(?)
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.address, self.address, max(int(limit), MAX_ACTION_LOG_ENTRIES)),
        ):
            date_text, time_text = _split_history_ts(str(row.get("ts") or ""))
            channel = row.get("channel")
            entry: dict[str, Any] = {
                "ts": str(row.get("ts") or ""),
                "date": date_text,
                "time": time_text,
                "action": str(row.get("action") or ""),
                "detail": str(row.get("output") or row.get("status") or ""),
                "status": str(row.get("status") or ""),
            }
            if channel is not None:
                try:
                    entry["pump"] = int(channel) + 1
                except (TypeError, ValueError):
                    pass
            params = row.get("params_json")
            if params:
                try:
                    parsed = json.loads(str(params))
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    entry["params"] = parsed
            entries.append(entry)

        raw = self.data.get("action_log", [])
        if isinstance(raw, list):
            entries.extend(entry for entry in raw[:limit] if isinstance(entry, dict))

        seen: set[tuple[str, str, Any, str]] = set()
        deduped: list[dict[str, Any]] = []
        for entry in entries:
            key = (
                str(entry.get("ts") or entry.get("date") or ""),
                str(entry.get("action") or ""),
                entry.get("pump"),
                str(entry.get("detail") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped[:limit]

    def container_ml(self, pump_idx: int) -> float:
        """Return local remaining container volume."""
        rows = self._sqlite_rows(
            """
            SELECT volume_ml
            FROM containers
            WHERE device_key=? AND channel=?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (self.address, int(pump_idx)),
        )
        if rows:
            return round(float(rows[0].get("volume_ml") or 0.0), 1)
        return float(self.data.get("containers_ml", {}).get(str(pump_idx), DEFAULT_CONTAINER_ML))

    def calibration(self, pump_idx: int) -> dict[str, Any] | None:
        """Return the latest stored calibration metadata for one pump."""
        rows = self._sqlite_rows(
            """
            SELECT measured_ml, calibrated_at, reminder_days, reminder_at, test_ml
            FROM doser_calibrations
            WHERE device_key=? AND channel=?
            LIMIT 1
            """,
            (self.address, int(pump_idx)),
        )
        if rows:
            row = rows[0]
            return {
                "measured_ml": round(float(row.get("measured_ml") or 0.0), 2),
                "calibrated_at": str(row.get("calibrated_at") or ""),
                "reminder_days": int(row.get("reminder_days") or DEFAULT_CALIBRATION_REMINDER_DAYS),
                "reminder_at": str(row.get("reminder_at") or ""),
                "test_ml": round(float(row.get("test_ml") or 0.0), 1),
            }
        raw = self.data.get("calibrations", {}).get(str(pump_idx))
        return dict(raw) if isinstance(raw, dict) else None

    async def async_record_calibration(
        self,
        pump_idx: int,
        measured_ml: float,
        reminder_days: int,
        test_ml: float | None,
    ) -> dict[str, Any]:
        """Persist the latest accepted calibration and its renewal reminder."""
        days = max(1, min(3650, int(reminder_days)))
        calibrated = dt_util.utcnow().replace(tzinfo=UTC)
        reminder = calibrated + timedelta(days=days)
        record = {
            "measured_ml": round(float(measured_ml), 2),
            "calibrated_at": calibrated.isoformat(),
            "reminder_days": days,
            "reminder_at": reminder.isoformat(),
            "test_ml": round(float(test_ml), 1) if test_ml is not None else 0.0,
        }
        params = {
            "scope": "doser",
            "source": "calibration",
            "pump": int(pump_idx) + 1,
            **record,
        }
        self._sqlite_execute(
            [
                (
                    """
                    CREATE TABLE IF NOT EXISTS doser_calibrations (
                        device_key TEXT NOT NULL,
                        channel INTEGER NOT NULL,
                        measured_ml REAL NOT NULL,
                        calibrated_at TEXT NOT NULL,
                        reminder_days INTEGER NOT NULL,
                        reminder_at TEXT NOT NULL,
                        test_ml REAL NOT NULL DEFAULT 0,
                        PRIMARY KEY (device_key, channel)
                    )
                    """,
                    (),
                ),
                (
                    """
                    INSERT INTO doser_calibrations(
                        device_key, channel, measured_ml, calibrated_at, reminder_days, reminder_at, test_ml
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_key, channel) DO UPDATE SET
                        measured_ml=excluded.measured_ml,
                        calibrated_at=excluded.calibrated_at,
                        reminder_days=excluded.reminder_days,
                        reminder_at=excluded.reminder_at,
                        test_ml=excluded.test_ml
                    """,
                    (
                        self.address,
                        int(pump_idx),
                        record["measured_ml"],
                        record["calibrated_at"],
                        record["reminder_days"],
                        record["reminder_at"],
                        record["test_ml"],
                    ),
                ),
                (
                    """
                    INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["calibrated_at"],
                        "",
                        self.address,
                        "doser_calibration",
                        int(pump_idx),
                        json.dumps(params, ensure_ascii=False),
                        "ok",
                        (f"gemessen {record['measured_ml']:.2f} mL; Erinnerung nach {record['reminder_days']} Tagen"),
                    ),
                ),
            ]
        )
        self.data.setdefault("calibrations", {})[str(pump_idx)] = record
        await self.async_add_log(
            "Kalibrierung gespeichert",
            pump_idx,
            f"{record['measured_ml']:.2f} mL; Erinnerung {reminder.date().isoformat()}",
        )
        return dict(record)

    def low_container_notification_enabled(self) -> bool:
        """Return whether low-container HA notifications are enabled."""
        return bool(self.data.get("low_container_notification_enabled", True))

    def low_container_notify_targets(self) -> list[str]:
        """Return selected notify service names for low-container push messages."""
        raw = self.data.get("low_container_notify_targets", [])
        if not isinstance(raw, list):
            return []
        targets: list[str] = []
        for item in raw:
            target = str(item).strip()
            if target.startswith("notify."):
                target = target.split(".", 1)[1]
            if target and target not in targets:
                targets.append(target)
        return targets[:3]

    def low_container_push_message_template(self) -> str:
        """Return low-container push message template."""
        value = str(self.data.get("low_container_push_message") or "").strip()
        return value or DEFAULT_LOW_CONTAINER_PUSH_MESSAGE

    def doser_safety_limits(self) -> dict[str, float]:
        """Return configured dosing safety limits."""
        raw = self.data.get("doser_safety", {})
        if not isinstance(raw, dict):
            raw = {}
        legacy_single = raw.get("max_single_ml", DEFAULT_MAX_AUTO_ML)
        return {
            "max_auto_ml": round(float(raw.get("max_auto_ml", legacy_single)), 1),
            "max_manual_ml": round(float(raw.get("max_manual_ml", legacy_single)), 1),
            "max_daily_ml": round(float(raw.get("max_daily_ml", DEFAULT_MAX_DAILY_ML)), 1),
        }

    async def async_set_doser_safety_limits(
        self, max_auto_ml: float, max_manual_ml: float, max_daily_ml: float
    ) -> dict[str, float]:
        """Persist dosing safety limits."""
        limits = {
            "max_auto_ml": round(float(max_auto_ml), 1),
            "max_manual_ml": round(float(max_manual_ml), 1),
            "max_daily_ml": round(float(max_daily_ml), 1),
        }
        self.data["doser_safety"] = limits
        self._sqlite_record_action(
            "set_doser_safety",
            None,
            limits,
            "ok",
            f"Automatisch={limits['max_auto_ml']:.1f} mL, Manuell={limits['max_manual_ml']:.1f} mL, Tagesmenge={limits['max_daily_ml']:.1f} mL",
        )
        await self.async_add_log(
            "Ueberdosierungsschutz gespeichert",
            None,
            f"Automatisch {limits['max_auto_ml']:.1f} mL, Manuell {limits['max_manual_ml']:.1f} mL, Tagesmenge {limits['max_daily_ml']:.1f} mL",
        )
        return limits

    async def async_set_low_container_notification_enabled(self, enabled: bool) -> None:
        """Enable or disable low-container HA notifications."""
        self.data["low_container_notification_enabled"] = bool(enabled)
        if not enabled:
            for pump_idx in range(self.pump_count):
                notification_id = self._low_container_notification_id(pump_idx)
                persistent_notification.async_dismiss(self.hass, notification_id)
            self.data["low_container_notified"] = {}
        else:
            for pump_idx in range(self.pump_count):
                self._sync_low_container_notification(pump_idx)
        await self.async_add_log("Push Behälterstand", None, "an" if enabled else "aus")

    async def async_set_low_container_push_settings(
        self, enabled: bool, targets: list[str], message_template: str | None = None
    ) -> dict[str, Any]:
        """Persist low-container push settings."""
        clean_targets: list[str] = []
        for item in targets:
            target = str(item).strip()
            if target.startswith("notify."):
                target = target.split(".", 1)[1]
            if target and target not in clean_targets:
                clean_targets.append(target)
        clean_targets = clean_targets[:3]
        message = str(message_template or "").strip() or DEFAULT_LOW_CONTAINER_PUSH_MESSAGE
        self.data["low_container_notification_enabled"] = bool(enabled)
        self.data["low_container_notify_targets"] = clean_targets
        self.data["low_container_push_message"] = message
        if not enabled:
            for pump_idx in range(self.pump_count):
                notification_id = self._low_container_notification_id(pump_idx)
                persistent_notification.async_dismiss(self.hass, notification_id)
            self.data["low_container_notified"] = {}
        else:
            for pump_idx in range(self.pump_count):
                self._sync_low_container_notification(pump_idx)
        await self.async_add_log(
            "Push Behälterstand",
            None,
            f"{'an' if enabled else 'aus'}; {', '.join(clean_targets) if clean_targets else 'keine Zusatzgeraete'}",
        )
        return {"enabled": bool(enabled), "targets": clean_targets, "message": message}

    def _low_container_threshold_ml(self) -> float:
        """Return the low-container warning threshold in mL."""
        return round(DEFAULT_CONTAINER_ML * LOW_CONTAINER_THRESHOLD_PERCENT / 100.0, 1)

    def _low_container_notification_id(self, pump_idx: int) -> str:
        """Return a stable persistent notification id for one pump."""
        address = self.address.lower().replace(":", "_")
        return f"{DOMAIN}_doser_low_container_{address}_ch{pump_idx + 1}"

    def _sync_low_container_notification(self, pump_idx: int) -> None:
        """Create or clear a HA notification for a low remaining container volume."""
        key = str(pump_idx)
        remaining_ml = self.container_ml(pump_idx)
        threshold_ml = self._low_container_threshold_ml()
        notified = self.data.setdefault("low_container_notified", {})
        notification_id = self._low_container_notification_id(pump_idx)

        if not self.low_container_notification_enabled():
            if notified.pop(key, None):
                persistent_notification.async_dismiss(self.hass, notification_id)
            return

        if remaining_ml <= threshold_ml:
            if notified.get(key):
                return
            channel = f"CH{pump_idx + 1}"
            channel_name = (
                DEFAULT_CHANNEL_NAMES[pump_idx]
                if 0 <= pump_idx < len(DEFAULT_CHANNEL_NAMES)
                else f"Kanal {pump_idx + 1}"
            )
            message = self._format_low_container_push_message(channel, channel_name, remaining_ml, threshold_ml)
            title = f"Chihiros Doser: {channel} Behaelter niedrig"
            persistent_notification.async_create(
                self.hass,
                message,
                title=title,
                notification_id=notification_id,
            )
            self._send_low_container_push_targets(title, message)
            notified[key] = True
            return

        if notified.pop(key, None):
            persistent_notification.async_dismiss(self.hass, notification_id)

    def _format_low_container_push_message(
        self, channel: str, channel_name: str, remaining_ml: float, threshold_ml: float
    ) -> str:
        """Format low-container push message template."""
        replacements = {
            "{ch}": channel,
            "{channel}": channel_name,
            "{device}": "Chihiros Doser",
            "{remaining}": f"{remaining_ml:.1f}",
            "{threshold}": f"{threshold_ml:.1f}",
        }
        message = self.low_container_push_message_template()
        for placeholder, value in replacements.items():
            message = message.replace(placeholder, value)
        return message

    def _send_low_container_push_targets(self, title: str, message: str) -> None:
        """Send low-container push message to selected notify services."""
        for service in self.low_container_notify_targets():
            if not self.hass.services.has_service("notify", service):
                continue
            coro = self.hass.services.async_call(
                "notify",
                service,
                {"title": title, "message": message},
                blocking=False,
            )
            self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, coro)

    async def async_set_container_ml(self, pump_idx: int, ml: float) -> None:
        """Set local remaining container volume."""
        amount = round(float(ml), 1)
        self._sqlite_execute(
            [
                (
                    """
                    INSERT INTO containers(device_key, channel, volume_ml, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(device_key, channel) DO UPDATE SET
                        volume_ml=excluded.volume_ml,
                        updated_at=excluded.updated_at
                    """,
                    (self.address, int(pump_idx), amount, _utc_now()),
                )
            ]
        )
        self.data.setdefault("containers_ml", {})[str(pump_idx)] = amount
        if amount <= self._low_container_threshold_ml() and self.low_container_notification_enabled():
            self.data.setdefault("low_container_notified", {}).pop(str(pump_idx), None)
        self._sync_low_container_notification(pump_idx)
        if amount <= self._low_container_threshold_ml() and self.low_container_notification_enabled():
            await self.async_add_log(
                "Push Behaelterstand gesendet",
                pump_idx,
                f"{amount:.1f} mL <= {self._low_container_threshold_ml():.1f} mL",
            )
        await self.async_add_log("Behaelter gesetzt", pump_idx, f"{amount:.1f} mL")

    async def async_record_manual_dose_ml(self, pump_idx: int, ml: float) -> None:
        """Add one successful manual dose to local totals and remaining volume."""
        amount = round(float(ml), 1)
        key = str(pump_idx)
        day = _today()
        now = _utc_now()
        current_remaining = self.container_ml(pump_idx)
        next_remaining = round(max(0.0, current_remaining - amount), 1)
        self._sqlite_execute(
            [
                (
                    """
                    INSERT INTO manual_history(device_key, channel, ml, ts, day)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.address, int(pump_idx), amount, now, day),
                ),
                (
                    """
                    INSERT INTO manual_daily(device_key, channel, day, ml)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(device_key, channel, day) DO UPDATE SET
                        ml=round(manual_daily.ml + excluded.ml, 3)
                    """,
                    (self.address, int(pump_idx), day, amount),
                ),
                (
                    """
                    INSERT INTO containers(device_key, channel, volume_ml, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(device_key, channel) DO UPDATE SET
                        volume_ml=excluded.volume_ml,
                        updated_at=excluded.updated_at
                    """,
                    (self.address, int(pump_idx), next_remaining, now),
                ),
            ]
        )
        self.data.setdefault("manual_daily_ml", {})
        self.data["manual_daily_ml"][key] = round(float(self.data["manual_daily_ml"].get(key, 0.0)) + amount, 1)
        self.data.setdefault("containers_ml", {})
        self.data["containers_ml"][key] = next_remaining
        self._sync_low_container_notification(pump_idx)
        await self.async_add_log("Manuelle Dosierung", pump_idx, f"{amount:.1f} mL")

    async def async_record_auto_dose_ml(self, pump_idx: int, ml: float) -> None:
        """Add one automatic dose to local remaining volume and log."""
        amount = round(float(ml), 1)
        key = str(pump_idx)
        self.data.setdefault("containers_ml", {})
        remaining = float(self.data["containers_ml"].get(key, DEFAULT_CONTAINER_ML))
        self.data["containers_ml"][key] = round(max(0.0, remaining - amount), 1)
        self._sync_low_container_notification(pump_idx)
        await self.async_add_log("Automatische Dosierung", pump_idx, f"{amount:.1f} mL")

    async def async_set_auto_daily_values(self, values_ml: list[float], mode: int = 0x1E) -> None:
        """Store automatic daily values read from the physical device."""
        now = _utc_now()
        day = _today()
        values = [round(float(value), 1) for value in values_ml[: self.pump_count]]
        raw_json = json.dumps({"mode": int(mode), "values_ml": values}, ensure_ascii=False)
        self._sqlite_execute(
            [
                (
                    """
                    INSERT INTO doser_auto_totals(device_key, channel, day, mode, ml, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_key, channel, day, mode) DO UPDATE SET
                        ml=excluded.ml,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (self.address, channel, day, int(mode), value, raw_json, now),
                )
                for channel, value in enumerate(values)
            ]
        )
        await self.async_add_log(
            "Tageswerte vom Geraet", None, ", ".join(f"CH{idx + 1} {value:.1f} mL" for idx, value in enumerate(values))
        )

    async def async_record_auto_total_checkpoint(
        self,
        label: str,
        values_ml: list[float],
        *,
        mode: int = 0x1E,
        channel: int | None = None,
        run_at: Any = None,
    ) -> None:
        """Record one automatic-total checkpoint around a scheduled run."""
        values = [round(float(value), 1) for value in values_ml[: self.pump_count]]
        detail = ", ".join(f"CH{idx + 1} {value:.1f} mL" for idx, value in enumerate(values))
        self._sqlite_record_action(
            "auto_total_checkpoint",
            channel,
            {
                "label": str(label),
                "mode": int(mode),
                "values": values,
                "run_at": run_at.isoformat() if hasattr(run_at, "isoformat") else None,
            },
            "ok",
            detail,
        )
        await self.async_add_log(f"Tageswerte {label}", channel, detail)

    async def async_record_auto_total_read_failure(
        self,
        label: str,
        detail: str,
        *,
        channel: int | None = None,
        run_at: Any = None,
        mode: int = 0x1E,
    ) -> None:
        """Record a failed automatic-total checkpoint without raising from its background task."""
        self._sqlite_record_action(
            "auto_total_checkpoint",
            channel,
            {
                "label": str(label),
                "mode": int(mode),
                "run_at": run_at.isoformat() if hasattr(run_at, "isoformat") else None,
            },
            "error",
            str(detail),
        )

    async def async_record_notification_poll(
        self,
        status: str,
        detail: str,
        values_ml: list[float] | None = None,
        *,
        interval_minutes: int = 15,
        mode: int = 0x1E,
        raw_frames: list[bytes] | None = None,
    ) -> None:
        """Record one periodic Doser notification read in the shared history."""
        values = [round(float(value), 1) for value in (values_ml or [])[: self.pump_count]]
        frames = [bytes(frame).hex(" ").upper() for frame in (raw_frames or [])[:16]]
        self._sqlite_record_action(
            "doser_notification_poll",
            None,
            {
                "interval_minutes": int(interval_minutes),
                "mode": int(mode),
                "values": values,
                "raw_frames": frames,
            },
            str(status),
            str(detail),
        )
        await self.async_save()

    async def async_apply_auto_daily_delta(
        self,
        before_ml: list[float],
        after_ml: list[float],
        *,
        mode: int = 0x1E,
        channel: int | None = None,
        run_at: Any = None,
    ) -> None:
        """Subtract positive automatic daily deltas from local containers."""
        deltas: list[float] = []
        for idx in range(self.pump_count):
            if channel is not None and idx != channel:
                deltas.append(0.0)
                continue
            before = float(before_ml[idx]) if idx < len(before_ml) else 0.0
            after = float(after_ml[idx]) if idx < len(after_ml) else 0.0
            deltas.append(round(max(0.0, after - before), 1))
        if not any(value > 0 for value in deltas):
            return
        now = _utc_now()
        statements: list[tuple[str, tuple[Any, ...]]] = []
        for idx, delta in enumerate(deltas):
            if delta <= 0:
                continue
            next_remaining = round(max(0.0, self.container_ml(idx) - delta), 1)
            statements.append(
                (
                    """
                    INSERT INTO containers(device_key, channel, volume_ml, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(device_key, channel) DO UPDATE SET
                        volume_ml=excluded.volume_ml,
                        updated_at=excluded.updated_at
                    """,
                    (self.address, idx, next_remaining, now),
                )
            )
            self.data.setdefault("containers_ml", {})[str(idx)] = next_remaining
        statements.append(
            (
                """
                INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    "",
                    self.address,
                    "auto_dose_delta",
                    channel,
                    json.dumps(
                        {
                            "mode": int(mode),
                            "before": before_ml,
                            "after": after_ml,
                            "delta": deltas,
                            "run_at": run_at.isoformat() if hasattr(run_at, "isoformat") else None,
                        },
                        ensure_ascii=False,
                    ),
                    "ok",
                    ", ".join(f"CH{idx + 1} {value:.1f} mL" for idx, value in enumerate(deltas)),
                ),
            )
        )
        self._sqlite_execute(statements)
        for idx, delta in enumerate(deltas):
            if delta > 0:
                self._sync_low_container_notification(idx)
        await self.async_add_log(
            "Auto-Differenz", channel, ", ".join(f"CH{idx + 1} {value:.1f} mL" for idx, value in enumerate(deltas))
        )

    def schedule(self, pump_idx: int) -> DoserSchedule | None:
        """Return local schedule row for one pump."""
        row = self._sqlite_schedule_row(pump_idx)
        if row is not None:
            type_id = int(row.get("schedule_type_id") or schedule_type_id(row.get("schedule_kind") or "single_dose"))
            kind = schedule_kind_from_id(type_id, str(row.get("schedule_kind") or "single_dose"))
            entries = []
            try:
                entries = json.loads(str(row.get("entries_json") or "[]"))
            except json.JSONDecodeError:
                entries = []
            interval_minutes = None
            if kind == "interval" and entries and isinstance(entries[0], dict):
                interval_minutes = int(entries[0].get("minute") or 0)
            timer_entries = tuple(
                (
                    f"{int(entry.get('hour') or 0):02d}:{int(entry.get('minute') or 0):02d}",
                    round(float(entry.get("ml") or 0.0), 1),
                )
                for entry in entries
                if kind == "timer" and isinstance(entry, dict)
            )
            window_entries = tuple(
                (
                    f"{int(entry.get('start_hour') or 0):02d}:{int(entry.get('start_minute') or 0):02d}",
                    f"{int(entry.get('end_hour') or 0):02d}:{int(entry.get('end_minute') or 0):02d}",
                    int(entry.get("value") or 1),
                )
                for entry in entries
                if kind == "window" and isinstance(entry, dict)
            )
            return DoserSchedule(
                pump_idx=pump_idx,
                active=bool(int(row.get("enabled") or 0)),
                time=str(row.get("schedule_time") or "00:00"),
                ml=round(float(row.get("dose_ml") or 0.0), 1),
                weekdays=self._weekdays_from_mask(int(row.get("weekdays_mask") or 127)),
                kind=kind,
                interval_minutes=interval_minutes,
                timer_entries=timer_entries,
                window_entries=window_entries,
                schedule_type_id=type_id,
                valid_from_tomorrow=bool(int(row.get("valid_from_tomorrow") or 0))
                if "valid_from_tomorrow" in row
                else False,
            )
        raw = self.data.get("schedules", {}).get(str(pump_idx))
        if not isinstance(raw, dict):
            return None
        try:
            weekdays = raw.get("weekdays", ["everyday"])
            return DoserSchedule(
                pump_idx=pump_idx,
                active=bool(raw.get("active", True)),
                time=str(raw.get("time", "00:00")),
                ml=float(raw.get("ml", 0.0)),
                weekdays=tuple(str(day) for day in weekdays),
                kind=schedule_kind_from_id(raw.get("schedule_type_id"), str(raw.get("kind", "single_dose"))),
                interval_minutes=int(raw["interval_minutes"]) if "interval_minutes" in raw else None,
                timer_entries=tuple(
                    (str(entry.get("time") or "00:00"), round(float(entry.get("ml") or 0.0), 1))
                    for entry in raw.get("timer_entries", [])
                    if isinstance(entry, dict)
                ),
                window_entries=tuple(
                    (
                        str(entry.get("start") or "00:00"),
                        str(entry.get("end") or "00:00"),
                        int(entry.get("doses") or 1),
                    )
                    for entry in raw.get("window_entries", [])
                    if isinstance(entry, dict)
                ),
                schedule_type_id=int(raw["schedule_type_id"]) if "schedule_type_id" in raw else None,
                valid_from_tomorrow=bool(raw.get("valid_from_tomorrow", False)),
            )
        except (TypeError, ValueError):
            return None

    async def async_set_schedule(self, schedule: DoserSchedule) -> None:
        """Persist one local schedule row."""
        kind = str(schedule.kind or "single_dose")
        type_id = schedule_type_id(kind)
        interval_minutes = schedule.interval_minutes
        if kind == "interval":
            interval_minutes = max(0, min(59, int(interval_minutes if interval_minutes is not None else 0)))
            schedule_time = f"00:{interval_minutes:02d}"
            timer_type = 1
            entries = [{"hour": 0, "minute": interval_minutes, "value": 0}]
        elif kind == "timer":
            timer_entries = tuple(schedule.timer_entries)
            schedule_time = timer_entries[0][0] if timer_entries else "00:00"
            timer_type = 3
            entries = []
            for time_text, ml in timer_entries:
                hour, minute = [int(part) for part in str(time_text).split(":", 1)]
                entries.append({"hour": hour, "minute": minute, "ml": round(float(ml), 1)})
        elif kind == "window":
            window_entries = tuple(schedule.window_entries)
            schedule_time = window_entries[0][0] if window_entries else "00:00"
            timer_type = 0
            entries = []
            for start_text, end_text, doses in window_entries:
                start_hour, start_minute = [int(part) for part in str(start_text).split(":", 1)]
                end_hour, end_minute = [int(part) for part in str(end_text).split(":", 1)]
                entries.append(
                    {
                        "start_hour": start_hour,
                        "start_minute": start_minute,
                        "end_hour": end_hour,
                        "end_minute": end_minute,
                        "value": int(doses),
                    }
                )
        else:
            schedule_time = str(schedule.time)
            timer_type = 0
            entries = []
        self._sqlite_execute(
            [
                (
                    "DELETE FROM doser_schedules WHERE device_key=? AND channel=?",
                    (self.address, int(schedule.pump_idx)),
                ),
                (
                    """
                    INSERT INTO doser_schedules(
                        device_key, channel, schedule_kind, schedule_type_id, schedule_time, weekdays_mask,
                        dose_ml, timer_type, entries_json, enabled, valid_from_tomorrow, source, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.address,
                        int(schedule.pump_idx),
                        kind,
                        type_id,
                        schedule_time,
                        self._weekdays_mask(schedule.weekdays),
                        round(float(schedule.ml), 1),
                        timer_type,
                        json.dumps(entries, ensure_ascii=False),
                        1 if schedule.active else 0,
                        1 if schedule.valid_from_tomorrow else 0,
                        "home-assistant",
                        _utc_now(),
                    ),
                ),
            ]
        )
        self.data.setdefault("schedules", {})[str(schedule.pump_idx)] = {
            "active": schedule.active,
            "time": schedule_time,
            "ml": round(float(schedule.ml), 1),
            "weekdays": list(schedule.weekdays),
            "kind": kind,
            "schedule_type_id": type_id,
            "valid_from_tomorrow": bool(schedule.valid_from_tomorrow),
        }
        if kind == "timer":
            self.data["schedules"][str(schedule.pump_idx)]["timer_entries"] = [
                {"time": time_text, "ml": round(float(ml), 1)} for time_text, ml in schedule.timer_entries
            ]
        if kind == "window":
            self.data["schedules"][str(schedule.pump_idx)]["window_entries"] = [
                {"start": start, "end": end, "doses": int(doses)} for start, end, doses in schedule.window_entries
            ]
        if interval_minutes is not None:
            self.data["schedules"][str(schedule.pump_idx)]["interval_minutes"] = interval_minutes
        state = "aktiv" if schedule.active else "inaktiv"
        valid_detail = ", gueltig ab morgen" if schedule.valid_from_tomorrow else ""
        self._sqlite_record_action(
            "set_doser_schedule",
            schedule.pump_idx,
            {
                "active": bool(schedule.active),
                "schedule_kind": kind,
                "schedule_type_id": type_id,
                "time": schedule_time,
                "ml": round(float(schedule.ml), 1),
                "interval_minutes": interval_minutes,
                "timer_entries": [
                    {"time": time_text, "ml": round(float(ml), 1)} for time_text, ml in schedule.timer_entries
                ],
                "window_entries": [
                    {"start": start, "end": end, "doses": int(doses)} for start, end, doses in schedule.window_entries
                ],
                "weekdays": list(schedule.weekdays),
                "valid_from_tomorrow": bool(schedule.valid_from_tomorrow),
            },
            "ok",
            "lokal gespeichert",
        )
        await self.async_add_log(
            "Zeitplan gespeichert",
            schedule.pump_idx,
            f"{state}, {kind}, {schedule_time}, {schedule.ml:.1f} mL{valid_detail}",
        )

    async def async_record_schedule_set_send_status(
        self,
        pump_idx: int,
        send_status: str,
        send_detail: str = "",
    ) -> None:
        """Record whether a schedule write was sent to the physical device."""
        schedule = self.data.get("schedules", {}).get(str(pump_idx), {})
        schedule_params = dict(schedule) if isinstance(schedule, dict) else {}
        self._sqlite_record_action(
            "set_doser_schedule_send",
            pump_idx,
            {"send_status": send_status, **schedule_params},
            send_status,
            send_detail,
        )
        if send_status == "ok":
            await self.async_add_log("Geraet senden OK", pump_idx, send_detail or "Zeitplan gesendet")
        elif send_status == "error":
            await self.async_add_log("Geraet senden FAIL", pump_idx, send_detail or "Zeitplan nicht gesendet")
        else:
            await self.async_add_log(
                "Geraet senden nicht angefordert", pump_idx, send_detail or "nur lokal gespeichert"
            )

    async def async_reset_schedule(
        self,
        pump_idx: int,
    ) -> None:
        """Remove one local schedule row."""
        deleted_sqlite = self._sqlite_execute(
            [
                (
                    "DELETE FROM doser_schedules WHERE device_key=? AND channel=?",
                    (self.address, int(pump_idx)),
                )
            ]
        )
        self.data.setdefault("schedules", {}).pop(str(pump_idx), None)
        self._sqlite_record_action(
            "reset_doser_schedule",
            pump_idx,
            {"deleted_local": bool(deleted_sqlite)},
            "ok",
            "lokal zurueckgesetzt",
        )
        await self.async_add_log("Zeitplan zurueckgesetzt", pump_idx)

    async def async_disable_schedule_for_safety(
        self,
        pump_idx: int,
    ) -> None:
        """Mark one local schedule inactive after the safety limit was reached."""
        now = _utc_now()
        self._sqlite_execute(
            [
                (
                    """
                    UPDATE doser_schedules
                    SET enabled=0, updated_at=?
                    WHERE device_key=? AND channel=?
                    """,
                    (now, self.address, int(pump_idx)),
                )
            ]
        )
        raw = self.data.setdefault("schedules", {}).get(str(pump_idx))
        if isinstance(raw, dict):
            raw["active"] = False
        await self.async_save()

    async def async_record_schedule_reset_send_status(
        self,
        pump_idx: int,
        send_status: str,
        send_detail: str = "",
    ) -> None:
        """Record whether the reset command was sent to the physical device."""
        self._sqlite_record_action(
            "reset_doser_schedule_send",
            pump_idx,
            {"send_status": send_status},
            send_status,
            send_detail,
        )
        if send_status == "ok":
            await self.async_add_log("Geraet senden OK", pump_idx, send_detail or "Zeitplan deaktiviert")
        elif send_status == "error":
            await self.async_add_log("Geraet senden FAIL", pump_idx, send_detail or "Zeitplan nicht deaktiviert")
        else:
            await self.async_add_log("Geraet senden nicht angefordert", pump_idx, send_detail or "nur lokal geloescht")

    def auto_daily_ml(self, pump_idx: int) -> float:
        """Return locally stored automatic daily amount for display."""
        rows = self._sqlite_rows(
            """
            SELECT ml
            FROM doser_auto_totals
            WHERE device_key=? AND channel=? AND day=?
            ORDER BY CASE WHEN mode=30 THEN 0 ELSE 1 END, updated_at DESC
            LIMIT 1
            """,
            (self.address, int(pump_idx), _today()),
        )
        if rows:
            return round(float(rows[0].get("ml") or 0.0), 1)
        return 0.0

    def manual_daily_ml(self, pump_idx: int) -> float:
        """Return locally stored manual daily amount for display."""
        rows = self._sqlite_rows(
            """
            SELECT ml
            FROM manual_daily
            WHERE device_key=? AND channel=? AND day=?
            LIMIT 1
            """,
            (self.address, int(pump_idx), _today()),
        )
        if rows:
            return round(float(rows[0].get("ml") or 0.0), 1)
        self._ensure_today()
        return float(self.data.get("manual_daily_ml", {}).get(str(pump_idx), 0.0))


async def async_store_for_device(hass: HomeAssistant, address: str, pump_count: int = 4) -> DoserExtStore:
    """Create and load the extension store for one device."""
    store = DoserExtStore(hass, address, pump_count)
    await store.async_load()
    return store
