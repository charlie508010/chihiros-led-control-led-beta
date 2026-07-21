"""Runtime BLE client for Chihiros LED devices."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.service import (
    BleakGATTCharacteristic,  # type: ignore
    BleakGATTServiceCollection,
)
from bleak.exc import BleakDBusError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakError,  # type: ignore
    BleakNotFoundError,
    establish_connection,
    retry_bluetooth_connection_error,
)
from rich import print as rich_print

from . import commands
from .const import LEGACY_UART_CHAR_UUID, UART_RX_CHAR_UUID, UART_TX_CHAR_UUID
from .debug_output import (
    compact_frame_info,
    debug_frame_rows,
    frame_params,
    render_compare_log,
    render_protocol_debug,
    render_raw_notifications,
    render_tx_protocol_debug,
)
from .exceptions import CharacteristicMissingError
from .models import FALLBACK, DeviceModel
from .protocol import (
    FanStatusNotification,
    ParsedNotification,
    RuntimeNotification,
    ScheduleSnapshotNotification,
    calculate_checksum,
    next_message_id,
    parse_notification,
)
from .weekday_encoding import WeekdaySelect, encode_selected_weekdays

DEFAULT_ATTEMPTS = 3
BLEAK_BACKOFF_TIME = 0.25
COMMAND_NOTIFICATION_WAIT = 0.5
AUTH_NOTIFICATION_WAIT = 3.0
SCHEDULE_DELETE_SETTLE_WAIT = 3.5
NotificationCallback = Callable[[ParsedNotification], None]


class ChihirosDevice:
    """Concrete BLE client for a Chihiros LED device."""

    _logger: logging.Logger

    def __init__(
        self,
        ble_device: BLEDevice,
        model: DeviceModel = FALLBACK,
        advertisement_data: AdvertisementData | None = None,
    ) -> None:
        """Create a device client."""
        self._ble_device = ble_device
        self.model = model
        self._logger = logging.getLogger(ble_device.address.replace(":", "-"))
        self._advertisement_data = advertisement_data
        self._client: BleakClientWithServiceCache | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._operation_lock: asyncio.Lock = asyncio.Lock()
        self._read_char: BleakGATTCharacteristic | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._expected_disconnect = False
        self._msg_id = next_message_id()
        self._notification_callbacks: set[NotificationCallback] = set()
        self.last_runtime_notification: RuntimeNotification | None = None
        self.last_fan_status_notification: FanStatusNotification | None = None
        self.last_schedule_snapshot_notification: ScheduleSnapshotNotification | None = None
        self.raw_notifications: list[bytes] = []
        self.tx_debug_frames: list[bytes] = []
        self.debug_frames: list[dict[str, object]] = []
        self._last_operation_debug_range: tuple[int, int, int, int, int, int] | None = None
        self._last_characteristic_summary = ""
        self._tx_debug_counter = 0
        self._connection_prelude_mode = "standard"
        self._connection_prelude_commands: list[bytes] = []
        self._connection_prelude_commands_sent = False
        self._schedule_notification_event = asyncio.Event()
        self.loop = asyncio.get_running_loop()

    def set_log_level(self, level: int | str) -> None:
        """Set log level."""
        if isinstance(level, str):
            level = logging._nameToLevel.get(level, logging.INFO)
        self._logger.setLevel(level)

    def clear_debug_buffers(self) -> None:
        """Reset collected TX/RX debug frames."""
        self.raw_notifications.clear()
        self.tx_debug_frames.clear()
        self.debug_frames.clear()
        self._last_operation_debug_range = None

    @staticmethod
    def _frame_params(payload: bytes | bytearray) -> list[int]:
        """Return payload parameters without checksum."""
        return frame_params(payload)

    def _compact_frame_info(self, payload: bytes | bytearray, direction: str, timestamp: str = "") -> dict[str, object]:
        """Build compact frame data for shared debug output."""
        return compact_frame_info(payload, direction, timestamp)

    def debug_frame_rows(
        self,
        *,
        directions: set[str] | None = None,
        tx_commands: set[int] | None = None,
        rx_modes: set[int] | None = None,
    ) -> list[dict[str, object]]:
        """Return compact chronological debug rows."""
        return debug_frame_rows(
            debug_frames=self.debug_frames,
            tx_debug_frames=self.tx_debug_frames,
            raw_notifications=self.raw_notifications,
            directions=directions,
            tx_commands=tx_commands,
            rx_modes=rx_modes,
        )

    def render_compare_log(
        self,
        *,
        tx_commands: set[int] | None = None,
        rx_modes: set[int] | None = None,
    ) -> str:
        """Render compact app-log style rows for sent commands only."""
        del rx_modes
        return render_compare_log(
            debug_frames=self.debug_frames,
            tx_debug_frames=self.tx_debug_frames,
            raw_notifications=self.raw_notifications,
            tx_commands=tx_commands,
        )

    def render_raw_notifications(self, *, dedupe: bool = False, title: str = "GERÄTEANTWORT") -> str:
        """Render RX notifications in raw hex format."""
        return render_raw_notifications(
            self.raw_notifications,
            dedupe=dedupe,
            title=title,
            describe_rx_frame=self._describe_rx_frame,
        )

    def _render_tx_encode_block(self, payload: bytes | bytearray, index: int) -> str:
        """Render one TX block without terminal color codes."""
        return render_tx_protocol_debug(
            [payload],
            address=self.address,
            describe_tx_frame=self._describe_tx_frame,
            start_index=index,
        )

    def render_tx_protocol_debug(self) -> str:
        """Render all TX frames in detailed CLI/dashboard format."""
        return render_tx_protocol_debug(
            self.tx_debug_frames,
            address=self.address,
            describe_tx_frame=self._describe_tx_frame,
        )

    def render_protocol_debug(
        self,
        *,
        tx_commands: set[int] | None = None,
        rx_modes: set[int] | None = None,
        dedupe_rx: bool = False,
        last_operation: bool = False,
        include_missing_tx_frames: bool = False,
    ) -> str:
        """Render shared protocol debug text used by CLI and dashboard."""
        del rx_modes
        debug_frames = self.debug_frames
        tx_debug_frames = self.tx_debug_frames
        raw_notifications = self.raw_notifications
        if last_operation and self._last_operation_debug_range is not None:
            debug_start, debug_end, tx_start, tx_end, raw_start, raw_end = self._last_operation_debug_range
            debug_frames = self.debug_frames[debug_start:debug_end]
            tx_debug_frames = self.tx_debug_frames[tx_start:tx_end]
            raw_notifications = self.raw_notifications[raw_start:raw_end]
        return render_protocol_debug(
            debug_frames=debug_frames,
            tx_debug_frames=tx_debug_frames,
            raw_notifications=raw_notifications,
            address=self.address,
            describe_tx_frame=self._describe_tx_frame,
            describe_rx_frame=self._describe_rx_frame,
            tx_commands=tx_commands,
            dedupe_rx=dedupe_rx,
            include_missing_tx_frames=include_missing_tx_frames,
        )

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Update the BLE device and advertisement data."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data

    @property
    def current_msg_id(self) -> tuple[int, int]:
        """Get the current message id."""
        return self._msg_id

    def get_next_msg_id(self) -> tuple[int, int]:
        """Get the next message id."""
        self._msg_id = next_message_id(self._msg_id)
        return self._msg_id

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self.model.name

    @property
    def model_codes(self) -> tuple[str, ...]:
        """Return the model codes."""
        return self.model.advertised_codes

    @property
    def colors(self) -> dict[str, int]:
        """Return supported color channels."""
        return dict(self.model.color_channels)

    @property
    def address(self) -> str:
        """Return the BLE address."""
        return self._ble_device.address

    @property
    def name(self) -> str:
        """Get the device name."""
        if hasattr(self._ble_device, "name"):
            return self._ble_device.name or self._ble_device.address
        return self._ble_device.address

    @property
    def rssi(self) -> int | None:
        """Get the RSSI from the latest advertisement data."""
        if self._advertisement_data:
            return self._advertisement_data.rssi
        return None

    def _color_id(self, color: str | int) -> int | None:
        """Return protocol channel id for a color name or id."""
        color_id: int | None = None
        colors = self.model.color_channels
        if isinstance(color, int) and color in colors.values():
            color_id = color
        elif isinstance(color, str) and color in colors:
            color_id = colors[color]
        return color_id

    async def _set_channel_brightness(
        self,
        brightness: int,
        color: str | int,
    ) -> None:
        """Set brightness of one color channel."""
        color_id = self._color_id(color)
        if color_id is None:
            self._logger.warning("Color not supported: `%s`", color)
            return
        cmd = commands.create_set_brightness_command(self.get_next_msg_id(), color_id, brightness)
        await self._send_command(cmd, 3)

    def _validate_brightness_levels(self, brightness: Sequence[int]) -> None:
        """Validate brightness levels."""
        if not brightness:
            raise ValueError("At least one brightness level is required")
        max_brightness = self.model.max_brightness
        if any(level < 0 or level > max_brightness for level in brightness):
            raise ValueError(f"Brightness levels must be between 0 and {max_brightness}")

    def _normalize_brightness(self, brightness: int | Sequence[int] | Mapping[str | int, int]) -> dict[int, int]:
        """Normalize supported brightness inputs to protocol channel ids."""
        if isinstance(brightness, int):
            color_id = self._color_id(self._primary_schedule_color())
            assert color_id is not None  # nosec
            self._validate_brightness_levels((brightness,))
            return {color_id: brightness}

        if isinstance(brightness, Mapping):
            self._validate_brightness_levels(tuple(brightness.values()))
            result: dict[int, int] = {}
            for color, level in brightness.items():
                color_id = self._color_id(color)
                if color_id is None:
                    raise ValueError(f"Color not supported: {color}")
                result[color_id] = level
            return result

        brightness_values = list(brightness)
        self._validate_brightness_levels(brightness_values)
        channel_count = self._channel_count()
        if len(brightness_values) == 1:
            color_id = self._color_id(self._primary_schedule_color())
            assert color_id is not None  # nosec
            return {color_id: brightness_values[0]}
        if len(brightness_values) != channel_count:
            raise ValueError(f"Expected 1 or {channel_count} brightness levels")
        return dict(enumerate(brightness_values))

    def _channel_count(self) -> int:
        """Return number of protocol channel slots for this model."""
        return max(self.model.color_channels.values()) + 1

    def _brightness_parameter_values(self, brightness: int | Sequence[int] | Mapping[str | int, int]) -> list[int]:
        """Return auto schedule brightness parameters ordered by channel id."""
        brightness_by_channel = self._normalize_brightness(brightness)
        return [brightness_by_channel.get(channel_id, 255) for channel_id in range(self._channel_count())]

    async def set_brightness(self, brightness: int | Sequence[int] | Mapping[str | int, int]) -> None:
        """Set light brightness."""
        brightness_commands = [
            commands.create_set_brightness_command(self.get_next_msg_id(), color_id, brightness_level)
            for color_id, brightness_level in self._normalize_brightness(brightness).items()
        ]
        apply_command = commands.create_apply_manual_color_command(self.get_next_msg_id())
        await self._send_command([apply_command, *brightness_commands], 3)

    def _primary_schedule_color(self) -> str:
        """Return the single channel used by plain auto schedules."""
        if "white" in self.model.color_channels:
            return "white"
        return min(self.model.color_channels, key=self.model.color_channels.__getitem__)

    async def turn_on(self) -> None:
        """Turn on the light."""
        await self.set_brightness({color_name: self.model.max_brightness for color_name in self.model.color_channels})

    async def turn_off(self) -> None:
        """Turn off the light."""
        await self.set_brightness({color_name: 0 for color_name in self.model.color_channels})

    def add_notification_callback(self, callback: NotificationCallback) -> Callable[[], None]:
        """Register a callback for parsed device notifications."""
        self._notification_callbacks.add(callback)

        def remove_callback() -> None:
            self._notification_callbacks.discard(callback)

        return remove_callback

    async def query_status(self) -> None:
        """Ask the device to send its runtime/status notification snapshot."""
        self._logger.debug("%s: Skipping active status query; using passive notifications only", self.name)

    async def query_status_active(self, notification_wait: float = 3.0) -> None:
        """Actively request one runtime/status notification for diagnostics."""
        command = commands.create_base_auth_command(self.get_next_msg_id())
        await self._send_command(command, notification_wait=max(0.0, float(notification_wait)))

    async def set_fan_speed(self, speed_percent: int) -> None:
        """Set the fan speed percentage on fan-equipped models."""
        if not self.model.has_fan:
            raise ValueError(f"Model does not support fan control: {self.model.name}")
        command = commands.create_set_fan_speed_command(self.get_next_msg_id(), speed_percent)
        await self._send_command(command, 3)

    async def add_setting(
        self,
        sunrise: datetime,
        sunset: datetime,
        max_brightness: int | Sequence[int] | Mapping[str | int, int] | None = None,
        ramp_up_in_minutes: int = 1,
        weekdays: list[WeekdaySelect] | None = None,
        enable_auto_mode: bool = True,
        prepare_existing_setting: bool = False,
    ) -> None:
        """Add an automation setting without changing the device mode."""
        del enable_auto_mode  # Kept for API compatibility; mode changes are explicit operations.
        if weekdays is None:
            weekdays = [WeekdaySelect.everyday]
        if max_brightness is None:
            max_brightness = self.model.max_brightness
        brightness = self._brightness_parameter_values(max_brightness)
        schedule_cmd = commands.create_add_auto_setting_command(
            self.get_next_msg_id(),
            sunrise.time(),
            sunset.time(),
            brightness,
            ramp_up_in_minutes,
            encode_selected_weekdays(weekdays),
        )
        commands_to_send = [schedule_cmd]
        if prepare_existing_setting and self.model.schedule_reset_parameter != 5:
            clear_command = commands.create_delete_auto_setting_command(
                self.get_next_msg_id(),
                sunrise.time(),
                sunset.time(),
                ramp_up_in_minutes,
                encode_selected_weekdays(weekdays),
                brightness_channels=self._channel_count(),
            )
            second_clear_command = commands.create_delete_auto_setting_command(
                self.get_next_msg_id(),
                sunrise.time(),
                sunset.time(),
                ramp_up_in_minutes,
                encode_selected_weekdays(weekdays),
                brightness_channels=self._channel_count(),
            )
            commands_to_send = [clear_command, second_clear_command, schedule_cmd]
        await self._send_command(commands_to_send, 3, immediate_after_prelude=True)

    async def remove_setting(
        self,
        sunrise: datetime,
        sunset: datetime,
        max_brightness: int | Sequence[int] | Mapping[str | int, int] | None = None,
        ramp_up_in_minutes: int = 1,
        weekdays: list[WeekdaySelect] | None = None,
        delete_only: bool = False,
    ) -> None:
        """Remove an automation setting from the light."""
        if weekdays is None:
            weekdays = [WeekdaySelect.everyday]
        delete_command = commands.create_delete_auto_setting_command(
            self.get_next_msg_id(),
            sunrise.time(),
            sunset.time(),
            ramp_up_in_minutes,
            encode_selected_weekdays(weekdays),
            brightness_channels=self._channel_count(),
        )
        commands_to_send = [delete_command]
        if self.model.schedule_reset_parameter != 5 and not delete_only:
            first_finalize = commands.create_auto_parameter_command(
                self.get_next_msg_id(),
                self.model.schedule_reset_parameter,
            )
            second_delete_command = commands.create_delete_auto_setting_command(
                self.get_next_msg_id(),
                sunrise.time(),
                sunset.time(),
                ramp_up_in_minutes,
                encode_selected_weekdays(weekdays),
                brightness_channels=self._channel_count(),
            )
            second_finalize = commands.create_auto_parameter_command(
                self.get_next_msg_id(),
                self.model.schedule_reset_parameter,
            )
            commands_to_send = [delete_command, first_finalize, second_delete_command, second_finalize]
            if max_brightness is not None:
                commands_to_send.append(
                    commands.create_add_auto_setting_command(
                        self.get_next_msg_id(),
                        sunrise.time(),
                        sunset.time(),
                        self._brightness_parameter_values(max_brightness),
                        ramp_up_in_minutes,
                        encode_selected_weekdays(weekdays),
                    )
                )
        await self._send_command(commands_to_send, 3, immediate_after_prelude=True)

    async def replace_setting(
        self,
        previous_sunrise: datetime,
        previous_sunset: datetime,
        sunrise: datetime,
        sunset: datetime,
        max_brightness: int | Sequence[int] | Mapping[str | int, int],
        previous_ramp_up_in_minutes: int = 1,
        ramp_up_in_minutes: int = 1,
        previous_weekdays: list[WeekdaySelect] | None = None,
        weekdays: list[WeekdaySelect] | None = None,
        prepare_existing_setting: bool = False,
    ) -> None:
        """Replace one active automation setting without changing device mode."""
        previous_weekdays = previous_weekdays or [WeekdaySelect.everyday]
        weekdays = weekdays or [WeekdaySelect.everyday]
        delete_command = commands.create_delete_auto_setting_command(
            self.get_next_msg_id(),
            previous_sunrise.time(),
            previous_sunset.time(),
            previous_ramp_up_in_minutes,
            encode_selected_weekdays(previous_weekdays),
            brightness_channels=self._channel_count(),
        )
        add_command = commands.create_add_auto_setting_command(
            self.get_next_msg_id(),
            sunrise.time(),
            sunset.time(),
            self._brightness_parameter_values(max_brightness),
            ramp_up_in_minutes,
            encode_selected_weekdays(weekdays),
        )
        commands_to_send = [delete_command, add_command]
        if self.model.schedule_reset_parameter != 5:
            commands_to_send = [add_command]
            if prepare_existing_setting:
                clear_command = commands.create_delete_auto_setting_command(
                    self.get_next_msg_id(),
                    previous_sunrise.time(),
                    previous_sunset.time(),
                    previous_ramp_up_in_minutes,
                    encode_selected_weekdays(previous_weekdays),
                    brightness_channels=self._channel_count(),
                )
                second_clear_command = commands.create_delete_auto_setting_command(
                    self.get_next_msg_id(),
                    previous_sunrise.time(),
                    previous_sunset.time(),
                    previous_ramp_up_in_minutes,
                    encode_selected_weekdays(previous_weekdays),
                    brightness_channels=self._channel_count(),
                )
                commands_to_send = [clear_command, second_clear_command, add_command]
        await self._send_command(commands_to_send, 3, immediate_after_prelude=True)

    async def reset_settings(self) -> None:
        """Remove all automation settings from the light."""
        command = commands.create_reset_auto_settings_command(self.get_next_msg_id())
        await self._send_command(command, 3)

    async def send_auto_parameter(self, first_parameter: int) -> None:
        """Send a diagnostic 90/5 frame with ``[first_parameter, 255, 255]``."""
        command = commands.create_auto_parameter_command(self.get_next_msg_id(), first_parameter)
        await self._send_command(command, 3)

    async def hard_reset(self) -> None:
        """Send the four observed mode-5 reset stages, ending with stop/exit."""
        reset_commands = [
            commands.create_auto_parameter_command(self.get_next_msg_id(), first_parameter)
            for first_parameter in (5, 6, 7, 4)
        ]
        await self._send_command(reset_commands, 3)

    async def replace_settings(
        self,
        settings: Sequence[
            tuple[
                datetime,
                datetime,
                int | Sequence[int] | Mapping[str | int, int],
                int,
                list[WeekdaySelect] | None,
            ]
        ],
    ) -> None:
        """Replace all active schedules without changing the device mode."""
        if not settings:
            return
        await self.reset_settings()
        commands_to_send: list[bytearray] = []
        for sunrise, sunset, brightness, ramp, weekdays in settings:
            commands_to_send.append(
                commands.create_add_auto_setting_command(
                    self.get_next_msg_id(),
                    sunrise.time(),
                    sunset.time(),
                    self._brightness_parameter_values(brightness),
                    ramp,
                    encode_selected_weekdays(weekdays or [WeekdaySelect.everyday]),
                )
            )
        await self._send_command(commands_to_send, 3)

    async def enable_auto_mode(
        self,
        timestamp: datetime | None = None,
        settings: Sequence[
            tuple[
                datetime,
                datetime,
                int | Sequence[int] | Mapping[str | int, int],
                int,
                list[WeekdaySelect] | None,
            ]
        ]
        | None = None,
    ) -> None:
        """Switch to automatic mode and restore the active schedules."""
        del timestamp  # The standard connection prelude synchronizes the current local time.
        commands_to_send = [
            commands.create_switch_to_auto_mode_command(self.get_next_msg_id()),
            commands.create_reset_auto_settings_command(self.get_next_msg_id(), 5),
        ]
        for sunrise, sunset, brightness, ramp, weekdays in settings or ():
            commands_to_send.append(
                commands.create_add_auto_setting_command(
                    self.get_next_msg_id(),
                    sunrise.time(),
                    sunset.time(),
                    self._brightness_parameter_values(brightness),
                    ramp,
                    encode_selected_weekdays(weekdays or [WeekdaySelect.everyday]),
                )
            )
        await self._send_command(commands_to_send, 3)

    async def set_manual_mode(self) -> None:
        """Switch to manual mode."""
        await self.turn_on()

    async def _send_command(
        self,
        command: list[bytes] | bytes | bytearray,
        retry: int | None = None,
        notification_wait: float = COMMAND_NOTIFICATION_WAIT,
        connection_prelude: str = "standard",
        immediate_after_prelude: bool = False,
    ) -> None:
        """Send commands to the device."""
        commands_to_send = command if isinstance(command, list) else [bytes(command)]
        self._logger.debug(
            "%s: Sending commands %s",
            self.name,
            [command.hex() for command in commands_to_send],
        )
        if self._operation_lock.locked():
            self._logger.debug(
                "%s: Operation already in progress, waiting; RSSI: %s",
                self.name,
                self.rssi,
            )
        async with self._operation_lock:
            self._connection_prelude_mode = connection_prelude
            self._connection_prelude_commands = commands_to_send if immediate_after_prelude else []
            self._connection_prelude_commands_sent = False
            debug_start = len(self.debug_frames)
            tx_start = len(self.tx_debug_frames)
            raw_start = len(self.raw_notifications)
            try:
                await self._ensure_connected()
                del retry
                if not self._connection_prelude_commands_sent:
                    await self._send_command_locked(commands_to_send)
                if notification_wait:
                    await asyncio.sleep(notification_wait)
            finally:
                self._last_operation_debug_range = (
                    debug_start,
                    len(self.debug_frames),
                    tx_start,
                    len(self.tx_debug_frames),
                    raw_start,
                    len(self.raw_notifications),
                )
                self._connection_prelude_mode = "standard"
                self._connection_prelude_commands = []
                self._connection_prelude_commands_sent = False
                await self._execute_disconnect()

    async def _send_command_while_connected(self, commands_to_send: list[bytes], retry: int | None = None) -> None:
        """Send commands while connected."""
        self._logger.debug(
            "%s: Sending commands %s",
            self.name,
            [command.hex() for command in commands_to_send],
        )
        if self._operation_lock.locked():
            self._logger.debug(
                "%s: Operation already in progress, waiting; RSSI: %s",
                self.name,
                self.rssi,
            )
        async with self._operation_lock:
            try:
                await self._send_command_locked(commands_to_send)
                return
            except BleakNotFoundError:
                self._logger.error(
                    "%s: device not found, no longer in range, or poor RSSI: %s",
                    self.name,
                    self.rssi,
                    exc_info=True,
                )
                raise
            except CharacteristicMissingError as ex:
                self._logger.debug(
                    "%s: characteristic missing: %s; RSSI: %s",
                    self.name,
                    ex,
                    self.rssi,
                    exc_info=True,
                )
                raise
            except BLEAK_EXCEPTIONS:
                self._logger.debug("%s: communication failed", self.name, exc_info=True)
                raise

        raise RuntimeError("Unreachable")

    @retry_bluetooth_connection_error(DEFAULT_ATTEMPTS)
    async def _send_command_locked(self, commands_to_send: list[bytes]) -> None:
        """Send commands and retry transient Bluetooth failures."""
        try:
            await self._execute_command_locked(commands_to_send)
        except BleakDBusError as ex:
            await asyncio.sleep(BLEAK_BACKOFF_TIME)
            self._logger.debug(
                "%s: RSSI: %s; backing off %ss; disconnecting due to error: %s",
                self.name,
                self.rssi,
                BLEAK_BACKOFF_TIME,
                ex,
            )
            await self._execute_disconnect()
            raise
        except BleakError as ex:
            self._logger.debug("%s: RSSI: %s; disconnecting due to error: %s", self.name, self.rssi, ex)
            await self._execute_disconnect()
            raise

    async def _execute_command_locked(self, commands_to_send: list[bytes]) -> None:
        """Write commands to the BLE characteristic."""
        assert self._client is not None  # nosec
        if not self._read_char:
            raise CharacteristicMissingError("Read characteristic missing")
        if not self._write_char:
            raise CharacteristicMissingError("Write characteristic missing")
        for command in commands_to_send:
            self.tx_debug_frames.append(bytes(command))
            self.debug_frames.append(
                {
                    "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                    "dir": "tx",
                    "payload": bytes(command),
                }
            )
            if self._logger.isEnabledFor(logging.DEBUG):
                self._print_tx_encode(command)
                rich_print(
                    f"[green]DEBUG[/green]    [cyan]{self.address}[/cyan]: "
                    f"Sending commands [yellow]{[command.hex()]}[/yellow]"
                )
            await self._client.write_gatt_char(self._write_char, command, False)

    @staticmethod
    def _weekday_mask_text(mask: int) -> str:
        if mask == 0x7F:
            return "taeglich"
        names = [
            (64, "Mo"),
            (32, "Di"),
            (16, "Mi"),
            (8, "Do"),
            (4, "Fr"),
            (2, "Sa"),
            (1, "So"),
        ]
        selected = [name for bit, name in names if int(mask) & bit]
        return ",".join(selected) if selected else "-"

    def _describe_tx_frame(self, cmd_id: int | None, mode: int | None, params: list[int]) -> str:
        if cmd_id == 90 and mode == 4 and len(params) == 1:
            return f"App-Bestätigung Befehl={params[0]}"
        if cmd_id == 90 and mode == 9 and len(params) >= 6:
            return (
                "Gerätezeit setzen "
                f"20{params[0]:02d}-{params[1]:02d} Wochentag={params[2]} "
                f"{params[3]:02d}:{params[4]:02d}:{params[5]:02d}"
            )
        if cmd_id == 90 and mode == 5:
            if params in ([5, 255, 255], [7, 255, 255], [40, 255, 255]):
                return "Alle LED-Zeitplaene loeschen"
            if params == [11, 255, 255]:
                return "Schalter auf manuell setzen"
            if params == [18, 255, 255]:
                return "Automatikmodus aktivieren"
        if cmd_id == 165 and mode == 25 and len(params) >= 6:
            start = f"{params[0]:02d}:{params[1]:02d}"
            end = f"{params[2]:02d}:{params[3]:02d}"
            ramp = params[4]
            weekdays = self._weekday_mask_text(params[5])
            levels = params[6 : 6 + self._channel_count()]
            if levels and all(level == 255 for level in levels):
                return f"LED-Zeitplan deaktivieren {start}-{end}, Ramp={ramp} min, Wochentage={weekdays}"
            return f"LED-Zeitplan schreiben {start}-{end}, Ramp={ramp} min, Wochentage={weekdays}"
        return ""

    def _describe_rx_frame(self, payload: bytes) -> list[str]:
        if len(payload) >= 7 and payload[0] == 0x5B and payload[5] == 0xFE:
            schedule_curve = self._describe_schedule_curve_snapshot(payload)
            if schedule_curve:
                return schedule_curve
        parsed = parse_notification(payload, self.model.color_channels)
        if isinstance(parsed, RuntimeNotification):
            return [
                f"Laufzeitmeldung Firmware={parsed.firmware_version}, Laufzeit={parsed.runtime_minutes} min",
            ]
        if isinstance(parsed, ScheduleSnapshotNotification):
            lines = [f"Zeitplan-Snapshot Kurvenpunkte={len(parsed.points)}"]
            for index, point in enumerate(parsed.points, start=1):
                level = next(iter(point.levels.values()), 0)
                lines.append(f"#{index}: {point.hour:02d}:{point.minute:02d} Level={level}%")
            return lines
        return []

    @staticmethod
    def _describe_schedule_curve_snapshot(payload: bytes) -> list[str]:
        """Decode schedule snapshot RX frames as time/level curve points for debug output."""
        points: list[tuple[int, int, int]] = []
        for index in range(25, max(25, len(payload) - 1), 3):
            chunk = payload[index : index + 3]
            if len(chunk) < 3:
                break
            hour, minute, level = (int(value) for value in chunk)
            if hour > 23 or minute > 59 or level > 100:
                continue
            if hour == 0 and minute == 0 and level == 0:
                continue
            points.append((hour, minute, level))
        if not points:
            return []
        schedules = ChihirosDevice._schedule_curve_ranges(points)
        lines = [f"Zeitplan-Snapshot Kurvenpunkte={len(points)}, Zeitplaene={len(schedules)}"]
        lines.extend(
            f"Zeitplan {index}: {start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d} "
            f"Level={level}% Ramp={ramp} min"
            for index, (start_hour, start_minute, end_hour, end_minute, level, ramp) in enumerate(schedules, start=1)
        )
        lines.extend(
            f"Punkt {index}: {hour:02d}:{minute:02d} Level={level}%"
            for index, (hour, minute, level) in enumerate(points, start=1)
        )
        return lines

    @staticmethod
    def _schedule_curve_ranges(points: list[tuple[int, int, int]]) -> list[tuple[int, int, int, int, int, int]]:
        """Group zero/non-zero curve points into schedule ranges for debug output."""
        ranges: list[tuple[int, int, int, int, int, int]] = []
        index = 0
        while index < len(points):
            start_hour, start_minute, start_level = points[index]
            if start_level != 0:
                ramp = 1
                if index > 0 and points[index - 1][2] == 0:
                    previous_hour, previous_minute, _previous_level = points[index - 1]
                    candidate_ramp = ChihirosDevice._minute_distance(
                        previous_hour, previous_minute, start_hour, start_minute
                    )
                    if 1 <= candidate_ramp <= 150:
                        start_hour, start_minute = previous_hour, previous_minute
                        ramp = candidate_ramp
                end_index = index
                while end_index + 1 < len(points) and points[end_index + 1][2] == start_level:
                    end_index += 1
                if end_index + 1 < len(points) and points[end_index + 1][2] == 0:
                    end_hour, end_minute, _end_level = points[end_index + 1]
                    zero_index = end_index + 1
                    following_index = zero_index + 1
                    shares_boundary = (
                        following_index < len(points)
                        and points[following_index][2] != 0
                        and (points[following_index][0], points[following_index][1])
                        == ChihirosDevice._next_minute(end_hour, end_minute)
                    )
                    index = zero_index if shares_boundary else following_index
                elif end_index + 1 < len(points):
                    end_hour, end_minute = ChihirosDevice._active_point_default_range(start_hour, start_minute)
                    index = end_index + 1
                else:
                    index = end_index + 1
                    continue
                ranges.append((start_hour, start_minute, end_hour, end_minute, start_level, ramp))
                continue
            value_index = index + 1
            if value_index >= len(points):
                break
            value_hour, value_minute, level = points[value_index]
            if level == 0:
                index += 1
                continue
            end_index = value_index
            while end_index + 1 < len(points) and points[end_index + 1][2] == level:
                end_index += 1
            if end_index + 1 < len(points) and points[end_index + 1][2] == 0:
                end_hour, end_minute, _end_level = points[end_index + 1]
                zero_index = end_index + 1
                following_index = zero_index + 1
                shares_boundary = (
                    following_index < len(points)
                    and points[following_index][2] != 0
                    and (points[following_index][0], points[following_index][1])
                    == ChihirosDevice._next_minute(end_hour, end_minute)
                )
                index = zero_index if shares_boundary else following_index
            else:
                end_hour, end_minute = ChihirosDevice._next_minute(points[end_index][0], points[end_index][1])
                index = end_index + 1
            ramp = ChihirosDevice._minute_distance(start_hour, start_minute, value_hour, value_minute)
            ranges.append((start_hour, start_minute, end_hour, end_minute, level, ramp))
        return ranges

    @staticmethod
    def _minute_distance(start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> int:
        """Return the forward distance between two clock times in minutes."""
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        return (end - start) % (24 * 60)

    @staticmethod
    def _active_point_default_range(hour: int, minute: int) -> tuple[int, int]:
        """Return the display end for a non-trailing standalone active point."""
        del minute
        return (hour + 1) % 24, 0

    @staticmethod
    def _next_minute(hour: int, minute: int) -> tuple[int, int]:
        """Return the next minute for an hour/minute pair."""
        minute += 1
        if minute <= 59:
            return hour, minute
        return (hour + 1) % 24, 0

    def _print_tx_encode(self, payload: bytes | bytearray) -> None:
        data = bytes(payload)
        self._tx_debug_counter += 1

        cmd_id = data[0] if len(data) >= 1 else None
        version = data[1] if len(data) >= 2 else None
        command_length = data[2] if len(data) >= 3 else None
        msg_hi = data[3] if len(data) >= 4 else None
        msg_lo = data[4] if len(data) >= 5 else None
        mode = data[5] if len(data) >= 6 else None
        checksum = data[-1] if data else None

        params: list[int] = []
        if len(data) >= 7:
            total_after_header = max(0, len(data) - 7)
            if isinstance(command_length, int):
                if cmd_id == 0x5B:
                    param_len = max(0, command_length - 2)
                else:
                    param_len = max(0, command_length - 5)
            else:
                param_len = total_after_header
            if param_len != total_after_header:
                param_len = total_after_header
            params = [int(b) for b in data[6 : min(len(data) - 1, 6 + param_len)]]

        meaning = self._describe_tx_frame(cmd_id, mode, params)
        rich_print(f"[bright_cyan][TX #{self._tx_debug_counter}] Encode Message[/bright_cyan]")
        rich_print(f"  [white]Command Print[/white]    : [yellow]{[int(b) for b in data]}[/yellow]")
        rich_print(f"  [white]Command ID[/white]       : [yellow]{cmd_id}[/yellow]")
        rich_print(f"  [white]Version[/white]          : [yellow]{version}[/yellow]")
        rich_print(f"  [white]Command Length[/white]   : [yellow]{command_length}[/yellow]")
        rich_print(f"  [white]Message ID High[/white]  : [yellow]{msg_hi}[/yellow]")
        rich_print(f"  [white]Message ID Low[/white]   : [yellow]{msg_lo}[/yellow]")
        rich_print(f"  [white]Mode[/white]             : [yellow]{mode}[/yellow]")
        rich_print(f"  [white]Parameters[/white]       : [yellow]{params}[/yellow]")
        rich_print(f"  [white]Checksum[/white]         : [yellow]{checksum}[/yellow]")
        if meaning:
            rich_print(f"  [white]Bedeutung[/white]        : [yellow]{meaning}[/yellow]")
        rich_print("[bright_black]" + "-" * 72 + "[/bright_black]")

    def _notification_handler(self, _sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """Handle notification responses."""
        self.raw_notifications.append(bytes(data))
        self.debug_frames.append(
            {
                "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "dir": "rx",
                "payload": bytes(data),
            }
        )
        parsed = parse_notification(data, self.model.color_channels)
        if isinstance(parsed, RuntimeNotification):
            self.last_runtime_notification = parsed
            self._logger.debug(
                "%s: Runtime notification received; firmware=%s runtime_minutes=%s",
                self.name,
                parsed.firmware_version,
                parsed.runtime_minutes,
            )
            self._notify_callbacks(parsed)
            return
        if isinstance(parsed, FanStatusNotification):
            self.last_fan_status_notification = parsed
            self._logger.debug(
                "%s: Fan status notification received; firmware=%s fan_rpm=%s temperature_celsius=%s",
                self.name,
                parsed.firmware_version,
                parsed.fan_rpm,
                parsed.temperature_celsius,
            )
            self._notify_callbacks(parsed)
            return
        if isinstance(parsed, ScheduleSnapshotNotification):
            self.last_schedule_snapshot_notification = parsed
            self._schedule_notification_event.set()
            self._logger.debug(
                "%s: Schedule snapshot notification received; firmware=%s points=%s",
                self.name,
                parsed.firmware_version,
                parsed.points,
            )
            self._notify_callbacks(parsed)
            return
        self._logger.debug("%s: Notification received: %s", self.name, data.hex())

    def _notify_callbacks(self, notification: ParsedNotification) -> None:
        """Notify subscribers about a parsed device notification."""
        for callback in tuple(self._notification_callbacks):
            callback(notification)

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Handle disconnected callback."""
        if self._client is client:
            self._client = None
            self._read_char = None
            self._write_char = None
        if self._expected_disconnect:
            self._logger.debug("%s: Disconnected from device; RSSI: %s", self.name, self.rssi)
            return
        self._logger.debug(
            "%s: Device unexpectedly disconnected; RSSI: %s",
            self.name,
            self.rssi,
        )

    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve UART characteristics."""
        self._read_char = None
        self._write_char = None
        self._last_characteristic_summary = self._characteristic_summary(services)
        for characteristic in [UART_TX_CHAR_UUID, LEGACY_UART_CHAR_UUID]:
            if char := services.get_characteristic(characteristic):
                self._read_char = char
                break
        for characteristic in [UART_RX_CHAR_UUID, LEGACY_UART_CHAR_UUID]:
            if char := services.get_characteristic(characteristic):
                self._write_char = char
                break
        if self._read_char and self._write_char:
            return True
        for char in getattr(services, "characteristics", {}).values():
            properties = set(getattr(char, "properties", []) or [])
            if not self._read_char and properties.intersection({"notify", "indicate"}):
                self._read_char = char
            if not self._write_char and properties.intersection({"write", "write-without-response"}):
                self._write_char = char
            if self._read_char and self._write_char:
                break
        return bool(self._read_char and self._write_char)

    @staticmethod
    def _characteristic_summary(services: BleakGATTServiceCollection) -> str:
        """Return a compact service/characteristic summary for debug output."""
        characteristics = getattr(services, "characteristics", {}) or {}
        if not characteristics:
            return "keine Characteristics im Service-Cache"
        lines = []
        for char in characteristics.values():
            uuid = str(getattr(char, "uuid", "?"))
            properties = ",".join(str(prop) for prop in (getattr(char, "properties", []) or [])) or "-"
            handle = getattr(char, "handle", "?")
            lines.append(f"{uuid} handle={handle} props={properties}")
        return "\n".join(lines[:40])

    async def _resolve_client_characteristics(self, client: BleakClientWithServiceCache) -> bool:
        """Resolve characteristics from a connected client."""
        services = getattr(client, "services", None)
        resolved = self._resolve_characteristics(services) if services else False
        if not resolved:
            get_services = getattr(client, "get_services", None)
            if get_services:
                resolved = self._resolve_characteristics(await get_services())
        return resolved

    async def _ensure_connected(self) -> None:
        """Ensure a BLE connection exists."""
        if self._connect_lock.locked():
            self._logger.debug(
                "%s: Connection already in progress, waiting; RSSI: %s",
                self.name,
                self.rssi,
            )
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return
            self._logger.debug("%s: Connecting; RSSI: %s", self.name, self.rssi)
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                self._disconnected,
                use_services_cache=True,
                ble_device_callback=lambda: self._ble_device,
            )
            self._logger.debug("%s: Connected; RSSI: %s", self.name, self.rssi)
            try:
                resolved = await self._resolve_client_characteristics(client)
                if not resolved:
                    self._logger.debug(
                        "%s: UART characteristics missing from cache; reconnecting without service cache", self.name
                    )
                    await self._disconnect_client(client, self._read_char)
                    self._read_char = None
                    self._write_char = None
                    client = await establish_connection(
                        BleakClientWithServiceCache,
                        self._ble_device,
                        self.name,
                        self._disconnected,
                        use_services_cache=False,
                        ble_device_callback=lambda: self._ble_device,
                    )
                    resolved = await self._resolve_client_characteristics(client)
                if not resolved:
                    detail = self._last_characteristic_summary or "keine GATT-Details verfuegbar"
                    raise CharacteristicMissingError(
                        f"UART characteristics missing\nGefundene Characteristics:\n{detail}"
                    )

                self._client = client
                self._reset_disconnect_timer()

                self._logger.debug("%s: Subscribe to notifications; RSSI: %s", self.name, self.rssi)
                await client.start_notify(self._read_char, self._notification_handler)  # type: ignore
                await self._send_connection_prelude(client)
            except Exception:
                read_char = self._read_char
                self._client = None
                self._read_char = None
                self._write_char = None
                if self._disconnect_timer:
                    self._disconnect_timer.cancel()
                    self._disconnect_timer = None
                self._expected_disconnect = True
                await self._disconnect_client(client, read_char)
                raise

    async def _send_connection_prelude(self, client: BleakClientWithServiceCache) -> None:
        """Send the LED startup sequence observed in the vendor app/ESPHome flow."""
        if not self._write_char:
            raise CharacteristicMissingError("Write characteristic missing")
        timestamp = datetime.now()
        prelude = [commands.create_base_auth_command(self.get_next_msg_id())]
        if self._connection_prelude_mode == "automatic_tab":
            prelude.extend(
                [
                    commands.create_set_time_command(self.get_next_msg_id(), timestamp),
                    commands.create_set_date_command(self.get_next_msg_id(), timestamp),
                ]
            )
        else:
            prelude.extend(
                [
                    commands.create_set_time_command(self.get_next_msg_id(), timestamp),
                    commands.create_set_time_command(self.get_next_msg_id(), timestamp),
                ]
            )
        prelude.extend(self._command_with_next_message_id(command) for command in self._connection_prelude_commands)
        wait_for_auth_notification = bool(self._connection_prelude_commands)
        if wait_for_auth_notification:
            self._schedule_notification_event.clear()
        self._logger.debug(
            "%s: Sending connection prelude %s",
            self.name,
            [command.hex() for command in prelude],
        )
        deferred_start = len(prelude) - len(self._connection_prelude_commands)
        for index, command in enumerate(prelude):
            if self._connection_prelude_commands and index == deferred_start:
                await asyncio.sleep(SCHEDULE_DELETE_SETTLE_WAIT)
            self.tx_debug_frames.append(bytes(command))
            self.debug_frames.append(
                {
                    "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                    "dir": "tx",
                    "payload": bytes(command),
                }
            )
            if self._logger.isEnabledFor(logging.DEBUG):
                self._print_tx_encode(command)
                rich_print(
                    f"[green]DEBUG[/green]    [cyan]{self.address}[/cyan]: "
                    f"Sending commands [yellow]{[command.hex()]}[/yellow]"
                )
            await client.write_gatt_char(self._write_char, command, False)
            if index == 0 and wait_for_auth_notification:
                try:
                    await asyncio.wait_for(self._schedule_notification_event.wait(), timeout=AUTH_NOTIFICATION_WAIT)
                except TimeoutError as exc:
                    raise TimeoutError(
                        "No schedule snapshot notification received within "
                        f"{AUTH_NOTIFICATION_WAIT:.1f}s after authentication"
                    ) from exc
        if self._connection_prelude_commands:
            self._connection_prelude_commands_sent = True

    def _command_with_next_message_id(self, command: bytes) -> bytes:
        """Re-encode a deferred command with an ID following the prelude IDs."""
        if len(command) < 7:
            raise ValueError("Commands must contain at least 7 bytes")
        for _attempt in range(8):
            message_id = self.get_next_msg_id()
            updated = bytearray(command)
            updated[3:5] = bytes(message_id)
            updated[-1] = calculate_checksum(updated[:-1])
            if updated[-1] != 0x5A:
                return bytes(updated)
        raise ValueError("Could not create a deferred command without reserved checksum")

    def _reset_disconnect_timer(self) -> None:
        """Reset connection state without scheduling a delayed keepalive."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None
        self._expected_disconnect = False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        self._logger.debug("%s: Disconnecting", self.name)
        await self._execute_disconnect()

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            read_char = self._read_char
            client = self._client
            self._expected_disconnect = True
            if self._disconnect_timer:
                self._disconnect_timer.cancel()
                self._disconnect_timer = None
            self._client = None
            self._read_char = None
            self._write_char = None
            if client:
                await self._disconnect_client(client, read_char)

    async def _disconnect_client(
        self,
        client: BleakClientWithServiceCache,
        read_char: BleakGATTCharacteristic | None,
    ) -> None:
        """Disconnect an established BLE client without taking the connection lock."""
        if not client.is_connected:
            return
        if read_char:
            try:
                await client.stop_notify(read_char)
            except BleakError:
                self._logger.debug("%s: Failed to stop notifications", self.name, exc_info=True)
        await client.disconnect()
