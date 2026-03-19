"""The Dwelo integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DweloApi
from .const import DOMAIN
from .coordinator import DweloCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light", "button"]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current version."""
    if config_entry.version < 2:
        _LOGGER.info(
            "Migrating Dwelo config entry from version %s to 2",
            config_entry.version,
        )
        # v1 stored only a token; v2 requires email+password.
        # Bump the version — the first poll will fail auth (no credentials),
        # triggering the reauth flow where the user provides them.
        hass.config_entries.async_update_entry(config_entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dwelo from a config entry."""
    token = entry.data["token"]
    gateway_id = entry.data["gateway_id"]
    community_id = entry.data.get("community_id", "")

    session = async_get_clientsession(hass)
    api = DweloApi(token=token, gateway_id=gateway_id, session=session)

    coordinator = DweloCoordinator(hass, api, entry)

    # Fetch device metadata (names/types) once on startup — non-fatal if unavailable.
    await coordinator.async_load_devices()

    # Fetch community perimeter doors if a community ID was provided.
    if community_id:
        await coordinator.async_load_community_doors(community_id)

    # Do the first poll so entities have data immediately on setup.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
