"""Sensor platform for Sonicare Battery integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SonicareBatteryCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonicare Battery sensors."""
    coordinator: SonicareBatteryCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        SonicareBatterySensor(coordinator, entry),
        SonicareLastSeenSensor(coordinator, entry),
        SonicareRssiSensor(coordinator, entry),
    ])


class SonicareBatterySensor(CoordinatorEntity[SonicareBatteryCoordinator], RestoreEntity, SensorEntity):
    """Sonicare battery level sensor with state restoration."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = "Battery"

    def __init__(
        self,
        coordinator: SonicareBatteryCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._address = entry.data[CONF_ADDRESS]
        self._name = entry.data.get(CONF_NAME, self._address)
        self._restored_value: int | None = None

        self._attr_unique_id = f"{self._address}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self._name,
            manufacturer="Philips",
            model="Sonicare Kids",
        )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._restored_value = int(last_state.state)
                    # Also update coordinator cache so other logic can use it
                    self.coordinator._cached_data["battery_level"] = self._restored_value
                    _LOGGER.debug("Restored battery level: %s%%", self._restored_value)
                except (ValueError, TypeError):
                    pass

    @property
    def native_value(self) -> int | None:
        """Return the battery level (last known value)."""
        if self.coordinator.data and self.coordinator.data.get("battery_level") is not None:
            return self.coordinator.data.get("battery_level")
        return self._restored_value

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Always available once we have a reading - shows last known value
        since device is only visible during brushing sessions.
        """
        return True


class SonicareLastSeenSensor(CoordinatorEntity[SonicareBatteryCoordinator], RestoreEntity, SensorEntity):
    """Sonicare last seen timestamp sensor with state restoration."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_name = "Last Seen"

    def __init__(
        self,
        coordinator: SonicareBatteryCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._address = entry.data[CONF_ADDRESS]
        self._name = entry.data.get(CONF_NAME, self._address)
        self._restored_value: datetime | None = None

        self._attr_unique_id = f"{self._address}_last_seen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self._name,
            manufacturer="Philips",
            model="Sonicare Kids",
        )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._restored_value = datetime.fromisoformat(last_state.state)
                    _LOGGER.debug("Restored last seen: %s", self._restored_value)
                except (ValueError, TypeError):
                    pass

    @property
    def native_value(self) -> datetime | None:
        """Return when device was last seen."""
        if self.coordinator.last_seen is not None:
            return self.coordinator.last_seen
        return self._restored_value

    @property
    def available(self) -> bool:
        """Return if entity is available (always true, shows last known value)."""
        return True


class SonicareRssiSensor(CoordinatorEntity[SonicareBatteryCoordinator], RestoreEntity, SensorEntity):
    """Sonicare RSSI (signal strength) sensor with state restoration."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = "Signal Strength"
    _attr_entity_registry_enabled_default = False  # Disabled by default

    def __init__(
        self,
        coordinator: SonicareBatteryCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._address = entry.data[CONF_ADDRESS]
        self._name = entry.data.get(CONF_NAME, self._address)
        self._restored_value: int | None = None

        self._attr_unique_id = f"{self._address}_rssi"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self._name,
            manufacturer="Philips",
            model="Sonicare Kids",
        )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (None, "unknown", "unavailable"):
                try:
                    self._restored_value = int(last_state.state)
                    self.coordinator._cached_data["rssi"] = self._restored_value
                    _LOGGER.debug("Restored RSSI: %s dBm", self._restored_value)
                except (ValueError, TypeError):
                    pass

    @property
    def native_value(self) -> int | None:
        """Return the RSSI value."""
        if self.coordinator.data and self.coordinator.data.get("rssi") is not None:
            return self.coordinator.data.get("rssi")
        return self._restored_value

    @property
    def available(self) -> bool:
        """Return if entity is available (always true, shows last known value)."""
        return True
