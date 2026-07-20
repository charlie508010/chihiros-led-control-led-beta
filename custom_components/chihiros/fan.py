"""Compatibility wrapper for the LED plugin fan platform."""

from .plugins.led.entities.fan import ChihirosFanEntity
from .plugins.led.entities.fan import async_setup_entry as async_setup_led_plugin_entry

_legacy_async_setup_entry = async_setup_led_plugin_entry
async_setup_entry = async_setup_led_plugin_entry

__all__ = ["ChihirosFanEntity", "async_setup_entry"]
