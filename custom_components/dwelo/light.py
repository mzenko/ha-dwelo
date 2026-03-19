"""Dwelo light platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_LIGHT_SENSOR_TYPES, DOMAIN, SENSOR_TYPE_SWITCH_MULTILEVEL
from .coordinator import DweloCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dwelo lights from a config entry."""
    coordinator: DweloCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[LightEntity] = []
    for device_id, kind in coordinator.get_light_device_ids():
        name = coordinator.device_name(device_id)
        if kind == "dimmer":
            entities.append(DweloDimmerLight(coordinator, device_id, name))
        else:
            entities.append(DweloBinaryLight(coordinator, device_id, name))

    _LOGGER.debug("Setting up %d Dwelo light(s)", len(entities))
    async_add_entities(entities)


class _DweloLightBase(CoordinatorEntity[DweloCoordinator], LightEntity):
    """Shared base for Dwelo light entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DweloCoordinator,
        device_id: int,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"dwelo_{device_id}"
        # With has_entity_name=True, setting name=None uses the device name directly
        # (avoids "Living Room Living Room" duplication).
        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer="Dwelo",
        )

    @property
    def _sensors(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._device_id, {})


class DweloBinaryLight(_DweloLightBase):
    """A simple on/off Dwelo switch presented as a light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        # The API may return sensorType "light" or "switchBinary" depending on firmware.
        val = next(
            (self._sensors[st] for st in BINARY_LIGHT_SENSOR_TYPES if st in self._sensors),
            None,
        )
        if val is None:
            return None
        return str(val).lower() in ("on", "1", "true")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_on(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._device_id)
        await self.coordinator.async_request_refresh()


class DweloDimmerLight(_DweloLightBase):
    """A dimmable Dwelo multilevel switch presented as a light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def is_on(self) -> bool | None:
        val = self._sensors.get(SENSOR_TYPE_SWITCH_MULTILEVEL)
        if val is None:
            return None
        try:
            return int(val) > 0
        except (TypeError, ValueError):
            return None

    @property
    def brightness(self) -> int | None:
        val = self._sensors.get(SENSOR_TYPE_SWITCH_MULTILEVEL)
        if val is None:
            return None
        try:
            # Convert Dwelo 0–99 scale to HA 0–255 scale.
            return round(int(val) / 99 * 255)
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        await self.coordinator.api.turn_on(self._device_id, brightness=brightness)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._device_id)
        await self.coordinator.async_request_refresh()
