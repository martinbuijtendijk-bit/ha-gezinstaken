"""Elke gedeelde lijst uit de app wordt een todo-entiteit."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GezinstakenError
from .const import DOMAIN
from .coordinator import GezinstakenConfigEntry, GezinstakenCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GezinstakenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_lists() -> None:
        # Nieuwe lijsten in de app verschijnen vanzelf; zonder herstart.
        new = [list_id for list_id in coordinator.data if list_id not in known]
        known.update(new)
        if new:
            async_add_entities(GezinstakenTodoList(coordinator, list_id) for list_id in new)

    add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(add_new_lists))


def _to_item(raw: dict[str, Any]) -> TodoItem:
    due = raw.get("dueDate")
    return TodoItem(
        uid=raw["id"],
        summary=raw["title"],
        status=TodoItemStatus.COMPLETED if raw["completed"] else TodoItemStatus.NEEDS_ACTION,
        due=date.fromisoformat(due) if due else None,
        description=raw.get("description"),
    )


def _to_body(item: TodoItem) -> dict[str, Any]:
    due = item.due
    # Alleen een datum; een tijd wordt (nog) niet ondersteund.
    if due is not None and not isinstance(due, date):
        raise HomeAssistantError("Ongeldige datum")
    return {
        "title": item.summary,
        "completed": item.status == TodoItemStatus.COMPLETED,
        "dueDate": due.isoformat()[:10] if due else None,
        "description": item.description or None,
    }


class GezinstakenTodoList(CoordinatorEntity[GezinstakenCoordinator], TodoListEntity):
    """Een gedeelde lijst."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: GezinstakenCoordinator, list_id: str) -> None:
        super().__init__(coordinator)
        self._list_id = list_id
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{list_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Gezinstaken",
            manufacturer="Gezinstaken",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data["url"],
        )

    @property
    def available(self) -> bool:
        # Een in de app verwijderde lijst wordt "niet beschikbaar".
        return super().available and self._list_id in self.coordinator.data

    @property
    def name(self) -> str | None:
        lst = self.coordinator.data.get(self._list_id)
        return lst.name if lst else None

    @property
    def todo_items(self) -> list[TodoItem] | None:
        lst = self.coordinator.data.get(self._list_id)
        return [_to_item(raw) for raw in lst.items] if lst else None

    async def _call(self, coro) -> None:
        try:
            await coro
        except GezinstakenError as err:
            raise HomeAssistantError(f"Gezinstaken: {err}") from err
        # Direct vernieuwen (async_request_refresh wacht na een eerdere wijziging tot 10 s).
        await self.coordinator.async_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self._call(self.coordinator.client.create_item(self._list_id, _to_body(item)))

    async def async_update_todo_item(self, item: TodoItem) -> None:
        await self._call(self.coordinator.client.update_item(item.uid, _to_body(item)))

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        async def delete_all() -> None:
            for uid in uids:
                await self.coordinator.client.delete_item(uid)

        await self._call(delete_all())

    async def async_move_todo_item(self, uid: str, previous_uid: str | None = None) -> None:
        await self._call(self.coordinator.client.move_item(uid, previous_uid))
