"""Compatibility wrapper for the LED plugin light platform."""

from .plugins.led.entities.light import (
    ChihirosLightEntity,
)
from .plugins.led.entities.light import (
    async_setup_entry as async_setup_led_plugin_entry,
)

_legacy_async_setup_entry = async_setup_led_plugin_entry
async_setup_entry = async_setup_led_plugin_entry

__all__ = ["ChihirosLightEntity", "async_setup_entry"]
