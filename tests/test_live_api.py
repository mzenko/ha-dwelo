"""
Live integration tests against the real Dwelo API.

These tests make real HTTP requests — they verify that our API client and
coordinator logic work correctly against your actual unit.

Credentials are read from a .env file in the project root (never committed):
    DWELO_TOKEN=<your token>
    DWELO_GATEWAY_ID=<your gateway id>
"""
import os
import pprint

import aiohttp
import pytest
from dotenv import load_dotenv

from custom_components.dwelo.api import DweloApi
from custom_components.dwelo.const import (
    BINARY_LIGHT_SENSOR_TYPES,
    LIGHT_DEVICE_TYPES,
    NON_LIGHT_SENSOR_TYPES,
    SENSOR_TYPE_SWITCH_MULTILEVEL,
)

load_dotenv()

TOKEN = os.environ.get("DWELO_TOKEN", "")
GATEWAY_ID = os.environ.get("DWELO_GATEWAY_ID", "")
COMMUNITY_ID = os.environ.get("DWELO_COMMUNITY_ID", "")

pytestmark = pytest.mark.skipif(
    not TOKEN or not GATEWAY_ID,
    reason="DWELO_TOKEN and DWELO_GATEWAY_ID must be set in .env to run live tests",
)


# ---------------------------------------------------------------------------
# Shared session fixture
# ---------------------------------------------------------------------------
@pytest.fixture
async def api():
    async with aiohttp.ClientSession() as session:
        yield DweloApi(token=TOKEN, gateway_id=GATEWAY_ID, session=session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_sensor_states_returns_results(api):
    """Smoke test: the sensor/gateway endpoint responds with a non-empty list."""
    readings = await api.get_sensor_states()

    assert isinstance(readings, list), "Expected a list of sensor readings"
    assert len(readings) > 0, "Expected at least one sensor reading"

    print(f"\n=== {len(readings)} sensor readings ===")
    pprint.pprint(readings)


async def test_sensor_state_schema(api):
    """Every reading must have deviceId, sensorType, and value."""
    readings = await api.get_sensor_states()

    for r in readings:
        assert "deviceId" in r, f"Missing deviceId in: {r}"
        assert "sensorType" in r, f"Missing sensorType in: {r}"
        assert "value" in r, f"Missing value in: {r}"


async def test_unique_sensor_types(api):
    """Print the full set of sensorType values seen across all devices."""
    readings = await api.get_sensor_states()
    sensor_types = {r["sensorType"] for r in readings}

    print(f"\n=== Observed sensorTypes ===")
    pprint.pprint(sorted(sensor_types))

    # Just informational — no hard assertion on specific values,
    # but there must be at least one.
    assert len(sensor_types) > 0


async def test_device_sensor_map(api):
    """Print per-device sensor maps — useful for seeing which sensors each device has."""
    readings = await api.get_sensor_states()

    device_map: dict[int, dict] = {}
    for r in readings:
        did = int(r["deviceId"])
        device_map.setdefault(did, {})[r["sensorType"]] = r["value"]

    print(f"\n=== {len(device_map)} device(s) found ===")
    for device_id, sensors in sorted(device_map.items()):
        print(f"\n  Device {device_id}:")
        for st, val in sorted(sensors.items()):
            print(f"    {st}: {val!r}")


async def test_get_devices_endpoint(api):
    """Try the /v3/device/ listing endpoint and print whatever it returns."""
    devices = await api.get_devices()

    print(f"\n=== /v3/device/ returned {len(devices)} device(s) ===")
    pprint.pprint(devices)

    # Non-fatal if empty — the endpoint might not exist for all gateways.
    # But if we got something, it must be a list of dicts.
    for d in devices:
        assert isinstance(d, dict), f"Expected a dict, got: {d}"


async def test_light_device_discovery(api):
    """Verify the coordinator's light-detection logic finds at least one light."""
    readings = await api.get_sensor_states()
    devices_raw = await api.get_devices()

    # Rebuild sensor map (same logic as DweloCoordinator._async_update_data)
    sensor_map: dict[int, dict] = {}
    for r in readings:
        did = int(r["deviceId"])
        sensor_map.setdefault(did, {})[r["sensorType"]] = r["value"]

    # Rebuild device metadata map (same logic as DweloCoordinator.async_load_devices)
    # The API uses "uid" as the primary key, not "id".
    devices: dict[int, dict] = {int(d["uid"]): d for d in devices_raw if "uid" in d}

    # Replicate DweloCoordinator.get_light_device_ids()
    lights: list[tuple[int, str]] = []
    for device_id, sensors in sensor_map.items():
        meta = devices.get(device_id, {})
        dtype = meta.get("deviceType", "").lower()

        if dtype:
            if dtype not in LIGHT_DEVICE_TYPES:
                continue
            if dtype == "dimmer" or SENSOR_TYPE_SWITCH_MULTILEVEL in sensors:
                lights.append((device_id, "dimmer"))
            else:
                lights.append((device_id, "switch"))
        else:
            if NON_LIGHT_SENSOR_TYPES.intersection(sensors):
                continue
            if SENSOR_TYPE_SWITCH_MULTILEVEL in sensors:
                lights.append((device_id, "dimmer"))
            elif BINARY_LIGHT_SENSOR_TYPES.intersection(sensors):
                lights.append((device_id, "switch"))

    print(f"\n=== Detected light devices ===")
    for device_id, kind in sorted(lights):
        name = devices.get(device_id, {}).get("givenName", f"Device {device_id}")
        sensors = sensor_map[device_id]
        print(f"  [{kind:6s}] {device_id}  {name!r}  sensors={list(sensors)}")

    assert len(lights) > 0, (
        "No light devices detected.\n"
        "Check that your devices have 'switchBinary' or 'switchMultilevel' sensor types.\n"
        f"Observed sensor types: {sorted({st for s in sensor_map.values() for st in s})}"
    )


async def test_get_community_doors(api):
    """Verify community doors are returned and have the expected schema."""
    doors = await api.get_community_doors(COMMUNITY_ID)

    print(f"\n=== {len(doors)} community door(s) ===")
    for d in doors[:10]:
        print(f"  uid={d['uid']:4d}  panelId={d['panelId']}  secondsOpen={d['secondsOpen']}  name={d['name']!r}")
    if len(doors) > 10:
        print(f"  ... and {len(doors) - 10} more")

    assert len(doors) > 0, "Expected at least one community door"
    for d in doors:
        assert "uid" in d
        assert "panelId" in d
        assert "name" in d
        assert "secondsOpen" in d
