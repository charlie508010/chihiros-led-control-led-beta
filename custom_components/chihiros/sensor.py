"""Compatibility wrapper for the LED plugin sensor platform."""

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
async_setup_entry = async_setup_led_plugin_entry

__all__ = [
    "MAX_SENSOR_STATE_LENGTH",
    "SENSOR_DESCRIPTIONS",
    "ChihirosNotificationSensor",
    "_format_schedule_point",
    "_format_schedule_state",
    "async_setup_entry",
]
