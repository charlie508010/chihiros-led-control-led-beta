"""Compatibility wrapper for the LED plugin switch platform."""

from .plugins.led.entities.switch import (
    ChihirosAutoManualSwitch,
)
from .plugins.led.entities.switch import (
    async_setup_entry as async_setup_led_plugin_entry,
)
from .plugins.led.services import async_enable_led_auto_mode

_legacy_async_setup_entry = async_setup_led_plugin_entry
async_setup_entry = async_setup_led_plugin_entry

__all__ = [
    "ChihirosAutoManualSwitch",
    "async_enable_led_auto_mode",
    "async_setup_entry",
]
