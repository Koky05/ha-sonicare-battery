# Sonicare Battery for Home Assistant

[![HACS Validation](https://github.com/Koky05/ha-sonicare-battery/actions/workflows/validate.yml/badge.svg)](https://github.com/Koky05/ha-sonicare-battery/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration to read battery level from Philips Sonicare toothbrushes via Bluetooth LE.

## Features

- Reads battery level using standard Bluetooth Battery Service (0x180F)
- **Last Seen** timestamp - when the toothbrush was last detected
- **Signal Strength** (RSSI) sensor (disabled by default)
- State restoration after Home Assistant restart
- Uses `bleak_retry_connector` for stable BLE connections
- Auto-discovery of Sonicare devices
- Event-driven - only reads when toothbrush is detected (no polling)
- Translations: English, Slovak

## Supported Devices

Tested with:
- Philips Sonicare Kids HX6352/11
- Philips Sonicare Kids HX6322/12

Should work with any Sonicare toothbrush that exposes the standard Battery Service.

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter (USB dongle or built-in)
- Toothbrush must be active (brushing) for Bluetooth to be detected

## Installation

### HACS Installation (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/Koky05/ha-sonicare-battery` as an Integration
5. Search for "Sonicare Battery" and install it
6. Restart Home Assistant
7. Go to Settings > Devices & Services > Add Integration
8. Search for "Sonicare Battery"
9. Select your toothbrush from the list

### Manual Installation

1. Copy the `custom_components/sonicare_battery` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration
4. Search for "Sonicare Battery"
5. Select your toothbrush from the list

## How It Works

Sonicare toothbrushes only broadcast Bluetooth LE advertisements during active brushing sessions (~2 minutes). This integration is **event-driven**:

1. Registers a Bluetooth callback for your toothbrush's MAC address
2. When the toothbrush starts brushing and is detected via BLE advertisement, it updates RSSI and Last Seen immediately
3. Connects to the toothbrush and reads the battery level
4. After brushing ends and the toothbrush turns off, sensors keep their last known values
5. Values are restored after Home Assistant restart

## Sensors

| Sensor | Description | Default |
|--------|-------------|---------|
| Battery | Battery level percentage | Enabled |
| Last Seen | Timestamp of last detection | Enabled |
| Signal Strength | RSSI in dBm | Disabled |

## Troubleshooting

### Device not found

- Sonicare toothbrush Bluetooth is only active **during brushing** (not on charger for Kids models)
- Brushing session is ~2 minutes - device must be detected during this window
- Check that your Bluetooth adapter is working
- Make sure you are close enough to the Bluetooth adapter

### Connection issues

- Failed connection attempts can increment habluetooth failure counter, which may block subsequent detections
- Try restarting Home Assistant to reset the failure counter
- Make sure no other device (phone app) is connected to the toothbrush

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.sonicare_battery: debug
```

## Technical Details

The integration uses:
- Standard Bluetooth Battery Service UUID: `0x180F`
- Battery Level Characteristic UUID: `0x2A19`
- Sonicare proprietary characteristics (base: `477ea600-a260-11e4-ae37-0002a5d5xxxx`):
  - Handle State: `...4010` (INT8)
  - Brushing Mode: `...4080` (INT8)
  - Brushing Time: `...4090` (INT16, seconds)
  - Intensity: `...40b0` (INT8)
- `bleak_retry_connector` for reliable connections
- Event-driven updates when toothbrush is detected

## Known Limitations

- Sonicare Kids toothbrushes have inconsistent BLE behavior between devices
- Some models only accept BLE connections during active brushing (motor running)
- Bluetooth proxy (ESP32) support is untested
- Proprietary characteristics (brushing mode, intensity, handle state) are read but not exposed as sensors yet due to reliability concerns

## Credits

- Inspired by [sonicare-ble-hacs](https://github.com/GrumpyMeow/sonicare-ble-hacs) by GrumpyMeow
- Uses [Bleak](https://github.com/hbldh/bleak) for Bluetooth LE
- Connection improvements informed by [v6ak's fork](https://github.com/v6ak/sonicare-ble-hacs) analysis
