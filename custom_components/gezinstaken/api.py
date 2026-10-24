"""Kleine client voor de API van de Gezinstaken-webapp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


class GezinstakenError(Exception):
    """Algemene fout bij het praten met de app."""


class GezinstakenAuthError(GezinstakenError):
    """De API-sleutel is ongeldig of ingetrokken."""


@dataclass
class TodoListData:
    """Een gedeelde lijst met zijn taken."""

    id: str
    name: str
    icon: str
    items: list[dict[str, Any]]


class GezinstakenClient:
    """Praat met de webapp via een API-sleutel (Bearer)."""

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._url}{path}",
                headers=self._headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise GezinstakenAuthError("API-sleutel geweigerd")
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    message = (data or {}).get("error", {}).get("message", resp.reason)
                    raise GezinstakenError(f"{resp.status}: {message}")
                return data
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise GezinstakenError(f"Geen verbinding met {self._url}: {err}") from err

    async def info(self) -> dict[str, Any]:
        """Controleer adres en sleutel."""
        data = await self._request("GET", "/api/info")
        if data.get("app") != "gezinstaken":
            raise GezinstakenError("Dit adres is geen Gezinstaken-app")
        return data

    async def get_lists(self) -> list[TodoListData]:
        """Alle gedeelde lijsten met hun taken."""
        lists = (await self._request("GET", "/api/lists"))["lists"]
        result = []
        for lst in lists:
            items = (await self._request("GET", f"/api/lists/{lst['id']}/items"))["items"]
            result.append(TodoListData(id=lst["id"], name=lst["name"], icon=lst["icon"], items=items))
        return result

    async def create_item(self, list_id: str, body: dict[str, Any]) -> None:
        await self._request("POST", f"/api/lists/{list_id}/items", body)

    async def update_item(self, item_id: str, body: dict[str, Any]) -> None:
        await self._request("PATCH", f"/api/items/{item_id}", body)

    async def delete_item(self, item_id: str) -> None:
        await self._request("DELETE", f"/api/items/{item_id}")

    async def move_item(self, item_id: str, after_id: str | None) -> None:
        await self._request("POST", f"/api/items/{item_id}/move", {"afterId": after_id})
