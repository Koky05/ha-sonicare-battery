"""Config flow for Sonicare Battery integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SonicareBatteryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonicare Battery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, bluetooth.BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Get display name
        name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_device")

        if user_input is not None:
            name = user_input.get(CONF_NAME, self._discovery_info.name)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address.upper(),
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=self._discovery_info.name or self._discovery_info.address,
                    ): str,
                }
            ),
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address,
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            discovery_info = self._discovered_devices.get(user_input[CONF_ADDRESS])
            name = user_input.get(CONF_NAME)
            if not name and discovery_info:
                name = discovery_info.name or address

            return self.async_create_entry(
                title=name or address,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name or address,
                },
            )

        # Discover Sonicare devices
        self._discovered_devices = {}
        for discovery_info in bluetooth.async_discovered_service_info(self.hass):
            name = discovery_info.name or ""
            if "sonicare" in name.lower():
                self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Build selection list
        device_options = {
            address: f"{info.name or address} ({address})"
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(device_options),
                    vol.Optional(CONF_NAME): str,
                }
            ),
        )
