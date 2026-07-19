"""Runtime device resolution for the Chihiros Home Assistant integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Protocol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .dosing import CONF_PUMP_COUNT, normalize_pump_count
from .fake import create_fake_device, fake_devices_enabled, is_fake_address
from .vendor.chihiros_led_control import create_device, needs_device_type
from .vendor.chihiros_led_control.models import DeviceModel
from .vendor.chihiros_led_control.protocol import ParsedNotification, RuntimeNotification, ScheduleSnapshotNotification
from .vendor.chihiros_led_control.weekday_encoding import WeekdaySelect

NotificationCallback = Callable[[ParsedNotification], None]


class DosingChihirosClient(Protocol):
    """Home Assistant-facing dosing pump client surface."""

    raw_notifications: list[bytes]
    last_doser_totals: list[float] | None

    async def dose_ml(self, pump_idx: int, volume_ml: float) -> None:
        """Dose a volume in mL on a dosing pump channel."""

    async def add_schedule(
        self,
        pump_idx: int,
        schedule_time: time,
        dose_ml: float,
        weekdays_mask: int = 0x7F,
        active: bool = True,
        next_day_flag: bool = False,
    ) -> None:
        """Program one single-dose schedule."""

    async def add_interval_schedule(
        self,
        pump_idx: int,
        interval_minutes: int,
        dose_ml: float,
        weekdays_mask: int = 0x7F,
        active: bool = True,
        next_day_flag: bool = False,
    ) -> None:
        """Program one interval schedule."""

    async def read_auto_totals(self, mode: int = 0x34, *, clear_notifications: bool = True) -> list[float] | None:
        """Read automatic daily totals directly."""

    async def read_auto_totals_via_dialog(
        self,
        mode: int = 0x22,
        *,
        clear_notifications: bool = True,
    ) -> list[float] | None:
        """Read automatic daily totals using the Doser dialog sequence."""

    async def read_doser_notifications(self, notification_wait: float = 5.0) -> None:
        """Open the app-like Doser dialog and collect its complete notification burst."""


class ChihirosClient(Protocol):
    """Home Assistant-facing device client surface."""

    model: DeviceModel
    last_runtime_notification: RuntimeNotification | None
    last_schedule_snapshot_notification: ScheduleSnapshotNotification | None

    @property
    def address(self) -> str:
        """Return the device address."""

    @property
    def name(self) -> str:
        """Return the device name."""

    @property
    def model_name(self) -> str:
        """Return the model name."""

    @property
    def colors(self) -> dict[str, int]:
        """Return supported color channels."""

    def add_notification_callback(self, callback: NotificationCallback) -> Callable[[], None]:
        """Register a parsed notification callback."""

    async def query_status(self) -> None:
        """Request a current runtime/status snapshot."""

    async def query_status_active(self, notification_wait: float = 3.0) -> None:
        """Actively request a runtime/status snapshot for diagnostics."""

    async def set_brightness(self, brightness: int | Sequence[int] | Mapping[str | int, int]) -> None:
        """Set device brightness."""

    async def turn_on(self) -> None:
        """Turn the device on."""

    async def turn_off(self) -> None:
        """Turn the device off."""

    async def enable_auto_mode(
        self,
        timestamp: datetime | None = None,
        settings: Sequence[tuple[object, ...]] | None = None,
    ) -> None:
        """Enable automatic mode and optionally restore schedules."""

    async def set_manual_mode(self) -> None:
        """Enable manual mode."""

    async def add_setting(
        self,
        sunrise: datetime,
        sunset: datetime,
        max_brightness: int | Sequence[int] | Mapping[str | int, int] = 100,
        ramp_up_in_minutes: int = 1,
        weekdays: list[WeekdaySelect] | None = None,
        enable_auto_mode: bool = True,
    ) -> None:
        """Add a schedule setting."""

    async def remove_setting(
        self,
        sunrise: datetime,
        sunset: datetime,
        ramp_up_in_minutes: int = 1,
        weekdays: list[WeekdaySelect] | None = None,
    ) -> None:
        """Remove a schedule setting."""

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
    ) -> None:
        """Replace one active schedule setting."""

    async def reset_settings(self) -> None:
        """Reset schedule settings."""

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
        """Replace all active schedule settings."""

    async def disconnect(self) -> None:
        """Disconnect the client."""


@dataclass(frozen=True)
class ChihirosRuntime:
    """Resolved runtime device data for a config entry."""

    client: ChihirosClient
    address: str
    always_available: bool = False


async def resolve_chihiros_runtime(hass: HomeAssistant, entry: ConfigEntry) -> ChihirosRuntime:
    """Resolve a config entry to either a real BLE client or a development fake client."""
    if entry.unique_id is None:
        raise ConfigEntryNotReady(f"Entry doesn't have any unique_id {entry.title}")

    address: str = entry.unique_id
    if fake_devices_enabled() and is_fake_address(address):
        return ChihirosRuntime(
            client=create_fake_device(address, normalize_pump_count(entry.data.get(CONF_PUMP_COUNT))),
            address=address,
            always_available=True,
        )

    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find Chihiros BLE device with address {address}")
    if not ble_device.name:
        raise ConfigEntryNotReady(f"Found Chihiros BLE device with address {address} but can not find its name")
    if needs_device_type(ble_device.name):
        entry_name = entry.data.get(CONF_NAME)
        if entry_name:
            try:
                ble_device.name = entry_name
            except Exception:
                pass

    return ChihirosRuntime(
        client=create_device(ble_device, device_type=entry.data.get("device_type")),
        address=ble_device.address,
    )
