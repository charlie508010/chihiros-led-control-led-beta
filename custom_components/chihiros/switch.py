"""Switch platform for Chihiros LED Control to toggle auto/manual mode."""

# ruff: noqa: D102,D107,E501

import logging
from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ChihirosDataUpdateCoordinator
from .entity import chihiros_device_info, chihiros_entity_name, chihiros_unique_id
from .models import ChihirosData
from .packages.doser.entity import DoserExtEntity
from .packages.doser.storage import async_store_for_device, update_signal
from .packages.led.services import async_enable_led_auto_mode
from .runtime import ChihirosClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform for Chihiros LED Control."""
    chihiros_data: ChihirosData = hass.data[DOMAIN][entry.entry_id]
    if chihiros_data.dosing_totals:
        await async_add_doser_switches(hass, entry, async_add_entities, chihiros_data)
        return
    if not chihiros_data.device.colors:
        return
    async_add_entities(
        [
            ChihirosAutoManualSwitch(
                chihiros_data.coordinator,
                chihiros_data.device,
            )
        ]
    )


class ChihirosAutoManualSwitch(
    PassiveBluetoothCoordinatorEntity[ChihirosDataUpdateCoordinator],
    SwitchEntity,
):
    """Switch to toggle between auto and manual mode."""

    def __init__(
        self,
        coordinator: ChihirosDataUpdateCoordinator,
        device: ChihirosClient,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = chihiros_entity_name(device, "Auto Mode")
        self._attr_unique_id = chihiros_unique_id(coordinator.address, "auto_mode")
        self._attr_device_info = chihiros_device_info(device, coordinator.address)

    @property
    def available(self) -> bool:
        """Return whether the switch is available."""
        if self.coordinator.always_available:
            return True
        return super().available

    @property
    def is_on(self) -> bool:
        """Return True if the switch is in auto mode."""
        return self.coordinator.auto_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Auto mode: set brightness to auto level and enable auto mode."""
        await async_enable_led_auto_mode(self.coordinator.hass, self.coordinator, self._device)
        self.async_write_ha_state()
        _LOGGER.debug("Switched to auto mode for %s", self._device.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Manual mode: set brightness to last known or default value."""
        await self._device.set_manual_mode()
        self.coordinator.async_set_auto_mode(False)
        self.async_write_ha_state()
        _LOGGER.debug("Switched to manual mode for %s", self._device.name)


async def async_add_doser_switches(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    chihiros_data: ChihirosData,
) -> None:
    """Add extension switches for a dosing pump."""
    if not chihiros_data.dosing_totals:
        return
    store = await async_store_for_device(hass, chihiros_data.device.address, chihiros_data.dosing_totals.pump_count)
    entities: list[SwitchEntity] = [DoserExtLowContainerNotificationSwitch(chihiros_data, store)]
    entities.extend(
        DoserExtScheduleActiveSwitch(chihiros_data, store, pump_idx)
        for pump_idx in range(chihiros_data.dosing_totals.pump_count)
    )
    async_add_entities(entities)


class DoserExtLowContainerNotificationSwitch(SwitchEntity):
    """Device-level switch for low container notifications."""

    _attr_should_poll = False
    _attr_icon = "mdi:bell-alert-outline"
    _attr_name = "Low container notification"

    def __init__(self, chihiros_data: ChihirosData, store) -> None:
        self._device = chihiros_data.device
        self._store = store
        self._attr_unique_id = chihiros_unique_id(self._device.address, "doser_ext_low_container_notification")
        self._attr_device_info = chihiros_device_info(self._device, self._device.address)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, update_signal(self._device.address), self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        return self._store.low_container_notification_enabled()

    async def async_turn_on(self, **kwargs) -> None:
        await self._store.async_set_low_container_notification_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._store.async_set_low_container_notification_enabled(False)


class DoserExtScheduleActiveSwitch(DoserExtEntity, SwitchEntity):
    """Schedule active switch."""

    _attr_should_poll = False

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Schedule active")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, update_signal(self._device.address), self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        schedule = self._store.schedule(self._pump_idx)
        return bool(schedule.active) if schedule else False

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set_schedule_active(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_schedule_active(False)

    async def _async_set_schedule_active(self, active: bool) -> None:
        schedule = self._store.schedule(self._pump_idx)
        if schedule is None:
            return
        data = {
            "address": self._device.address,
            "pump": self._pump_idx + 1,
            "active": active,
            "kind": schedule.kind,
            "ml": schedule.ml,
            "weekdays": list(schedule.weekdays),
            "send": True,
        }
        if schedule.kind == "interval":
            data["interval"] = int(
                schedule.interval_minutes if schedule.interval_minutes is not None else schedule.time.split(":", 1)[1]
            )
        else:
            data["time"] = schedule.time
        await self.hass.services.async_call(DOMAIN, "set_doser_schedule", data, blocking=True)
