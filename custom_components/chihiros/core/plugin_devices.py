"""Home Assistant device bridge for externally installed device plugins."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, MANUFACTURER

_DOSER_NAME_PREFIXES = ("DYDOSE", "DYMIX")


def _is_doser_service_info(service_info: bluetooth.BluetoothServiceInfoBleak) -> bool:
    """Return whether Bluetooth metadata belongs to a Chihiros Doser."""
    name = str(service_info.name or service_info.device.name or "").upper()
    return name.startswith(_DOSER_NAME_PREFIXES)


class ChihirosPluginDeviceSensor(SensorEntity):
    """Expose one plugin-owned Bluetooth device without attaching it to an LED."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_native_value = "discovered"

    def __init__(self, service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Initialize the diagnostic device entity."""
        address = str(service_info.address).upper()
        name = str(service_info.name or service_info.device.name or address)
        self._attr_unique_id = f"doser_{address.replace(':', '').lower()}_status"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"doser:{address}")},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            manufacturer=MANUFACTURER,
            model="Dosing Pump",
            name=name,
        )


async def async_setup_doser_plugin_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register discovered Doser devices below the shared LED Core integration."""
    known_addresses: set[str] = set()

    @callback
    def async_add_service_info(service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        if not _is_doser_service_info(service_info):
            return
        address = str(service_info.address).upper()
        if not address or address in known_addresses:
            return
        known_addresses.add(address)
        async_add_entities([ChihirosPluginDeviceSensor(service_info)])

    for service_info in bluetooth.async_discovered_service_info(hass):
        async_add_service_info(service_info)

    for prefix in _DOSER_NAME_PREFIXES:
        entry.async_on_unload(
            bluetooth.async_register_callback(
                hass,
                lambda service_info, _change: async_add_service_info(service_info),
                {"local_name": f"{prefix}*"},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )
