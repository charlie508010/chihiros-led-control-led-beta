"""Chihiros HA integration root module."""

from __future__ import annotations

import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import EVENT_HOMEASSISTANT_STARTED, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common.notification_poll import (
    NOTIFICATION_POLL_GAP_SECONDS,
    NOTIFICATION_POLL_INTERVAL,
    NOTIFICATION_POLL_LAST_FINISHED,
    NOTIFICATION_POLL_LOCK,
    NotificationPollPayload,
    async_poll_device_notifications,
    async_track_notification_poll,
)
from .common.storage import record_led_notification_poll
from .const import DOMAIN
from .coordinator import ChihirosDataUpdateCoordinator
from .dosing import CONF_PUMP_COUNT, DosingDailyTotals, is_dosing_capable, normalize_pump_count
from .models import ChihirosData
from .packages.doser.registry import async_migrate_doser_ext_entity_devices
from .packages.doser.services import (
    ATTR_ML,
    ATTR_PUMP,
    SERVICE_DOSE_ML,
    async_trigger_dose_ml,
    async_update_doser_services,
)
from .packages.doser.watcher import DoserAutoTotalsWatcher
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
from .packages.stirrer.services import async_update_stirrer_services
from .runtime import resolve_chihiros_runtime

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH, Platform.SENSOR, Platform.NUMBER, Platform.BUTTON]

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
    "ATTR_ML",
    "ATTR_PERIODS",
    "ATTR_PUMP",
    "ATTR_RAMP_UP_MINUTES",
    "ATTR_SEND",
    "ATTR_START",
    "ATTR_WEEKDAYS",
    "REMOVE_SCHEDULE_SCHEMA",
    "RESET_SCHEDULE_SCHEMA",
    "SERVICE_ADD_SCHEDULE",
    "SERVICE_ENABLE_AUTO_MODE",
    "SERVICE_DOSE_ML",
    "SERVICE_REMOVE_SCHEDULE",
    "SERVICE_RESET_SCHEDULE",
    "SERVICE_SET_BRIGHTNESS",
    "SERVICE_SET_SCHEDULE",
    "SET_BRIGHTNESS_SCHEMA",
    "SET_SCHEDULE_SCHEMA",
    "async_trigger_dose_ml",
]

DOSER_EXT_WATCHERS = f"{DOMAIN}_doser_ext_watchers"
FRONTEND_PANEL_REGISTERED = f"{DOMAIN}_frontend_panel_registered"
FRONTEND_STATIC_URL = "/chihiros_static"
FRONTEND_PLUGIN_STATIC_URL = "/chihiros_plugin_static"
FRONTEND_PANEL_URL = "chihiros"
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
    async_update_led_services(hass, True, lambda data: _resolve_service_device(hass, data))
    await _async_register_frontend_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up chihiros from a config entry."""
    runtime = await resolve_chihiros_runtime(hass, entry)
    coordinator = ChihirosDataUpdateCoordinator(
        hass,
        runtime.client,
        runtime.address,
        always_available=runtime.always_available,
    )
    coordinator.async_start_bluetooth()

    dosing_totals = None
    dosing_volumes: list[float] = []
    if is_dosing_capable(runtime.client):
        dosing_totals = DosingDailyTotals(hass, runtime.address, normalize_pump_count(entry.data.get(CONF_PUMP_COUNT)))
        await dosing_totals.async_load()
        dosing_volumes = [1.0] * dosing_totals.pump_count

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = ChihirosData(
        entry.title, runtime.client, coordinator, dosing_totals, dosing_volumes
    )
    _async_update_services(hass)
    await _async_register_frontend_panel(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not dosing_totals and runtime.client.model.color_channels:
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
    if dosing_totals:
        chihiros_data = hass.data[DOMAIN][entry.entry_id]
        await async_migrate_doser_ext_entity_devices(hass, entry, chihiros_data)
        watcher = DoserAutoTotalsWatcher(hass, chihiros_data)
        hass.data.setdefault(DOSER_EXT_WATCHERS, {})[entry.entry_id] = watcher
        if getattr(hass, "is_running", False):
            watcher.start()
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, lambda _event: watcher.start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        unsubscribe = hass.data.get(RUNTIME_POLL_UNSUBS, {}).pop(entry.entry_id, None)
        if unsubscribe is not None:
            unsubscribe()
        watcher = hass.data.get(DOSER_EXT_WATCHERS, {}).pop(entry.entry_id, None)
        if watcher is not None:
            await watcher.stop()
        chihiros_data: ChihirosData = hass.data[DOMAIN].pop(entry.entry_id)
        chihiros_data.coordinator.async_close()
        if chihiros_data.dosing_totals:
            chihiros_data.dosing_totals.async_close()
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
            StaticPathConfig(
                FRONTEND_PLUGIN_STATIC_URL,
                str(Path(__file__).parent / "plugins"),
                cache_headers=False,
            ),
        ]
    )
    hass.http.register_view(ChihirosPluginBackendView())
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom-panel",
        sidebar_title=None,
        sidebar_icon="mdi:fish",
        frontend_url_path=FRONTEND_PANEL_URL,
        require_admin=False,
        config={
            "_panel_custom": {
                "name": "chihiros-panel",
                "module_url": f"{FRONTEND_STATIC_URL}/chihiros-panel.js?v={panel_version}",
                "embed_iframe": False,
                "trust_external_script": True,
            }
        },
    )
    hass.data[FRONTEND_PANEL_REGISTERED] = True


class ChihirosPluginBackendView(HomeAssistantView):
    """Call optional dashboard plugin backend functions from the HA panel."""

    url = "/api/chihiros/plugin-backend"
    name = "api:chihiros:plugin_backend"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle one plugin backend call."""
        try:
            data = await request.json()
        except ValueError:
            return web.json_response({"message": "Invalid JSON"}, status=400)

        plugin = re.sub(r"[^a-z0-9_]+", "", str(data.get("plugin") or "").strip().lower())
        function_name = re.sub(r"[^a-zA-Z0-9_]+", "", str(data.get("function") or "").strip())
        args = data.get("args", [])
        if not plugin or not function_name:
            return web.json_response({"message": "Plugin oder Funktion fehlt"}, status=400)
        if not isinstance(args, list):
            return web.json_response({"message": "args muss eine Liste sein"}, status=400)

        backend_path = Path(__file__).parent / "plugins" / plugin / "backend.py"
        if not backend_path.is_file():
            return web.json_response({"message": f"Plugin Backend nicht gefunden: {plugin}"}, status=404)

        try:
            spec = importlib.util.spec_from_file_location(f"chihiros_{plugin}_plugin_backend", backend_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Plugin Backend kann nicht geladen werden: {backend_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            func = getattr(module, function_name, None)
            if not callable(func):
                return web.json_response({"message": f"Plugin Funktion fehlt: {plugin}.{function_name}"}, status=404)
            result = func(*args)
        except ValueError as err:
            return web.json_response({"message": str(err)}, status=400)
        except Exception as err:  # noqa: BLE001
            return web.json_response({"message": str(err)}, status=500)

        return web.json_response(result if isinstance(result, dict) else {"result": result})


def _async_update_services(hass: HomeAssistant) -> None:
    """Register services that apply to currently configured device capabilities."""
    has_dosing_device = _has_dosing_devices(hass)
    has_stirrer_device = _has_stirrer_devices(hass)

    async_update_led_services(hass, True, lambda data: _resolve_service_device(hass, data))

    async_update_doser_services(hass, has_dosing_device, lambda data: _resolve_service_device(hass, data))
    async_update_stirrer_services(hass, has_stirrer_device)


def _has_dosing_devices(hass: HomeAssistant) -> bool:
    """Return whether any configured device supports dosing services."""
    return any(data.dosing_totals for data in hass.data.get(DOMAIN, {}).values())


def _has_stirrer_devices(hass: HomeAssistant) -> bool:
    """Return whether any configured device supports stirrer services."""
    return any(getattr(data.device, "is_stirrer", False) for data in hass.data.get(DOMAIN, {}).values())


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
