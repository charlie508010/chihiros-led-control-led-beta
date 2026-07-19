"""Dosing pump number controls."""

# ruff: noqa: D102,D107,E501

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from ...const import DOMAIN
from ...entity import chihiros_device_info, chihiros_entity_name, chihiros_unique_id
from ...models import ChihirosData
from ...runtime import ChihirosClient
from .entity import DoserExtEntity
from .storage import async_store_for_device, update_signal
from .types import DoserSchedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dosing pump volume controls."""
    chihiros_data: ChihirosData = hass.data[DOMAIN][entry.entry_id]
    if not chihiros_data.dosing_totals:
        return
    await async_add_doser_numbers(hass, entry, async_add_entities, chihiros_data)

    async_add_entities(
        ChihirosDosingVolumeNumber(chihiros_data.device, chihiros_data, pump_idx)
        for pump_idx in range(chihiros_data.dosing_totals.pump_count)
    )


class ChihirosDosingVolumeNumber(NumberEntity, RestoreEntity):
    """Number entity for a pump's manual dose volume."""

    _attr_should_poll = False
    _attr_native_min_value = 0.2
    _attr_native_max_value = 999.9
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_mode = NumberMode.BOX

    def __init__(self, device: ChihirosClient, chihiros_data: ChihirosData, pump_idx: int) -> None:
        """Initialize the dose volume number."""
        self._device = device
        self._chihiros_data = chihiros_data
        self._pump_idx = pump_idx
        pump_number = pump_idx + 1
        self._attr_name = chihiros_entity_name(device, f"Pump {pump_number} dose volume")
        self._attr_unique_id = chihiros_unique_id(device.address, f"dosing_pump_{pump_number}_dose_volume")
        self._attr_device_info = chihiros_device_info(device, device.address)
        self._attr_native_value = chihiros_data.dosing_volumes[pump_idx]

    async def async_added_to_hass(self) -> None:
        """Restore the last configured manual dose volume."""
        if last_state := await self.async_get_last_state():
            try:
                value = round(float(last_state.state), 1)
            except ValueError:
                return
            if self.native_min_value <= value <= self.native_max_value:
                self._set_value(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the dose volume for this pump."""
        self._set_value(round(value, 1))
        self.async_write_ha_state()

    def _set_value(self, value: float) -> None:
        """Update local runtime state for this pump volume."""
        self._chihiros_data.dosing_volumes[self._pump_idx] = value
        self._attr_native_value = value


async def async_add_doser_numbers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    chihiros_data: ChihirosData,
) -> None:
    """Add extension number controls for a dosing pump."""
    if not chihiros_data.dosing_totals:
        return
    store = await async_store_for_device(hass, chihiros_data.device.address, chihiros_data.dosing_totals.pump_count)
    entities = []
    for pump_idx in range(chihiros_data.dosing_totals.pump_count):
        entities.extend(
            [
                DoserExtRemainingNumber(chihiros_data, store, pump_idx),
                DoserExtScheduleAmountNumber(chihiros_data, store, pump_idx),
            ]
        )
    async_add_entities(entities)


class _DoserExtNumber(DoserExtEntity, NumberEntity):
    _attr_should_poll = False
    _attr_native_min_value = 0.0
    _attr_native_max_value = 999.9
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_mode = NumberMode.BOX

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, update_signal(self._device.address), self.async_write_ha_state)
        )


class DoserExtRemainingNumber(_DoserExtNumber):
    """Editable local remaining container volume."""

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Remaining volume")

    @property
    def native_value(self) -> float:
        return self._store.container_ml(self._pump_idx)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_container_ml(self._pump_idx, value)


class DoserExtScheduleAmountNumber(_DoserExtNumber):
    """Editable local schedule dose amount."""

    _attr_native_min_value = 0.2

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Schedule amount")

    @property
    def native_value(self) -> float:
        schedule = self._store.schedule(self._pump_idx)
        return schedule.ml if schedule else 0.2

    async def async_set_native_value(self, value: float) -> None:
        schedule = self._store.schedule(self._pump_idx) or DoserSchedule(
            pump_idx=self._pump_idx,
            active=True,
            time="00:00",
            ml=round(float(value), 1),
        )
        schedule.ml = round(float(value), 1)
        await self._store.async_set_schedule(schedule)
