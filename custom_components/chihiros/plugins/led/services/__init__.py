"""Canonical Home Assistant services provided by the LED plugin."""

from .runtime import async_enable_led_auto_mode, async_update_led_services

__all__ = ["async_enable_led_auto_mode", "async_update_led_services"]
