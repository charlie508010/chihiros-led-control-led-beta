"""Shared classification helpers for Chihiros config entries."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

ENTRY_DEVICE_KIND = "device_kind"
DEVICE_KIND_DOSER = "doser"


def is_doser_entry(entry: ConfigEntry) -> bool:
    """Return whether a config entry represents a Doser."""
    return entry.data.get(ENTRY_DEVICE_KIND) == DEVICE_KIND_DOSER
