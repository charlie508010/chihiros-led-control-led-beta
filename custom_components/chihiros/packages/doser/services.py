"""Service registration for optional dosing-pump extensions."""

# ruff: noqa: E501

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import time
from typing import Any, cast

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from ...common.debug import make_service_result
from ...const import DOMAIN
from ...models import ChihirosData
from ...runtime import DosingChihirosClient
from .protocol import (
    calibration_prime_frames,
    calibration_start_frames,
    calibration_submit_frames,
    calibration_test_frames,
    dosing_auth_frames,
    schedule_disable_frames,
    timer_schedule_frames,
    weekday_mask,
    window_schedule_frames,
)
from .storage import async_store_for_device
from .types import DoserSchedule

SEND_TIMEOUT_SECONDS = 45

SERVICE_DOSE_ML = "dose_ml"
SERVICE_SET_DOSER_SCHEDULE = "set_doser_schedule"
SERVICE_RESET_DOSER_SCHEDULE = "reset_doser_schedule"
SERVICE_SET_DOSER_CONTAINER = "set_doser_container"
SERVICE_SET_DOSER_PUSH_SETTINGS = "set_doser_push_settings"
SERVICE_SET_DOSER_SAFETY = "set_doser_safety"
SERVICE_START_DOSER_CALIBRATION = "start_doser_calibration"
SERVICE_SUBMIT_DOSER_CALIBRATION = "submit_doser_calibration"
SERVICE_PRIME_DOSER_CALIBRATION = "prime_doser_calibration"
SERVICE_TEST_DOSER_CALIBRATION = "test_doser_calibration"

ATTR_ADDRESS = "address"
ATTR_ACTIVE = "active"
ATTR_DEBUG = "debug"
ATTR_ENTRY_ID = "entry_id"
ATTR_INTERVAL = "interval"
ATTR_KIND = "kind"
ATTR_ML = "ml"
ATTR_MESSAGE = "message"
ATTR_MAX_AUTO_ML = "max_auto_ml"
ATTR_MAX_DAILY_ML = "max_daily_ml"
ATTR_MAX_MANUAL_ML = "max_manual_ml"
ATTR_MAX_SINGLE_ML = "max_single_ml"
ATTR_PUMP = "pump"
ATTR_SEND = "send"
ATTR_ENABLED = "enabled"
ATTR_TARGETS = "targets"
ATTR_TEST_ML = "test_ml"
ATTR_TIMERS = "timers"
ATTR_WINDOWS = "windows"
ATTR_DURATION = "duration"
ATTR_REMINDER_DAYS = "reminder_days"
ATTR_TIME = "time"
ATTR_VALID_FROM_TOMORROW = "valid_from_tomorrow"
ATTR_WEEKDAYS = "weekdays"

SELECTOR_SCHEMA = {
    vol.Optional(ATTR_ENTRY_ID): str,
    vol.Optional(ATTR_ADDRESS): str,
}
PUMP_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=4))
ML_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=999.9))
TIMER_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TIME): str,
        vol.Required(ATTR_ML): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=999.9)),
    }
)
WINDOW_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Required("doses"): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
    }
)

DOSE_ML_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Required(ATTR_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=999.9)),
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)
SET_DOSER_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Optional(ATTR_ACTIVE, default=True): bool,
        vol.Optional(ATTR_KIND, default="single_dose"): vol.In(["single_dose", "interval", "timer", "window"]),
        vol.Optional(ATTR_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        vol.Optional(ATTR_TIMERS, default=[]): vol.All(list, [TIMER_ENTRY_SCHEMA]),
        vol.Optional(ATTR_WINDOWS, default=[]): vol.All(list, [WINDOW_ENTRY_SCHEMA]),
        vol.Optional(ATTR_TIME): str,
        vol.Required(ATTR_ML): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=999.9)),
        vol.Optional(ATTR_WEEKDAYS, default=["everyday"]): vol.All(list, [str]),
        vol.Optional(ATTR_SEND, default=False): bool,
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_VALID_FROM_TOMORROW, default=False): bool,
    }
)


def _normalize_timer_entries(raw_entries: list[dict[str, Any]]) -> tuple[tuple[str, float], ...]:
    """Validate and chronologically normalize one app-style timer list."""
    if not 1 <= len(raw_entries) <= 24:
        raise HomeAssistantError("Timerlisten brauchen 1 bis 24 Einzeldosierungen")
    normalized: list[tuple[int, str, float]] = []
    for entry in raw_entries:
        time_text = str(entry.get(ATTR_TIME) or "")
        try:
            hour_text, minute_text = time_text.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            amount_ml = round(float(entry.get(ATTR_ML)), 1)
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("Timer-Eintraege brauchen eine gueltige Uhrzeit und Menge") from err
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise HomeAssistantError(f"Ungueltige Timer-Uhrzeit: {time_text}")
        if amount_ml < 0.1:
            raise HomeAssistantError("Timer-Einzelmengen muessen mindestens 0,1 ml betragen")
        normalized.append((hour * 60 + minute, f"{hour:02d}:{minute:02d}", amount_ml))
    normalized.sort(key=lambda item: item[0])
    minutes = [item[0] for item in normalized]
    if len(set(minutes)) != len(minutes):
        raise HomeAssistantError("Timer-Uhrzeiten duerfen nicht doppelt vorkommen")
    for index, current in enumerate(minutes):
        following = minutes[(index + 1) % len(minutes)] + (1440 if index == len(minutes) - 1 else 0)
        if following - current < 10:
            raise HomeAssistantError("Zwischen Timer-Einzeldosierungen muessen mindestens 10 Minuten liegen")
    entries = tuple((time_text, amount_ml) for _minute, time_text, amount_ml in normalized)
    if round(sum(amount_ml for _time_text, amount_ml in entries), 1) > 999.9:
        raise HomeAssistantError("Die Timer-Tagesmenge darf hoechstens 999,9 ml betragen")
    return entries


def _normalize_window_entries(raw_entries: list[dict[str, Any]]) -> tuple[tuple[str, str, int], ...]:
    """Validate custom time windows and their resulting daily dose positions."""
    if not raw_entries:
        raise HomeAssistantError("Benutzerdefinierte Plaene brauchen mindestens ein Zeitfenster")
    normalized: list[tuple[int, int, str, str, int]] = []
    total_doses = 0
    for entry in raw_entries:
        try:
            start_hour, start_minute = [int(part) for part in str(entry.get("start") or "").split(":", 1)]
            end_hour, end_minute = [int(part) for part in str(entry.get("end") or "").split(":", 1)]
            doses = int(entry.get("doses"))
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("Zeitfenster brauchen Start, Ende und Anzahl Dosierungen") from err
        if not 0 <= start_hour <= 23 or not 0 <= start_minute <= 59:
            raise HomeAssistantError("Ungueltiger Beginn im benutzerdefinierten Zeitfenster")
        if not 0 <= end_hour <= 23 or not 0 <= end_minute <= 59:
            raise HomeAssistantError("Ungueltiges Ende im benutzerdefinierten Zeitfenster")
        if not 1 <= doses <= 24:
            raise HomeAssistantError("Pro Zeitfenster sind 1 bis 24 Dosierungen erlaubt")
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if end < start or (end == start and doses > 1):
            raise HomeAssistantError("Das Ende eines Zeitfensters muss nach seinem Beginn liegen")
        duration = end - start
        if doses > 1 and duration > 30 * (doses - 1):
            raise HomeAssistantError("Zwischen benutzerdefinierten Dosierungen duerfen hoechstens 30 Minuten liegen")
        total_doses += doses
        normalized.append(
            (start, end, f"{start_hour:02d}:{start_minute:02d}", f"{end_hour:02d}:{end_minute:02d}", doses)
        )
    if total_doses > 24:
        raise HomeAssistantError("Benutzerdefinierte Plaene duerfen insgesamt hoechstens 24 Dosierungen enthalten")
    normalized.sort(key=lambda item: (item[0], item[1]))
    return tuple((start_text, end_text, doses) for _start, _end, start_text, end_text, doses in normalized)


RESET_DOSER_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Optional(ATTR_SEND, default=False): bool,
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)
SET_DOSER_CONTAINER_SCHEMA = vol.Schema(
    {**SELECTOR_SCHEMA, vol.Required(ATTR_PUMP): PUMP_SCHEMA, vol.Required(ATTR_ML): ML_SCHEMA}
)
SET_DOSER_PUSH_SETTINGS_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_ENABLED): bool,
        vol.Optional(ATTR_TARGETS, default=[]): vol.All(list, [str]),
        vol.Optional(ATTR_MESSAGE): str,
    }
)
SET_DOSER_SAFETY_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Optional(ATTR_MAX_AUTO_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=999.9)),
        vol.Optional(ATTR_MAX_MANUAL_ML): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=999.9)),
        vol.Optional(ATTR_MAX_SINGLE_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=999.9)),
        vol.Required(ATTR_MAX_DAILY_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=9999.9)),
    }
)
START_DOSER_CALIBRATION_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)
PRIME_DOSER_CALIBRATION_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Optional(ATTR_DURATION, default=3.0): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30.0)),
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)
SUBMIT_DOSER_CALIBRATION_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Required(ATTR_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=255.99)),
        vol.Optional(ATTR_TEST_ML): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=999.9)),
        vol.Optional(ATTR_REMINDER_DAYS, default=30): vol.All(vol.Coerce(int), vol.Range(min=1, max=3650)),
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)
TEST_DOSER_CALIBRATION_SCHEMA = vol.Schema(
    {
        **SELECTOR_SCHEMA,
        vol.Required(ATTR_PUMP): PUMP_SCHEMA,
        vol.Optional(ATTR_DEBUG, default=False): bool,
    }
)

Resolver = Callable[[dict[str, Any]], ChihirosData]


def _prepare_device_debug(device: Any, enabled: bool) -> None:
    if not enabled:
        return
    try:
        set_log_level = getattr(device, "set_log_level", None)
        if callable(set_log_level):
            set_log_level("DEBUG")
        clear_buffers = getattr(device, "clear_debug_buffers", None)
        if callable(clear_buffers):
            clear_buffers()
    except Exception:
        pass


def _device_protocol_debug(device: Any) -> str:
    try:
        render_protocol_debug = getattr(device, "render_protocol_debug", None)
        if callable(render_protocol_debug):
            return str(render_protocol_debug(tx_commands={0x5A, 0xA5}, dedupe_rx=True) or "").strip()
    except Exception as ex:
        return "\n".join(
            line
            for line in [
                f"Device: {getattr(device, 'name', '')}",
                f"Address: {getattr(device, 'address', '')}",
                f"Debug fallback error: {type(ex).__name__}: {ex}",
            ]
            if line.strip()
        )
    return ""


def _response_requested(call: ServiceCall) -> bool:
    return bool(getattr(call, "return_response", False))


def async_update_doser_services(hass: HomeAssistant, has_dosing_device: bool, resolve: Resolver) -> None:
    """Register or remove all Doser services depending on configured devices."""
    if has_dosing_device:
        _async_register_manual_dosing_service(hass, resolve)
    else:
        _async_remove_manual_dosing_service(hass)
    async_update_doser_extension_services(hass, has_dosing_device, resolve)


def _async_register_manual_dosing_service(hass: HomeAssistant, resolve: Resolver) -> None:
    """Register the manual dose service once."""

    async def async_dose_ml(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        volume_ml = float(call.data[ATTR_ML])
        debug = bool(call.data[ATTR_DEBUG])
        if pump_idx >= chihiros_data.dosing_totals.pump_count:
            raise HomeAssistantError(f"{chihiros_data.device.name} has {chihiros_data.dosing_totals.pump_count} pumps")
        _prepare_device_debug(chihiros_data.device, debug)
        try:
            await async_trigger_dose_ml(chihiros_data, pump_idx, volume_ml)
            store = await _store_for(chihiros_data, hass)
            await store.async_record_manual_dose_ml(pump_idx, volume_ml)
        except Exception as ex:
            result = make_service_result(
                service=SERVICE_DOSE_ML,
                ok=False,
                send_status="error",
                send_detail=str(ex),
                debug=debug,
                device=chihiros_data.device.name,
                address=chihiros_data.device.address,
                action="manual_dose",
                summary=f"Doser CH{pump_idx + 1} manual dose failed",
                request={"pump": pump_idx + 1, "ml": volume_ml},
                response={"ok": False, "error_type": type(ex).__name__, "error": str(ex)},
                raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
            )
            if _response_requested(call):
                return result
            raise
        result = make_service_result(
            service=SERVICE_DOSE_ML,
            ok=True,
            send_status="ok",
            send_detail="an Geraet gesendet",
            debug=debug,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="manual_dose",
            summary=f"Doser CH{pump_idx + 1} manual dose {volume_ml:.1f} mL",
            request={"pump": pump_idx + 1, "ml": volume_ml},
            response={"ok": True, "pump": pump_idx + 1, "ml": volume_ml},
            raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
        )
        return result if _response_requested(call) else None

    if hass.services.has_service(DOMAIN, SERVICE_DOSE_ML):
        hass.services.async_remove(DOMAIN, SERVICE_DOSE_ML)
    hass.services.async_register(
        DOMAIN,
        SERVICE_DOSE_ML,
        async_dose_ml,
        schema=DOSE_ML_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _async_remove_manual_dosing_service(hass: HomeAssistant) -> None:
    """Remove the manual dose service if it is registered."""
    if hass.services.has_service(DOMAIN, SERVICE_DOSE_ML):
        hass.services.async_remove(DOMAIN, SERVICE_DOSE_ML)


async def async_trigger_dose_ml(chihiros_data: ChihirosData, pump_idx: int, volume_ml: float) -> None:
    """Trigger a manual dose and update local totals."""
    chihiros_data = _ensure_doser(chihiros_data)
    store = await _store_for(chihiros_data, chihiros_data.coordinator.hass)
    safety = store.doser_safety_limits()
    current_manual_daily = chihiros_data.dosing_totals.total_ml(pump_idx)
    next_manual_daily = round(current_manual_daily + float(volume_ml), 1)
    if next_manual_daily > safety["max_manual_ml"]:
        detail = (
            f"CH{pump_idx + 1}: Manuell {next_manual_daily:.1f} mL > Limit "
            f"{safety['max_manual_ml']:.1f} mL. Manuelle Dosierung wurde blockiert."
        )
        await store.async_add_log("Ueberdosierungsschutz BLOCK", pump_idx, detail)
        _notify_doser_safety_blocked(chihiros_data.coordinator.hass, chihiros_data, pump_idx, detail)
        raise HomeAssistantError(f"Ueberdosierungsschutz: {detail}")
    current_daily = chihiros_data.dosing_totals.total_ml(pump_idx)
    next_daily = round(current_daily + float(volume_ml), 1)
    if next_daily > safety["max_daily_ml"]:
        detail = (
            f"CH{pump_idx + 1}: Tagesmenge {next_daily:.1f} mL > Limit "
            f"{safety['max_daily_ml']:.1f} mL. Manuelle Dosierung wurde blockiert."
        )
        await store.async_add_log("Ueberdosierungsschutz BLOCK", pump_idx, detail)
        _notify_doser_safety_blocked(chihiros_data.coordinator.hass, chihiros_data, pump_idx, detail)
        raise HomeAssistantError(f"Ueberdosierungsschutz: {detail}")
    dosing_device = cast(DosingChihirosClient, chihiros_data.device)
    await dosing_device.dose_ml(pump_idx, volume_ml)
    await chihiros_data.dosing_totals.async_add_dose(pump_idx, volume_ml)


def async_update_doser_extension_services(hass: HomeAssistant, has_dosing_device: bool, resolve: Resolver) -> None:
    """Register or remove extension services depending on configured devices."""
    services = (
        SERVICE_SET_DOSER_SCHEDULE,
        SERVICE_RESET_DOSER_SCHEDULE,
        SERVICE_SET_DOSER_CONTAINER,
        SERVICE_SET_DOSER_PUSH_SETTINGS,
        SERVICE_SET_DOSER_SAFETY,
        SERVICE_START_DOSER_CALIBRATION,
        SERVICE_SUBMIT_DOSER_CALIBRATION,
        SERVICE_PRIME_DOSER_CALIBRATION,
        SERVICE_TEST_DOSER_CALIBRATION,
    )
    if not has_dosing_device:
        for service in services:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
        return

    async def _async_set_doser_schedule_impl(call: ServiceCall) -> dict[str, Any] | None:
        send_requested = bool(call.data[ATTR_SEND])
        requested_address = str(call.data.get(ATTR_ADDRESS) or "").strip().upper()
        if not send_requested and requested_address:
            chihiros_data = None
        else:
            chihiros_data = _ensure_doser(resolve(call.data))
        if chihiros_data is None:
            store = await async_store_for_device(hass, requested_address, 4)
            device_name = requested_address
            device_address = requested_address
        else:
            store = await _store_for(chihiros_data, hass)
            device_name = chihiros_data.device.name
            device_address = chihiros_data.device.address
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        kind = str(call.data[ATTR_KIND])
        interval_minutes = int(call.data[ATTR_INTERVAL]) if ATTR_INTERVAL in call.data else None
        timer_entries: tuple[tuple[str, float], ...] = ()
        window_entries: tuple[tuple[str, str, int], ...] = ()
        if kind == "interval":
            if interval_minutes is None:
                raise HomeAssistantError("Intervall-Zeitplaene brauchen das Feld interval")
            schedule_time = f"00:{interval_minutes:02d}"
        elif kind == "timer":
            timer_entries = _normalize_timer_entries(list(call.data[ATTR_TIMERS]))
            schedule_time = timer_entries[0][0]
        elif kind == "window":
            window_entries = _normalize_window_entries(list(call.data[ATTR_WINDOWS]))
            schedule_time = window_entries[0][0]
        elif ATTR_TIME in call.data:
            schedule_time = str(call.data[ATTR_TIME])
        else:
            raise HomeAssistantError("Zeitplaene ohne Intervall brauchen das Feld time")
        schedule = DoserSchedule(
            pump_idx=pump_idx,
            active=bool(call.data[ATTR_ACTIVE]),
            time=schedule_time,
            ml=float(call.data[ATTR_ML]),
            weekdays=tuple(str(day) for day in call.data[ATTR_WEEKDAYS]),
            kind=kind,
            interval_minutes=interval_minutes,
            timer_entries=timer_entries,
            window_entries=window_entries,
            valid_from_tomorrow=bool(call.data[ATTR_VALID_FROM_TOMORROW]),
        )
        if schedule.kind != "timer" and schedule.ml < 0.2:
            raise HomeAssistantError("Dosiermengen brauchen mindestens 0.2 mL")
        if schedule.kind == "interval" and schedule.ml < 5.0:
            raise HomeAssistantError("Intervall-Zeitplaene brauchen mindestens 5.0 mL")
        if schedule.kind == "timer":
            schedule.ml = round(sum(amount_ml for _time_text, amount_ml in schedule.timer_entries), 1)
        safety = store.doser_safety_limits()
        if schedule.kind == "timer":
            max_single_ml = safety.get("max_single_ml", safety["max_auto_ml"])
            oversized = [amount_ml for _time_text, amount_ml in schedule.timer_entries if amount_ml > max_single_ml]
            if oversized:
                raise HomeAssistantError(
                    f"Ueberdosierungsschutz: Timer-Einzelmenge {max(oversized):.1f} mL > Limit {max_single_ml:.1f} mL"
                )
        auto_today_ml = store.auto_daily_ml(pump_idx)
        auto_limit_reached = auto_today_ml >= safety["max_auto_ml"]
        if auto_limit_reached and not schedule.valid_from_tomorrow:
            schedule.valid_from_tomorrow = True
            await store.async_add_log(
                "Ueberdosierungsschutz",
                pump_idx,
                (
                    f"Automatisch heute {auto_today_ml:.1f} mL >= Limit "
                    f"{safety['max_auto_ml']:.1f} mL; Zeitplan gueltig ab morgen"
                ),
            )
        if schedule.ml > safety["max_daily_ml"]:
            detail = (
                f"CH{pump_idx + 1}: Tagesmenge {schedule.ml:.1f} mL > Limit "
                f"{safety['max_daily_ml']:.1f} mL. Zeitplan wurde nicht gespeichert."
            )
            await store.async_add_log("Ueberdosierungsschutz BLOCK", pump_idx, detail)
            if chihiros_data is not None:
                _notify_doser_safety_blocked(hass, chihiros_data, pump_idx, detail)
            raise HomeAssistantError(f"Ueberdosierungsschutz: {detail}")
        try:
            await store.async_set_schedule(schedule)
        except Exception as ex:
            if not _response_requested(call):
                raise
            error_text = str(ex).strip() or type(ex).__name__
            return make_service_result(
                service=SERVICE_SET_DOSER_SCHEDULE,
                ok=False,
                send_status="error",
                send_detail=f"lokal nicht gespeichert: {type(ex).__name__}: {error_text}",
                debug=bool(call.data[ATTR_DEBUG]),
                device=device_name,
                address=device_address,
                action="set_doser_schedule",
                summary=f"Doser CH{pump_idx + 1} {kind} local save failed",
                request={
                    "pump": pump_idx + 1,
                    "active": schedule.active,
                    "kind": schedule.kind,
                    "time": schedule.time,
                    "timers": [{"time": time_text, "ml": amount_ml} for time_text, amount_ml in schedule.timer_entries],
                    "windows": [
                        {"start": start, "end": end, "doses": doses} for start, end, doses in schedule.window_entries
                    ],
                    "ml": schedule.ml,
                    "weekdays": list(schedule.weekdays),
                    "send": bool(call.data[ATTR_SEND]),
                },
                response={"ok": False, "error_type": type(ex).__name__, "error": error_text},
                raw_debug=f"Local Doser schedule save failed\n{type(ex).__name__}: {error_text}",
            )
        send_status = "local"
        send_detail = "nur lokal gespeichert"
        debug_output = ""
        if chihiros_data is not None:
            _prepare_device_debug(chihiros_data.device, bool(call.data[ATTR_DEBUG]))
        if send_requested:
            if chihiros_data is None:
                raise HomeAssistantError(f"Chihiros device address not found: {requested_address}")
            try:
                if schedule.active:
                    if schedule.valid_from_tomorrow:
                        disable_frames = schedule_disable_frames(chihiros_data.device.get_next_msg_id, pump_idx)
                        await asyncio.wait_for(
                            _send_extension_frames(chihiros_data, disable_frames),
                            timeout=SEND_TIMEOUT_SECONDS,
                        )
                        if bool(call.data[ATTR_DEBUG]):
                            debug_output = _device_protocol_debug(chihiros_data.device)
                            if debug_output:
                                debug_output = f"{debug_output}\n\n"
                    schedule_debug_output = await asyncio.wait_for(
                        _send_doser_schedule(hass, chihiros_data, schedule, bool(call.data[ATTR_DEBUG])),
                        timeout=SEND_TIMEOUT_SECONDS,
                    )
                    debug_output = f"{debug_output}{schedule_debug_output}"
                else:
                    frames = schedule_disable_frames(chihiros_data.device.get_next_msg_id, pump_idx)
                    await asyncio.wait_for(
                        _send_extension_frames(
                            chihiros_data,
                            frames,
                        ),
                        timeout=SEND_TIMEOUT_SECONDS,
                    )
                    if bool(call.data[ATTR_DEBUG]):
                        debug_output = _device_protocol_debug(chihiros_data.device)
            except TimeoutError:
                send_status = "error"
                send_detail = f"nicht an Geraet gesendet: Timeout nach {SEND_TIMEOUT_SECONDS}s"
            except Exception as ex:
                send_status = "error"
                error_text = str(ex).strip() or type(ex).__name__
                send_detail = f"nicht an Geraet gesendet: {error_text}"
                debug_output = getattr(ex, "debug_output", "") or debug_output
                if bool(call.data[ATTR_DEBUG]):
                    debug_output = debug_output or _device_protocol_debug(chihiros_data.device)
                    marker = "Service Debug Marker: doser-service-v2"
                    if marker not in debug_output:
                        diagnostic_hint = (
                            "\n\n"
                            f"{marker}\n"
                            "Wenn dieser Marker fehlt, laeuft in Home Assistant noch alter Integrationscode.\n"
                            "Dann Home Assistant Core neu starten oder die Chihiros Integration neu laden."
                        )
                        debug_output = f"{debug_output}{diagnostic_hint}" if debug_output else diagnostic_hint.strip()
            else:
                send_status = "ok"
                send_detail = "an Geraet gesendet" if schedule.active else "am Geraet deaktiviert"
                if schedule.active and schedule.valid_from_tomorrow:
                    send_detail = f"{send_detail}; gueltig ab morgen"
        try:
            await store.async_record_schedule_set_send_status(pump_idx, send_status, send_detail)
        except Exception as ex:
            error_text = str(ex).strip() or type(ex).__name__
            send_detail = (
                f"{send_detail}; Zeitplan gespeichert, Statusprotokoll fehlgeschlagen: "
                f"{type(ex).__name__}: {error_text}"
            )
        result = make_service_result(
            service=SERVICE_SET_DOSER_SCHEDULE,
            ok=send_status in ("ok", "local"),
            send_status=send_status,
            send_detail=send_detail,
            debug=bool(call.data[ATTR_DEBUG]),
            device=device_name,
            address=device_address,
            action="set_doser_schedule",
            summary=f"Doser CH{pump_idx + 1} {kind}",
            request={
                "pump": pump_idx + 1,
                "active": schedule.active,
                "kind": schedule.kind,
                "time": schedule.time,
                "interval": schedule.interval_minutes,
                "timers": [{"time": time_text, "ml": amount_ml} for time_text, amount_ml in schedule.timer_entries],
                "windows": [
                    {"start": start, "end": end, "doses": doses} for start, end, doses in schedule.window_entries
                ],
                "ml": schedule.ml,
                "weekdays": list(schedule.weekdays),
                "send": bool(call.data[ATTR_SEND]),
                "valid_from_tomorrow": schedule.valid_from_tomorrow,
            },
            response={
                "ok": send_status in ("ok", "local"),
                "send_status": send_status,
                "send_detail": send_detail,
            },
            details={
                "channel": pump_idx + 1,
                "channel_index": pump_idx,
                "auto_limit_reached": auto_limit_reached,
            },
            raw_debug=debug_output,
        )
        return result if _response_requested(call) else None

    async def async_set_doser_schedule(call: ServiceCall) -> dict[str, Any] | None:
        try:
            return await _async_set_doser_schedule_impl(call)
        except Exception as ex:
            if not _response_requested(call):
                raise
            error_text = str(ex).strip() or type(ex).__name__
            address = str(call.data.get(ATTR_ADDRESS) or "")
            pump = int(call.data.get(ATTR_PUMP) or 0)
            kind = str(call.data.get(ATTR_KIND) or "")
            return make_service_result(
                service=SERVICE_SET_DOSER_SCHEDULE,
                ok=False,
                send_status="error",
                send_detail=f"Zeitplan nicht gespeichert: {type(ex).__name__}: {error_text}",
                debug=bool(call.data.get(ATTR_DEBUG, False)),
                device=address,
                address=address,
                action="set_doser_schedule",
                summary=f"Doser CH{pump} {kind} failed before save",
                request=dict(call.data),
                response={"ok": False, "error_type": type(ex).__name__, "error": error_text},
                details={"service_debug_marker": "doser-schedule-service-v4-local-direct"},
                raw_debug=(
                    f"Service Debug Marker: doser-schedule-service-v4-local-direct\n{type(ex).__name__}: {error_text}"
                ),
            )

    async def async_reset_doser_schedule(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        store = await _store_for(chihiros_data, hass)
        await store.async_reset_schedule(pump_idx)
        send_status = "local"
        send_detail = "nur lokal geloescht"
        debug_output = ""
        _prepare_device_debug(chihiros_data.device, bool(call.data[ATTR_DEBUG]))
        if bool(call.data[ATTR_SEND]):
            try:
                frames = schedule_disable_frames(chihiros_data.device.get_next_msg_id, pump_idx)
                await asyncio.wait_for(
                    _send_extension_frames(
                        chihiros_data,
                        frames,
                    ),
                    timeout=SEND_TIMEOUT_SECONDS,
                )
                if bool(call.data[ATTR_DEBUG]):
                    debug_output = _device_protocol_debug(chihiros_data.device)
            except TimeoutError:
                send_status = "error"
                send_detail = f"nicht an Geraet gesendet: Timeout nach {SEND_TIMEOUT_SECONDS}s"
            except Exception as ex:
                send_status = "error"
                send_detail = f"nicht an Geraet gesendet: {ex}"
            else:
                send_status = "ok"
                send_detail = "an Geraet gesendet"
        await store.async_record_schedule_reset_send_status(pump_idx, send_status, send_detail)
        result = make_service_result(
            service=SERVICE_RESET_DOSER_SCHEDULE,
            ok=send_status in ("ok", "local"),
            send_status=send_status,
            send_detail=send_detail,
            debug=bool(call.data[ATTR_DEBUG]),
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="disable_doser_schedule",
            summary=f"Doser CH{pump_idx + 1} reset",
            request={
                "pump": pump_idx + 1,
                "send": bool(call.data[ATTR_SEND]),
            },
            response={
                "ok": send_status in ("ok", "local"),
                "send_status": send_status,
                "send_detail": send_detail,
            },
            details={
                "channel": pump_idx + 1,
                "channel_index": pump_idx,
            },
            raw_debug=debug_output,
        )
        return result if _response_requested(call) else None

    async def async_set_doser_container(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        store = await _store_for(chihiros_data, hass)
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        amount = float(call.data[ATTR_ML])
        await store.async_set_container_ml(pump_idx, amount)
        result = make_service_result(
            service=SERVICE_SET_DOSER_CONTAINER,
            ok=True,
            send_status="local",
            send_detail="nur lokal gespeichert",
            debug=False,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="set_doser_container",
            summary=f"Doser CH{pump_idx + 1} container volume {amount:.1f} mL stored locally",
            request={"pump": pump_idx + 1, "ml": amount},
            response={"ok": True, "stored_locally": True},
        )
        return result if _response_requested(call) else None

    async def async_set_doser_push_settings(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        store = await _store_for(chihiros_data, hass)
        settings = await store.async_set_low_container_push_settings(
            bool(call.data[ATTR_ENABLED]),
            list(call.data[ATTR_TARGETS]),
            str(call.data.get(ATTR_MESSAGE, "")),
        )
        result = {"ok": True, **settings}
        return result if _response_requested(call) else None

    async def async_set_doser_safety(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        store = await _store_for(chihiros_data, hass)
        legacy_single = float(call.data[ATTR_MAX_SINGLE_ML]) if ATTR_MAX_SINGLE_ML in call.data else 50.0
        limits = await store.async_set_doser_safety_limits(
            float(call.data.get(ATTR_MAX_AUTO_ML, legacy_single)),
            float(call.data.get(ATTR_MAX_MANUAL_ML, legacy_single)),
            float(call.data[ATTR_MAX_DAILY_ML]),
        )
        result = {"ok": True, **limits}
        return result if _response_requested(call) else None

    async def async_start_doser_calibration(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        debug = bool(call.data[ATTR_DEBUG])
        _prepare_device_debug(chihiros_data.device, debug)
        await _send_extension_frames(
            chihiros_data,
            lambda: calibration_start_frames(chihiros_data.device.get_next_msg_id, pump_idx),
            connection_prelude="doser_manual",
        )
        store = await _store_for(chihiros_data, hass)
        await store.async_add_log("Kalibrierung gestartet", pump_idx)
        result = make_service_result(
            service=SERVICE_START_DOSER_CALIBRATION,
            ok=True,
            send_status="ok",
            send_detail="Kalibrierung am Geraet gestartet",
            debug=debug,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="start_doser_calibration",
            summary=f"Doser CH{pump_idx + 1} calibration start",
            request={"pump": pump_idx + 1},
            response={"ok": True},
            raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
        )
        return result if _response_requested(call) else None

    async def async_prime_doser_calibration(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        duration = float(call.data[ATTR_DURATION])
        debug = bool(call.data[ATTR_DEBUG])
        _prepare_device_debug(chihiros_data.device, debug)
        await _send_calibration_prime(chihiros_data, pump_idx, duration)
        store = await _store_for(chihiros_data, hass)
        await store.async_add_log("Kalibrierung Schlauch gefuellt", pump_idx, f"{duration:.1f} s")
        result = make_service_result(
            service=SERVICE_PRIME_DOSER_CALIBRATION,
            ok=True,
            send_status="ok",
            send_detail=f"Schlauch {duration:.1f} s gefuellt",
            debug=debug,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="prime_doser_calibration",
            summary=f"Doser CH{pump_idx + 1} hose fill",
            request={"pump": pump_idx + 1, "duration": duration},
            response={"ok": True},
            raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
        )
        return result if _response_requested(call) else None

    async def async_submit_doser_calibration(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        measured_ml = float(call.data[ATTR_ML])
        test_ml = float(call.data[ATTR_TEST_ML]) if ATTR_TEST_ML in call.data else None
        reminder_days = int(call.data[ATTR_REMINDER_DAYS])
        debug = bool(call.data[ATTR_DEBUG])
        _prepare_device_debug(chihiros_data.device, debug)
        await _send_extension_frames(
            chihiros_data,
            lambda: calibration_submit_frames(
                chihiros_data.device.get_next_msg_id,
                pump_idx,
                measured_ml,
                test_ml,
            ),
            connection_prelude="doser_manual",
        )
        store = await _store_for(chihiros_data, hass)
        calibration = await store.async_record_calibration(pump_idx, measured_ml, reminder_days, test_ml)
        result = make_service_result(
            service=SERVICE_SUBMIT_DOSER_CALIBRATION,
            ok=True,
            send_status="ok",
            send_detail="Kalibrierwert an Geraet gesendet und lokal gespeichert",
            debug=debug,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="submit_doser_calibration",
            summary=f"Doser CH{pump_idx + 1} calibration {measured_ml:.2f} mL",
            request={
                "pump": pump_idx + 1,
                "ml": measured_ml,
                "test_ml": test_ml,
                "reminder_days": reminder_days,
            },
            response={"ok": True, "calibration": calibration},
            raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
        )
        return result if _response_requested(call) else None

    async def async_test_doser_calibration(call: ServiceCall) -> dict[str, Any] | None:
        chihiros_data = _ensure_doser(resolve(call.data))
        pump_idx = int(call.data[ATTR_PUMP]) - 1
        debug = bool(call.data[ATTR_DEBUG])
        _prepare_device_debug(chihiros_data.device, debug)
        await _send_extension_frames(
            chihiros_data,
            lambda: calibration_test_frames(chihiros_data.device.get_next_msg_id, pump_idx),
            connection_prelude="doser_manual",
        )
        store = await _store_for(chihiros_data, hass)
        await store.async_add_log("Kalibrierung Testdosierung", pump_idx, "4.0 mL")
        result = make_service_result(
            service=SERVICE_TEST_DOSER_CALIBRATION,
            ok=True,
            send_status="ok",
            send_detail="4.0 mL Kalibrier-Testdosierung an Geraet gesendet",
            debug=debug,
            device=chihiros_data.device.name,
            address=chihiros_data.device.address,
            action="test_doser_calibration",
            summary=f"Doser CH{pump_idx + 1} calibration test 4.0 mL",
            request={"pump": pump_idx + 1, "ml": 4.0},
            response={"ok": True},
            raw_debug=_device_protocol_debug(chihiros_data.device) if debug else "",
        )
        return result if _response_requested(call) else None

    _register(
        hass,
        SERVICE_SET_DOSER_SCHEDULE,
        async_set_doser_schedule,
        SET_DOSER_SCHEDULE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_RESET_DOSER_SCHEDULE,
        async_reset_doser_schedule,
        RESET_DOSER_SCHEDULE_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_SET_DOSER_CONTAINER,
        async_set_doser_container,
        SET_DOSER_CONTAINER_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_SET_DOSER_PUSH_SETTINGS,
        async_set_doser_push_settings,
        SET_DOSER_PUSH_SETTINGS_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass, SERVICE_SET_DOSER_SAFETY, async_set_doser_safety, SET_DOSER_SAFETY_SCHEMA, SupportsResponse.OPTIONAL
    )
    _register(
        hass,
        SERVICE_START_DOSER_CALIBRATION,
        async_start_doser_calibration,
        START_DOSER_CALIBRATION_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_SUBMIT_DOSER_CALIBRATION,
        async_submit_doser_calibration,
        SUBMIT_DOSER_CALIBRATION_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_PRIME_DOSER_CALIBRATION,
        async_prime_doser_calibration,
        PRIME_DOSER_CALIBRATION_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    _register(
        hass,
        SERVICE_TEST_DOSER_CALIBRATION,
        async_test_doser_calibration,
        TEST_DOSER_CALIBRATION_SCHEMA,
        SupportsResponse.OPTIONAL,
    )


def _register(
    hass: HomeAssistant,
    service: str,
    handler,
    schema: vol.Schema,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    if hass.services.has_service(DOMAIN, service):
        hass.services.async_remove(DOMAIN, service)
    hass.services.async_register(DOMAIN, service, handler, schema=schema, supports_response=supports_response)


def _ensure_doser(chihiros_data: ChihirosData) -> ChihirosData:
    if not chihiros_data.dosing_totals:
        raise HomeAssistantError(f"{chihiros_data.device.name} is not a dosing pump")
    return chihiros_data


def _notify_doser_safety_blocked(hass: HomeAssistant, chihiros_data: ChihirosData, pump_idx: int, detail: str) -> None:
    """Show a Home Assistant notification when the dosing safety limit blocks a schedule."""
    address = chihiros_data.device.address.lower().replace(":", "_")
    persistent_notification.async_create(
        hass,
        detail,
        title=f"Chihiros Doser Ueberdosierungsschutz CH{pump_idx + 1}",
        notification_id=f"{DOMAIN}_doser_safety_blocked_{address}_ch{pump_idx + 1}",
    )


async def _store_for(chihiros_data: ChihirosData, hass: HomeAssistant):
    pump_count = chihiros_data.dosing_totals.pump_count if chihiros_data.dosing_totals else 4
    return await async_store_for_device(hass, chihiros_data.device.address, pump_count)


async def _send_extension_frames(
    chihiros_data: ChihirosData,
    frames: list[bytearray] | Callable[[], list[bytearray]],
    *,
    connection_prelude: str = "standard",
) -> None:
    device = chihiros_data.device
    send_command = getattr(device, "_send_command", None)
    if send_command is None:
        raise HomeAssistantError(f"{device.name} cannot send raw dosing extension frames")
    resolved_frames = frames() if callable(frames) else frames
    await send_command(
        resolved_frames,
        3,
        connection_prelude=connection_prelude,
        immediate_after_prelude=True,
    )


async def _send_calibration_prime(chihiros_data: ChihirosData, pump_idx: int, duration: float) -> None:
    """Fill one calibration hose for a bounded duration and always send the stop frame."""
    device = chihiros_data.device
    ensure_connected = getattr(device, "_ensure_connected", None)
    send_locked = getattr(device, "_send_command_locked", None)
    disconnect = getattr(device, "_execute_disconnect", None)
    operation_lock = getattr(device, "_operation_lock", None)
    send_command = getattr(device, "_send_command", None)
    if ensure_connected is None or send_locked is None or disconnect is None or operation_lock is None:
        if send_command is None:
            raise HomeAssistantError(f"{device.name} cannot send raw dosing extension frames")
        await send_command(
            calibration_prime_frames(device.get_next_msg_id, pump_idx, True),
            3,
            connection_prelude="doser_manual",
        )
        try:
            await asyncio.sleep(duration)
        finally:
            await send_command(
                calibration_prime_frames(device.get_next_msg_id, pump_idx, False, prepared=True),
                3,
                connection_prelude="doser_manual",
            )
        return
    async with operation_lock:
        previous_prelude = getattr(device, "_connection_prelude_mode", "standard")
        device._connection_prelude_mode = "doser_manual"
        started = False
        try:
            await ensure_connected()
            start_frames = calibration_prime_frames(device.get_next_msg_id, pump_idx, True)
            for frame in start_frames:
                await send_locked([bytes(frame)])
                await asyncio.sleep(0.15)
            started = True
            await asyncio.sleep(duration)
        finally:
            try:
                if started:
                    for frame in calibration_prime_frames(device.get_next_msg_id, pump_idx, False, prepared=True):
                        await send_locked([bytes(frame)])
            finally:
                device._connection_prelude_mode = previous_prelude
                await disconnect()


async def _send_timer_schedule(chihiros_data: ChihirosData, schedule: DoserSchedule, *, window: bool = False) -> None:
    """Send one timer list or custom-window plan through the shared Doser connection."""
    device = chihiros_data.device
    ensure_connected = getattr(device, "_ensure_connected", None)
    send_locked = getattr(device, "_send_command_locked", None)
    disconnect = getattr(device, "_execute_disconnect", None)
    operation_lock = getattr(device, "_operation_lock", None)
    if ensure_connected is None or send_locked is None or disconnect is None or operation_lock is None:
        raise HomeAssistantError(f"{device.name} cannot send app-style Doser scheduler frames")
    async with operation_lock:
        previous_prelude = getattr(device, "_connection_prelude_mode", "standard")
        device._connection_prelude_mode = "doser_manual"
        try:
            await ensure_connected()
            auth_frames = dosing_auth_frames(device.get_next_msg_id)
            await asyncio.sleep(0.4)
            await send_locked([bytes(auth_frames[0])])
            await asyncio.sleep(0.12)
            await send_locked([bytes(auth_frames[1])])
            await asyncio.sleep(0.5)
            frames = (
                window_schedule_frames(device.get_next_msg_id, schedule)
                if window
                else timer_schedule_frames(device.get_next_msg_id, schedule)
            )
            for index, frame in enumerate(frames):
                await send_locked([bytes(frame)])
                if index < len(frames) - 1:
                    await asyncio.sleep(0.15)
        finally:
            device._connection_prelude_mode = previous_prelude
            await disconnect()


async def _send_doser_schedule(
    hass: HomeAssistant, chihiros_data: ChihirosData, schedule: DoserSchedule, debug: bool
) -> str:
    """Send through the integration's shared device instance and BLE locks."""
    del hass
    dosing_device = cast(DosingChihirosClient, chihiros_data.device)
    encoded_weekdays = weekday_mask(tuple(schedule.weekdays))
    if schedule.kind == "timer":
        await _send_timer_schedule(chihiros_data, schedule)
    elif schedule.kind == "window":
        await _send_timer_schedule(chihiros_data, schedule, window=True)
    elif schedule.kind == "interval":
        await dosing_device.add_interval_schedule(
            int(schedule.pump_idx),
            max(0, min(59, int(schedule.interval_minutes or 0))),
            float(schedule.ml),
            weekdays_mask=encoded_weekdays,
            active=True,
            next_day_flag=bool(schedule.valid_from_tomorrow),
        )
    else:
        hour, minute = [int(part) for part in str(schedule.time).split(":", 1)]
        await dosing_device.add_schedule(
            int(schedule.pump_idx),
            time(hour, minute),
            float(schedule.ml),
            weekdays_mask=encoded_weekdays,
            active=True,
            next_day_flag=bool(schedule.valid_from_tomorrow),
        )
    return _device_protocol_debug(chihiros_data.device) if debug else ""
