"""Config flow for the Dwelo integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DweloApi, DweloApiError, DweloAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required("token"): str,
    }
)


class DweloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dwelo.

    Step 1 (token): user pastes their Dwelo API token.
    Step 2 (unit):  auto-discovered units are shown; user picks one.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._token: str = ""
        self._units: list[dict] = []  # [{gateway_id, community_id, label}, ...]

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: collect the API token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._token = user_input["token"].strip()

            session = async_get_clientsession(self.hass)
            # Use a dummy gateway_id — we only need the token for discovery calls.
            api = DweloApi(
                token=self._token, gateway_id="0", session=session
            )

            try:
                communities = await api.get_communities()
            except DweloAuthError:
                errors["base"] = "invalid_auth"
            except DweloApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Dwelo config flow")
                errors["base"] = "unknown"
            else:
                # Discover all units (addresses) across all communities.
                self._units = []
                for community in communities:
                    cid = community["uid"]
                    cname = community.get("name", f"Community {cid}")
                    try:
                        addresses = await api.get_addresses(cid)
                    except DweloApiError:
                        continue
                    for addr in addresses:
                        gw_id = addr.get("gatewayId")
                        if not gw_id:
                            continue
                        unit_label = addr.get("unit", "")
                        label = f"{cname} — Unit {unit_label}" if unit_label else cname
                        self._units.append(
                            {
                                "gateway_id": str(gw_id),
                                "community_id": str(cid),
                                "label": label,
                            }
                        )

                if not self._units:
                    errors["base"] = "no_units"
                elif len(self._units) == 1:
                    # Only one unit — skip selection step.
                    return await self._create_entry(self._units[0])
                else:
                    return await self.async_step_select_unit()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_TOKEN_SCHEMA,
            errors=errors,
        )

    async def async_step_select_unit(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: let the user pick which unit to configure (multi-unit only)."""
        if user_input is not None:
            chosen_gw = user_input["unit"]
            unit = next(u for u in self._units if u["gateway_id"] == chosen_gw)
            return await self._create_entry(unit)

        unit_options = {u["gateway_id"]: u["label"] for u in self._units}

        return self.async_show_form(
            step_id="select_unit",
            data_schema=vol.Schema(
                {vol.Required("unit"): vol.In(unit_options)}
            ),
        )

    async def _create_entry(self, unit: dict) -> config_entries.FlowResult:
        """Create a config entry for the chosen unit."""
        gateway_id = unit["gateway_id"]
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=unit["label"],
            data={
                "token": self._token,
                "gateway_id": gateway_id,
                "community_id": unit["community_id"],
            },
        )
