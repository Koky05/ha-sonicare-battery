"""Constants for Sonicare Battery integration."""
from enum import IntEnum

DOMAIN = "sonicare_battery"

# Standard Bluetooth Battery Service UUIDs
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Sonicare proprietary service/characteristic UUIDs
# Base: 477ea600-a260-11e4-ae37-0002a5d5xxxx
SONICARE_UUID_BASE = "477ea600-a260-11e4-ae37-0002a5d5"

# Handle Service (0001) characteristics
HANDLE_STATE_CHAR_UUID = f"{SONICARE_UUID_BASE}4010"  # INT8 - device state

# State Service (0002) characteristics
BRUSHING_MODE_CHAR_UUID = f"{SONICARE_UUID_BASE}4080"  # INT8 - brushing mode
BRUSHING_TIME_CHAR_UUID = f"{SONICARE_UUID_BASE}4090"  # INT16 - active time in seconds
INTENSITY_CHAR_UUID = f"{SONICARE_UUID_BASE}40b0"  # INT8 - intensity level

# Session Service (0004) characteristics
LAST_SESSION_ID_CHAR_UUID = f"{SONICARE_UUID_BASE}40d0"  # INT16 - last session ID

# Brush Service (0006) characteristics
BRUSH_LIFETIME_CHAR_UUID = f"{SONICARE_UUID_BASE}4280"  # INT16 - lifetime hours
BRUSH_USAGE_CHAR_UUID = f"{SONICARE_UUID_BASE}4290"  # INT16 - usage hours


class HandleState(IntEnum):
    """Sonicare handle states."""

    OFF = 0
    STANDBY = 1
    RUN = 2  # Actively brushing
    CHARGE = 3
    SHUTDOWN = 4
    VALIDATE = 6
    UNKNOWN = 7

    @classmethod
    def get_name(cls, value: int) -> str:
        """Get human-readable name for state."""
        names = {
            0: "Off",
            1: "Standby",
            2: "Brushing",
            3: "Charging",
            4: "Shutdown",
            6: "Validate",
            7: "Unknown",
        }
        return names.get(value, f"Unknown ({value})")


class BrushingMode(IntEnum):
    """Sonicare brushing modes."""

    CLEAN = 0
    WHITE_PLUS = 1
    GUM_HEALTH = 2
    DEEP_CLEAN_PLUS = 3

    @classmethod
    def get_name(cls, value: int) -> str:
        """Get human-readable name for mode."""
        names = {
            0: "Clean",
            1: "White+",
            2: "Gum Health",
            3: "Deep Clean+",
        }
        return names.get(value, f"Unknown ({value})")


class Intensity(IntEnum):
    """Sonicare intensity levels."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @classmethod
    def get_name(cls, value: int) -> str:
        """Get human-readable name for intensity."""
        names = {
            0: "Low",
            1: "Medium",
            2: "High",
        }
        return names.get(value, f"Unknown ({value})")


# Update interval in seconds (battery doesn't change quickly)
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour

# Connection settings
CONNECTION_TIMEOUT = 30.0  # Original working value
MAX_RETRIES = 3  # Original working value
