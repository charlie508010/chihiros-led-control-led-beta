"""Integration to integrate Keymitt BLE devices with Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .runtime import ChihirosClient
from .vendor.chihiros_led_control.protocol import (
    ParsedNotification,
    RuntimeNotification,
    SchedulePoint,
    ScheduleSnapshotNotification,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_RUNTIME_MINUTES = "runtime_minutes"
ATTR_RUNTIME_NOTIFICATION = "runtime_notification"
ATTR_RUNTIME_NOTIFICATION_PAYLOAD = "runtime_notification_payload"
ATTR_LAST_NOTIFICATION = "last_notification"
ATTR_RECENT_NOTIFICATIONS = "recent_notifications"
ATTR_SCHEDULE_POINTS = "schedule_points"


class ChihirosDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator that tracks passive Bluetooth availability events."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ChihirosClient,
        address: str,
        always_available: bool = False,
    ) -> None:
        """Initialize."""
        self.api: ChihirosClient = client
        self.data: dict[str, Any] = {}
        self._device_address = address
        self._auto_mode = False
        self.always_available = always_available
        self._remove_notification_callback = client.add_notification_callback(self._queue_notification)
        self._remove_bluetooth_callback: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            address,
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    @property
    def auto_mode(self) -> bool:
        """Return whether the device is currently assumed to be in auto mode."""
        return self._auto_mode

    @callback
    def async_set_auto_mode(self, enabled: bool) -> None:
        """Update the assumed auto/manual mode and notify entities."""
        if self._auto_mode == enabled:
            return
        self._auto_mode = enabled
        self.async_update_listeners()

    async def async_request_status(self) -> None:
        """Refresh HA entities from the latest passive notification data."""
        self.async_update_listeners()

    @callback
    def async_clear_schedule_snapshot(self) -> None:
        """Discard cached schedule data before a command that changes the device schedule."""
        self.data.pop(ATTR_SCHEDULE_POINTS, None)
        last_notification = self.data.get(ATTR_LAST_NOTIFICATION)
        if isinstance(last_notification, dict) and last_notification.get("parsed_type") == "schedule_snapshot":
            self.data.pop(ATTR_LAST_NOTIFICATION, None)
        self.api.last_schedule_snapshot_notification = None
        self.async_update_listeners()

    @callback
    def async_start_bluetooth(self) -> None:
        """Start tracking passive Bluetooth availability events."""
        if self._remove_bluetooth_callback is not None:
            return
        self._remove_bluetooth_callback = self.async_start()

    def async_close(self) -> None:
        """Remove callbacks held by this coordinator."""
        if self._remove_bluetooth_callback is not None:
            self._remove_bluetooth_callback()
            self._remove_bluetooth_callback = None
        self._remove_notification_callback()

    def _queue_notification(self, notification: ParsedNotification) -> None:
        """Queue notification handling on the Home Assistant event loop."""
        self.hass.loop.call_soon_threadsafe(self._async_handle_notification, notification)

    @callback
    def _async_handle_notification(self, notification: ParsedNotification) -> None:
        """Store parsed notification data and update entities."""
        debug_notification: dict[str, Any] | None = None
        if isinstance(notification, RuntimeNotification):
            self.data[ATTR_FIRMWARE_VERSION] = notification.firmware_version
            self.data[ATTR_RUNTIME_MINUTES] = notification.runtime_minutes
            self.data[ATTR_RUNTIME_NOTIFICATION] = notification.raw.hex(" ")
            self.data[ATTR_RUNTIME_NOTIFICATION_PAYLOAD] = notification.raw[6:].hex(" ")
            debug_notification = _notification_to_debug_dict(notification, "runtime")
        elif isinstance(notification, ScheduleSnapshotNotification):
            self.data[ATTR_FIRMWARE_VERSION] = notification.firmware_version
            self.data[ATTR_SCHEDULE_POINTS] = tuple(_schedule_point_to_dict(point) for point in notification.points)
            debug_notification = _notification_to_debug_dict(notification, "schedule_snapshot")
        if debug_notification is not None:
            self.data[ATTR_LAST_NOTIFICATION] = debug_notification
            recent = list(self.data.get(ATTR_RECENT_NOTIFICATIONS, ()))
            recent = [item for item in recent if item.get("parsed_type") != debug_notification["parsed_type"]]
            recent.append(debug_notification)
            self.data[ATTR_RECENT_NOTIFICATIONS] = tuple(recent[-2:])
        self.async_update_listeners()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        _LOGGER.debug("%s: Bluetooth event: %s", self._device_address, change)
        super()._async_handle_bluetooth_event(service_info, change)

    @callback
    def _async_handle_unavailable(self, service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Handle the device going unavailable."""
        _LOGGER.debug("%s: Chihiros device unavailable", self._device_address)
        super()._async_handle_unavailable(service_info)


def _schedule_point_to_dict(point: SchedulePoint) -> dict[str, Any]:
    """Return a Home Assistant-friendly schedule point."""
    return {
        "time": f"{point.hour:02d}:{point.minute:02d}",
        "levels": dict(point.levels),
    }


def _notification_to_debug_dict(
    notification: RuntimeNotification | ScheduleSnapshotNotification,
    parsed_type: str,
) -> dict[str, Any]:
    """Return a Home Assistant-friendly raw notification diagnostic payload."""
    raw = notification.raw
    mode = raw[5] if len(raw) > 5 else None
    return {
        "firmware_version": notification.firmware_version,
        "frame": raw.hex(" "),
        "payload": raw[6:].hex(" "),
        "mode": f"0x{mode:02x}" if mode is not None else None,
        "parsed_type": parsed_type,
    }
