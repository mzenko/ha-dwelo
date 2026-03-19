DOMAIN = "dwelo"
API_BASE_URL = "https://api.dwelo.com"

DEFAULT_SCAN_INTERVAL = 30  # seconds

# Sensor type values returned by GET /v3/sensor/gateway/{gateway_id}/
# "light" is the confirmed value for a Z-Wave binary switch with load=light.
# The "switchBinary" / "switchMultilevel" names are kept as fallbacks in case
# other firmware versions use the Z-Wave command-class names directly.
SENSOR_TYPE_LIGHT = "light"
SENSOR_TYPE_SWITCH_BINARY = "switchBinary"
SENSOR_TYPE_SWITCH_MULTILEVEL = "switchMultilevel"

# sensorTypes whose presence indicates a binary (on/off) light.
BINARY_LIGHT_SENSOR_TYPES = frozenset({SENSOR_TYPE_LIGHT, SENSOR_TYPE_SWITCH_BINARY})

# Sensor types that indicate a device is NOT a light (e.g. thermostat readings).
# Devices whose sensor data contains any of these are excluded from the light platform.
NON_LIGHT_SENSOR_TYPES = frozenset({"temperature", "setToHeat", "setToCool", "state", "mode"})

# deviceType strings from GET /v3/device/ that map to lights.
# Used when the device-listing endpoint is available; ignored otherwise.
LIGHT_DEVICE_TYPES = frozenset({"switch", "dimmer", "light"})
