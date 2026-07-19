"""Shared entities for optional dosing-pump extensions."""

# ruff: noqa: D107

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo

from ...const import DOMAIN, MANUFACTURER
from ...entity import chihiros_unique_id
from ...models import ChihirosData
from .storage import DoserExtStore

CHANNEL_NAMES = ("Nitrat", "Phosphat", "Eisen", "Kalium")


def channel_name(pump_idx: int) -> str:
    """Return display channel name."""
    if 0 <= pump_idx < len(CHANNEL_NAMES):
        return f"CH{pump_idx + 1} {CHANNEL_NAMES[pump_idx]}"
    return f"CH{pump_idx + 1}"


class DoserExtEntity:
    """Mixin with common Chihiros dosing extension metadata."""

    _attr_should_poll = False

    def __init__(self, chihiros_data: ChihirosData, store: DoserExtStore, pump_idx: int, suffix: str) -> None:
        self._chihiros_data = chihiros_data
        self._device = chihiros_data.device
        self._store = store
        self._pump_idx = pump_idx
        key = suffix.lower().replace(" ", "_")
        self._attr_name = suffix
        self._attr_unique_id = chihiros_unique_id(self._device.address, f"doser_ext_ch{pump_idx + 1}_{key}")
        address = self._device.address.upper()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{address}_CH{pump_idx + 1}")},
            manufacturer=MANUFACTURER,
            model="Dosing Pump Channel",
            name=channel_name(pump_idx),
            via_device=(DOMAIN, address),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device metadata."""
        return self._attr_device_info
