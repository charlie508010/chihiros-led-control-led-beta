"""Service registration for future Chihiros stirrer support."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


def async_update_stirrer_services(hass: HomeAssistant, enabled: bool) -> None:
    """Register or remove stirrer services.

    The package is intentionally present now so device activation can grow without
    changing the integration layout again when stirrer services are added.
    """
    _ = (hass, enabled)


__all__ = ["async_update_stirrer_services"]
