"""Fan platform for fan-equipped Chihiros LED devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import PassiveBluetoothCoordinatorEntity
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from ....const import DOMAIN
from ..coordinator import ATTR_FAN_RPM, ChihirosDataUpdateCoordinator
from ..models import ChihirosData
from ..runtime import ChihirosClient
from .base import chihiros_device_info, chihiros_entity_name, chihiros_unique_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a fan entity when the LED model has a fan."""
    chihiros_data: ChihirosData = hass.data[DOMAIN][entry.entry_id]
    if chihiros_data.device.model.has_fan:
        async_add_entities([ChihirosFanEntity(chihiros_data.coordinator, chihiros_data.device)])


class ChihirosFanEntity(
    PassiveBluetoothCoordinatorEntity[ChihirosDataUpdateCoordinator],
    FanEntity,
    RestoreEntity,
):
    """Representation of a Chihiros LED cooling fan."""

    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, coordinator: ChihirosDataUpdateCoordinator, device: ChihirosClient) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = chihiros_entity_name(device, "Fan")
        self._attr_unique_id = chihiros_unique_id(coordinator.address, "fan")
        self._attr_device_info = chihiros_device_info(device, coordinator.address)
        self._attr_percentage = 0

    async def async_added_to_hass(self) -> None:
        """Restore the last requested fan percentage."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._attr_percentage = last_state.attributes.get("percentage") or 0

    @property
    def available(self) -> bool:
        """Return whether the fan is available."""
        return True if self.coordinator.always_available else super().available

    @property
    def is_on(self) -> bool:
        """Return whether the fan is running."""
        return bool(self._attr_percentage)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose measured fan RPM from the latest notification."""
        fan_rpm = self.coordinator.data.get(ATTR_FAN_RPM)
        return None if fan_rpm is None else {ATTR_FAN_RPM: fan_rpm}

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        try:
            await self._device.set_fan_speed(percentage)
        except Exception as ex:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to set fan speed for {self.name}") from ex
        self._attr_available = True
        self._attr_percentage = percentage
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        del preset_mode, kwargs
        await self.async_set_percentage(percentage if percentage is not None else self._attr_percentage or 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        del kwargs
        await self.async_set_percentage(0)
