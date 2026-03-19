"""Config flow for the Dwelo integration."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DweloApi, DweloApiError, DweloAuthError, DweloLoginError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
    }
)


class DweloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dwelo.

    Step 1 (user): user enters Dwelo email and password.
    Step 2 (unit):  auto-discovered units are shown; user picks one.
    """

    VERSION = 2

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._token: str = ""
        self._units: list[dict] = []  # [{gateway_id, community_id, label}, ...]

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: collect email and password, login to get a token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input["email"].strip()
            self._password = user_input["password"]

            session = async_get_clientsession(self.hass)

            try:
                self._token = await DweloApi.async_login(
                    self._email, self._password, session
                )
            except DweloLoginError:
                errors["base"] = "invalid_auth"
            except DweloApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Dwelo login")
                errors["base"] = "unknown"
            else:
                # Login succeeded — discover units.
                api = DweloApi(
                    token=self._token, gateway_id="0", session=session
                )
                try:
                    return await self._discover_units(api)
                except DweloApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during Dwelo discovery")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    async def _discover_units(
        self, api: DweloApi
    ) -> config_entries.ConfigFlowResult:
        """Discover all units and advance to selection or entry creation."""
        communities = await api.get_communities()

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
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_CREDENTIALS_SCHEMA,
                errors={"base": "no_units"},
            )
        if len(self._units) == 1:
            return await self._create_entry(self._units[0])
        return await self.async_step_select_unit()

    async def async_step_select_unit(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
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

    async def _create_entry(self, unit: dict) -> config_entries.ConfigFlowResult:
        """Create a config entry for the chosen unit."""
        gateway_id = unit["gateway_id"]
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=unit["label"],
            data={
                "email": self._email,
                "password": self._password,
                "token": self._token,
                "gateway_id": gateway_id,
                "community_id": unit["community_id"],
            },
        )

    # ------------------------------------------------------------------
    # Reauth flow
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauth triggered by ConfigEntryAuthFailed."""
        self._email = entry_data.get("email", "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show reauth form and validate new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input["email"].strip()
            self._password = user_input["password"]

            session = async_get_clientsession(self.hass)
            try:
                new_token = await DweloApi.async_login(
                    self._email, self._password, session
                )
            except DweloLoginError:
                errors["base"] = "invalid_auth"
            except DweloApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Dwelo reauth")
                errors["base"] = "unknown"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                assert entry is not None
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        "email": self._email,
                        "password": self._password,
                        "token": new_token,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("email", default=self._email): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
