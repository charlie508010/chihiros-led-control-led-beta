"""LED plugin entrypoint used by the Chihiros Core loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_setup_plugin(hass: HomeAssistant, manifest: object) -> bool:
    """Register the LED plugin metadata while compatibility services remain active."""
    del hass, manifest
    return True
