"""Haalt periodiek alle gedeelde lijsten op."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GezinstakenAuthError, GezinstakenClient, GezinstakenError, TodoListData
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GezinstakenConfigEntry = ConfigEntry[GezinstakenCoordinator]


class GezinstakenCoordinator(DataUpdateCoordinator[dict[str, TodoListData]]):
    """Lijsten per id."""

    config_entry: GezinstakenConfigEntry

    def __init__(self, hass: HomeAssistant, entry: GezinstakenConfigEntry, client: GezinstakenClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict[str, TodoListData]:
        try:
            lists = await self.client.get_lists()
        except GezinstakenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GezinstakenError as err:
            raise UpdateFailed(str(err)) from err
        return {lst.id: lst for lst in lists}
