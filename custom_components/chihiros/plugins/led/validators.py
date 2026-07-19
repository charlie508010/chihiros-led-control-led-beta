"""Validation helpers for LED schedule services."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_END,
    ATTR_LEVELS,
    ATTR_START,
    ATTR_WEEKDAYS,
)
from .models import ChihirosData
from .vendor.chihiros_led_control.schedule_validation import normalize_schedule_weekdays
from .vendor.chihiros_led_control.weekday_encoding import WeekdaySelect


def parse_schedule_time(value: str) -> datetime:
    """Parse an HH:MM schedule value into a datetime accepted by the runtime client."""
    try:
        parsed_time = datetime.strptime(value, "%H:%M").time()
    except ValueError as ex:
        raise HomeAssistantError(f"Invalid schedule time {value!r}; expected HH:MM") from ex
    return datetime.combine(date.today(), parsed_time)


def parse_weekdays(value: list[str] | None) -> list[WeekdaySelect] | None:
    """Parse service weekday strings."""
    if value is None:
        return None
    return [WeekdaySelect(weekday) for weekday in value]


def brightness_from_service_data(data: dict[str, Any]) -> int | dict[str, int]:
    """Return brightness data accepted by the runtime client."""
    if ATTR_LEVELS in data:
        return dict(data[ATTR_LEVELS])
    brightness = data[ATTR_BRIGHTNESS]
    if isinstance(brightness, dict):
        return dict(brightness)
    return brightness


def validate_time_range(start: datetime, end: datetime) -> None:
    """Validate schedule start/end ordering."""
    if start >= end:
        raise HomeAssistantError("Schedule start time must be before end time")


def validate_schedule_periods(chihiros_data: ChihirosData, periods: list[dict[str, Any]]) -> None:
    """Validate a full replacement schedule before writing anything to the device."""
    if not periods:
        raise HomeAssistantError("Schedule must contain at least one period")
    for period in periods:
        validate_schedule_period(chihiros_data, period)


def validate_schedule_period(chihiros_data: ChihirosData, data: dict[str, Any]) -> dict[str, Any]:
    """Validate one schedule period against the selected device."""
    start = parse_schedule_time(data[ATTR_START])
    end = parse_schedule_time(data[ATTR_END])
    validate_time_range(start, end)
    validate_schedule_brightness(chihiros_data, data)
    weekdays = normalize_schedule_weekdays(parse_weekdays(data.get(ATTR_WEEKDAYS)))
    return {
        "weekdays": weekdays,
    }


def validate_schedule_brightness(chihiros_data: ChihirosData, data: dict[str, Any]) -> None:
    """Validate schedule channel levels against the device model."""
    supported_channels = set(chihiros_data.device.colors)
    brightness = brightness_from_service_data(data)
    if isinstance(brightness, int):
        if not supported_channels:
            raise HomeAssistantError(f"{chihiros_data.device.name} does not expose any controllable channels")
        return
    if not brightness:
        raise HomeAssistantError("Schedule levels must contain at least one channel")
    requested_channels = set(brightness)
    unsupported_channels = requested_channels - supported_channels
    if unsupported_channels:
        unsupported = ", ".join(sorted(unsupported_channels))
        supported = ", ".join(sorted(supported_channels))
        raise HomeAssistantError(
            f"Channel {unsupported} is not supported by {chihiros_data.device.name}. Supported channels: {supported}"
        )


def validate_brightness(chihiros_data: ChihirosData, brightness: int | dict[str, int]) -> None:
    """Validate manual brightness data against the selected device."""
    supported_channels = set(chihiros_data.device.colors)
    if isinstance(brightness, int):
        if not supported_channels:
            raise HomeAssistantError(f"{chihiros_data.device.name} does not expose any controllable channels")
        return
    if not brightness:
        raise HomeAssistantError("Brightness must contain at least one channel")
    requested_channels = set(brightness)
    unsupported_channels = requested_channels - supported_channels
    if unsupported_channels:
        unsupported = ", ".join(sorted(unsupported_channels))
        supported = ", ".join(sorted(supported_channels))
        raise HomeAssistantError(
            f"Channel {unsupported} is not supported by {chihiros_data.device.name}. Supported channels: {supported}"
        )


def normalized_period_weekdays(periods: list[dict[str, Any]]) -> list[list[str]]:
    """Return service-debug friendly normalized weekdays for periods."""
    return [
        sorted(
            str(day.value if hasattr(day, "value") else day)
            for day in normalize_schedule_weekdays(period.get(ATTR_WEEKDAYS))
        )
        for period in periods
    ]
