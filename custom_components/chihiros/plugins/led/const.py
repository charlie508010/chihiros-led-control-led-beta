"""Constants for the Chihiros LED package."""

from __future__ import annotations

import voluptuous as vol

from .vendor.chihiros_led_control.weekday_encoding import WeekdaySelect

SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_ENABLE_AUTO_MODE = "enable_auto_mode"
SERVICE_REMOVE_SCHEDULE = "remove_schedule"
SERVICE_RESET_SCHEDULE = "reset_schedule"
SERVICE_SET_BRIGHTNESS = "set_brightness"
SERVICE_SET_SCHEDULE = "set_schedule"

ATTR_ACTIVE = "active"
ATTR_ADDRESS = "address"
ATTR_BRIGHTNESS = "brightness"
ATTR_DEBUG = "debug"
ATTR_DELETE_ONLY = "delete_only"
ATTR_END = "end"
ATTR_ENABLE_AUTO_MODE = "enable_auto_mode"
ATTR_ENTITY_ID = "entity_id"
ATTR_ENTRY_ID = "entry_id"
ATTR_LEVELS = "levels"
ATTR_NOTIFY_DEBUG_FILE = "notify_debug_file"
ATTR_PERIODS = "periods"
ATTR_PRESERVE_LOCAL = "preserve_local"
ATTR_PREVIOUS_PERIOD = "previous_period"
ATTR_PREVIOUS_INDEX = "previous_index"
ATTR_RAMP_UP_MINUTES = "ramp_up_minutes"
ATTR_SEND = "send"
ATTR_START = "start"
ATTR_WEEKDAYS = "weekdays"

WEEKDAY_VALUES = [weekday.value for weekday in WeekdaySelect]

BRIGHTNESS_VALUE_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
LEVELS_SCHEMA = {str: BRIGHTNESS_VALUE_SCHEMA}
SCHEDULE_SELECTOR_SCHEMA = {
    vol.Optional(ATTR_ENTRY_ID): str,
    vol.Optional(ATTR_ENTITY_ID): str,
    vol.Optional(ATTR_ADDRESS): str,
}
SCHEDULE_PERIOD_SCHEMA = {
    vol.Required(ATTR_START): str,
    vol.Required(ATTR_END): str,
    vol.Optional(ATTR_ACTIVE, default=True): bool,
    vol.Optional(ATTR_ENABLE_AUTO_MODE, default=True): bool,
    vol.Optional(ATTR_BRIGHTNESS, default=100): vol.Any(BRIGHTNESS_VALUE_SCHEMA, LEVELS_SCHEMA),
    vol.Optional(ATTR_LEVELS): LEVELS_SCHEMA,
    vol.Optional(ATTR_RAMP_UP_MINUTES, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
    vol.Optional(ATTR_WEEKDAYS): vol.All(list, [vol.In(WEEKDAY_VALUES)]),
}
ADD_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        **SCHEDULE_PERIOD_SCHEMA,
        vol.Optional(ATTR_PREVIOUS_PERIOD): vol.Schema(SCHEDULE_PERIOD_SCHEMA),
        vol.Optional(ATTR_PREVIOUS_INDEX): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_DELETE_ONLY, default=False): bool,
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
    }
)
ENABLE_AUTO_MODE_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        vol.Optional(ATTR_PERIODS): vol.All(list, [vol.Schema(SCHEDULE_PERIOD_SCHEMA)]),
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
    }
)
REMOVE_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        vol.Required(ATTR_START): str,
        vol.Required(ATTR_END): str,
        vol.Optional(ATTR_RAMP_UP_MINUTES, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        vol.Optional(ATTR_WEEKDAYS): vol.All(list, [vol.In(WEEKDAY_VALUES)]),
        vol.Optional(ATTR_DELETE_ONLY, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
    }
)
RESET_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
        vol.Optional(ATTR_PRESERVE_LOCAL, default=False): bool,
    }
)
SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        vol.Required(ATTR_PERIODS): vol.All(list, [vol.Schema(SCHEDULE_PERIOD_SCHEMA)]),
        vol.Optional(ATTR_SEND, default=True): bool,
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
    }
)
SET_BRIGHTNESS_SCHEMA = vol.Schema(
    {
        **SCHEDULE_SELECTOR_SCHEMA,
        vol.Required(ATTR_BRIGHTNESS): vol.Any(BRIGHTNESS_VALUE_SCHEMA, LEVELS_SCHEMA),
        vol.Optional(ATTR_DEBUG, default=False): bool,
        vol.Optional(ATTR_NOTIFY_DEBUG_FILE, default=False): bool,
    }
)
