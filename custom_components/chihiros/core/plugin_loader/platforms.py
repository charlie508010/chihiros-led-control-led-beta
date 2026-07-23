"""Forward Home Assistant platform setup calls to loaded Chihiros plugins."""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

from .loader import async_load_plugins

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)
_DOMAIN = "chihiros_led_core"
_PACKAGED_CORE_PLUGIN_IDS = frozenset({"led"})
_SEPARATE_INTEGRATION_PLUGIN_IDS = frozenset({"doser"})


async def async_setup_plugin_platform_entries(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
) -> None:
    """Let every loaded plugin add entities for one Home Assistant platform."""
    registry = await async_load_plugins(hass, _DOMAIN)
    setup_name = f"async_setup_{platform}_entry"
    for loaded in registry.all():
        if loaded.manifest.plugin_id in _PACKAGED_CORE_PLUGIN_IDS:
            continue
        if loaded.manifest.plugin_id in _SEPARATE_INTEGRATION_PLUGIN_IDS:
            _LOGGER.debug(
                "Skipping separate Home Assistant integration plugin %s for LED entry %s",
                loaded.manifest.plugin_id,
                entry.entry_id,
            )
            continue
        if platform not in loaded.manifest.platforms:
            continue
        setup = getattr(loaded.module, setup_name, None)
        if not callable(setup):
            _LOGGER.warning(
                "Chihiros plugin %s declares platform %s but has no %s",
                loaded.manifest.plugin_id,
                platform,
                setup_name,
            )
            continue
        try:
            result: Any = setup(hass, entry, async_add_entities)
            if inspect.isawaitable(result):
                await result
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Chihiros plugin %s failed to set up platform %s",
                loaded.manifest.plugin_id,
                platform,
            )
