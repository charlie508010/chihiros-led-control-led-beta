"""Compatibility wrapper for the LED plugin sensor platform."""

from __future__ import annotations

from .core.plugin_loader.platforms import async_setup_plugin_platform_entries
from .plugins.led.entities.sensor import (
    MAX_SENSOR_STATE_LENGTH,
    SENSOR_DESCRIPTIONS,
    ChihirosNotificationSensor,
    _format_schedule_point,
    _format_schedule_state,
)
from .plugins.led.entities.sensor import (
    async_setup_entry as async_setup_led_plugin_entry,
)

_legacy_async_setup_entry = async_setup_led_plugin_entry


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up built-in LED sensors and plugin sensor entities."""
    await async_setup_led_plugin_entry(hass, entry, async_add_entities)
    await async_setup_plugin_platform_entries(hass, entry, async_add_entities, "sensor")


__all__ = [
    "MAX_SENSOR_STATE_LENGTH",
    "SENSOR_DESCRIPTIONS",
    "ChihirosNotificationSensor",
    "_format_schedule_point",
    "_format_schedule_state",
    "async_setup_entry",
]
