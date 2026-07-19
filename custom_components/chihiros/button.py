"""Dosing pump button controls."""

# ruff: noqa: D102,D107

from __future__ import annotations

from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import chihiros_device_info, chihiros_entity_name, chihiros_unique_id
from .models import ChihirosData
from .packages.doser.entity import DoserExtEntity
from .packages.doser.services import async_trigger_dose_ml
from .packages.doser.storage import async_store_for_device
from .runtime import ChihirosClient, DosingChihirosClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dosing pump buttons."""
    chihiros_data: ChihirosData = hass.data[DOMAIN][entry.entry_id]
    if not chihiros_data.dosing_totals:
        return
    await async_add_doser_buttons(hass, entry, async_add_entities, chihiros_data)

    async_add_entities(
        ChihirosDosingButton(chihiros_data.device, chihiros_data, pump_idx)
        for pump_idx in range(chihiros_data.dosing_totals.pump_count)
    )


class ChihirosDosingButton(ButtonEntity):
    """Button entity for a one-shot manual dose."""

    _attr_should_poll = False

    def __init__(self, device: ChihirosClient, chihiros_data: ChihirosData, pump_idx: int) -> None:
        """Initialize the dosing button."""
        self._device = device
        self._chihiros_data = chihiros_data
        self._pump_idx = pump_idx
        pump_number = pump_idx + 1
        self._attr_name = chihiros_entity_name(device, f"Dose pump {pump_number}")
        self._attr_unique_id = chihiros_unique_id(device.address, f"dosing_pump_{pump_number}_dose")
        self._attr_device_info = chihiros_device_info(device, device.address)

    async def async_press(self) -> None:
        """Trigger a manual dose using this pump's configured volume."""
        ml = self._chihiros_data.dosing_volumes[self._pump_idx]
        await async_trigger_dose_ml(self._chihiros_data, self._pump_idx, ml)
        store = await async_store_for_device(
            self.hass,
            self._device.address,
            self._chihiros_data.dosing_totals.pump_count if self._chihiros_data.dosing_totals else 4,
        )
        await store.async_record_manual_dose_ml(self._pump_idx, ml)


async def async_add_doser_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    chihiros_data: ChihirosData,
) -> None:
    """Add extension buttons for a dosing pump."""
    if not chihiros_data.dosing_totals:
        return
    store = await async_store_for_device(hass, chihiros_data.device.address, chihiros_data.dosing_totals.pump_count)
    entities = [DoserExtReadDailyButton(chihiros_data, store, 0)]
    for pump_idx in range(chihiros_data.dosing_totals.pump_count):
        entities.extend(
            [
                DoserExtResetScheduleButton(chihiros_data, store, pump_idx),
                DoserExtCalibrationStartButton(chihiros_data, store, pump_idx),
            ]
        )
    async_add_entities(entities)


class DoserExtReadDailyButton(DoserExtEntity, ButtonEntity):
    """Button to request fresh status/daily values."""

    _attr_should_poll = False

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Read daily values")
        self._attr_name = "Tageswerte lesen"
        self._attr_unique_id = f"{self._device.address}_doser_ext_read_daily_values"
        self._attr_device_info = chihiros_device_info(self._device, self._device.address)

    async def async_press(self) -> None:
        dosing_device = cast(DosingChihirosClient, self._device)
        values = await dosing_device.read_auto_totals(mode=0x1E)
        if values is None:
            values = await dosing_device.read_auto_totals_via_dialog(mode=0x1E)
        await self._store.async_set_auto_daily_values(values, mode=0x1E)


class DoserExtResetScheduleButton(DoserExtEntity, ButtonEntity):
    """Button to reset one local schedule row."""

    _attr_should_poll = False

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Reset schedule")

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            DOMAIN,
            "reset_doser_schedule",
            {"address": self._device.address, "pump": self._pump_idx + 1},
            blocking=True,
        )


class DoserExtCalibrationStartButton(DoserExtEntity, ButtonEntity):
    """Button to start calibration for one channel."""

    _attr_should_poll = False

    def __init__(self, chihiros_data: ChihirosData, store, pump_idx: int) -> None:
        super().__init__(chihiros_data, store, pump_idx, "Start calibration")
        self._attr_name = "Kalibrieren"

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            DOMAIN,
            "start_doser_calibration",
            {"address": self._device.address, "pump": self._pump_idx + 1},
            blocking=True,
        )
