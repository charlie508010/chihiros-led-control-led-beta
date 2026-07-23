"""Diagnostic entity that gives each Doser its own Home Assistant device."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add one diagnostic entity for one independently configured Doser."""
    async_add_entities([ChihirosDoserStatusSensor(entry)])


class ChihirosDoserStatusSensor(SensorEntity):
    """Represent one discovered Doser without attaching it to an LED."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_native_value = "discovered"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Doser status sensor."""
        address = str(entry.data[CONF_ADDRESS]).upper()
        name = str(entry.data.get(CONF_NAME) or entry.title)
        self._attr_unique_id = f"{address}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=name,
        )
