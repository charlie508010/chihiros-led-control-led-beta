"""LED plugin entrypoint used by the Chihiros Core loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .entities import ENTITY_PLATFORMS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_setup_plugin(hass: HomeAssistant, manifest: object) -> bool:
    """Register the LED plugin's platform metadata with the shared Core."""
    domain_data = hass.data.setdefault("chihiros_led_core_plugins", {})
    domain_data["led"] = {
        "manifest": manifest,
        "platforms": ENTITY_PLATFORMS,
    }
    return True
