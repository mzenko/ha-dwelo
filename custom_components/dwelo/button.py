"""Dwelo community door button platform.

Each "perimeter door" is a PDK cloud-managed door buzzer. Pressing the button
sends a momentary open command; the door relocks automatically after secondsOpen seconds.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DweloCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dwelo community door buttons from a config entry."""
    coordinator: DweloCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        DweloCommunityDoor(coordinator, door)
        for door in coordinator.community_doors
    ]

    _LOGGER.debug("Setting up %d Dwelo community door(s)", len(entities))
    async_add_entities(entities)


class DweloCommunityDoor(ButtonEntity):
    """A Dwelo community perimeter door presented as a HA button.

    Pressing the button buzzes the door open for secondsOpen seconds (typically 3 s).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: DweloCoordinator, door: dict[str, Any]) -> None:
        self._coordinator = coordinator
        self._door_uid: int = int(door["uid"])
        self._panel_id: str = door["panelId"]

        self._attr_unique_id = f"dwelo_door_{self._door_uid}"
        # With has_entity_name=True, name=None uses the device name directly.
        self._attr_name = None
        self._attr_icon = "mdi:door"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"door_{self._door_uid}")},
            name=door["name"],
            manufacturer="Dwelo / PDK",
            model="Perimeter Door",
        )

    async def async_press(self) -> None:
        """Buzz the door open."""
        await self._coordinator.api.open_door(self._door_uid, self._panel_id)
