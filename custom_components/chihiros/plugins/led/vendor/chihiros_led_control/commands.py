"""High-level Chihiros command builders."""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from .protocol import create_command_encoding, encode_timestamp

AUTO_SETTING_PARAMETER_COUNT = 14
AUTO_SETTING_METADATA_PARAMETER_COUNT = 6


def _validate_byte(value: int) -> int:
    if value < 0 or value > 255:
        raise ValueError(f"Parameter byte out of range 0..255: {value}")
    return int(value)


def create_base_auth_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the base LED auth/status command used at connection startup."""
    return create_command_encoding(90, 4, msg_id, [1])


def create_set_time_command(msg_id: tuple[int, int], timestamp: datetime.datetime | None = None) -> bytearray:
    """Create the current time command."""
    return create_command_encoding(90, 9, msg_id, encode_timestamp(timestamp or datetime.datetime.now()))


def create_set_date_command(msg_id: tuple[int, int], timestamp: datetime.datetime | None = None) -> bytearray:
    """Create the shortened date-only command used when opening the automatic tab."""
    return create_command_encoding(90, 9, msg_id, encode_timestamp(timestamp or datetime.datetime.now())[:3])


def create_set_brightness_command(msg_id: tuple[int, int], color: int, brightness_level: int) -> bytearray:
    """Create a brightness command."""
    return create_command_encoding(90, 7, msg_id, [color, brightness_level])


def create_set_fan_speed_command(msg_id: tuple[int, int], speed_percent: int) -> bytearray:
    """Create a fan speed command for fan-equipped LED devices."""
    if speed_percent < 0 or speed_percent > 100:
        raise ValueError("Fan speed must be between 0 and 100 percent")
    return create_command_encoding(90, 15, msg_id, [speed_percent])


def create_apply_manual_color_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the command that applies a manually selected LED color."""
    return create_command_encoding(90, 5, msg_id, [11, 255, 255])


def create_add_auto_setting_command(
    msg_id: tuple[int, int],
    sunrise: datetime.time,
    sunset: datetime.time,
    brightness: Sequence[int],
    ramp_up_minutes: int,
    weekdays: int,
) -> bytearray:
    """Create an add auto setting command."""
    if len(brightness) > AUTO_SETTING_PARAMETER_COUNT - AUTO_SETTING_METADATA_PARAMETER_COUNT:
        raise ValueError("Auto setting brightness has too many channel values")

    wire_ramp_up_minutes = max(1, int(ramp_up_minutes))
    parameters = [
        sunrise.hour,
        sunrise.minute,
        sunset.hour,
        sunset.minute,
        wire_ramp_up_minutes,
        weekdays,
        *brightness,
    ]
    parameters.extend([255] * (AUTO_SETTING_PARAMETER_COUNT - len(parameters)))

    return create_command_encoding(165, 25, msg_id, parameters)


def create_delete_auto_setting_command(
    msg_id: tuple[int, int],
    sunrise: datetime.time,
    sunset: datetime.time,
    ramp_up_minutes: int,
    weekdays: int,
    brightness_channels: int = 3,
) -> bytearray:
    """Create a delete auto setting command."""
    return create_add_auto_setting_command(
        msg_id,
        sunrise,
        sunset,
        [255] * brightness_channels,
        ramp_up_minutes,
        weekdays,
    )


def create_reset_auto_settings_command(msg_id: tuple[int, int], reset_parameter: int = 5) -> bytearray:
    """Create a reset auto settings command."""
    return create_auto_parameter_command(msg_id, reset_parameter)


def create_auto_parameter_command(msg_id: tuple[int, int], first_parameter: int) -> bytearray:
    """Create a diagnostic 90/5 command with a variable first parameter."""
    return create_command_encoding(90, 5, msg_id, [_validate_byte(first_parameter), 255, 255])


def create_switch_to_auto_mode_command(msg_id: tuple[int, int]) -> bytearray:
    """Create a switch to auto mode command."""
    return create_switch_to_automatic_tab_command(msg_id)


def create_switch_to_automatic_tab_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the shortened auto-mode command used when opening the automatic tab."""
    return create_command_encoding(90, 5, msg_id, [18, 255])
