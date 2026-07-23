"""Forward button entities to externally installed Chihiros plugins."""

from __future__ import annotations

from .core.plugin_loader.platforms import async_setup_plugin_platform_entries


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up button entities declared by the matching external plugin."""
    await async_setup_plugin_platform_entries(hass, entry, async_add_entities, "button")


__all__ = ["async_setup_entry"]
