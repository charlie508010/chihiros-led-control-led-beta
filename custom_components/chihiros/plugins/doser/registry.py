"""Registry helpers for optional Doser plugin entities."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN, MANUFACTURER
from ...models import ChihirosData
from .entity import channel_name

_LOGGER = logging.getLogger(__name__)


async def async_migrate_doser_ext_entity_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    chihiros_data: ChihirosData,
) -> None:
    """Create per-channel devices and attach extension entities to them."""
    if not chihiros_data.dosing_totals:
        return

    address = chihiros_data.device.address.upper()
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    parent = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, address)},
        manufacturer=MANUFACTURER,
        model=chihiros_data.device.model_name,
        name=chihiros_data.device.name,
    )

    read_unique_id = f"{address}_doser_ext_read_daily_values"
    for entity_entry in tuple(entity_registry.entities.values()):
        if entity_entry.platform != DOMAIN:
            continue
        unique_id = str(entity_entry.unique_id)
        if unique_id == read_unique_id:
            if entity_entry.device_id != parent.id:
                entity_registry.async_update_entity(entity_entry.entity_id, device_id=parent.id)

    for pump_idx in range(chihiros_data.dosing_totals.pump_count):
        pump_number = pump_idx + 1
        channel_device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{address}_CH{pump_number}")},
            manufacturer=MANUFACTURER,
            model="Dosing Pump Channel",
            name=channel_name(pump_idx),
            via_device=(DOMAIN, address),
        )
        _LOGGER.debug(
            "Ensured Doser channel device %s via parent %s for %s",
            channel_device.id,
            parent.id,
            address,
        )
        needle = f"{address}_doser_ext_ch{pump_number}_"
        for entity_entry in tuple(entity_registry.entities.values()):
            if entity_entry.platform != DOMAIN:
                continue
            if not str(entity_entry.unique_id).startswith(needle):
                continue
            if entity_entry.device_id == channel_device.id:
                continue
            entity_registry.async_update_entity(entity_entry.entity_id, device_id=channel_device.id)
