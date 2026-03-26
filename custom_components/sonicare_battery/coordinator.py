"""Data coordinator for Sonicare Battery integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    BATTERY_LEVEL_CHAR_UUID,
    HANDLE_STATE_CHAR_UUID,
    BRUSHING_TIME_CHAR_UUID,
    BRUSHING_MODE_CHAR_UUID,
    INTENSITY_CHAR_UUID,
    HandleState,
    BrushingMode,
    Intensity,
    CONNECTION_TIMEOUT,
    MAX_RETRIES,
)

_LOGGER = logging.getLogger(__name__)

# Minimum time between BLE reads (avoid spamming during brushing session)
MIN_READ_INTERVAL = timedelta(seconds=30)

# Maximum pending read tasks (prevent task accumulation)
MAX_PENDING_TASKS = 1


class SonicareBLEReader:
    """Handles BLE communication with Sonicare device.

    Separated from coordinator for better modularity and testability.
    """

    def __init__(self, address: str) -> None:
        """Initialize the BLE reader."""
        self._address = address

    async def read_characteristic(
        self,
        client: BleakClient,
        uuid: str,
        timeout: float = 5.0,
    ) -> bytes | None:
        """Read a single characteristic with timeout and error handling."""
        try:
            data = await asyncio.wait_for(
                client.read_gatt_char(uuid),
                timeout=timeout,
            )
            return data if data else None
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout reading %s from %s", uuid[-4:], self._address)
            return None
        except BleakError as err:
            _LOGGER.debug("BLE error reading %s: %s", uuid[-4:], err)
            return None
        except Exception as err:
            _LOGGER.debug("Error reading %s: %s", uuid[-4:], err)
            return None

    async def read_all_characteristics(
        self,
        client: BleakClient,
    ) -> dict[str, Any]:
        """Read all Sonicare characteristics from connected client."""
        result: dict[str, Any] = {}

        # Read battery level first (standard BLE Battery Service) - most important
        battery_data = await self.read_characteristic(
            client, BATTERY_LEVEL_CHAR_UUID, timeout=10.0
        )
        if battery_data and len(battery_data) >= 1:
            battery_level = int(battery_data[0])
            if 0 <= battery_level <= 100:
                result["battery_level"] = battery_level
                _LOGGER.debug("Battery: %d%%", battery_level)

        # Try to read Sonicare proprietary characteristics (may not be available on all models)
        # Read handle state
        state_data = await self.read_characteristic(client, HANDLE_STATE_CHAR_UUID, timeout=3.0)
        if state_data and len(state_data) >= 1:
            state_value = int(state_data[0])
            result["handle_state"] = state_value
            result["handle_state_name"] = HandleState.get_name(state_value)
            _LOGGER.debug("Handle state: %s", result["handle_state_name"])

        # Read brushing time - INT16
        time_data = await self.read_characteristic(client, BRUSHING_TIME_CHAR_UUID, timeout=3.0)
        if time_data and len(time_data) >= 2:
            result["brushing_time"] = int.from_bytes(time_data[:2], byteorder="little")
            _LOGGER.debug("Brushing time: %ds", result["brushing_time"])

        # Read brushing mode
        mode_data = await self.read_characteristic(client, BRUSHING_MODE_CHAR_UUID, timeout=3.0)
        if mode_data and len(mode_data) >= 1:
            mode_value = int(mode_data[0])
            result["brushing_mode"] = mode_value
            result["brushing_mode_name"] = BrushingMode.get_name(mode_value)
            _LOGGER.debug("Brushing mode: %s", result["brushing_mode_name"])

        # Read intensity
        intensity_data = await self.read_characteristic(client, INTENSITY_CHAR_UUID, timeout=3.0)
        if intensity_data and len(intensity_data) >= 1:
            intensity_value = int(intensity_data[0])
            result["intensity"] = intensity_value
            result["intensity_name"] = Intensity.get_name(intensity_value)
            _LOGGER.debug("Intensity: %s", result["intensity_name"])

        return result


class SonicareBatteryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Sonicare battery level updates.

    This coordinator is event-driven - it reads data only when the device
    is detected via Bluetooth advertisement.

    Resource management:
    - Uses asyncio.Lock to prevent concurrent BLE connections
    - Tracks pending tasks for proper cleanup on unload
    - Enforces minimum interval between reads
    - Limits pending task count to prevent accumulation

    Logging:
    - Uses DEBUG level for detailed troubleshooting
    - Enable via configuration.yaml:
        logger:
          logs:
            custom_components.sonicare_battery: debug
    """

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: bluetooth.BLEDevice | None,
        address: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Sonicare {address}",
            update_interval=None,  # Event-driven, no polling
        )
        self._ble_device = ble_device
        self._address = address
        self._ble_reader = SonicareBLEReader(address)

        # State tracking
        self._last_rssi: int | None = None
        self._last_seen: datetime | None = None
        self._last_read: datetime | None = None

        # Resource management
        self._read_lock = asyncio.Lock()
        self._pending_task: asyncio.Task | None = None
        self._shutdown = False

        # Cached data (reused to avoid memory allocation)
        self._cached_data: dict[str, Any] = {
            "battery_level": None,
            "rssi": None,
            "last_seen": None,
            "available": False,
            "handle_state": None,
            "handle_state_name": None,
            "brushing_time": None,
            "brushing_mode": None,
            "brushing_mode_name": None,
            "intensity": None,
            "intensity_name": None,
        }

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and cancel pending tasks."""
        self._shutdown = True

        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
            try:
                await self._pending_task
            except asyncio.CancelledError:
                pass

        _LOGGER.debug("Coordinator shutdown for %s", self._address)

    @callback
    def async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle bluetooth event - device detected, trigger data read."""
        if self._shutdown:
            return

        self._ble_device = service_info.device
        self._last_rssi = service_info.rssi
        self._last_seen = dt_util.utcnow()

        # Update cached data with availability (cheap operation)
        self._cached_data["rssi"] = self._last_rssi
        self._cached_data["last_seen"] = self._last_seen.isoformat()
        self._cached_data["available"] = True

        # Check if we should read (avoid too frequent reads)
        now = dt_util.utcnow()
        if self._last_read and (now - self._last_read) < MIN_READ_INTERVAL:
            _LOGGER.debug(
                "Skipping read - last read was %s ago",
                now - self._last_read,
            )
            return

        # Check if a read is already in progress or pending
        if self._read_lock.locked():
            _LOGGER.debug("Read already in progress for %s", self._address)
            return

        if self._pending_task and not self._pending_task.done():
            _LOGGER.debug("Read task already pending for %s", self._address)
            return

        _LOGGER.debug(
            "Device %s detected (RSSI=%s), scheduling read",
            self._address,
            self._last_rssi,
        )

        # Create and track the task
        self._pending_task = self.hass.async_create_task(
            self._async_read_on_detection(),
            name=f"sonicare_read_{self._address}",
        )

    async def _async_read_on_detection(self) -> None:
        """Read data when device is detected."""
        if self._shutdown:
            return

        async with self._read_lock:
            try:
                # No delay - connect immediately while device is available
                if self._shutdown:
                    return

                data = await self._async_connect_and_read()
                if data:
                    self._cached_data.update(data)
                    self._last_read = dt_util.utcnow()
                    self.async_set_updated_data(self._cached_data)

                    _LOGGER.debug(
                        "Read complete: battery=%s%%, state=%s, time=%ss",
                        data.get("battery_level", "?"),
                        data.get("handle_state_name", "?"),
                        data.get("brushing_time", "?"),
                    )
            except asyncio.CancelledError:
                _LOGGER.debug("Read cancelled for %s", self._address)
                raise
            except Exception as err:
                _LOGGER.warning(
                    "Failed to read from %s: %s",
                    self._address,
                    err,
                )

    async def _async_connect_and_read(self) -> dict[str, Any] | None:
        """Connect to device and read all characteristics."""
        # Get fresh BLE device reference
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address.upper(), connectable=True
        )

        if ble_device:
            self._ble_device = ble_device

        if not self._ble_device:
            _LOGGER.debug("Device %s not available for connection", self._address)
            return None

        client: BleakClient | None = None
        try:
            _LOGGER.debug("Connecting to %s...", self._address)
            client = await asyncio.wait_for(
                establish_connection(
                    client_class=BleakClientWithServiceCache,
                    device=self._ble_device,
                    name=self._address,
                    disconnected_callback=self._on_disconnect,
                    max_attempts=MAX_RETRIES,
                    use_services_cache=True,
                ),
                timeout=CONNECTION_TIMEOUT,
            )
            _LOGGER.debug("Connected to %s, reading characteristics...", self._address)

            # Read all characteristics
            result = await self._ble_reader.read_all_characteristics(client)

            # Add metadata
            result["rssi"] = self._last_rssi
            result["last_seen"] = (
                self._last_seen.isoformat() if self._last_seen else None
            )
            result["available"] = True

            return result

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout connecting to %s", self._address)
            return None

        except asyncio.CancelledError:
            _LOGGER.debug("Connection cancelled for %s", self._address)
            raise

        except BleakError as err:
            _LOGGER.warning("BLE error for %s: %s", self._address, err)
            return None

        except Exception as err:
            _LOGGER.error("Unexpected error for %s: %s", self._address, err)
            return None

        finally:
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception as err:
                    _LOGGER.debug("Error disconnecting: %s", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Return cached data (no scheduled polling)."""
        return self._cached_data

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection."""
        _LOGGER.debug("Disconnected from %s", self._address)

    @property
    def last_seen(self) -> datetime | None:
        """Return when device was last seen."""
        return self._last_seen
