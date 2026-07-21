"""Tests for the Chihiros BLE client."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import pytest

import chihiros_led_control.client as client_module
from chihiros_led_control.client import ChihirosDevice
from chihiros_led_control.models import RGB_CHANNELS, WHITE_CHANNELS, WRGB_CHANNELS, DeviceModel
from chihiros_led_control.protocol import (
    FanStatusNotification,
    RuntimeNotification,
    SchedulePoint,
    ScheduleSnapshotNotification,
    calculate_checksum,
)
from chihiros_led_control.weekday_encoding import WeekdaySelect


class FakeBLEDevice:
    """Small BLEDevice stand-in for client tests."""

    def __init__(self) -> None:
        """Create a fake BLE device."""
        self.name = "DYNA2-test"
        self.address = "AA:BB:CC:DD:EE:FF"


def test_compare_log_renders_sent_frames_only() -> None:
    """App-log comparison output must not include received frames."""

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        device.debug_frames.extend(
            [
                {"dir": "tx", "payload": bytes.fromhex("5a010800700505ffff79"), "time": "09.07.2026 04:31:34"},
                {"dir": "rx", "payload": bytes.fromhex("5b030a00010a01ffffffc8118faa"), "time": "09.07.2026 04:31:35"},
                {"dir": "tx", "payload": bytes.fromhex("5a01060074040176"), "time": "09.07.2026 04:31:38"},
                {
                    "dir": "rx",
                    "payload": bytes.fromhex(
                        "5b03300001fe04041f0400000000000000000004000000000000000a040000000000000000040000000000000000000000"
                    ),
                    "time": "09.07.2026 04:31:38",
                },
            ]
        )
        return device.render_compare_log()

    output = asyncio.run(run())

    assert '"dir": "tx"' in output
    assert "[INFO SYSTEM]" in output
    assert "[INFO]  {" not in output
    assert '"dir": "rx"' not in output
    assert "5B" not in output


def test_enable_auto_mode_sends_switch_and_reset() -> None:
    """Auto mode setup sends app-observed mode 18 followed by mode 5."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.enable_auto_mode()

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5, 5]
    assert sent_commands[0][6:-1] == bytes([18, 255])
    assert sent_commands[1][6:9] == bytes([5, 255, 255])


def test_enable_auto_mode_restores_existing_schedules_after_switch() -> None:
    """Stored schedules follow the two automatic-tab mode frames."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.enable_auto_mode(
            datetime(2026, 6, 16, 20, 30, 45),
            [
                (
                    datetime(2026, 6, 16, 12, 0),
                    datetime(2026, 6, 16, 18, 0),
                    {"red": 100, "green": 100, "blue": 100, "white": 100},
                    1,
                    [WeekdaySelect.everyday],
                )
            ],
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5, 5, 25]
    assert sent_commands[0][6:-1] == bytes([18, 255])
    assert sent_commands[1][6:9] == bytes([5, 255, 255])
    assert sent_commands[2][6:-1] == bytes([12, 0, 18, 0, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255])


def test_manual_color_apply_debug_meaning() -> None:
    """Manual color apply frames have a clear debug description."""

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        return device._describe_tx_frame(90, 5, [11, 255, 255])

    assert asyncio.run(run()) == "Schalter auf manuell setzen"


def test_schedule_delete_debug_meaning() -> None:
    """A mode 25 frame with cleared channel slots is described as schedule deactivation."""

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        return device._describe_tx_frame(165, 25, [9, 0, 17, 0, 1, 127, *([255] * 8)])

    assert asyncio.run(run()) == "LED-Zeitplan deaktivieren 09:00-17:00, Ramp=1 min, Wochentage=taeglich"


def test_remove_setting_sends_delete_immediately_after_connection_prelude() -> None:
    """Schedule deletion avoids a connector delay between RTC sync and the delete frame."""
    send_options: dict[str, object] = {}

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs: object,
        ) -> None:
            del command, retry
            send_options.update(kwargs)

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.remove_setting(
            datetime(2026, 7, 16, 22, 0),
            datetime(2026, 7, 16, 23, 0),
            ramp_up_in_minutes=1,
        )

    asyncio.run(run())

    assert send_options == {"immediate_after_prelude": True}


def test_dyu1000_remove_setting_sends_delete_finalize_sequence() -> None:
    """DYU1000 inactive schedule send repeats delete/finalize by default."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs: object,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.remove_setting(
            datetime(2026, 7, 16, 12, 0),
            datetime(2026, 7, 16, 18, 0),
            ramp_up_in_minutes=1,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 5, 25, 5]
    assert sent_commands[0][6:-1] == bytes([12, 0, 18, 0, 1, 127, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([40, 255, 255])
    assert sent_commands[2][6:-1] == bytes([12, 0, 18, 0, 1, 127, *([255] * 8)])
    assert sent_commands[3][6:-1] == bytes([40, 255, 255])


def test_dyu1000_delete_only_remove_setting_sends_delete_and_finalize_frame() -> None:
    """DYU1000 row deletion sends one delete frame and one finalize frame."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs: object,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.remove_setting(
            datetime(2026, 7, 16, 12, 0),
            datetime(2026, 7, 16, 18, 0),
            ramp_up_in_minutes=1,
            weekdays=[WeekdaySelect.monday, WeekdaySelect.wednesday, WeekdaySelect.friday],
            delete_only=True,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 5]
    assert sent_commands[0][6:-1] == bytes([12, 0, 18, 0, 1, 84, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([40, 255, 255])


def test_dyu1000_inactive_schedule_can_append_app_matching_final_values() -> None:
    """DYU1000 inactive schedule can append the app-observed final value frame."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs: object,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.remove_setting(
            datetime(2026, 7, 16, 12, 0),
            datetime(2026, 7, 16, 18, 0),
            max_brightness=(100, 100, 100, 100),
            ramp_up_in_minutes=1,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 5, 25, 5, 25]
    assert sent_commands[0][6:-1] == bytes([12, 0, 18, 0, 1, 127, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([40, 255, 255])
    assert sent_commands[2][6:-1] == bytes([12, 0, 18, 0, 1, 127, *([255] * 8)])
    assert sent_commands[3][6:-1] == bytes([40, 255, 255])
    assert sent_commands[4][6:-1] == bytes([12, 0, 18, 0, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255])


def test_connection_prelude_appends_ordered_schedule_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deferred command is the fourth write with an ID behind both RTC writes."""
    writes: list[bytes] = []
    delete_command = bytes.fromhex("a5011600011916001700017fffffffffffffffff00")
    device: ChihirosDevice
    monkeypatch.setattr(client_module, "SCHEDULE_DELETE_SETTLE_WAIT", 0)

    class FakeClient:
        async def write_gatt_char(self, _characteristic: object, command: bytes, _response: bool) -> None:
            writes.append(bytes(command))
            if len(writes) == 1:
                device._schedule_notification_event.set()  # noqa: SLF001

    async def run() -> None:
        nonlocal device
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device._write_char = object()  # type: ignore[assignment]
        device._connection_prelude_commands = [delete_command]

        await device._send_connection_prelude(FakeClient())  # type: ignore[arg-type]

        assert device._connection_prelude_commands_sent is True  # noqa: SLF001

    asyncio.run(run())

    assert [command[5] for command in writes] == [4, 9, 9, 25]
    assert [command[4] for command in writes] == sorted(command[4] for command in writes)
    assert writes[-1][3:5] != delete_command[3:5]
    assert writes[-1][-1] == calculate_checksum(writes[-1][:-1])
    assert writes[-1][5:-1] == delete_command[5:-1]


def test_schedule_delete_waits_for_auth_notification_before_rtc(monkeypatch: pytest.MonkeyPatch) -> None:
    """RTC and delete writes start only after the initial auth notification arrives."""
    writes: list[int] = []
    notification_released = False
    monkeypatch.setattr(client_module, "SCHEDULE_DELETE_SETTLE_WAIT", 0)

    class FakeClient:
        async def write_gatt_char(self, _characteristic: object, command: bytes, _response: bool) -> None:
            nonlocal notification_released
            writes.append(command[5])
            if len(writes) == 1:
                assert notification_released is False
                notification_released = True
                device._notification_handler(  # type: ignore[arg-type]
                    None,
                    bytearray([0x5B, 0x17, 0x08, 0x00, 0x01, 0xFE, 0x08, 0x00, 0x32]),
                )
            else:
                assert notification_released is True

    async def run() -> None:
        nonlocal device
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device._write_char = object()  # type: ignore[assignment]
        device._connection_prelude_commands = [bytes.fromhex("a5011600011916001700017fffffffffffffffff00")]

        await device._send_connection_prelude(FakeClient())  # type: ignore[arg-type]

    device: ChihirosDevice
    asyncio.run(run())

    assert writes == [4, 9, 9, 25]


def test_schedule_write_stops_when_auth_notification_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """RTC and schedule frames must not be sent without the app-observed notification."""
    writes: list[int] = []
    monkeypatch.setattr(client_module, "AUTH_NOTIFICATION_WAIT", 0)
    monkeypatch.setattr(client_module, "SCHEDULE_DELETE_SETTLE_WAIT", 0)

    class FakeClient:
        async def write_gatt_char(self, _characteristic: object, command: bytes, _response: bool) -> None:
            writes.append(command[5])

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device._write_char = object()  # type: ignore[assignment]
        device._connection_prelude_commands = [bytes.fromhex("a5011600011916001700017fffffffffffffffff00")]

        with pytest.raises(TimeoutError, match="No schedule snapshot notification received"):
            await device._send_connection_prelude(FakeClient())  # type: ignore[arg-type]

    asyncio.run(run())

    assert writes == [4]


def test_schedule_delete_waits_after_rtc_like_vendor_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app-observed settling delay occurs after both RTC writes and before delete."""
    events: list[str] = []
    device: ChihirosDevice

    async def capture_sleep(delay: float) -> None:
        events.append(f"sleep:{delay:.1f}")

    class FakeClient:
        async def write_gatt_char(self, _characteristic: object, command: bytes, _response: bool) -> None:
            events.append(f"write:{command[5]}")
            if command[5] == 4:
                device._schedule_notification_event.set()  # noqa: SLF001

    async def run() -> None:
        nonlocal device
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device._write_char = object()  # type: ignore[assignment]
        device._connection_prelude_commands = [bytes.fromhex("a5011600011916001700017fffffffffffffffff00")]
        monkeypatch.setattr(asyncio, "sleep", capture_sleep)

        await device._send_connection_prelude(FakeClient())  # type: ignore[arg-type]

    asyncio.run(run())

    assert events == ["write:4", "write:9", "write:9", "sleep:3.5", "write:25"]


def test_query_status_is_passive() -> None:
    """Status refresh does not open an active BLE transaction."""
    calls: list[str] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]

        async def ensure_connected() -> None:
            calls.append("connect")

        async def disconnect() -> None:
            calls.append("disconnect")

        device._ensure_connected = ensure_connected  # type: ignore[method-assign]
        device._execute_disconnect = disconnect  # type: ignore[method-assign]

        await device.query_status()

    asyncio.run(run())

    assert calls == []


def test_query_status_stays_passive_after_command_send() -> None:
    """A refresh immediately after a write must not open a second BLE transaction."""
    events: list[str] = []
    sleeps: list[float] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]

        async def ensure_connected() -> None:
            events.append("connect")

        async def send_locked(commands: list[bytes]) -> None:
            events.append(f"send:{len(commands)}")

        async def execute_disconnect() -> None:
            events.append("disconnect")

        async def capture_sleep(delay: float) -> None:
            sleeps.append(delay)

        device._ensure_connected = ensure_connected  # type: ignore[method-assign]
        device._send_command_locked = send_locked  # type: ignore[method-assign]
        device._execute_disconnect = execute_disconnect  # type: ignore[method-assign]
        original_sleep = asyncio.sleep
        asyncio.sleep = capture_sleep  # type: ignore[method-assign]

        try:
            await device._send_command([b"\x01"])  # noqa: SLF001
            await device.query_status()
        finally:
            asyncio.sleep = original_sleep  # type: ignore[method-assign]

    asyncio.run(run())

    assert events == ["connect", "send:1", "disconnect"]
    assert sleeps == [0.5]


def test_query_status_active_sends_base_auth_and_waits_for_notification() -> None:
    """Diagnostic runtime polling sends mode 4 with parameter 1."""
    sent: list[tuple[bytes, float]] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]

        async def send(command: bytes | bytearray, **kwargs: float) -> None:
            sent.append((bytes(command), float(kwargs["notification_wait"])))

        device._send_command = send  # type: ignore[method-assign]
        await device.query_status_active(notification_wait=4.0)

    asyncio.run(run())

    frame, wait = sent[0]
    assert frame[0:3] == bytes.fromhex("5a0106")
    assert frame[5:7] == bytes([4, 1])
    assert wait == 4.0


def test_set_fan_speed_requires_supported_model_and_sends_command() -> None:
    """Fan control is limited to fan-equipped models and sends mode 15."""
    sent: list[bytes] = []

    async def run() -> None:
        unsupported = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="does not support fan control"):
            await unsupported.set_fan_speed(50)

        vivid = ChihirosDevice(  # type: ignore[arg-type]
            FakeBLEDevice(),
            DeviceModel("WRGB VIVID III", ("DYVVD3",), WRGB_CHANNELS, has_fan=True),
        )

        async def capture(command: bytes | bytearray, _retry: int) -> None:
            sent.append(bytes(command))

        vivid._send_command = capture  # type: ignore[method-assign]
        await vivid.set_fan_speed(53)

    asyncio.run(run())

    assert sent[0][5:-1] == bytes([15, 53])


def test_send_command_disconnects_after_command_batch() -> None:
    """Command batches do not keep the BLE connection alive."""
    events: list[str] = []
    sleeps: list[float] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]

        async def ensure_connected() -> None:
            events.append("connect")

        async def send_locked(commands: list[bytes]) -> None:
            events.append(f"send:{len(commands)}")

        async def execute_disconnect() -> None:
            events.append("disconnect")

        async def capture_sleep(delay: float) -> None:
            sleeps.append(delay)

        device._ensure_connected = ensure_connected  # type: ignore[method-assign]
        device._send_command_locked = send_locked  # type: ignore[method-assign]
        device._execute_disconnect = execute_disconnect  # type: ignore[method-assign]
        original_sleep = asyncio.sleep
        asyncio.sleep = capture_sleep  # type: ignore[method-assign]

        try:
            await device._send_command([b"\x01", b"\x02"])  # noqa: SLF001
        finally:
            asyncio.sleep = original_sleep  # type: ignore[method-assign]

    asyncio.run(run())

    assert events == ["connect", "send:2", "disconnect"]
    assert sleeps == [0.5]


def test_remote_disconnect_callback_is_diagnostic_only(caplog: pytest.LogCaptureFixture) -> None:
    """A device-first disconnect does not create a Home Assistant warning."""
    caplog.set_level(logging.DEBUG)

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        device._disconnected(None)  # type: ignore[arg-type]  # noqa: SLF001

    asyncio.run(run())

    assert "Device unexpectedly disconnected" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_remote_disconnect_callback_discards_stale_client() -> None:
    """A device-first disconnect forces the next operation to establish a fresh connection."""

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        client = object()
        device._client = client  # type: ignore[assignment]  # noqa: SLF001
        device._read_char = object()  # type: ignore[assignment]  # noqa: SLF001
        device._write_char = object()  # type: ignore[assignment]  # noqa: SLF001

        device._disconnected(client)  # type: ignore[arg-type]  # noqa: SLF001

        assert device._client is None  # noqa: SLF001
        assert device._read_char is None  # noqa: SLF001
        assert device._write_char is None  # noqa: SLF001

    asyncio.run(run())


def test_notification_handler_stores_and_publishes_runtime_notification() -> None:
    """Parsed runtime notifications are stored and sent to subscribers."""
    received: list[RuntimeNotification] = []
    frame = bytearray.fromhex("5b170a00010a01ffffffffff13888c")

    async def run() -> ChihirosDevice:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        device.add_notification_callback(received.append)
        device._notification_handler(None, frame)  # type: ignore[arg-type]
        return device

    device = asyncio.run(run())
    assert device.last_runtime_notification == RuntimeNotification(
        firmware_version=23,
        runtime_minutes=5000,
        raw=bytes(frame),
    )
    assert received == [device.last_runtime_notification]


def test_notification_handler_stores_and_publishes_fan_status() -> None:
    """Parsed fan notifications are stored and sent to subscribers."""
    received: list[FanStatusNotification] = []
    frame = bytearray.fromhex("5b 1b 10 00 01 0b 02 58 19 00 01 00 00 00 00 00 48 22")

    async def run() -> ChihirosDevice:
        device = ChihirosDevice(  # type: ignore[arg-type]
            FakeBLEDevice(),
            DeviceModel("WRGB VIVID III", ("DYVVD3",), WRGB_CHANNELS, has_fan=True),
        )
        device.add_notification_callback(received.append)
        device._notification_handler(None, frame)  # type: ignore[arg-type]
        return device

    device = asyncio.run(run())

    assert device.last_fan_status_notification == FanStatusNotification(27, 600, 25, bytes(frame))
    assert received == [device.last_fan_status_notification]


def test_notification_handler_stores_and_publishes_schedule_snapshot() -> None:
    """Parsed schedule notifications are stored and sent to subscribers."""
    received: list[ScheduleSnapshotNotification] = []

    async def run() -> ChihirosDevice:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test", (), WHITE_CHANNELS))  # type: ignore[arg-type]
        device.add_notification_callback(received.append)
        device._notification_handler(
            None,  # type: ignore[arg-type]
            bytearray([0x5B, 0x17, 0x08, 0x00, 0x01, 0xFE, 0x08, 0x00, 0x32]),
        )
        return device

    device = asyncio.run(run())
    assert isinstance(device.last_schedule_snapshot_notification, ScheduleSnapshotNotification)
    assert received == [device.last_schedule_snapshot_notification]


def test_render_protocol_debug_decodes_schedule_snapshot_as_curve_points() -> None:
    """Schedule snapshot RX debug output uses time/level curve points."""
    frame = bytes.fromhex(
        "5B15300001FE060F060D320000000000000000000000060F06110000110141153B41160000090000090105103B0500000000"
    )

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device.raw_notifications.append(frame)
        return device.render_raw_notifications()

    output = asyncio.run(run())

    assert "Bedeutung        : Zeitplan-Snapshot Kurvenpunkte=7, Zeitplaene=2" in output
    assert "Details          : Zeitplan 1: 17:00-22:00 Level=65%" in output
    assert "Details          : Zeitplan 2: 09:00-17:00 Level=5%" in output
    assert "Details          : Punkt 2: 17:01 Level=65%" in output
    assert "red=0%" not in output


def test_render_protocol_debug_closes_trailing_schedule_at_existing_boundary() -> None:
    """A truncated second schedule uses the first schedule's matching start boundary."""
    frame = bytes.fromhex(
        "5B15300001FE030F0609000000000000000000000000030F06110000110141153B41160000090000090105103B0500000000"
    )

    schedules = ChihirosDevice._describe_schedule_curve_snapshot(frame)

    assert "Zeitplan-Snapshot Kurvenpunkte=7, Zeitplaene=2" in schedules
    assert "Zeitplan 1: 17:00-22:00 Level=65% Ramp=1 min" in schedules
    assert "Zeitplan 2: 09:00-17:00 Level=5% Ramp=1 min" in schedules


def test_render_protocol_debug_ignores_incomplete_active_schedule_point() -> None:
    """A standalone active point without an end marker is not a schedule."""
    frame = bytes(
        [
            0x5B,
            0x15,
            0x30,
            0x00,
            0x01,
            0xFE,
            6,
            16,
            15,
            13,
            50,
            *([0] * 11),
            6,
            16,
            15,
            17,
            0,
            0,
            17,
            1,
            65,
            21,
            59,
            65,
            22,
            0,
            0,
            9,
            0,
            0,
            9,
            1,
            5,
            16,
            59,
            5,
            22,
            30,
            98,
            0,
        ]
    )

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device.raw_notifications.append(frame)
        return device.render_raw_notifications()

    output = asyncio.run(run())

    assert "Bedeutung        : Zeitplan-Snapshot Kurvenpunkte=8, Zeitplaene=2" in output
    assert "Details          : Zeitplan 3:" not in output


def test_render_protocol_debug_preserves_active_schedule_minutes() -> None:
    """An active point followed by a zero point keeps its exact start and end minutes."""
    parameters = [
        7,
        5,
        29,
        1,
        56,
        5,
        27,
        0,
        0,
        1,
        57,
        2,
        9,
        4,
        7,
        0,
        7,
        5,
        29,
        17,
        0,
        0,
        17,
        1,
        65,
        21,
        59,
        65,
        22,
        0,
        0,
        9,
        0,
        5,
        22,
        15,
        100,
        23,
        15,
        0,
        0,
        0,
        0,
    ]
    frame = bytes([0x5B, 0x15, 0x30, 0x00, 0x01, 0xFE, *parameters, 0x00])

    async def run() -> str:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]
        device.raw_notifications.append(frame)
        return device.render_raw_notifications()

    output = asyncio.run(run())

    assert "Bedeutung        : Zeitplan-Snapshot Kurvenpunkte=7, Zeitplaene=3" in output
    assert "Details          : Zeitplan 3: 22:15-23:15 Level=100%" in output


def test_render_protocol_debug_reuses_adjacent_schedule_boundary() -> None:
    """A shared zero point is both the previous end and next ramp start."""
    points = [(9, 0, 0), (9, 1, 5), (16, 59, 5), (17, 0, 0), (17, 1, 65), (21, 59, 65), (22, 0, 0)]

    ranges = ChihirosDevice._schedule_curve_ranges(points)

    assert ranges == [(9, 0, 17, 0, 5, 1), (17, 0, 22, 0, 65, 1)]


def test_render_protocol_debug_decodes_thirty_minute_schedule_ramp() -> None:
    """A zero point followed by the target level encodes the ramp start and duration."""
    points = [
        (9, 0, 0),
        (9, 1, 5),
        (16, 59, 5),
        (17, 0, 0),
        (17, 30, 65),
        (21, 30, 65),
        (22, 0, 0),
    ]

    ranges = ChihirosDevice._schedule_curve_ranges(points)

    assert ranges == [(9, 0, 17, 0, 5, 1), (17, 0, 22, 0, 65, 30)]


def test_render_protocol_debug_decodes_zero_level_schedule_snapshot() -> None:
    """A schedule with only 0% points is still a valid stored schedule."""
    points = [(22, 0, 0), (22, 1, 0), (23, 58, 0), (23, 59, 0)]

    ranges = ChihirosDevice._schedule_curve_ranges(points)

    assert ranges == [(22, 0, 23, 59, 0, 1)]


def test_render_protocol_debug_sorts_auto_mode_schedule_snapshot_points() -> None:
    """Auto-mode snapshots may report the 0% tail before earlier active schedules."""
    points = [
        (22, 0, 0),
        (22, 1, 0),
        (23, 58, 0),
        (23, 59, 0),
        (9, 0, 0),
        (9, 1, 5),
        (16, 59, 5),
        (17, 0, 0),
        (17, 1, 65),
        (21, 59, 65),
    ]

    ranges = ChihirosDevice._schedule_curve_ranges(points)

    assert sorted(ranges) == [
        (9, 0, 17, 0, 5, 1),
        (17, 0, 22, 0, 65, 1),
        (22, 0, 23, 59, 0, 1),
    ]


def test_set_brightness_sends_all_true_wrgb_channels() -> None:
    """Brightness commands can set red, green, blue, and white in one call."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.set_brightness((10, 20, 30, 40))

    asyncio.run(run())

    assert [command[6:8] for command in sent_commands] == [
        bytes([11, 255]),
        bytes([0, 10]),
        bytes([1, 20]),
        bytes([2, 30]),
        bytes([3, 40]),
    ]
    assert [command[5] for command in sent_commands] == [5, 7, 7, 7, 7]


def test_set_brightness_accepts_channel_mapping() -> None:
    """Brightness commands can target a named channel."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.set_brightness({"white": 40})

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5, 7]
    assert sent_commands[0][6:9] == bytes([11, 255, 255])
    assert sent_commands[1][6:8] == bytes([3, 40])


def test_turn_off_uses_standard_prelude_and_model_channels() -> None:
    """Turning a light off uses the standard prelude and all model channels."""
    sent_commands: list[bytes] = []
    send_options: dict[str, object] = {}

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test RGB", (), RGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs: object,
        ) -> None:
            del retry
            send_options.update(kwargs)
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.turn_off()

    asyncio.run(run())

    assert send_options == {}
    assert [command[5] for command in sent_commands] == [5, 7, 7, 7]
    assert [command[6:-1] for command in sent_commands[1:]] == [bytes([0, 0]), bytes([1, 0]), bytes([2, 0])]


def test_add_setting_sends_four_channel_brightness() -> None:
    """True WRGB auto schedules encode red, green, blue, and white levels."""
    sent_commands: list[bytes] = []
    send_options: dict[str, object] = {}

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry
            send_options.update(kwargs)
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.add_setting(
            sunrise=datetime(2026, 6, 14, 8, 0),
            sunset=datetime(2026, 6, 14, 18, 30),
            max_brightness=(10, 20, 30, 40),
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25]
    assert sent_commands[0][6:-1] == bytes([8, 0, 18, 30, 1, 127, 10, 20, 30, 40, 255, 255, 255, 255])
    assert send_options == {"immediate_after_prelude": True}


def test_add_setting_uses_white_channel_for_true_wrgb_models() -> None:
    """Single-channel auto schedules target the white slot on true WRGB models."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.add_setting(
            sunrise=datetime(2026, 6, 14, 8, 0),
            sunset=datetime(2026, 6, 14, 18, 30),
            max_brightness=40,
        )

    asyncio.run(run())

    assert sent_commands[0][6:-1] == bytes([8, 0, 18, 30, 1, 127, 255, 255, 255, 40, 255, 255, 255, 255])


def test_add_setting_uses_first_channel_when_model_has_no_white_channel() -> None:
    """Single-channel auto schedules keep targeting the first channel on RGB-only models."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test RGB", (), RGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]

        await device.add_setting(
            sunrise=datetime(2026, 6, 14, 8, 0),
            sunset=datetime(2026, 6, 14, 18, 30),
            max_brightness=40,
        )

    asyncio.run(run())

    assert sent_commands[0][6:-1] == bytes([8, 0, 18, 30, 1, 127, 40, 255, 255, 255, 255, 255, 255, 255])


def test_add_setting_skips_auto_mode_even_when_legacy_flag_is_enabled() -> None:
    """Schedule writes never implicitly send mode 5 [18, 255]."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.add_setting(
            sunrise=datetime(2026, 6, 14, 9, 0),
            sunset=datetime(2026, 6, 14, 17, 0),
            max_brightness=(5, 5, 5, 5),
            ramp_up_in_minutes=1,
            enable_auto_mode=True,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25]
    assert sent_commands[0][6:-1] == bytes([9, 0, 17, 0, 1, 127, 5, 5, 5, 5, 255, 255, 255, 255])


def test_dyu1000_add_setting_prepares_existing_row_like_app() -> None:
    """DYU1000 second add clears the target row twice before sending the active row."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.add_setting(
            sunrise=datetime(2026, 7, 1, 18, 0),
            sunset=datetime(2026, 7, 1, 22, 0),
            max_brightness=(100, 100, 100, 100),
            ramp_up_in_minutes=1,
            weekdays=[WeekdaySelect.tuesday, WeekdaySelect.thursday, WeekdaySelect.saturday],
            prepare_existing_setting=True,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 25, 25]
    assert sent_commands[0][6:-1] == bytes([18, 0, 22, 0, 1, 42, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([18, 0, 22, 0, 1, 42, *([255] * 8)])
    assert sent_commands[2][6:-1] == bytes([18, 0, 22, 0, 1, 42, 100, 100, 100, 100, 255, 255, 255, 255])


def test_replace_setting_does_not_enable_auto_mode() -> None:
    """Editing deletes and rewrites the row without implicitly enabling auto mode."""
    sent_commands: list[bytes] = []
    send_options: dict[str, object] = {}

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry
            send_options.update(kwargs)
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.replace_setting(
            previous_sunrise=datetime(2026, 6, 14, 9, 0),
            previous_sunset=datetime(2026, 6, 14, 17, 0),
            sunrise=datetime(2026, 6, 14, 9, 0),
            sunset=datetime(2026, 6, 14, 17, 0),
            max_brightness=(10, 5, 5, 5),
            previous_ramp_up_in_minutes=1,
            ramp_up_in_minutes=1,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 25]
    assert sent_commands[0][6:-1] == bytes([9, 0, 17, 0, 1, 127, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([9, 0, 17, 0, 1, 127, 10, 5, 5, 5, 255, 255, 255, 255])
    assert send_options == {"immediate_after_prelude": True}


def test_dyu1000_replace_setting_matches_app_edit_sequence() -> None:
    """DYU1000 active edit sends only the replacement row after the connection prelude."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.replace_setting(
            previous_sunrise=datetime(2026, 7, 1, 12, 0),
            previous_sunset=datetime(2026, 7, 1, 18, 0),
            sunrise=datetime(2026, 7, 1, 12, 0),
            sunset=datetime(2026, 7, 1, 18, 0),
            max_brightness=(100, 100, 100, 100),
            previous_ramp_up_in_minutes=1,
            ramp_up_in_minutes=1,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25]
    assert sent_commands[0][6:-1] == bytes([12, 0, 18, 0, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255])


def test_dyu1000_replace_second_setting_prepares_existing_row_like_app() -> None:
    """DYU1000 second edit clears the previous row twice before sending the replacement row."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray, retry: int | None = None, **kwargs: object
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.replace_setting(
            previous_sunrise=datetime(2026, 7, 1, 18, 0),
            previous_sunset=datetime(2026, 7, 1, 22, 0),
            sunrise=datetime(2026, 7, 1, 18, 0),
            sunset=datetime(2026, 7, 1, 22, 0),
            max_brightness=(100, 100, 100, 100),
            previous_ramp_up_in_minutes=1,
            ramp_up_in_minutes=1,
            previous_weekdays=[WeekdaySelect.tuesday, WeekdaySelect.thursday, WeekdaySelect.saturday],
            weekdays=[WeekdaySelect.wednesday, WeekdaySelect.sunday],
            prepare_existing_setting=True,
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [25, 25, 25]
    assert sent_commands[0][6:-1] == bytes([18, 0, 22, 0, 1, 42, *([255] * 8)])
    assert sent_commands[1][6:-1] == bytes([18, 0, 22, 0, 1, 42, *([255] * 8)])
    assert sent_commands[2][6:-1] == bytes([18, 0, 22, 0, 1, 17, 100, 100, 100, 100, 255, 255, 255, 255])


def test_replace_settings_resets_existing_rows_without_switching_automatic_tab() -> None:
    """Full schedule writes clear old rows before sending only the requested mode 25 rows."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.replace_settings(
            [
                (datetime(2026, 6, 14, 17, 0), datetime(2026, 6, 14, 22, 0), (65, 40, 65, 55), 1, None),
                (datetime(2026, 6, 14, 9, 0), datetime(2026, 6, 14, 17, 0), (10, 5, 5, 5), 1, None),
            ]
        )

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5, 25, 25]
    assert sent_commands[0][6:-1] == bytes([5, 255, 255])
    assert sent_commands[1][6:-1] == bytes([17, 0, 22, 0, 1, 127, 65, 40, 65, 55, 255, 255, 255, 255])
    assert sent_commands[2][6:-1] == bytes([9, 0, 17, 0, 1, 127, 10, 5, 5, 5, 255, 255, 255, 255])


def test_dyu1000_replace_settings_empty_does_not_send_finalize_parameter() -> None:
    """An empty schedule write must not misuse the DYU1000 delete finalizer."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.replace_settings([])

    asyncio.run(run())

    assert sent_commands == []


def test_dyu1000_reset_settings_uses_original_single_reset_command() -> None:
    """The standard reset keeps the original single parameter-5 command."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
            schedule_reset_from_snapshot=True,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]
        populated_snapshot = ScheduleSnapshotNotification(
            21,
            (
                SchedulePoint(17, 0, {"red": 0}),
                SchedulePoint(19, 0, {"red": 65}),
                SchedulePoint(20, 0, {"red": 65}),
                SchedulePoint(22, 0, {"red": 0}),
                SchedulePoint(22, 15, {"red": 100}),
                SchedulePoint(23, 15, {"red": 0}),
            ),
        )
        isolated_zero_ramp_snapshot = ScheduleSnapshotNotification(
            21,
            (SchedulePoint(22, 15, {"red": 100}), SchedulePoint(23, 15, {"red": 0})),
        )
        empty_snapshot = ScheduleSnapshotNotification(21, ())
        snapshots = iter((populated_snapshot, isolated_zero_ramp_snapshot, empty_snapshot))

        async def keep_snapshot(notification_wait: float = 3.0) -> None:
            del notification_wait
            device.last_schedule_snapshot_notification = next(snapshots)

        device.query_status_active = keep_snapshot  # type: ignore[method-assign]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.reset_settings()

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5]
    assert sent_commands[0][6:9] == bytes([5, 255, 255])


def test_dyu1000_reset_settings_does_not_query_snapshot() -> None:
    """The original reset command does not inspect or delete snapshot ranges first."""
    sent_commands: list[bytes] = []
    send_options: list[dict[str, object]] = []
    query_count = 0

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
            schedule_reset_from_snapshot=True,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]
        populated_snapshot = ScheduleSnapshotNotification(
            21,
            (SchedulePoint(22, 15, {"red": 100}), SchedulePoint(23, 15, {"red": 0})),
        )
        empty_snapshot = ScheduleSnapshotNotification(21, ())

        async def keep_snapshot(notification_wait: float = 3.0) -> None:
            nonlocal query_count
            del notification_wait
            query_count += 1
            device.last_schedule_snapshot_notification = populated_snapshot if query_count == 1 else empty_snapshot

        device.query_status_active = keep_snapshot  # type: ignore[method-assign]

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs,
        ) -> None:
            del retry
            send_options.append(kwargs)
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.reset_settings()

    asyncio.run(run())

    assert query_count == 0
    assert [command[5] for command in sent_commands] == [5]
    assert sent_commands[0][6:9] == bytes([5, 255, 255])
    assert send_options == [{}]


def test_dyu1000_reset_settings_ignores_existing_snapshot_points() -> None:
    """The original reset sends parameter 5 without interpreting existing points."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        model = DeviceModel(
            "Universal WRGB",
            ("DYU1000",),
            WRGB_CHANNELS,
            max_brightness=100,
            schedule_reset_parameter=40,
            schedule_reset_from_snapshot=True,
        )
        device = ChihirosDevice(FakeBLEDevice(), model)  # type: ignore[arg-type]
        snapshot = ScheduleSnapshotNotification(
            21,
            (SchedulePoint(9, 0, {"red": 5}), SchedulePoint(17, 0, {"red": 0})),
        )

        async def keep_schedule(notification_wait: float = 3.0) -> None:
            del notification_wait
            device.last_schedule_snapshot_notification = snapshot

        async def capture_command(
            command: list[bytes] | bytes | bytearray,
            retry: int | None = None,
            **kwargs,
        ) -> None:
            del retry, kwargs
            if isinstance(command, list):
                sent_commands.extend(bytes(item) for item in command)
            else:
                sent_commands.append(bytes(command))

        device.query_status_active = keep_schedule  # type: ignore[method-assign]
        device._send_command = capture_command  # type: ignore[method-assign]
        await device.reset_settings()

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5]
    assert sent_commands[0][6:9] == bytes([5, 255, 255])


def test_send_auto_parameter_encodes_selected_value() -> None:
    """The diagnostic helper keeps the trailing auto parameters at 255."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            assert not isinstance(command, list)
            sent_commands.append(bytes(command))

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.send_auto_parameter(1)

    asyncio.run(run())

    assert sent_commands[0][5] == 5
    assert sent_commands[0][6:9] == bytes([1, 255, 255])


def test_hard_reset_sends_all_four_mode_5_stages_in_order() -> None:
    """Hard reset sends stages 5, 6, 7 and finishes with stop/exit stage 4."""
    sent_commands: list[bytes] = []

    async def run() -> None:
        device = ChihirosDevice(FakeBLEDevice(), DeviceModel("Test WRGB", (), WRGB_CHANNELS))  # type: ignore[arg-type]

        async def capture_command(command: list[bytes] | bytes | bytearray, retry: int | None = None) -> None:
            del retry
            assert isinstance(command, list)
            sent_commands.extend(bytes(item) for item in command)

        device._send_command = capture_command  # type: ignore[method-assign]
        await device.hard_reset()

    asyncio.run(run())

    assert [command[5] for command in sent_commands] == [5, 5, 5, 5]
    assert [command[6:9] for command in sent_commands] == [
        bytes([5, 255, 255]),
        bytes([6, 255, 255]),
        bytes([7, 255, 255]),
        bytes([4, 255, 255]),
    ]
