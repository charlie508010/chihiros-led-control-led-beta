"""Compatibility wrapper for built-in and external plugin switches."""

from __future__ import annotations

from .core.device_entries import is_doser_entry
from .core.plugin_loader.platforms import async_setup_plugin_platform_entries
from .plugins.led.entities.switch import (
    ChihirosAutoManualSwitch,
)
from .plugins.led.entities.switch import (
    async_setup_entry as async_setup_led_plugin_entry,
)
from .plugins.led.services import async_enable_led_auto_mode

_legacy_async_setup_entry = async_setup_led_plugin_entry


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up built-in LED switches or external Doser plugin switches."""
    if not is_doser_entry(entry):
        await async_setup_led_plugin_entry(hass, entry, async_add_entities)
    await async_setup_plugin_platform_entries(hass, entry, async_add_entities, "switch")

__all__ = [
    "ChihirosAutoManualSwitch",
    "async_enable_led_auto_mode",
    "async_setup_entry",
]
