"""Observed Chihiros dosing-pump frame helpers.

This module intentionally stays outside the upstream vendor package so the
reverse-engineered dosing additions can be reviewed or moved independently.
"""

# ruff: noqa: E501

from __future__ import annotations

from datetime import datetime

from ...vendor.chihiros_led_control.protocol import create_command_encoding
from .types import DoserSchedule

TIMER_ENTRIES_PER_FRAME = 13
TIMER_MAX_ENTRIES = 24
WINDOW_MAX_DOSES = 24


def split_ml_25_6(ml: float) -> tuple[int, int]:
    """Encode mL as 25.6 mL buckets plus 0.1 mL remainder."""
    if ml < 0.0 or ml > 999.9:
        raise ValueError("Volume must be between 0.0 and 999.9 mL")
    tenths_ml = int(round(float(ml) * 10))
    return divmod(tenths_ml, 256)


def split_calibration_ml(measured_ml: float) -> tuple[int, int]:
    """Encode an app-observed calibration measurement as whole mL and hundredths."""
    hundredths_ml = int(round(float(measured_ml) * 100))
    if hundredths_ml < 0 or hundredths_ml > 25599:
        raise ValueError("Calibration volume must be between 0.00 and 255.99 mL")
    return divmod(hundredths_ml, 100)


def dosing_auth_frames(next_msg_id) -> list[bytearray]:
    """Return the two app-observed dosing auth frames."""
    return [
        create_command_encoding(165, 4, next_msg_id(), [4]),
        create_command_encoding(165, 4, next_msg_id(), [5]),
    ]


def app_schedule_prelude_frames(next_msg_id) -> list[bytearray]:
    """Return the app-observed prelude before writing dosing schedules."""
    now = datetime.now()
    time_params = [
        (now.year - 2000) & 0xFF,
        now.month & 0xFF,
        now.isoweekday() & 0xFF,
        now.hour & 0xFF,
        now.minute & 0xFF,
        now.second & 0xFF,
    ]
    return [
        create_command_encoding(90, 4, next_msg_id(), [1]),
        create_command_encoding(90, 9, next_msg_id(), time_params),
        create_command_encoding(90, 9, next_msg_id(), time_params),
        *dosing_auth_frames(next_msg_id),
    ]


def weekday_mask(weekdays: tuple[str, ...]) -> int:
    """Return the dosing-pump weekday bitmask used by the app protocol."""
    selected = {str(day).lower() for day in weekdays}
    if not selected or "everyday" in selected:
        return 127
    bits = {
        "monday": 64,
        "tuesday": 32,
        "wednesday": 16,
        "thursday": 8,
        "friday": 4,
        "saturday": 2,
        "sunday": 1,
    }
    mask = 0
    for day in selected:
        mask |= bits.get(day, 0)
    return mask or 127


def timer_params(pump_idx: int, timer_type: int, hour: int, minute: int) -> list[int]:
    """Return the 0x15 timer frame parameters."""
    return [int(pump_idx), int(timer_type), int(hour), int(minute), 0, 0]


def timer_schedule_frames(next_msg_id, schedule: DoserSchedule) -> list[bytearray]:
    """Return the app-observed active, total and chunked timer-list frames."""
    entries = tuple(schedule.timer_entries)
    if not 1 <= len(entries) <= TIMER_MAX_ENTRIES:
        raise ValueError(f"Timer lists need 1..{TIMER_MAX_ENTRIES} entries")
    total_ml = round(sum(float(ml) for _time_text, ml in entries), 1)
    total_high, total_low = split_ml_25_6(total_ml)
    frames = [
        create_command_encoding(165, 32, next_msg_id(), [schedule.pump_idx, 0, 1]),
        create_command_encoding(
            165,
            27,
            next_msg_id(),
            [
                schedule.pump_idx,
                weekday_mask(schedule.weekdays),
                1 if schedule.active else 0,
                1 if schedule.valid_from_tomorrow else 0,
                total_high,
                total_low,
            ],
            sanitize_parameters=False,
        ),
    ]
    for offset in range(0, len(entries), TIMER_ENTRIES_PER_FRAME):
        params = [schedule.pump_idx, 3]
        for time_text, ml in entries[offset : offset + TIMER_ENTRIES_PER_FRAME]:
            hour, minute = [int(part) for part in str(time_text).split(":", 1)]
            amount_tenths = int(round(float(ml) * 10))
            if not 0 <= amount_tenths <= 0xFFFF:
                raise ValueError("Timer entry volume must fit into an unsigned 16-bit tenth-mL value")
            params.extend([hour, minute, amount_tenths >> 8, amount_tenths & 0xFF])
        frames.append(create_command_encoding(165, 21, next_msg_id(), params, sanitize_parameters=False))
    return frames


def window_schedule_frames(next_msg_id, schedule: DoserSchedule) -> list[bytearray]:
    """Return the app-observed active, daily-total and custom-window frames."""
    entries = tuple(schedule.window_entries)
    if not entries:
        raise ValueError("Custom schedules need at least one time window")
    total_doses = sum(int(doses) for _start, _end, doses in entries)
    if not 1 <= total_doses <= WINDOW_MAX_DOSES:
        raise ValueError(f"Custom schedules need 1..{WINDOW_MAX_DOSES} doses in total")
    total_high, total_low = split_ml_25_6(float(schedule.ml))
    frames = [
        create_command_encoding(165, 32, next_msg_id(), [schedule.pump_idx, 0, 1]),
        create_command_encoding(
            165,
            27,
            next_msg_id(),
            [
                schedule.pump_idx,
                weekday_mask(schedule.weekdays),
                1 if schedule.active else 0,
                1 if schedule.valid_from_tomorrow else 0,
                total_high,
                total_low,
            ],
            sanitize_parameters=False,
        ),
    ]
    params = [schedule.pump_idx]
    for start_text, end_text, doses in entries:
        start_hour, start_minute = [int(part) for part in str(start_text).split(":", 1)]
        end_hour, end_minute = [int(part) for part in str(end_text).split(":", 1)]
        params.extend([start_hour, start_minute, end_hour, end_minute, int(doses)])
    frames.append(create_command_encoding(165, 23, next_msg_id(), params))
    return frames


def calibration_prepare_frames(next_msg_id, pump_idx: int) -> list[bytearray]:
    """Return channel selection and dosing auth after the central connection prelude."""
    return [
        create_command_encoding(165, 5, next_msg_id(), [25 + int(pump_idx), 255, 255]),
        *dosing_auth_frames(next_msg_id),
    ]


def calibration_prime_frames(next_msg_id, pump_idx: int, active: bool, *, prepared: bool = False) -> list[bytearray]:
    """Return the confirmed hose-fill on/off frame for one selected pump channel."""
    if not 0 <= int(pump_idx) <= 3:
        raise ValueError("pump_idx must be 0..3")
    params = [255] * 10
    params[2 + int(pump_idx)] = 1 if active else 0
    frames = [] if prepared or not active else calibration_prepare_frames(next_msg_id, pump_idx)
    return [*frames, create_command_encoding(165, 20, next_msg_id(), params)]


def calibration_start_frames(next_msg_id, pump_idx: int, *, prepared: bool = False) -> list[bytearray]:
    """Return frames to start calibration for a pump channel."""
    frames = [] if prepared else calibration_prepare_frames(next_msg_id, pump_idx)
    return [*frames, create_command_encoding(165, 22, next_msg_id(), [pump_idx, 5, 255, 255])]


def calibration_submit_frames(next_msg_id, pump_idx: int, measured_ml: float, test_ml: float | None) -> list[bytearray]:
    """Return frames to submit calibration result and optionally run a test dose."""
    whole_ml, hundredths = split_calibration_ml(measured_ml)
    frames = [create_command_encoding(165, 22, next_msg_id(), [pump_idx, 255, whole_ml, hundredths])]
    if test_ml is not None:
        test_high, test_low = split_ml_25_6(test_ml)
        frames.append(create_command_encoding(165, 27, next_msg_id(), [pump_idx, 0, 0, test_high, test_low]))
    return frames


def calibration_test_frames(next_msg_id, pump_idx: int, test_ml: float = 4.0) -> list[bytearray]:
    """Return the confirmed separate calibration test-dose frame."""
    test_high, test_low = split_ml_25_6(test_ml)
    return [create_command_encoding(165, 27, next_msg_id(), [pump_idx, 0, 0, test_high, test_low])]


def schedule_frames(next_msg_id, schedule: DoserSchedule) -> list[bytearray]:
    """Return app-style frames to write one dosing schedule."""
    dose_high, dose_low = split_ml_25_6(schedule.ml)
    valid_from_tomorrow = 1 if schedule.valid_from_tomorrow else 0
    if schedule.kind == "interval":
        hour = 0
        minute = max(0, min(59, int(schedule.interval_minutes if schedule.interval_minutes is not None else 0)))
        timer_type = 1
    else:
        hour, minute = [int(part) for part in schedule.time.split(":", 1)]
        timer_type = 0
    return [
        *app_schedule_prelude_frames(next_msg_id),
        create_command_encoding(165, 32, next_msg_id(), [schedule.pump_idx, 0, 1]),
        create_command_encoding(
            165,
            27,
            next_msg_id(),
            [
                schedule.pump_idx,
                weekday_mask(schedule.weekdays),
                1 if schedule.active else 0,
                valid_from_tomorrow,
                dose_high,
                dose_low,
            ],
        ),
        create_command_encoding(165, 21, next_msg_id(), timer_params(schedule.pump_idx, timer_type, hour, minute)),
        create_command_encoding(90, 4, next_msg_id(), [1]),
    ]


def schedule_disable_frames(next_msg_id, pump_idx: int) -> list[bytearray]:
    """Return frames to disable the dosing schedule for one pump channel."""
    return [
        *dosing_auth_frames(next_msg_id),
        create_command_encoding(165, 32, next_msg_id(), [int(pump_idx), 0, 0]),
    ]
