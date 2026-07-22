"""Service registration for Chihiros LED schedule features."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from ....const import DOMAIN
from ....core.diagnostics import make_service_result
from ....core.services import response_requested
from ....core.storage import state_db_path
from ..const import (
    ADD_SCHEDULE_SCHEMA,
    ATTR_ACTIVE,
    ATTR_ADDRESS,
    ATTR_BRIGHTNESS,
    ATTR_DEBUG,
    ATTR_DELETE_ONLY,
    ATTR_ENABLE_AUTO_MODE,
    ATTR_END,
    ATTR_ENTITY_ID,
    ATTR_ENTRY_ID,
    ATTR_LEVELS,
    ATTR_NOTIFY_DEBUG_FILE,
    ATTR_PERIODS,
    ATTR_PRESERVE_LOCAL,
    ATTR_PREVIOUS_INDEX,
    ATTR_PREVIOUS_PERIOD,
    ATTR_RAMP_UP_MINUTES,
    ATTR_SEND,
    ATTR_START,
    ATTR_WEEKDAYS,
    ENABLE_AUTO_MODE_SCHEMA,
    REMOVE_SCHEDULE_SCHEMA,
    RESET_SCHEDULE_SCHEMA,
    SERVICE_ADD_SCHEDULE,
    SERVICE_ENABLE_AUTO_MODE,
    SERVICE_REMOVE_SCHEDULE,
    SERVICE_RESET_SCHEDULE,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_SCHEDULE,
    SET_BRIGHTNESS_SCHEMA,
    SET_SCHEDULE_SCHEMA,
)
from ..models import ChihirosData
from ..storage import (
    delete_led_schedule_rows,
    finish_led_schedule_verification,
    initialize_led_schedule_storage,
    load_active_led_schedule_settings,
    load_led_schedule_rows,
    record_led_schedule_rows,
    save_led_schedule_verification_job,
)
from ..types import ResolveDevice
from ..validators import (
    brightness_from_service_data,
    normalized_period_weekdays,
    parse_schedule_time,
    parse_weekdays,
    validate_brightness,
    validate_schedule_period,
    validate_schedule_periods,
    validate_time_range,
)

_LOGGER = logging.getLogger(__name__)
LED_VERIFICATION_TASKS = f"{DOMAIN}_led_verification_tasks"
LED_RUNTIME_POLL_LOCK = f"{DOMAIN}_runtime_poll_lock"
LED_VERIFICATION_QUERY_TIMEOUT = 20
LED_VERIFICATION_RESTORE_TIMEOUT = 30


def async_update_led_services(hass: HomeAssistant, enabled: bool, resolve_device: ResolveDevice) -> None:
    """Register or remove LED services based on configured LED devices."""
    if enabled:
        _async_register_led_services(hass, resolve_device)
    else:
        async_remove_led_services(hass)


def async_remove_led_services(hass: HomeAssistant) -> None:
    """Remove light schedule services if they are registered."""
    for service in (
        SERVICE_ADD_SCHEDULE,
        SERVICE_ENABLE_AUTO_MODE,
        SERVICE_REMOVE_SCHEDULE,
        SERVICE_RESET_SCHEDULE,
        SERVICE_SET_BRIGHTNESS,
        SERVICE_SET_SCHEDULE,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


def _async_register_led_services(hass: HomeAssistant, resolve_device: ResolveDevice) -> None:
    """Register LED schedule management services."""

    async def _initialize_storage() -> None:
        await hass.async_add_executor_job(initialize_led_schedule_storage)

    hass.async_create_task(_initialize_storage(), "initialize LED schedule storage")

    def _register_or_replace(
        service: str,
        handler,
        *,
        schema,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=schema,
            supports_response=supports_response,
        )

    async def async_add_schedule(call: ServiceCall) -> dict[str, Any] | None:
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "start": call.data.get(ATTR_START, ""),
            "end": call.data.get(ATTR_END, ""),
            "active": bool(call.data.get(ATTR_ACTIVE, True)),
            "brightness": call.data.get(ATTR_BRIGHTNESS, ""),
            "levels": call.data.get(ATTR_LEVELS, {}),
            "ramp_up_minutes": call.data.get(ATTR_RAMP_UP_MINUTES, 1),
            "weekdays": call.data.get(ATTR_WEEKDAYS, []),
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            validate_schedule_period(chihiros_data, call.data)
            device_key = str(chihiros_data.device.address or chihiros_data.title)
            stored_rows = await hass.async_add_executor_job(load_led_schedule_rows, device_key)
            active = bool(call.data.get(ATTR_ACTIVE, True))
            restore_rows = stored_rows[:2] if active and len(stored_rows) > 2 else []
            if restore_rows:
                await _remove_stored_schedule_rows(chihiros_data.device, restore_rows)
            previous_period = call.data.get(ATTR_PREVIOUS_PERIOD)
            if isinstance(previous_period, dict) and not restore_rows:
                validate_schedule_period(chihiros_data, previous_period)
                previous_index = call.data.get(ATTR_PREVIOUS_INDEX)
                prepare_existing_setting = (
                    int(previous_index) > 0
                    if previous_index is not None
                    else _stored_row_index(stored_rows, previous_period) > 0
                )
                await chihiros_data.device.replace_setting(
                    parse_schedule_time(previous_period[ATTR_START]),
                    parse_schedule_time(previous_period[ATTR_END]),
                    parse_schedule_time(call.data[ATTR_START]),
                    parse_schedule_time(call.data[ATTR_END]),
                    brightness_from_service_data(call.data),
                    previous_ramp_up_in_minutes=previous_period[ATTR_RAMP_UP_MINUTES],
                    ramp_up_in_minutes=call.data[ATTR_RAMP_UP_MINUTES],
                    previous_weekdays=parse_weekdays(previous_period.get(ATTR_WEEKDAYS)),
                    weekdays=parse_weekdays(call.data.get(ATTR_WEEKDAYS)),
                    prepare_existing_setting=prepare_existing_setting,
                )
                _replaced = True
            else:
                await async_add_schedule_period(
                    chihiros_data,
                    call.data,
                    prepare_existing_setting=active and bool(stored_rows),
                )
                _replaced = False
            if active:
                target = _verification_row(call.data)
                await _record_or_schedule_led_verification(
                    hass,
                    chihiros_data,
                    device_key,
                    target,
                    restore_rows,
                    notify_debug_file=bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
                )
            return {}

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_ADD_SCHEDULE,
            action="add_schedule_period",
            summary="LED schedule period sent",
            request=request,
            operation=_operation,
        )

    async def async_enable_auto_mode(call: ServiceCall) -> dict[str, Any] | None:
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "debug": bool(call.data.get(ATTR_DEBUG, False)),
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
            "periods": call.data.get(ATTR_PERIODS, []),
            "remaining_periods": call.data.get("remaining_periods", []),
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            device_key = str(chihiros_data.device.address or chihiros_data.title)
            explicit_periods = call.data.get(ATTR_PERIODS)
            settings = None
            verification_rows: list[dict[str, Any]] = []
            if explicit_periods is not None:
                validate_schedule_periods(chihiros_data, explicit_periods)
                active_periods = [period for period in explicit_periods if bool(period.get(ATTR_ACTIVE, True))]
                settings = [
                    (
                        parse_schedule_time(period[ATTR_START]),
                        parse_schedule_time(period[ATTR_END]),
                        brightness_from_service_data(period),
                        int(period[ATTR_RAMP_UP_MINUTES]),
                        parse_weekdays(period.get(ATTR_WEEKDAYS)),
                    )
                    for period in active_periods
                ]
                verification_rows = [_verification_row(period) for period in active_periods]
            else:
                verification_rows = await hass.async_add_executor_job(load_led_schedule_rows, device_key)
            schedule_count = await async_enable_led_auto_mode(
                hass,
                chihiros_data.coordinator,
                chihiros_data.device,
                settings,
            )
            await _record_or_schedule_led_verifications(
                hass,
                chihiros_data,
                device_key,
                verification_rows,
                notify_debug_file=bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
            )
            return {"schedules_restored": schedule_count, "verification_scheduled": bool(verification_rows)}

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_ENABLE_AUTO_MODE,
            action="enable_auto_mode",
            summary="LED auto mode enabled",
            request=request,
            operation=_operation,
        )

    async def async_remove_schedule(call: ServiceCall) -> dict[str, Any] | None:
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "start": call.data.get(ATTR_START, ""),
            "end": call.data.get(ATTR_END, ""),
            "ramp_up_minutes": call.data.get(ATTR_RAMP_UP_MINUTES, 1),
            "weekdays": call.data.get(ATTR_WEEKDAYS, []),
            "periods": call.data.get(ATTR_PERIODS, []),
            "delete_only": bool(call.data.get(ATTR_DELETE_ONLY, False)),
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            periods = call.data.get(ATTR_PERIODS)
            if periods:
                validate_schedule_periods(chihiros_data, periods)
                settings = [
                    (
                        parse_schedule_time(period[ATTR_START]),
                        parse_schedule_time(period[ATTR_END]),
                        int(period[ATTR_RAMP_UP_MINUTES]),
                        parse_weekdays(period.get(ATTR_WEEKDAYS)),
                    )
                    for period in periods
                ]
                remaining_periods = call.data.get("remaining_periods")
                await chihiros_data.device.remove_settings(
                    settings,
                    finalize=not bool(remaining_periods),
                )
            else:
                start = parse_schedule_time(call.data[ATTR_START])
                end = parse_schedule_time(call.data[ATTR_END])
                validate_time_range(start, end)
                await chihiros_data.device.remove_setting(
                    start,
                    end,
                    ramp_up_in_minutes=call.data[ATTR_RAMP_UP_MINUTES],
                    weekdays=parse_weekdays(call.data.get(ATTR_WEEKDAYS)),
                    delete_only=bool(call.data.get(ATTR_DELETE_ONLY, False)),
                )
            await async_refresh_status(chihiros_data)
            return {"rows_deleted": len(periods) if isinstance(periods, list) and periods else 1}

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_REMOVE_SCHEDULE,
            action="remove_schedule",
            summary="LED schedule deleted",
            request=request,
            operation=_operation,
        )

    async def async_reset_schedule(call: ServiceCall) -> dict[str, Any] | None:
        preserve_local = bool(call.data.get(ATTR_PRESERVE_LOCAL, False))
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "debug": bool(call.data.get(ATTR_DEBUG, False)),
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
            "preserve_local": preserve_local,
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            chihiros_data.coordinator.async_clear_schedule_snapshot()
            await chihiros_data.device.reset_settings()
            deleted_rows = 0 if preserve_local else delete_led_schedule_rows(chihiros_data)
            await async_refresh_status(chihiros_data)
            return {"rows_deleted": deleted_rows, "local_preserved": preserve_local}

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_RESET_SCHEDULE,
            action="reset_settings()",
            summary="LED schedule reset",
            request=request,
            operation=_operation,
            debug_last_operation=False,
        )

    async def async_set_schedule(call: ServiceCall) -> dict[str, Any] | None:
        send = bool(call.data.get(ATTR_SEND, True))
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "send": send,
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
            "periods": call.data.get(ATTR_PERIODS, []),
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            validate_schedule_periods(chihiros_data, call.data[ATTR_PERIODS])
            device_key = str(chihiros_data.device.address or chihiros_data.title)
            stored_rows = await hass.async_add_executor_job(load_led_schedule_rows, device_key)
            if send:
                active_settings = [
                    (
                        parse_schedule_time(period[ATTR_START]),
                        parse_schedule_time(period[ATTR_END]),
                        brightness_from_service_data(period),
                        int(period[ATTR_RAMP_UP_MINUTES]),
                        parse_weekdays(period.get(ATTR_WEEKDAYS)),
                    )
                    for period in call.data[ATTR_PERIODS]
                    if bool(period.get(ATTR_ACTIVE, True))
                ]
                if len(call.data[ATTR_PERIODS]) == 1 and len(stored_rows) > 2:
                    await _remove_stored_schedule_rows(chihiros_data.device, stored_rows[:2])
                await chihiros_data.device.replace_settings(active_settings)
            if len(call.data[ATTR_PERIODS]) != 1 or not stored_rows:
                record_led_schedule_rows(chihiros_data, call.data[ATTR_PERIODS], sent=send)
            if send and len(call.data[ATTR_PERIODS]) == 1:
                target = _verification_row(call.data[ATTR_PERIODS][0])
                restore_rows = stored_rows[:2] if len(stored_rows) > 2 else []
                await _record_or_schedule_led_verification(
                    hass,
                    chihiros_data,
                    device_key,
                    target,
                    restore_rows,
                    notify_debug_file=bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
                )
            return {
                "rows": len(call.data[ATTR_PERIODS]),
                "send": send,
                "weekdays_normalized": normalized_period_weekdays(call.data[ATTR_PERIODS]),
            }

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_SET_SCHEDULE,
            action="replace_schedule_periods",
            summary=f"LED schedule rows: {len(call.data.get(ATTR_PERIODS, []))}",
            request=request,
            operation=_operation,
            ok_send_status="ok" if send else "local",
            ok_send_detail="an Geraet gesendet" if send else "nur lokal gespeichert",
            debug_last_operation=send,
        )

    async def async_set_brightness(call: ServiceCall) -> dict[str, Any] | None:
        brightness = brightness_from_service_data(call.data)
        request = {
            "entry_id": call.data.get(ATTR_ENTRY_ID, ""),
            "entity_id": call.data.get(ATTR_ENTITY_ID, ""),
            "address": call.data.get(ATTR_ADDRESS, ""),
            "brightness": brightness,
            "debug": bool(call.data.get(ATTR_DEBUG, False)),
            "notify_debug_file": bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False)),
        }

        async def _operation(chihiros_data: ChihirosData) -> dict[str, Any]:
            validate_brightness(chihiros_data, brightness)
            await chihiros_data.device.set_brightness(brightness)
            await async_refresh_status(chihiros_data)
            return {"brightness": brightness}

        return await _async_led_send_service(
            call,
            hass=hass,
            resolve_device=resolve_device,
            service=SERVICE_SET_BRIGHTNESS,
            action="set_brightness",
            summary="LED brightness sent",
            request=request,
            operation=_operation,
        )

    _register_or_replace(
        SERVICE_ADD_SCHEDULE,
        async_add_schedule,
        schema=ADD_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _register_or_replace(
        SERVICE_ENABLE_AUTO_MODE,
        async_enable_auto_mode,
        schema=ENABLE_AUTO_MODE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _register_or_replace(
        SERVICE_REMOVE_SCHEDULE,
        async_remove_schedule,
        schema=REMOVE_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _register_or_replace(
        SERVICE_RESET_SCHEDULE,
        async_reset_schedule,
        schema=RESET_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _register_or_replace(
        SERVICE_SET_BRIGHTNESS,
        async_set_brightness,
        schema=SET_BRIGHTNESS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    _register_or_replace(
        SERVICE_SET_SCHEDULE,
        async_set_schedule,
        schema=SET_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_led_send_service(
    call: ServiceCall,
    *,
    hass: HomeAssistant,
    resolve_device: ResolveDevice,
    service: str,
    action: str,
    summary: str,
    request: dict[str, Any],
    operation: Any,
    ok_send_status: str = "ok",
    ok_send_detail: str = "an Geraet gesendet",
    debug_last_operation: bool = True,
) -> dict[str, Any] | None:
    """Run one LED send service with one shared response/debug path."""
    debug = bool(call.data.get(ATTR_DEBUG, False))
    notify_debug_file = bool(call.data.get(ATTR_NOTIFY_DEBUG_FILE, False))
    chihiros_data: ChihirosData | None = None
    try:
        chihiros_data = await _async_resolve_led_device(hass, resolve_device, call.data)
        ensure_light_device(chihiros_data)
        prepare_device_debug(chihiros_data.device, debug or notify_debug_file)
        details = await operation(chihiros_data)
        debug_output = (
            led_service_debug_output(
                chihiros_data.device,
                last_operation=debug_last_operation,
                include_missing_tx_frames=service == SERVICE_SET_BRIGHTNESS,
            )
            if debug and debug_last_operation
            else ""
        )
        notify_debug_path = ""
        if notify_debug_file:
            notify_output = debug_output or led_service_debug_output(
                chihiros_data.device,
                last_operation=False,
                include_missing_tx_frames=service == SERVICE_SET_BRIGHTNESS,
            )
            notify_debug_path = await _append_led_notify_debug_file(
                hass,
                str(getattr(chihiros_data.device, "address", "") or chihiros_data.title),
                service,
                [
                    f"Service: {service}",
                    f"Action: {action}",
                    f"Summary: {summary}",
                    f"Send status: {ok_send_status}",
                    f"Send detail: {ok_send_detail}",
                    "",
                    notify_output or "Keine TX/RX/Notify-Debugdaten erfasst.",
                ],
            )
        response = {
            "ok": True,
            "send_status": ok_send_status,
            "send_detail": ok_send_detail,
        }
        result_details = details if isinstance(details, dict) else {}
        if notify_debug_path:
            result_details = {**result_details, "notify_debug_file": notify_debug_path}
        result = make_service_result(
            service=service,
            ok=True,
            send_status=ok_send_status,
            send_detail=ok_send_detail,
            debug=debug,
            device=chihiros_data.device.name,
            address=str(getattr(chihiros_data.device, "address", "")),
            action=action,
            summary=summary,
            request=request,
            response=response,
            details=result_details or None,
            raw_debug=debug_output,
        )
        return result if response_requested(call) else None
    except Exception as ex:
        debug_output = (
            led_service_debug_output(
                chihiros_data.device,
                last_operation=debug_last_operation,
                include_missing_tx_frames=service == SERVICE_SET_BRIGHTNESS,
            )
            if debug and chihiros_data is not None and debug_last_operation
            else ""
        )
        result = make_service_result(
            service=service,
            ok=False,
            send_status="fail",
            send_detail=str(ex),
            debug=debug,
            device=chihiros_data.device.name if chihiros_data is not None else "",
            address=(
                str(getattr(chihiros_data.device, "address", ""))
                if chihiros_data is not None
                else str(call.data.get(ATTR_ADDRESS, ""))
            ),
            action=action,
            summary=f"{summary} failed",
            request=request,
            response={
                "ok": False,
                "send_status": "fail",
                "send_detail": str(ex),
            },
            details={
                "error_type": type(ex).__name__,
            },
            raw_debug=debug_output,
        )
        return result if response_requested(call) else None


async def _append_led_notify_debug_file(
    hass: HomeAssistant,
    device_key: str,
    phase: str,
    lines: list[str],
) -> str:
    """Append one LED notify/debug block to the per-device diagnostic file."""
    return await hass.async_add_executor_job(_append_led_notify_debug_file_sync, device_key, phase, lines)


def _append_led_notify_debug_file_sync(device_key: str, phase: str, lines: list[str]) -> str:
    """Write one LED notify/debug block outside the event loop."""
    safe_device = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(device_key or "device").upper()).strip("_") or "device"
    directory = state_db_path().parent / "debug"
    path = directory / f"led-notify-{safe_device}-{dt_util.now().strftime('%Y%m%d')}.log"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = dt_util.now().isoformat()
    body = "\n".join(str(line) for line in lines).strip()
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    "=" * 72,
                    f"LED DEBUG START | {timestamp} | {phase}",
                    f"Geraet: {safe_device}",
                    "-" * 72,
                    body,
                    "-" * 72,
                    f"LED DEBUG ENDE  | {dt_util.now().isoformat()} | {phase}",
                    "=" * 72,
                    "",
                ]
            )
            + "\n"
        )
    return str(path)


async def async_enable_led_auto_mode(
    hass: HomeAssistant,
    coordinator: Any,
    device: Any,
    settings: list[tuple[Any, ...]] | None = None,
) -> int:
    """Enable automatic mode and restore active schedules from the shared database."""
    if settings is None:
        settings = await hass.async_add_executor_job(
            load_active_led_schedule_settings,
            str(device.address),
        )
    await device.enable_auto_mode(dt_util.now())
    if settings:
        await device.replace_settings(settings)
    coordinator.async_set_auto_mode(True)
    return len(settings)


async def _async_resolve_led_device(
    hass: HomeAssistant,
    resolve_device: ResolveDevice,
    data: dict[str, Any],
) -> ChihirosData:
    """Resolve an LED runtime, reloading unloaded entries once when needed."""
    try:
        return resolve_device(data)
    except HomeAssistantError:
        if hass.data.get(DOMAIN):
            raise

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return resolve_device(data)

    for entry in entries:
        await hass.config_entries.async_reload(entry.entry_id)
    return resolve_device(data)


async def async_add_schedule_period(
    chihiros_data: ChihirosData,
    data: dict[str, Any],
    *,
    enable_auto_mode: bool | None = None,
    prepare_existing_setting: bool = False,
) -> None:
    """Add or delete one auto schedule period."""
    start = parse_schedule_time(data[ATTR_START])
    end = parse_schedule_time(data[ATTR_END])
    if not bool(data.get(ATTR_ACTIVE, True)):
        await chihiros_data.device.remove_setting(
            start,
            end,
            max_brightness=None if bool(data.get(ATTR_DELETE_ONLY, False)) else brightness_from_service_data(data),
            ramp_up_in_minutes=data[ATTR_RAMP_UP_MINUTES],
            weekdays=parse_weekdays(data.get(ATTR_WEEKDAYS)),
            delete_only=bool(data.get(ATTR_DELETE_ONLY, False)),
        )
        return
    await chihiros_data.device.add_setting(
        start,
        end,
        max_brightness=brightness_from_service_data(data),
        ramp_up_in_minutes=data[ATTR_RAMP_UP_MINUTES],
        weekdays=parse_weekdays(data.get(ATTR_WEEKDAYS)),
        enable_auto_mode=(
            bool(data.get(ATTR_ENABLE_AUTO_MODE, True)) if enable_auto_mode is None else enable_auto_mode
        ),
        prepare_existing_setting=prepare_existing_setting,
    )


def ensure_light_device(chihiros_data: ChihirosData) -> None:
    """Validate that the selected service target is a light."""
    model = getattr(chihiros_data.device, "model", None)
    if not getattr(model, "color_channels", None):
        raise HomeAssistantError(f"{chihiros_data.device.name} is not a light")


async def async_refresh_status(chihiros_data: ChihirosData) -> None:
    """Refresh schedule sensors after a schedule write."""
    try:
        await chihiros_data.coordinator.async_request_status()
    except Exception:
        _LOGGER.debug("Failed to refresh Chihiros status after schedule write", exc_info=True)


def prepare_device_debug(device: Any, enabled: bool) -> None:
    """Enable LED protocol debug for one operation."""
    if not enabled:
        return
    try:
        set_log_level = getattr(device, "set_log_level", None)
        if callable(set_log_level):
            set_log_level(logging.DEBUG)
        clear_buffers = getattr(device, "clear_debug_buffers", None)
        if callable(clear_buffers):
            clear_buffers()
    except Exception as ex:
        _LOGGER.debug("prepare LED debug fallback failed: %s", ex, exc_info=True)


def device_protocol_debug(
    device: Any,
    *,
    last_operation: bool = False,
    include_missing_tx_frames: bool = False,
) -> str:
    """Render protocol debug from the device if supported."""
    try:
        render_protocol_debug = getattr(device, "render_protocol_debug", None)
        if callable(render_protocol_debug):
            return str(
                render_protocol_debug(
                    tx_commands={0x5A, 0xA5},
                    dedupe_rx=True,
                    last_operation=last_operation,
                    include_missing_tx_frames=include_missing_tx_frames,
                )
                or ""
            ).strip()
    except Exception as ex:
        _LOGGER.debug("LED protocol debug fallback failed: %s", ex, exc_info=True)
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


def led_service_debug_output(
    device: Any,
    *,
    last_operation: bool = True,
    include_missing_tx_frames: bool = False,
) -> str:
    """Return LED protocol debug, falling back to full buffers if the last operation is empty."""
    output = device_protocol_debug(
        device,
        last_operation=last_operation,
        include_missing_tx_frames=include_missing_tx_frames,
    )
    if output or not last_operation:
        return output
    return device_protocol_debug(device, last_operation=False, include_missing_tx_frames=include_missing_tx_frames)


def _verification_row(period: dict[str, Any]) -> dict[str, Any]:
    """Normalize one service period for a delayed device comparison."""
    ramp = max(1, int(period.get(ATTR_RAMP_UP_MINUTES, 1)))
    return {
        "start": str(period[ATTR_START]),
        "end": str(period[ATTR_END]),
        "levels": brightness_from_service_data(period),
        "ramp": ramp,
        "weekdays": [str(value) for value in period.get(ATTR_WEEKDAYS) or ["everyday"]],
    }


def _debug_schedule_target(target: dict[str, Any]) -> str:
    """Return one compact schedule target line for debug files."""
    levels = target.get("levels") if isinstance(target.get("levels"), dict) else {}
    levels_text = ", ".join(f"{key}={value}" for key, value in sorted(levels.items())) or "-"
    weekdays = ",".join(str(value) for value in target.get("weekdays") or []) or "-"
    return (
        f"{target.get('start', '')}-{target.get('end', '')}; "
        f"levels: {levels_text}; ramp: {target.get('ramp', '-')}; weekdays: {weekdays}"
    )


def _debug_schedule_target_range(target: dict[str, Any]) -> str:
    """Return one compact schedule start/end range for debug block titles."""
    return f"{target.get('start', '')}-{target.get('end', '')}"


def _verification_target_signature(target: dict[str, Any]) -> str:
    """Return a stable verification identity for one complete schedule target."""
    levels = target.get("levels") if isinstance(target.get("levels"), dict) else {}
    weekdays = target.get("weekdays") if isinstance(target.get("weekdays"), list) else []
    return "|".join(
        (
            str(target.get("start", "")),
            str(target.get("end", "")),
            ",".join(f"{key}={int(value)}" for key, value in sorted(levels.items())),
            str(int(target.get("ramp", 1))),
            ",".join(sorted(str(value) for value in weekdays)),
        )
    )


def _verification_restore_rows(restore_rows: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the full row set that must be written back after a one-row verification."""
    target_signature = _verification_target_signature(target)
    rows = [row for row in restore_rows if _verification_target_signature(row) != target_signature]
    rows.append(target)
    return rows


async def _record_or_schedule_led_verification(
    hass: HomeAssistant,
    chihiros_data: ChihirosData,
    device_key: str,
    target: dict[str, Any],
    restore_rows: list[dict[str, Any]],
    *,
    notify_debug_file: bool = False,
) -> None:
    """Persist a pending verification job and schedule a delayed device check."""
    await hass.async_add_executor_job(save_led_schedule_verification_job, device_key, target, restore_rows)
    _schedule_led_verification(hass, chihiros_data, target, restore_rows, notify_debug_file=notify_debug_file)


async def _record_or_schedule_led_verifications(
    hass: HomeAssistant,
    chihiros_data: ChihirosData,
    device_key: str,
    targets: list[dict[str, Any]],
    *,
    notify_debug_file: bool = False,
) -> None:
    """Persist all rows as pending and check them with one device query."""
    for target in targets:
        await hass.async_add_executor_job(save_led_schedule_verification_job, device_key, target, [])
    if targets:
        targets = sorted(
            targets,
            key=lambda target: not any(int(value) > 0 for value in target.get("levels", {}).values()),
        )
        _schedule_led_verification_batch(hass, chihiros_data, targets, notify_debug_file=notify_debug_file)


def _led_verification_task_key(device_key: str, target: dict[str, Any]) -> str:
    """Return the persisted one-row verification task key."""
    return f"{device_key}|{_verification_target_signature(target)}"


def _schedule_led_verification(
    hass: HomeAssistant,
    chihiros_data: ChihirosData,
    target: dict[str, Any],
    restore_rows: list[dict[str, Any]],
    *,
    notify_debug_file: bool = False,
) -> None:
    """Run one delayed check for each latest schedule-row write."""
    device_key = str(chihiros_data.device.address or chihiros_data.title)
    task_key = _led_verification_task_key(device_key, target)
    tasks = hass.data.setdefault(LED_VERIFICATION_TASKS, {})
    previous = tasks.pop(task_key, None)
    if previous is not None and not previous.done():
        previous.cancel()

    async def _verify() -> None:
        status: str | None = None
        cancelled = False
        try:
            await asyncio.sleep(60)
            lock = hass.data.setdefault(LED_RUNTIME_POLL_LOCK, asyncio.Lock())
            async with lock:
                try:
                    chihiros_data.device.last_schedule_snapshot_notification = None
                    prepare_device_debug(chihiros_data.device, notify_debug_file)
                    await asyncio.wait_for(
                        chihiros_data.device.query_status_active(), timeout=LED_VERIFICATION_QUERY_TIMEOUT
                    )
                    snapshot = chihiros_data.device.last_schedule_snapshot_notification
                    status = (
                        "verified" if _schedule_snapshot_matches(chihiros_data.device, snapshot, target) else "failed"
                    )
                    if notify_debug_file:
                        await _append_led_notify_debug_file(
                            hass,
                            device_key,
                            f"schedule verification {_debug_schedule_target_range(target)}",
                            [
                                f"Target: {_debug_schedule_target(target)}",
                                f"Status: {status}",
                                f"Restore rows: {len(restore_rows)}",
                                "",
                                led_service_debug_output(chihiros_data.device, last_operation=False)
                                or "Keine TX/RX/Notify-Debugdaten erfasst.",
                            ],
                        )
                finally:
                    if restore_rows:
                        settings = [
                            _stored_row_to_setting(row) for row in _verification_restore_rows(restore_rows, target)
                        ]
                        await asyncio.wait_for(
                            chihiros_data.device.replace_settings(settings),
                            timeout=LED_VERIFICATION_RESTORE_TIMEOUT,
                        )
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Delayed LED schedule verification failed for %s", device_key)
        finally:
            # A replacement task for the same schedule owns the persisted job.
            # Finishing here would delete that newer job and create a false
            # failure in history.
            if not cancelled and status is not None:
                await hass.async_add_executor_job(finish_led_schedule_verification, device_key, target, status)
                await async_refresh_status(chihiros_data)
            if tasks.get(task_key) is asyncio.current_task():
                tasks.pop(task_key, None)

    tasks[task_key] = hass.async_create_task(_verify(), f"verify LED schedule {device_key} {target['start']}")


def _schedule_led_verification_batch(
    hass: HomeAssistant,
    chihiros_data: ChihirosData,
    targets: list[dict[str, Any]],
    *,
    notify_debug_file: bool = False,
) -> None:
    """Run delayed checks and temporarily remove verified rows so hidden rows can surface."""
    device_key = str(chihiros_data.device.address or chihiros_data.title)
    task_key = f"{device_key}|batch"
    tasks = hass.data.setdefault(LED_VERIFICATION_TASKS, {})
    for key in [task_key, *[_led_verification_task_key(device_key, target) for target in targets]]:
        previous = tasks.pop(key, None)
        if previous is not None and not previous.done():
            previous.cancel()

    async def _verify() -> None:
        statuses: dict[int, str | None] = {id(target): None for target in targets}
        remaining = list(targets)
        removed_rows: list[dict[str, Any]] = []
        cancelled = False
        try:
            await asyncio.sleep(60)
            lock = hass.data.setdefault(LED_RUNTIME_POLL_LOCK, asyncio.Lock())
            async with lock:
                try:
                    for attempt in range(max(1, len(targets))):
                        chihiros_data.device.last_schedule_snapshot_notification = None
                        prepare_device_debug(chihiros_data.device, notify_debug_file)
                        await asyncio.wait_for(
                            chihiros_data.device.query_status_active(), timeout=LED_VERIFICATION_QUERY_TIMEOUT
                        )
                        snapshot = chihiros_data.device.last_schedule_snapshot_notification
                        matched_target = next(
                            (
                                target
                                for target in remaining
                                if _schedule_snapshot_matches(chihiros_data.device, snapshot, target)
                            ),
                            None,
                        )
                        matched_rows = [matched_target] if matched_target is not None else []
                        if matched_target is not None:
                            statuses[id(matched_target)] = "verified"
                            remaining = [target for target in remaining if target is not matched_target]
                        elif snapshot is not None:
                            for target in remaining:
                                statuses[id(target)] = "failed"
                        if notify_debug_file:
                            await _append_led_notify_debug_file(
                                hass,
                                device_key,
                                "schedule batch verification "
                                f"{', '.join(_debug_schedule_target_range(target) for target in targets)}",
                                [
                                    f"Attempt: {attempt + 1}",
                                    f"Matched: {len(matched_rows)}",
                                    f"Remaining: {len(remaining)}",
                                    *[f"Matched target: {_debug_schedule_target(target)}" for target in matched_rows],
                                    "",
                                    led_service_debug_output(chihiros_data.device, last_operation=False)
                                    or "Keine TX/RX/Notify-Debugdaten erfasst.",
                                ],
                            )
                        if not remaining or matched_target is None:
                            break
                        await _remove_stored_schedule_rows(chihiros_data.device, matched_rows)
                        removed_rows.extend(matched_rows)
                        remaining_settings = [_stored_row_to_setting(row) for row in remaining]
                        await asyncio.wait_for(
                            chihiros_data.device.replace_settings(remaining_settings),
                            timeout=LED_VERIFICATION_RESTORE_TIMEOUT,
                        )
                finally:
                    if removed_rows:
                        prepare_device_debug(chihiros_data.device, notify_debug_file)
                        settings = [_stored_row_to_setting(row) for row in targets]
                        await asyncio.wait_for(
                            chihiros_data.device.replace_settings(settings),
                            timeout=LED_VERIFICATION_RESTORE_TIMEOUT,
                        )
                        if notify_debug_file:
                            chihiros_data.device.last_schedule_snapshot_notification = None
                            await asyncio.wait_for(
                                chihiros_data.device.query_status_active(),
                                timeout=LED_VERIFICATION_QUERY_TIMEOUT,
                            )
                            await _append_led_notify_debug_file(
                                hass,
                                device_key,
                                "schedule batch restore "
                                f"{', '.join(_debug_schedule_target_range(target) for target in targets)}",
                                [
                                    f"Restored targets: {len(targets)}",
                                    *[f"Restored target: {_debug_schedule_target(target)}" for target in targets],
                                    "",
                                    led_service_debug_output(chihiros_data.device, last_operation=False)
                                    or "Keine TX/RX/Notify-Debugdaten erfasst.",
                                ],
                            )
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Delayed LED schedule batch verification failed for %s", device_key)
        finally:
            if not cancelled:
                for target in targets:
                    status = statuses[id(target)]
                    if status is None:
                        continue
                    await hass.async_add_executor_job(
                        finish_led_schedule_verification,
                        device_key,
                        target,
                        status,
                    )
                await async_refresh_status(chihiros_data)
            if tasks.get(task_key) is asyncio.current_task():
                tasks.pop(task_key, None)

    tasks[task_key] = hass.async_create_task(_verify(), f"verify LED schedule batch {device_key}")


def _stored_row_to_setting(row: dict[str, Any]) -> tuple[datetime, datetime, dict[str, int], int, list[Any]]:
    """Convert a complete temporary DB row back to the client setting format."""
    today = dt_util.now().date()
    start = datetime.combine(today, datetime.strptime(str(row["start"]), "%H:%M").time())
    end = datetime.combine(today, datetime.strptime(str(row["end"]), "%H:%M").time())
    return (
        start,
        end,
        {str(key): int(value) for key, value in row["levels"].items()},
        max(1, int(row["ramp"])),
        parse_weekdays(row.get("weekdays")),
    )


def _stored_row_index(rows: list[dict[str, Any]], period: dict[str, Any]) -> int:
    """Return the matching stored schedule-row index, or -1 when unknown."""
    period_start = str(period.get(ATTR_START, ""))
    period_end = str(period.get(ATTR_END, ""))
    period_ramp = max(1, int(period.get(ATTR_RAMP_UP_MINUTES, 1)))
    period_weekdays = [weekday.value for weekday in parse_weekdays(period.get(ATTR_WEEKDAYS))]
    for index, row in enumerate(rows):
        row_weekdays = [weekday.value for weekday in parse_weekdays(row.get("weekdays"))]
        if (
            str(row.get("start", "")) == period_start
            and str(row.get("end", "")) == period_end
            and max(1, int(row.get("ramp", 1))) == period_ramp
            and row_weekdays == period_weekdays
        ):
            return index
    return -1


async def _remove_stored_schedule_rows(device: Any, rows: list[dict[str, Any]]) -> None:
    """Temporarily remove the two device-visible rows without changing channel values."""
    for row in rows:
        start, end, _levels, ramp, weekdays = _stored_row_to_setting(row)
        await device.remove_setting(
            start,
            end,
            ramp_up_in_minutes=ramp,
            weekdays=weekdays,
        )


def _schedule_snapshot_matches(device: Any, snapshot: Any, target: dict[str, Any]) -> bool:
    """Compare one requested period with the schedule ranges returned by the device."""
    if snapshot is None:
        return False
    start_hour, start_minute = (int(value) for value in str(target["start"]).split(":"))
    end_hour, end_minute = (int(value) for value in str(target["end"]).split(":"))
    expected_by_channel = {str(channel).lower(): int(value) for channel, value in target["levels"].items()}
    positive_expected_levels = {level for level in expected_by_channel.values() if level > 0}
    fallback_expected_levels = positive_expected_levels or {0}
    if not getattr(snapshot, "points", ()) and not positive_expected_levels:
        return True

    def _minutes(hour: int, minute: int) -> int:
        return (hour * 60) + minute

    target_start = _minutes(start_hour, start_minute)
    target_end = _minutes(end_hour, end_minute)

    def _overlaps_target(start: int, end: int) -> bool:
        return start < target_end and end > target_start

    def _range_window_matches(sh: int, sm: int, eh: int, em: int) -> bool:
        range_start = _minutes(sh, sm)
        range_end = _minutes(eh, em)
        return abs(range_start - target_start) <= 1 and abs(range_end - target_end) <= 1

    def _implicit_zero_range_matches(points: list[tuple[int, int, int]]) -> bool:
        if positive_expected_levels:
            return False
        ranges = device._schedule_curve_ranges(sorted(points))  # noqa: SLF001
        has_left_boundary = False
        for sh, sm, eh, em, level, _ramp in ranges:
            range_start = _minutes(sh, sm)
            range_end = _minutes(eh, em)
            if range_end == target_start:
                has_left_boundary = True
            if level > 0 and _overlaps_target(range_start, range_end):
                return False
        return has_left_boundary

    def _ranges_match(points: list[tuple[int, int, int]], expected_levels: set[int]) -> bool:
        ranges = device._schedule_curve_ranges(sorted(points))  # noqa: SLF001
        return any(
            _range_window_matches(sh, sm, eh, em) and level in expected_levels for sh, sm, eh, em, level, ramp in ranges
        ) or _implicit_zero_range_matches(points)

    primary_points = [
        (int(point.hour), int(point.minute), int(next(iter(getattr(point, "levels", {}).values()), 0)))
        for point in snapshot.points
    ]
    if _ranges_match(primary_points, fallback_expected_levels):
        return True

    snapshot_channels = sorted(
        {str(channel).lower() for point in snapshot.points for channel in getattr(point, "levels", {}).keys()}
    )
    for channel in snapshot_channels:
        if channel not in expected_by_channel:
            continue
        channel_points = [
            (int(point.hour), int(point.minute), int(getattr(point, "levels", {}).get(channel, 0)))
            for point in snapshot.points
        ]
        if _ranges_match(channel_points, {expected_by_channel[channel]}):
            return True

    return False
