"""Sonicare Battery integration for Home Assistant.

A simple integration to read battery level from Philips Sonicare toothbrushes
via Bluetooth LE using the standard Battery Service (0x180F).

This integration is event-driven - it only reads battery when the toothbrush
is detected via Bluetooth (typically during brushing sessions).
"""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SonicareBatteryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonicare Battery from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    # Get the BLE device if currently available (may be None if device is off)
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )

    # Note: We don't raise ConfigEntryNotReady if device not found
    # because Sonicare only broadcasts during brushing sessions
    if not ble_device:
        _LOGGER.info(
            "Sonicare device %s not currently available. "
            "Battery will be read when toothbrush is detected.",
            address,
        )

    # Create coordinator (event-driven, no polling)
    coordinator = SonicareBatteryCoordinator(
        hass=hass,
        ble_device=ble_device,
        address=address,
    )

    # Initial refresh (will just return empty cached data)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register callback for bluetooth detection
    # This is the key - we get notified when the device starts advertising
    # Note: Address must be uppercase for reliable matching
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            coordinator.async_handle_bluetooth_event,
            bluetooth.BluetoothCallbackMatcher(address=address.upper()),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    _LOGGER.info(
        "Sonicare Battery integration set up for %s. "
        "Waiting for device to be detected...",
        address,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Shutdown coordinator first to cancel pending tasks
    coordinator: SonicareBatteryCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_shutdown()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
