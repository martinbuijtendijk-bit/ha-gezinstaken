"""Instellen via de interface: adres van de app en een API-sleutel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GezinstakenAuthError, GezinstakenClient, GezinstakenError
from .const import CONF_API_KEY, CONF_URL, DOMAIN


class GezinstakenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, url: str, api_key: str) -> dict[str, str]:
        client = GezinstakenClient(async_get_clientsession(self.hass), url, api_key)
        try:
            await client.info()
        except GezinstakenAuthError:
            return {"base": "invalid_auth"}
        except GezinstakenError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if urlparse(url).scheme not in ("http", "https"):
                errors[CONF_URL] = "invalid_url"
            else:
                errors = await self._validate(url, user_input[CONF_API_KEY].strip())
                if not errors:
                    # Pas na een geslaagde controle: een mislukte poging blokkeert zo geen nieuwe poging.
                    await self.async_set_unique_id(urlparse(url).netloc.lower(), raise_on_progress=False)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Gezinstaken", data={CONF_URL: url, CONF_API_KEY: user_input[CONF_API_KEY].strip()})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Nieuwe sleutel invullen nadat de oude is ingetrokken."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._validate(entry.data[CONF_URL], user_input[CONF_API_KEY].strip())
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY].strip()})
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}), errors=errors)
