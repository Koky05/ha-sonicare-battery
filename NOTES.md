# Sonicare Battery HA Integration - Development Notes

## Current Status (2026-02-05)

Integration rolled back to basic functionality with 3 sensors:
- Battery (with state restoration)
- Last Seen (with state restoration)
- Signal Strength/RSSI (disabled by default, with state restoration)

## Devices

| Name | MAC Address | Model |
|------|-------------|-------|
| Max | 24:E5:AA:7A:52:A7 | Sonicare4Kids |
| Ema | 24:E5:AA:80:37:CA | Sonicare4Kids |

## Key Observations

### BLE Connection Behavior

1. **Sonicare Kids toothbrushes have inconsistent BLE behavior:**
   - Max: Previously connected successfully when just "on" (display showing, not brushing)
   - Ema: Only accepts connections during active brushing (motor running)
   - This may be due to firmware differences between the two devices

2. **Connection failures poison habluetooth failure counter:**
   - Failed connection attempts increment a failure counter in habluetooth
   - High failure count can block subsequent detection callbacks
   - This prevents the integration from receiving notifications when device is detected

3. **Toothbrush auto-off:**
   - Display turns off automatically after a short timeout when not brushing
   - BLE advertising stops when display is off
   - Device must be actively on (or brushing) to be detected

### What Works

- Device detection via Bluetooth advertisements
- Battery reading during active brushing sessions
- State restoration after HA restart (sensors keep last known values)
- RSSI and Last Seen timestamps update on detection

### What Doesn't Work Reliably

- Reading battery when toothbrush is just "on" but not brushing (device-dependent)
- Reading proprietary characteristics (Handle State, Brushing Time, Mode, Intensity) - removed in rollback
- Connection attempts when not actively brushing cause timeouts

## Configuration

### const.py Settings
```python
CONNECTION_TIMEOUT = 30.0  # seconds
MAX_RETRIES = 3
MIN_READ_INTERVAL = 30  # seconds between reads
```

### Debug Logging
Enable in configuration.yaml:
```yaml
logger:
  logs:
    custom_components.sonicare_battery: debug
```

## Files Modified

| File | Changes |
|------|---------|
| sensor.py | Simplified to 3 sensors, added RestoreEntity mixin |
| coordinator.py | Reverted retry logic, uses single connection attempt |
| const.py | Reverted to original timeout values |
| __init__.py | Fixed uppercase address in BluetoothCallbackMatcher |
| config_flow.py | Fixed uppercase address storage |

## Removed Features (in rollback)

- Handle State sensor
- Brushing Time sensor
- Brushing Mode sensor
- Intensity sensor
- Multi-attempt retry logic

## Future Considerations

1. **Passive monitoring only:** Consider removing BLE connection attempts entirely and just tracking device presence via advertisements (RSSI, Last Seen)

2. **Charger detection:** Investigate if devices behave differently when on charger vs handheld

3. **Firmware investigation:** Different Sonicare Kids may have different firmware with different BLE behavior

4. **Alternative approach:** Use advertisement data if available (some BLE devices include battery in advertisement without requiring connection)

## SSH Access

- Host: 192.168.2.239
- User: root
- Password: Tknib9184#0912
