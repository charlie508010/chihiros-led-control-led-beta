"""Config flow for separately registered Chihiros Doser devices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN

DOSER_NAME_PREFIX = "DYDOSE"


def _is_doser_name(name: str | None) -> bool:
    """Return whether a Bluetooth name belongs to a Doser."""
    return str(name or "").upper().startswith(DOSER_NAME_PREFIX)


class ChihirosDoserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one independent config entry per Doser device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize discovery state."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        if not _is_doser_name(discovery_info.name):
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm a discovered Doser."""
        assert self._discovery_info is not None
        discovery = self._discovery_info
        title = discovery.name or f"Chihiros Doser {discovery.address}"
        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={CONF_ADDRESS: discovery.address, CONF_NAME: title},
            )
        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": title}
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": title},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user select a currently discovered Doser."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            title = discovery.name or f"Chihiros Doser {address}"
            return self.async_create_entry(
                title=title,
                data={CONF_ADDRESS: address, CONF_NAME: title},
            )

        current_ids = self._async_current_ids()
        self._discovered_devices = {
            discovery.address: discovery
            for discovery in async_discovered_service_info(self.hass)
            if discovery.address not in current_ids and _is_doser_name(discovery.name)
        }
        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        choices = {
            address: discovery.name or address for address, discovery in sorted(self._discovered_devices.items())
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )
