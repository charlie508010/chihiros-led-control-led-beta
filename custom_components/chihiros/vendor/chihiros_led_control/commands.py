"""High-level Chihiros command builders."""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from .protocol import calculate_checksum, create_command_encoding, encode_timestamp, next_message_id

AUTO_SETTING_PARAMETER_COUNT = 14
AUTO_SETTING_METADATA_PARAMETER_COUNT = 6
DOSE_VOLUME_BUCKET_TENTHS_ML = 256
DOSER_WEEKDAY_MASK_EVERYDAY = 0x7F


def _validate_byte(value: int) -> int:
    if value < 0 or value > 255:
        raise ValueError(f"Parameter byte out of range 0..255: {value}")
    return int(value)


def create_doser_command_encoding(
    cmd_id: int,
    cmd_mode: int,
    msg_id: tuple[int, int],
    parameters: list[int],
) -> bytearray:
    """Encode an A5/5A dosing-pump or MagStirrer command without payload rewriting."""
    params = [_validate_byte(int(value)) for value in parameters]
    safe_msg_id = msg_id
    for _attempt in range(8):
        frame = bytearray(
            [
                _validate_byte(cmd_id),
                1,
                len(params) + 5,
                _validate_byte(safe_msg_id[0]),
                _validate_byte(safe_msg_id[1]),
                _validate_byte(cmd_mode),
                *params,
            ]
        )
        checksum = calculate_checksum(frame)
        if checksum != 0x5A:
            return frame + bytes([checksum])
        safe_msg_id = next_message_id(safe_msg_id)
    return frame + bytes([checksum])


def _create_doser_query_encoding(
    cmd_mode: int,
    msg_id: tuple[int, int],
    parameters: list[int],
) -> bytearray:
    """Encode a 5B Doser query frame."""
    params = [_validate_byte(int(value)) for value in parameters]
    frame = bytearray(
        [
            0x5B,
            1,
            len(params) + 2,
            _validate_byte(msg_id[0]),
            _validate_byte(msg_id[1]),
            _validate_byte(cmd_mode),
            *params,
        ]
    )
    checksum = frame[1]
    for value in frame[2:]:
        checksum ^= value
    return frame + bytes([checksum & 0xFF])


def create_base_auth_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the base LED auth/status command used at connection startup."""
    return create_command_encoding(90, 4, msg_id, [1])


def split_dose_volume_ml(ml: float) -> tuple[int, int]:
    """Encode a dosing pump volume as 25.6 mL buckets plus 0.1 mL remainder."""
    if ml < 0.2 or ml > 999.9:
        raise ValueError("Dose volume must be between 0.2 and 999.9 mL")
    tenths_ml = int(round(ml * 10))
    return divmod(tenths_ml, DOSE_VOLUME_BUCKET_TENTHS_ML)


def create_dose_auth_1_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the first dosing pump auth command."""
    return create_doser_command_encoding(165, 4, msg_id, [4])


def create_dose_auth_2_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the second dosing pump auth command."""
    return create_doser_command_encoding(165, 4, msg_id, [5])


def create_manual_dose_command(msg_id: tuple[int, int], pump_idx: int, volume_ml: float) -> bytearray:
    """Create a manual dosing command for one pump.

    Volumes are encoded as ``high * 25.6 mL + low * 0.1 mL``. This is compatible
    with the older single-byte examples for doses up to 25.5 mL because
    ``high`` is then zero.
    """
    if pump_idx < 0 or pump_idx > 3:
        raise ValueError("Pump index must be between 0 and 3")
    high, low = split_dose_volume_ml(volume_ml)
    return create_doser_command_encoding(165, 27, msg_id, [pump_idx, 0, 0, high, low])


def create_doser_set_time_command(
    msg_id: tuple[int, int],
    timestamp: datetime.datetime | None = None,
) -> bytearray:
    """Create the Doser/MagStirrer time-sync command."""
    return create_doser_command_encoding(90, 9, msg_id, encode_timestamp(timestamp or datetime.datetime.now()))


def create_doser_order_confirmation(msg_id: tuple[int, int], command_id: int, mode: int, command: int) -> bytearray:
    """Create a one-byte Doser/MagStirrer confirmation frame."""
    return create_doser_command_encoding(command_id, mode, msg_id, [command])


def create_doser_schedule_active_command(
    msg_id: tuple[int, int],
    pump_idx: int,
    active: bool,
    catch_up_missed: int = 0,
) -> bytearray:
    """Create the Doser schedule active/catch-up frame."""
    return create_doser_command_encoding(165, 32, msg_id, [pump_idx, catch_up_missed, 1 if active else 0])


def create_doser_schedule_time_command(
    msg_id: tuple[int, int],
    pump_idx: int,
    performance_time: datetime.time,
    timer_type: int = 0,
) -> bytearray:
    """Create the Doser schedule time frame."""
    return create_doser_command_encoding(
        165,
        21,
        msg_id,
        [pump_idx, timer_type, performance_time.hour, performance_time.minute, 0, 0],
    )


def create_doser_schedule_amount_command(
    msg_id: tuple[int, int],
    pump_idx: int,
    weekdays_mask: int,
    dose_ml: float,
    active: bool = True,
    next_day_flag: bool = False,
) -> bytearray:
    """Create the Doser schedule amount frame used by the current app."""
    high, low = split_dose_volume_ml(dose_ml)
    return create_doser_command_encoding(
        165,
        27,
        msg_id,
        [
            pump_idx,
            weekdays_mask & DOSER_WEEKDAY_MASK_EVERYDAY,
            1 if active else 0,
            1 if next_day_flag else 0,
            high,
            low,
        ],
    )


def create_doser_schedule_commands(
    msg_id_time: tuple[int, int],
    msg_id_amount: tuple[int, int],
    pump_idx: int,
    performance_time: datetime.time,
    weekdays_mask: int,
    dose_ml: float,
    active: bool = True,
    next_day_flag: bool = False,
    timer_type: int = 0,
) -> list[bytearray]:
    """Create the Doser schedule amount and time frames in app order."""
    return [
        create_doser_schedule_amount_command(
            msg_id_amount,
            pump_idx,
            weekdays_mask,
            dose_ml,
            active=active,
            next_day_flag=next_day_flag,
        ),
        create_doser_schedule_time_command(msg_id_time, pump_idx, performance_time, timer_type=timer_type),
    ]


def create_doser_timer_payload(
    pump_idx: int, timer_type: int, entries: Sequence[tuple[datetime.time, int]]
) -> list[int]:
    """Build Doser timer-list parameters as ``[channel, timer_type, HH, MM, hi, lo...]``."""
    if not entries:
        raise ValueError("At least one timer entry is required")
    params = [pump_idx, timer_type]
    for entry_time, raw_value in entries:
        params.extend([entry_time.hour, entry_time.minute, (raw_value >> 8) & 0xFF, raw_value & 0xFF])
    return params


def create_doser_custom_schedule_command(
    msg_id: tuple[int, int],
    mode: int,
    parameters: list[int],
) -> bytearray:
    """Create a Doser custom schedule command for timer/window variants."""
    return create_doser_command_encoding(165, mode, msg_id, parameters)


def create_doser_totals_query_command(msg_id: tuple[int, int], mode: int = 0x34) -> bytearray:
    """Create a Doser daily totals query frame."""
    return _create_doser_query_encoding(mode, msg_id, [])


def create_magstirrer_power_command(msg_id: tuple[int, int], on: bool) -> bytearray:
    """Create the MagStirrer run/power frame."""
    return create_doser_command_encoding(
        165,
        20,
        msg_id,
        [0xFF, 0xFF, 1 if on else 0, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
    )


def create_magstirrer_auto_mode_command(
    msg_id: tuple[int, int],
    channel_idx: int,
    active: bool,
    catch_up: int = 0,
) -> bytearray:
    """Create the MagStirrer channel active/catch-up frame."""
    return create_doser_schedule_active_command(msg_id, channel_idx, active, catch_up)


def create_magstirrer_runtime_speed_command(
    msg_id: tuple[int, int],
    channel_idx: int,
    runtime_minutes: int,
    speed_percent: int,
) -> bytearray:
    """Create the MagStirrer runtime/speed frame."""
    return create_doser_command_encoding(165, 42, msg_id, [channel_idx, 0, runtime_minutes, speed_percent])


def create_magstirrer_timer_command(
    msg_id: tuple[int, int],
    channel_idx: int,
    entries: Sequence[tuple[datetime.time, int]],
    timer_type: int = 3,
) -> bytearray:
    """Create the MagStirrer timer-list frame."""
    return create_doser_command_encoding(165, 21, msg_id, create_doser_timer_payload(channel_idx, timer_type, entries))


def create_set_time_command(msg_id: tuple[int, int], timestamp: datetime.datetime | None = None) -> bytearray:
    """Create the current time command."""
    return create_command_encoding(90, 9, msg_id, encode_timestamp(timestamp or datetime.datetime.now()))


def create_set_date_command(msg_id: tuple[int, int], timestamp: datetime.datetime | None = None) -> bytearray:
    """Create the shortened date-only command used when opening the automatic tab."""
    return create_command_encoding(90, 9, msg_id, encode_timestamp(timestamp or datetime.datetime.now())[:3])


def create_doser_year_command(msg_id: tuple[int, int], timestamp: datetime.datetime | None = None) -> bytearray:
    """Create the one-byte year command observed before manual Doser actions."""
    return create_doser_command_encoding(90, 9, msg_id, [int((timestamp or datetime.datetime.now()).year) % 100])


def create_set_brightness_command(msg_id: tuple[int, int], color: int, brightness_level: int) -> bytearray:
    """Create a brightness command."""
    return create_command_encoding(90, 7, msg_id, [color, brightness_level])


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
    return create_command_encoding(90, 5, msg_id, [18, 255, 255])


def create_switch_to_automatic_tab_command(msg_id: tuple[int, int]) -> bytearray:
    """Create the shortened auto-mode command used when opening the automatic tab."""
    return create_command_encoding(90, 5, msg_id, [18, 255])
