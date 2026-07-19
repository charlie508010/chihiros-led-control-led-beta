"""Tests for Chihiros BLE protocol helpers."""

from __future__ import annotations

import datetime

from chihiros_led_control import commands
from chihiros_led_control.models import RGB_CHANNELS, WHITE_CHANNELS, WRGB_CHANNELS
from chihiros_led_control.protocol import (
    RuntimeNotification,
    SchedulePoint,
    ScheduleSnapshotNotification,
    calculate_checksum,
    create_command_encoding,
    encode_timestamp,
    next_message_id,
    parse_notification,
)

SCHEDULE_SNAPSHOT_PREFIX = [
    0x5B,
    0x17,
    0x30,
    0x00,
    0x01,
    0xFE,
    0x01,
    0x12,
    0x0B,
    0x0D,
    0x0F,
    0x00,
    0x00,
    0x00,
    0x00,
    0x11,
    0x08,
    0x11,
    0x0C,
    0x11,
    0x13,
    0x00,
    0x01,
    0x12,
    0x0B,
]


def test_next_message_id_skips_reserved_lower_byte() -> None:
    """Message ids skip reserved lower byte 90."""
    assert next_message_id((0, 89)) == (0, 91)


def test_next_message_id_skips_reserved_higher_byte() -> None:
    """Message ids skip reserved higher byte 90."""
    assert next_message_id((89, 255)) == (91, 0)


def test_next_message_id_preserves_higher_byte() -> None:
    """Message ids increment the lower byte without resetting the higher byte."""
    assert next_message_id((1, 1)) == (1, 2)


def test_next_message_id_skips_reserved_lower_byte_with_higher_byte() -> None:
    """Message ids skip reserved lower byte without resetting the higher byte."""
    assert next_message_id((1, 89)) == (1, 91)


def test_next_message_id_wraps_after_maximum() -> None:
    """Message ids wrap after the maximum byte pair."""
    assert next_message_id((255, 255)) == (0, 1)


def test_calculate_checksum_xors_command_bytes() -> None:
    """Checksum is calculated by XORing bytes after the command id."""
    assert calculate_checksum(bytes([90, 1, 7, 0, 1, 7, 0, 100])) == 100


def test_command_encoding_sanitizes_reserved_parameter() -> None:
    """Command encoding avoids the reserved byte in parameters."""
    command = create_command_encoding(90, 7, (0, 1), [0, 90])

    assert command == bytearray([90, 1, 7, 0, 1, 7, 0, 89, 89])


def test_command_encoding_can_keep_reserved_parameter_for_newer_protocols() -> None:
    """Command encoding can keep reserved bytes when requested."""
    command = create_command_encoding(165, 27, (0, 1), [0, 90], avoid_reserved_byte=False)

    assert command == bytearray([165, 1, 7, 0, 1, 27, 0, 90, 70])


def test_command_encoding_can_keep_parameter_and_still_protect_message_id() -> None:
    """Newer commands keep reserved parameters while retaining message-id protection."""
    command = create_command_encoding(165, 21, (0, 90), [0, 90], sanitize_parameters=False)

    assert command[3:5] == bytearray([0, 91])
    assert command[6:8] == bytearray([0, 90])


def test_command_encoding_normalizes_reserved_message_id() -> None:
    """Command encoding avoids reserved message IDs passed directly."""
    command = create_command_encoding(90, 7, (0, 90), [0, 100])

    assert command[3:5] == bytearray([0, 91])


def test_set_brightness_command_encoding() -> None:
    """Brightness commands encode color and brightness."""
    assert commands.create_set_brightness_command((0, 1), 0, 100) == bytearray([90, 1, 7, 0, 1, 7, 0, 100, 100])


def test_automatic_tab_short_command_encodings() -> None:
    """Automatic-tab transitions use the observed shortened date and mode frames."""
    timestamp = datetime.datetime(2026, 7, 12, 15, 26, 43)

    assert commands.create_set_date_command((0, 1), timestamp)[5:-1] == bytes([9, 26, 7, 7])
    assert commands.create_switch_to_automatic_tab_command((0, 2))[5:-1] == bytes([5, 18, 255])


def test_apply_manual_color_command_encoding() -> None:
    """Manual color updates include the app's apply command."""
    assert commands.create_apply_manual_color_command((0, 1)) == bytearray([90, 1, 8, 0, 1, 5, 11, 255, 255, 6])


def test_base_auth_command_encoding() -> None:
    """Base auth commands use the LED status/auth frame."""
    assert commands.create_base_auth_command((0, 1)) == bytearray([90, 1, 6, 0, 1, 4, 1, 3])


def test_dosing_auth_command_encoding() -> None:
    """Dosing auth commands use DEVICE auth data 4 and 5."""
    assert commands.create_dose_auth_1_command((0, 4)) == bytearray([165, 1, 6, 0, 4, 4, 4, 3])
    assert commands.create_dose_auth_2_command((0, 5)) == bytearray([165, 1, 6, 0, 5, 4, 5, 3])


def test_doser_year_command_encoding() -> None:
    """Manual Doser setup sends only the two-digit year in its second mode-9 frame."""
    timestamp = datetime.datetime(2026, 7, 16, 8, 30, 21)
    command = commands.create_doser_year_command((0, 3), timestamp)
    assert command[5:-1] == bytearray([9, 26])


def test_manual_dose_command_encoding_small_volume() -> None:
    """Manual dose encoding is compatible with single-byte examples for small volumes."""
    assert commands.create_manual_dose_command((0, 6), 0, 2.0) == bytearray([165, 1, 10, 0, 6, 27, 0, 0, 0, 0, 20, 2])


def test_manual_dose_command_encoding_large_volume() -> None:
    """Manual dose encoding supports 25.6 mL buckets for larger volumes."""
    assert commands.split_dose_volume_ml(29.0) == (1, 34)
    command = commands.create_manual_dose_command((0, 6), 2, 29.0)
    assert command[6:-1] == bytearray([2, 0, 0, 1, 34])


def test_manual_dose_command_matches_app_channel_two_26_ml() -> None:
    """The app encodes 26.0 mL on channel two as one 25.6 mL bucket plus four tenths."""
    assert commands.split_dose_volume_ml(26.0) == (1, 4)
    command = commands.create_manual_dose_command((0, 6), 1, 26.0)
    assert command[6:-1] == bytearray([1, 0, 0, 1, 4])


def test_auto_setting_command_accepts_four_channel_brightness() -> None:
    """Auto schedule commands can encode true WRGB brightness values."""
    command = commands.create_add_auto_setting_command(
        (0, 1),
        datetime.time(8, 0),
        datetime.time(18, 30),
        (10, 20, 30, 40),
        15,
        127,
    )

    assert command[6:-1] == bytearray([8, 0, 18, 30, 15, 127, 10, 20, 30, 40, 255, 255, 255, 255])


def test_auto_setting_command_normalizes_zero_ramp_to_one_minute() -> None:
    """Mode 25 must never transmit a zero-minute LED ramp."""
    command = commands.create_add_auto_setting_command(
        (0, 1),
        datetime.time(22, 15),
        datetime.time(23, 15),
        (100, 100, 100, 100),
        0,
        127,
    )

    assert command[6:-1] == bytearray([22, 15, 23, 15, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255])


def test_encode_timestamp() -> None:
    """Timestamps are encoded as protocol parameters."""
    timestamp = datetime.datetime(2026, 6, 11, 9, 8, 7)

    assert encode_timestamp(timestamp) == [26, 6, 4, 9, 8, 7]


def test_parse_runtime_notification() -> None:
    """Runtime notifications expose firmware and runtime minutes."""
    frame = bytearray.fromhex("5b170a00010a01ffffffffff13888c")
    notification = parse_notification(frame)

    assert notification == RuntimeNotification(firmware_version=23, runtime_minutes=5000, raw=bytes(frame))


def test_parse_runtime_notification_uses_changing_tail_counter() -> None:
    """Runtime comes from the changing tail bytes, not the fixed 0x01ff status field."""
    frame = bytearray.fromhex("5b150a00010a01ffffffff08908d")

    assert parse_notification(frame) == RuntimeNotification(
        firmware_version=21,
        runtime_minutes=2192,
        raw=bytes(frame),
    )


def test_parse_schedule_snapshot_notification_requires_channel_context() -> None:
    """Schedule snapshot notifications need model channel context."""
    notification = parse_notification(
        bytearray(
            [
                0x5B,
                0x17,
                0x13,
                0x00,
                0x01,
                0xFE,
                0x0D,
                0x0F,
                0x00,
                0x0D,
                0x2D,
                0x64,
                0x15,
                0x0F,
                0x64,
                0x15,
                0x2D,
                0x00,
                0x00,
            ]
        )
    )

    assert notification is None


def test_parse_schedule_snapshot_notification_for_single_channel_model() -> None:
    """Single-channel schedule snapshots use the model channel name."""
    notification = parse_notification(
        bytearray([*SCHEDULE_SNAPSHOT_PREFIX, 0x08, 0x00, 0x32]),
        WHITE_CHANNELS,
    )

    assert notification == ScheduleSnapshotNotification(
        firmware_version=23,
        points=(SchedulePoint(hour=8, minute=0, levels={"white": 50}),),
    )


def test_parse_schedule_snapshot_notification_for_rgb_model() -> None:
    """RGB schedule snapshots expose the common curve level under every channel."""
    notification = parse_notification(
        bytearray(
            [
                *SCHEDULE_SNAPSHOT_PREFIX,
                0x08,
                0x00,
                0x0A,
                0x12,
                0x1E,
                0x28,
            ]
        ),
        RGB_CHANNELS,
    )

    assert notification == ScheduleSnapshotNotification(
        firmware_version=23,
        points=(
            SchedulePoint(hour=8, minute=0, levels={"red": 10, "green": 10, "blue": 10}),
            SchedulePoint(hour=18, minute=30, levels={"red": 40, "green": 40, "blue": 40}),
        ),
    )


def test_parse_schedule_snapshot_notification_for_true_wrgb_model() -> None:
    """True WRGB schedule snapshots expose the common curve level under every channel."""
    notification = parse_notification(
        bytearray(
            [
                *SCHEDULE_SNAPSHOT_PREFIX,
                0x08,
                0x00,
                0x0A,
                0x12,
                0x1E,
                0x32,
            ]
        ),
        WRGB_CHANNELS,
    )

    assert notification == ScheduleSnapshotNotification(
        firmware_version=23,
        points=(
            SchedulePoint(hour=8, minute=0, levels={"red": 10, "green": 10, "blue": 10, "white": 10}),
            SchedulePoint(hour=18, minute=30, levels={"red": 50, "green": 50, "blue": 50, "white": 50}),
        ),
    )


def test_parse_schedule_snapshot_notification_skips_metadata_prefix() -> None:
    """Schedule snapshots skip status metadata before hour/minute/level data points."""
    notification = parse_notification(
        bytearray(
            [
                *SCHEDULE_SNAPSHOT_PREFIX,
                0x0D,
                0x0F,
                0x00,
                0x0D,
                0x2D,
                0x64,
                0x15,
                0x0F,
                0x64,
                0x15,
                0x2D,
                0x00,
            ]
        ),
        WHITE_CHANNELS,
    )

    assert notification == ScheduleSnapshotNotification(
        firmware_version=23,
        points=(
            SchedulePoint(hour=13, minute=15, levels={"white": 0}),
            SchedulePoint(hour=13, minute=45, levels={"white": 100}),
            SchedulePoint(hour=21, minute=15, levels={"white": 100}),
            SchedulePoint(hour=21, minute=45, levels={"white": 0}),
        ),
    )
