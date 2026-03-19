"""DataUpdateCoordinator for Dwelo."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DweloApi, DweloApiError, DweloAuthError, DweloLoginError
from .const import (
    BINARY_LIGHT_SENSOR_TYPES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LIGHT_DEVICE_TYPES,
    NON_LIGHT_SENSOR_TYPES,
    SENSOR_TYPE_SWITCH_MULTILEVEL,
)

_LOGGER = logging.getLogger(__name__)


class DweloCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Polls /v3/sensor/gateway/{id}/ and exposes per-device sensor maps."""

    def __init__(self, hass: HomeAssistant, api: DweloApi, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.config_entry = entry
        # device_id -> metadata dict (name, deviceType, …)
        self.devices: dict[int, dict[str, Any]] = {}
        # uid -> door dict (name, panelId, secondsOpen, …)
        self.community_doors: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch all sensor readings and reshape into {device_id: {sensorType: value}}."""
        try:
            readings = await self.api.get_sensor_states()
        except DweloAuthError:
            readings = await self._try_reauth()
        except DweloApiError as err:
            raise UpdateFailed(f"Error communicating with Dwelo API: {err}") from err

        sensor_map: dict[int, dict[str, Any]] = {}
        for reading in readings:
            device_id = int(reading["deviceId"])
            sensor_map.setdefault(device_id, {})[reading["sensorType"]] = reading["value"]

        return sensor_map

    async def _try_reauth(self) -> list[dict[str, Any]]:
        """Attempt to re-login and retry the sensor fetch.

        Returns sensor readings on success.
        Raises ConfigEntryAuthFailed if re-login fails.
        """
        email = self.config_entry.data.get("email")
        password = self.config_entry.data.get("password")
        if not email or not password:
            raise ConfigEntryAuthFailed(
                "Dwelo token expired and no stored credentials for re-login"
            )

        try:
            session = async_get_clientsession(self.hass)
            new_token = await DweloApi.async_login(email, password, session)
        except (DweloLoginError, DweloApiError) as err:
            raise ConfigEntryAuthFailed(
                "Dwelo token expired and re-login failed"
            ) from err

        self.api.update_token(new_token)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, "token": new_token},
        )
        _LOGGER.info("Dwelo token refreshed via auto-reauth")

        try:
            return await self.api.get_sensor_states()
        except DweloAuthError as err:
            raise ConfigEntryAuthFailed(
                "Dwelo auth still failing after re-login"
            ) from err

    async def async_load_devices(self) -> None:
        """Fetch device metadata (names, types). Non-fatal if the endpoint is absent."""
        raw = await self.api.get_devices()
        # The API returns "uid" as the primary key, not "id".
        self.devices = {int(d["uid"]): d for d in raw if "uid" in d}
        _LOGGER.debug("Loaded %d device metadata entries", len(self.devices))

    def get_light_device_ids(self) -> list[tuple[int, str]]:
        """Return (device_id, kind) pairs for light-type devices.

        ``kind`` is ``"switch"`` (binary on/off) or ``"dimmer"`` (multilevel).

        Detection strategy
        ------------------
        1. If device metadata from ``/v3/device/`` is present and has a
           ``deviceType`` field, use that to decide inclusion and kind.
        2. Otherwise fall back to sensorType inference:
           - Devices with ``switchMultilevel`` → dimmer
           - Devices with ``switchBinary`` (and no non-light sensor types) → switch
        """
        if not self.data:
            return []

        result: list[tuple[int, str]] = []

        for device_id, sensors in self.data.items():
            meta = self.devices.get(device_id, {})
            dtype = meta.get("deviceType", "").lower()

            if dtype:
                # Metadata-based detection
                if dtype not in LIGHT_DEVICE_TYPES:
                    continue
                if dtype == "dimmer" or SENSOR_TYPE_SWITCH_MULTILEVEL in sensors:
                    result.append((device_id, "dimmer"))
                else:
                    result.append((device_id, "switch"))
            else:
                # Sensor-type inference — exclude anything that looks like a
                # thermostat or other non-light device.
                if NON_LIGHT_SENSOR_TYPES.intersection(sensors):
                    continue
                if SENSOR_TYPE_SWITCH_MULTILEVEL in sensors:
                    result.append((device_id, "dimmer"))
                elif BINARY_LIGHT_SENSOR_TYPES.intersection(sensors):
                    result.append((device_id, "switch"))

        return result

    async def async_load_community_doors(self, community_id: str) -> None:
        """Fetch community perimeter doors. Non-fatal if unavailable."""
        self.community_doors = await self.api.get_community_doors(community_id)
        _LOGGER.debug("Loaded %d community door(s)", len(self.community_doors))

    def device_name(self, device_id: int) -> str:
        """Human-readable name for a device, falling back to the numeric ID."""
        meta = self.devices.get(device_id, {})
        # The API returns the user-assigned name in "givenName".
        return meta.get("givenName") or f"Dwelo Device {device_id}"
