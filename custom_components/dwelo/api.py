"""Dwelo cloud API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class DweloApiError(Exception):
    """General API error."""


class DweloAuthError(DweloApiError):
    """Raised when the token is invalid or expired."""


class DweloApi:
    """Thin async wrapper around the Dwelo cloud REST API."""

    def __init__(
        self,
        token: str,
        gateway_id: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._token = token
        self._gateway_id = gateway_id
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{API_BASE_URL}{path}"
        try:
            async with self._session.request(
                method, url, headers=self._headers, timeout=REQUEST_TIMEOUT, **kwargs
            ) as resp:
                if resp.status == 401:
                    raise DweloAuthError(
                        "Authentication failed — verify your Dwelo token"
                    )
                resp.raise_for_status()
                return await resp.json()
        except DweloApiError:
            raise
        except aiohttp.ClientResponseError as err:
            raise DweloApiError(f"HTTP error {err.status}: {err.message}") from err
        except aiohttp.ClientError as err:
            raise DweloApiError(f"Connection error: {err}") from err

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------

    async def get_sensor_states(self) -> list[dict[str, Any]]:
        """Return all sensor readings for the gateway.

        Each entry: {"deviceId": int, "sensorType": str, "value": str|int|float}
        """
        data = await self._request(
            "GET", f"/v3/sensor/gateway/{self._gateway_id}/"
        )
        return data.get("results", [])

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return device metadata (name, deviceType, …) for the gateway.

        Each entry typically: {"id": int, "name": str, "deviceType": str, …}
        Returns an empty list if the endpoint is unavailable.
        """
        try:
            data = await self._request(
                "GET", "/v3/device/", params={"gateway": self._gateway_id}
            )
            return data.get("results", [])
        except DweloApiError:
            _LOGGER.debug(
                "Could not fetch device list from /v3/device/ — "
                "device names will fall back to device IDs"
            )
            return []

    # ------------------------------------------------------------------
    # Command endpoints
    # ------------------------------------------------------------------

    async def turn_on(self, device_id: int, brightness: int | None = None) -> None:
        """Turn a light on.

        Args:
            device_id: Dwelo device ID.
            brightness: Optional HA brightness (0–255). Converted to the
                        Dwelo 0–99 scale when provided.
        """
        payload: dict[str, Any] = {"command": "on"}
        if brightness is not None:
            # HA uses 0–255; Dwelo multilevel uses 0–99.
            payload["commandValue"] = round(brightness / 255 * 99)
        await self._request(
            "POST", f"/v3/device/{device_id}/command/", json=payload
        )

    async def turn_off(self, device_id: int) -> None:
        """Turn a light off."""
        await self._request(
            "POST", f"/v3/device/{device_id}/command/", json={"command": "off"}
        )

    # ------------------------------------------------------------------
    # Community door (perimeter) endpoints
    # ------------------------------------------------------------------

    async def get_community_doors(self, community_id: str) -> list[dict[str, Any]]:
        """Return all perimeter doors for a community.

        Each entry: {"uid": int, "name": str, "panelId": str, "secondsOpen": float, "communityId": int}
        """
        try:
            data = await self._request(
                "GET", f"/v3/perimeter/door/community/{community_id}/"
            )
            return data.get("results", [])
        except DweloApiError:
            _LOGGER.debug("Could not fetch community doors for community %s", community_id)
            return []

    async def open_door(self, door_uid: int, panel_id: str) -> None:
        """Buzz a community door open (momentarily unlocks for secondsOpen seconds)."""
        await self._request(
            "POST",
            f"/v3/perimeter/door/{door_uid}/open/",
            json={"panelId": panel_id},
        )

    # ------------------------------------------------------------------
    # Discovery helpers (token-only, no gateway_id needed)
    # ------------------------------------------------------------------

    async def get_communities(self) -> list[dict[str, Any]]:
        """Return communities the authenticated user has access to."""
        data = await self._request("GET", "/v3/community/", params={"limit": 5000})
        return data.get("results", [])

    async def get_addresses(self, community_id: int) -> list[dict[str, Any]]:
        """Return unit addresses for a community (includes gatewayId)."""
        data = await self._request(
            "GET", "/v4/address/", params={"communityId": community_id}
        )
        return data.get("results", [])

    async def async_validate(self) -> None:
        """Raise DweloAuthError or DweloApiError if credentials are invalid."""
        await self.get_sensor_states()
