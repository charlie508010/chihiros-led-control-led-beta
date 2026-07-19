"""Chihiros HA integration root module."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import ChihirosDataUpdateCoordinator
from .core.notifications import (
    NOTIFICATION_POLL_GAP_SECONDS,
    NOTIFICATION_POLL_INTERVAL,
    NOTIFICATION_POLL_LAST_FINISHED,
    NOTIFICATION_POLL_LOCK,
    NotificationPollPayload,
    async_poll_device_notifications,
    async_track_notification_poll,
)
from .core.plugin_loader import async_load_plugins
from .core.storage import record_led_notification_poll
from .models import ChihirosData
from .packages.led.const import (
    ADD_SCHEDULE_SCHEMA,
    ATTR_ACTIVE,
    ATTR_ADDRESS,
    ATTR_BRIGHTNESS,
    ATTR_DEBUG,
    ATTR_END,
    ATTR_ENTITY_ID,
    ATTR_ENTRY_ID,
    ATTR_LEVELS,
    ATTR_PERIODS,
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
from .packages.led.services import async_update_led_services
from .runtime import resolve_chihiros_runtime

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH, Platform.SENSOR]

__all__ = [
    "ADD_SCHEDULE_SCHEMA",
    "ENABLE_AUTO_MODE_SCHEMA",
    "ATTR_ACTIVE",
    "ATTR_ADDRESS",
    "ATTR_BRIGHTNESS",
    "ATTR_DEBUG",
    "ATTR_END",
    "ATTR_ENTITY_ID",
    "ATTR_ENTRY_ID",
    "ATTR_LEVELS",
    "ATTR_PERIODS",
    "ATTR_RAMP_UP_MINUTES",
    "ATTR_SEND",
    "ATTR_START",
    "ATTR_WEEKDAYS",
    "REMOVE_SCHEDULE_SCHEMA",
    "RESET_SCHEDULE_SCHEMA",
    "SERVICE_ADD_SCHEDULE",
    "SERVICE_ENABLE_AUTO_MODE",
    "SERVICE_REMOVE_SCHEDULE",
    "SERVICE_RESET_SCHEDULE",
    "SERVICE_SET_BRIGHTNESS",
    "SERVICE_SET_SCHEDULE",
    "SET_BRIGHTNESS_SCHEMA",
    "SET_SCHEDULE_SCHEMA",
]

FRONTEND_PANEL_REGISTERED = f"{DOMAIN}_frontend_panel_registered"
FRONTEND_STATIC_URL = "/chihiros_led_core_static"
FRONTEND_PANEL_URL = "chihiros-led-core"
RUNTIME_POLL_UNSUBS = f"{DOMAIN}_runtime_poll_unsubs"
RUNTIME_POLL_LOCK = NOTIFICATION_POLL_LOCK
RUNTIME_POLL_LAST_FINISHED = NOTIFICATION_POLL_LAST_FINISHED
RUNTIME_POLL_INTERVAL = NOTIFICATION_POLL_INTERVAL
RUNTIME_POLL_GAP_SECONDS = NOTIFICATION_POLL_GAP_SECONDS


def _frontend_panel_version() -> str:
    """Return a cache-busting version for the custom panel module."""
    try:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "dev"
    return str(manifest.get("version") or "dev")


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the bundled Chihiros dashboard panel."""
    await async_load_plugins(hass, DOMAIN)
    async_update_led_services(hass, True, lambda data: _resolve_service_device(hass, data))
    await _async_register_frontend_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up chihiros from a config entry."""
    await async_load_plugins(hass, DOMAIN)
    runtime = await resolve_chihiros_runtime(hass, entry)
    coordinator = ChihirosDataUpdateCoordinator(
        hass,
        runtime.client,
        runtime.address,
        always_available=runtime.always_available,
    )
    coordinator.async_start_bluetooth()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = ChihirosData(entry.title, runtime.client, coordinator)
    _async_update_services(hass)
    await _async_register_frontend_panel(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if runtime.client.model.color_channels:
        async def _async_record_poll(status: str, output: str, notifications: int) -> None:
            try:
                await hass.async_add_executor_job(
                    record_led_notification_poll,
                    runtime.address,
                    entry.title,
                    status,
                    output,
                    notifications,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Could not persist active status query result for %s", runtime.address)

        async def _async_poll_runtime(_now: Any) -> None:
            async def _query() -> NotificationPollPayload:
                previous_runtime = runtime.client.last_runtime_notification
                previous_schedule = runtime.client.last_schedule_snapshot_notification
                await runtime.client.query_status_active()
                fresh = tuple(
                    notification
                    for notification, previous in (
                        (runtime.client.last_runtime_notification, previous_runtime),
                        (runtime.client.last_schedule_snapshot_notification, previous_schedule),
                    )
                    if notification is not None and notification is not previous
                )
                raw_frames = tuple(bytes(notification.raw) for notification in fresh if notification.raw)
                return NotificationPollPayload(
                    success=bool(fresh),
                    raw_frames=raw_frames,
                    notification_count=len(fresh),
                )

            result = await async_poll_device_notifications(
                hass,
                address=runtime.address,
                device_type="led",
                mode=0x04,
                expected_modes=(0x0A, 0xFE),
                query=_query,
            )
            await _async_record_poll(result.status, result.output, result.notifications)

        unsubscribe = async_track_notification_poll(hass, _async_poll_runtime)
        hass.data.setdefault(RUNTIME_POLL_UNSUBS, {})[entry.entry_id] = unsubscribe
        await _async_poll_runtime(None)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        unsubscribe = hass.data.get(RUNTIME_POLL_UNSUBS, {}).pop(entry.entry_id, None)
        if unsubscribe is not None:
            unsubscribe()
        chihiros_data: ChihirosData = hass.data[DOMAIN].pop(entry.entry_id)
        chihiros_data.coordinator.async_close()
        await chihiros_data.device.disconnect()
        _async_update_services(hass)

    return unload_ok


async def _async_register_frontend_panel(hass: HomeAssistant) -> None:
    """Register the bundled Chihiros dashboard panel once."""
    if hass.data.get(FRONTEND_PANEL_REGISTERED):
        return

    panel_version = await hass.async_add_executor_job(_frontend_panel_version)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_STATIC_URL,
                str(Path(__file__).parent / "www"),
                cache_headers=False,
            ),
        ]
    )
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom-panel",
        sidebar_title=None,
        sidebar_icon="mdi:fish",
        frontend_url_path=FRONTEND_PANEL_URL,
        require_admin=False,
        config={
            "_panel_custom": {
                "name": "chihiros-led-core-panel",
                "module_url": f"{FRONTEND_STATIC_URL}/chihiros-panel.js?v={panel_version}",
                "embed_iframe": False,
                "trust_external_script": True,
            }
        },
    )
    hass.data[FRONTEND_PANEL_REGISTERED] = True


def _async_update_services(hass: HomeAssistant) -> None:
    """Register services that apply to currently configured device capabilities."""
    async_update_led_services(hass, True, lambda data: _resolve_service_device(hass, data))


def _resolve_service_device(hass: HomeAssistant, data: dict[str, Any]) -> ChihirosData:
    """Resolve a service call to one configured Chihiros device."""
    entries: dict[str, ChihirosData] = hass.data.get(DOMAIN, {})
    if entry_id := data.get(ATTR_ENTRY_ID):
        if entry_id in entries:
            return entries[entry_id]
        raise HomeAssistantError(f"Chihiros config entry not found: {entry_id}")

    if entity_id := data.get(ATTR_ENTITY_ID):
        entity = er.async_get(hass).async_get(str(entity_id))
        if entity and entity.config_entry_id in entries:
            return entries[entity.config_entry_id]

    if address := data.get(ATTR_ADDRESS):
        normalized_address = _normalize_device_address(address)
        for entry_id, chihiros_data in entries.items():
            config_entry = hass.config_entries.async_get_entry(entry_id)
            known_addresses = {
                _normalize_device_address(chihiros_data.device.address),
                _normalize_device_address(config_entry.data.get(CONF_ADDRESS, "") if config_entry else ""),
                _normalize_device_address(config_entry.unique_id if config_entry else ""),
            }
            if normalized_address in known_addresses:
                return chihiros_data
            address_bearing_names = (
                chihiros_data.title,
                chihiros_data.device.name,
                config_entry.title if config_entry else "",
            )
            if any(_normalize_device_address(name).endswith(normalized_address) for name in address_bearing_names):
                return chihiros_data
        entity_registry = er.async_get(hass)
        for entity in entity_registry.entities.values():
            if entity.config_entry_id not in entries:
                continue
            registry_identity = _normalize_device_address(f"{entity.entity_id} {entity.unique_id}")
            if normalized_address in registry_identity:
                return entries[entity.config_entry_id]

    light_entries = [chihiros_data for chihiros_data in entries.values() if chihiros_data.device.colors]
    if len(light_entries) == 1:
        return light_entries[0]
    if not light_entries:
        raise HomeAssistantError(
            "LED-Geraet ist ueber Bluetooth nicht erreichbar. Schliesse die Chihiros-App auf anderen Handys "
            "vollstaendig "
            "und trenne dort die Bluetooth-Verbindung. Danach kurz warten und erneut senden."
        )
    if address := data.get(ATTR_ADDRESS):
        raise HomeAssistantError(f"Chihiros device address not found: {address}")
    if entity_id := data.get(ATTR_ENTITY_ID):
        raise HomeAssistantError(f"Chihiros entity is not linked to a loaded config entry: {entity_id}")

    if len(entries) == 1:
        return next(iter(entries.values()))
    raise HomeAssistantError("Multiple Chihiros devices are configured; provide entry_id or address")


def _normalize_device_address(value: object) -> str:
    """Normalize a Bluetooth address for service-device matching."""
    return re.sub(r"[^0-9A-F]", "", str(value or "").upper())
