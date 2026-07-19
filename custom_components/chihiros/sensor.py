"""Sensor platform for Chihiros notification data."""

# ruff: noqa: D102,D107,E501

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    ATTR_FIRMWARE_VERSION,
    ATTR_LAST_NOTIFICATION,
    ATTR_RECENT_NOTIFICATIONS,
    ATTR_RUNTIME_MINUTES,
    ATTR_RUNTIME_NOTIFICATION,
    ATTR_RUNTIME_NOTIFICATION_PAYLOAD,
    ATTR_SCHEDULE_POINTS,
    ChihirosDataUpdateCoordinator,
)
from .dosing import DosingDailyTotals
from .entity import chihiros_device_info, chihiros_entity_name, chihiros_unique_id
from .models import ChihirosData
from .packages.doser.entity import DoserExtEntity
from .packages.doser.storage import async_store_for_device, update_signal
from .packages.doser.watcher import timer_status_for_hass, timer_status_signal
from .runtime import ChihirosClient

_LOGGER = logging.getLogger(__name__)
MAX_SENSOR_STATE_LENGTH = 255


SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=ATTR_FIRMWARE_VERSION,
        name="Firmware Version",
    ),
    SensorEntityDescription(
        key=ATTR_RUNTIME_MINUTES,
        name="Runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key=ATTR_SCHEDULE_POINTS,
        name="Schedule",
    ),
    SensorEntityDescription(
        key=ATTR_LAST_NOTIFICATION,
        name="Last Notification",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up notification sensors for Chihiros LED Control."""
    chihiros_data: ChihirosData = hass.data[DOMAIN][entry.entry_id]
    if chihiros_data.dosing_totals:
        await async_add_doser_sensors(hass, entry, async_add_entities, chihiros_data)
        async_add_entities(
            ChihirosDosingDailyTotalSensor(
                chihiros_data.coordinator,
                chihiros_data.device,
                chihiros_data.dosing_totals,
                pump_idx,
            )
            for pump_idx in range(chihiros_data.dosing_totals.pump_count)
        )
        return

    async_add_entities(
        ChihirosNotificationSensor(
            chihiros_data.coordinator,
            chihiros_data.device,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class ChihirosNotificationSensor(
    PassiveBluetoothCoordinatorEntity[ChihirosDataUpdateCoordinator],
    SensorEntity,
):
    """Sensor backed by parsed Chihiros notification data."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ChihirosDataUpdateCoordinator,
        device: ChihirosClient,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._attr_name = chihiros_entity_name(device, description.name)
        self._attr_unique_id = chihiros_unique_id(coordinator.address, description.key)
        self._attr_device_info = chihiros_device_info(device, coordinator.address)
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_force_update = description.key == ATTR_LAST_NOTIFICATION

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""
        if self.coordinator.always_available:
            return True
        return super().available

    @property
    def native_value(self) -> int | str | None:
        """Return the current sensor value."""
        value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key == ATTR_LAST_NOTIFICATION:
            if not isinstance(value, dict):
                return None
            return value.get("mode")
        if self.entity_description.key == ATTR_SCHEDULE_POINTS:
            if value is None:
                return None
            return _format_schedule_state(value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return detailed notification data."""
        if self.entity_description.key == ATTR_LAST_NOTIFICATION:
            notification = self.coordinator.data.get(ATTR_LAST_NOTIFICATION)
            if not isinstance(notification, dict):
                return None
            notifications = [
                item for item in self.coordinator.data.get(ATTR_RECENT_NOTIFICATIONS, ()) if isinstance(item, dict)
            ]
            runtime_frame = self.coordinator.data.get(ATTR_RUNTIME_NOTIFICATION)
            if runtime_frame and not any(item.get("parsed_type") == "runtime" for item in notifications):
                notifications.insert(
                    0,
                    {
                        "firmware_version": self.coordinator.data.get(ATTR_FIRMWARE_VERSION),
                        "frame": runtime_frame,
                        "payload": self.coordinator.data.get(ATTR_RUNTIME_NOTIFICATION_PAYLOAD),
                        "mode": "0x0a",
                        "parsed_type": "runtime",
                    },
                )
            if not any(item.get("parsed_type") == notification.get("parsed_type") for item in notifications):
                notifications.append(notification)
            notifications.sort(key=lambda item: item.get("parsed_type") != "runtime")
            return {
                **notification,
                "notifications": tuple(notifications[:2]),
            }
        if self.entity_description.key != ATTR_SCHEDULE_POINTS:
            return None
        points = self.coordinator.data.get(ATTR_SCHEDULE_POINTS)
        if points is None:
            return None
        return {"points": points}


class ChihirosDosingDailyTotalSensor(SensorEntity):
    """Sensor for locally tracked manual dosing total for today."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: ChihirosDataUpdateCoordinator,
        device: ChihirosClient,
        totals: DosingDailyTotals,
        pump_idx: int,
    ) -> None:
        """Initialize the dosing total sensor."""
        self._device = device
        self._totals = totals
        self._pump_idx = pump_idx
        pump_number = pump_idx + 1
        self._attr_name = chihiros_entity_name(device, f"Pump {pump_number} dosed today")
        self._attr_unique_id = chihiros_unique_id(coordinator.address, f"dosing_pump_{pump_number}_dosed_today")
        self._attr_device_info = chihiros_device_info(device, coordinator.address)

    async def async_added_to_hass(self) -> None:
        """Subscribe to dosing total updates."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._totals.address_signal, self.async_write_ha_state)
        )

    @property
    def native_value(self) -> float:
        """Return today's tracked total."""
        return self._totals.total_ml(self._pump_idx)


def _format_schedule_state(points: tuple[dict[str, Any], ...]) -> str:
    """Return a compact display value for schedule points."""
    if not points:
        return "No schedule"
    formatted_points = [_format_schedule_point(point) for point in points]
    schedule = "; ".join(formatted_points)
    if len(schedule) <= MAX_SENSOR_STATE_LENGTH:
        return schedule
    return f"{len(points)} points"


def _format_schedule_point(point: dict[str, Any]) -> str:
    """Return one compact schedule point."""
    levels = point.get("levels", {})
    if not isinstance(levels, dict) or not levels:
        return str(point.get("time", "unknown"))
    unique_levels = set(levels.values())
    if len(unique_levels) == 1:
        return f"{point.get('time', 'unknown')} {unique_levels.pop()}%"
    level_text = "/".join(f"{color[:1].upper()}{level}" for color, level in levels.items())
    return f"{point.get('time', 'unknown')} {level_text}"


async def async_add_doser_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    chihiros_data: ChihirosData,
) -> None:
    """Add extension sensors for a dosing pump."""
    if not chihiros_data.dosing_totals:
        return
    store = await async_store_for_device(hass, chihiros_data.device.address, chihiros_data.dosing_totals.pump_count)
    entities = [DoserExtActionLogSensor(chihiros_data, store), DoserExtTimerStatusSensor(chihiros_data)]
    for pump_idx in range(chihiros_data.dosing_totals.pump_count):
        entities.extend(
            [
                DoserExtDailyTotalSensor(chihiros_data, store, pump_idx),
                DoserExtAutoDailySensor(chihiros_data, store, pump_idx),
                DoserExtManualDailySensor(chihiros_data, store, pump_idx),
                DoserExtRemainingSensor(chihiros_data, store, pump_idx),
                DoserExtScheduleTimeSensor(chihiros_data, store, pump_idx),
                DoserExtScheduleAmountSensor(chihiros_data, store, pump_idx),
                DoserExtCalibrationSensor(chihiros_data, store, pump_idx),
            ]
        )
    async_add_entities(entities)


class _DoserExtSensor(DoserExtEntity, SensorEntity):
    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, update_signal(self._device.address), self._handle_store_update)
        )

    @callback
    def _handle_store_update(self) -> None:
        self.async_schedule_update_ha_state(True)
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Reload persisted dosing data before Home Assistant reads this sensor."""
        await self._store.async_load()


class _DoserExtVolumeSensor(_DoserExtSensor):
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_suggested_display_precision = 1


class DoserExtActionLogSensor(_DoserExtSensor):
    """Recent dosing action log."""

    _attr_icon = "mdi:history"

    def __init__(self, chihiros_data: ChihirosData, store) -> None:
        self._chihiros_data = chihiros_data
        self._device = chihiros_data.device
        self._store = store
        self._pump_idx = 0
        self._attr_name = "Doser history"
        self._attr_unique_id = chihiros_unique_id(self._device.address, "doser_ext_history")
        self._attr_device_info = chihiros_device_info(self._device, self._device.address)

    @property
    def native_value(self) -> str:
        entries = self._store.action_log(1)
        if not entries:
            return "Keine Aktionen"
        entry = entries[0]
        pump = entry.get("pump")
        prefix = f"CH{pump} " if pump else ""
        return f"{entry.get('time', '')} {prefix}{entry.get('action', '')}".strip()

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "entries": self._store.action_log(120),
            "low_container_push_enabled": self._store.low_container_notification_enabled(),
            "low_container_push_targets": self._store.low_container_notify_targets(),
            "low_container_push_message": self._store.low_container_push_message_template(),
        }


class DoserExtTimerStatusSensor(SensorEntity):
    """Auto-total timer diagnostic status."""

    _attr_should_poll = False
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(self, chihiros_data: ChihirosData) -> None:
        self._chihiros_data = chihiros_data
        self._device = chihiros_data.device
        self._attr_name = "Doser timer status"
        self._attr_unique_id = chihiros_unique_id(self._device.address, "doser_ext_timer_status")
        self._attr_device_info = chihiros_device_info(self._device, self._device.address)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, timer_status_signal(self._device.address), self.async_write_ha_state)
        )

    @property
    def native_value(self) -> str:
        status = timer_status_for_hass(self.hass, self._device.address)
        return str(status.get("state") or "unbekannt")

    @property
    def extra_state_attributes(self) -> dict:
        return timer_status_for_hass(self.hass, self._device.address)


class DoserExtDailyTotalSensor(_DoserExtVolumeSensor):
    """Combined automatic and manual total for today."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Daily dose")

    @property
    def native_value(self) -> float:
        return round(self._store.auto_daily_ml(self._pump_idx) + self._store.manual_daily_ml(self._pump_idx), 1)


class DoserExtAutoDailySensor(_DoserExtVolumeSensor):
    """Automatic scheduled dose total for today."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Auto daily dose")

    @property
    def native_value(self) -> float:
        return self._store.auto_daily_ml(self._pump_idx)


class DoserExtManualDailySensor(_DoserExtVolumeSensor):
    """Manual dose total for today."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Manual daily dose")

    @property
    def native_value(self) -> float:
        return self._store.manual_daily_ml(self._pump_idx)


class DoserExtRemainingSensor(_DoserExtVolumeSensor):
    """Local remaining container volume."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Remaining")

    @property
    def native_value(self) -> float:
        return self._store.container_ml(self._pump_idx)


class DoserExtScheduleTimeSensor(_DoserExtSensor):
    """Stored schedule time."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Schedule time")

    @property
    def native_value(self) -> str | None:
        schedule = self._store.schedule(self._pump_idx)
        if not schedule:
            return None
        if schedule.kind == "interval" and schedule.interval_minutes is not None:
            return f"{schedule.interval_minutes} min"
        return schedule.time

    @property
    def extra_state_attributes(self) -> dict:
        schedule = self._store.schedule(self._pump_idx)
        if not schedule:
            return {}
        return {
            "schedule_kind": schedule.kind,
            "schedule_type_id": schedule.schedule_type_id,
            "interval_minutes": schedule.interval_minutes,
            "weekdays": schedule.weekdays,
            "timer_entries": tuple(
                {"time": time_text, "ml": round(float(ml), 1)} for time_text, ml in schedule.timer_entries
            ),
            "window_entries": tuple(
                {"start": start, "end": end, "doses": int(doses)} for start, end, doses in schedule.window_entries
            ),
        }


class DoserExtScheduleAmountSensor(_DoserExtVolumeSensor):
    """Stored schedule dose amount."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Schedule amount")

    @property
    def native_value(self) -> float | None:
        schedule = self._store.schedule(self._pump_idx)
        return schedule.ml if schedule else None

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the complete timer list as a fallback for the dashboard editor."""
        schedule = self._store.schedule(self._pump_idx)
        if not schedule:
            return {}
        return {
            "schedule_kind": schedule.kind,
            "schedule_type_id": schedule.schedule_type_id,
            "weekdays": schedule.weekdays,
            "timer_entries": tuple(
                {"time": time_text, "ml": round(float(ml), 1)} for time_text, ml in schedule.timer_entries
            ),
            "window_entries": tuple(
                {"start": start, "end": end, "doses": int(doses)} for start, end, doses in schedule.window_entries
            ),
        }


class DoserExtCalibrationSensor(_DoserExtSensor):
    """Latest calibration measurement and renewal reminder."""

    _attr_icon = "mdi:tune-vertical"

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Calibration")

    @property
    def native_value(self) -> str | None:
        calibration = self._store.calibration(self._pump_idx)
        if not calibration:
            return None
        calibrated_at = dt_util.parse_datetime(str(calibration.get("calibrated_at") or ""))
        if calibrated_at is None:
            return str(calibration.get("calibrated_at") or "") or None
        return dt_util.as_local(calibrated_at).date().isoformat()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        calibration = self._store.calibration(self._pump_idx)
        if not calibration:
            return {}
        reminder_at = dt_util.parse_datetime(str(calibration.get("reminder_at") or ""))
        return {
            **calibration,
            "reminder_due": bool(reminder_at and reminder_at <= dt_util.utcnow()),
        }
