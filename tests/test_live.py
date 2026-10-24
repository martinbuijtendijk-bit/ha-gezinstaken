"""Integratietest tegen een draaiende app (lokaal: npm run dev op poort 3010).

Start met: GZT_URL=http://localhost:3010 GZT_KEY=gzt_... .venv/bin/pytest tests -p no:cacheprovider
"""

import os

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gezinstaken.const import DOMAIN

URL = os.environ.get("GZT_URL", "")
KEY = os.environ.get("GZT_KEY", "")

pytestmark = pytest.mark.skipif(not KEY, reason="geen GZT_KEY")


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": URL, "api_key": "gzt_fout"})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": "http://127.0.0.1:1", "api_key": KEY})
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": URL + "/", "api_key": KEY})
    assert result["type"] == "create_entry"
    assert result["data"]["url"] == URL


async def test_todo_roundtrip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"url": URL, "api_key": KEY})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    entities = [e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)]
    print("entiteiten:", entities)
    assert "todo.gezinstaken_boodschappen" in entities
    eid = "todo.gezinstaken_boodschappen"
    state = hass.states.get(eid)
    print("status:", state.state, state.attributes)

    await hass.services.async_call("todo", "add_item", {"item": "Batterijen", "due_date": "2026-10-30", "description": "AA"}, target={"entity_id": eid}, blocking=True)
    items = (await hass.services.async_call("todo", "get_items", {}, target={"entity_id": eid}, blocking=True, return_response=True))[eid]["items"]
    bat = next(i for i in items if i["summary"] == "Batterijen")
    assert bat["due"] == "2026-10-30" and bat["description"] == "AA" and bat["status"] == "needs_action"

    await hass.services.async_call("todo", "update_item", {"item": "Batterijen", "status": "completed", "rename": "Batterijen AA"}, target={"entity_id": eid}, blocking=True)
    items = (await hass.services.async_call("todo", "get_items", {"status": "completed"}, target={"entity_id": eid}, blocking=True, return_response=True))[eid]["items"]
    assert any(i["summary"] == "Batterijen AA" for i in items)
    # Afgevinkte taak blijft zijn datum houden; nu datum wissen.
    await hass.services.async_call("todo", "update_item", {"item": "Batterijen AA", "due_date": None}, target={"entity_id": eid}, blocking=True)

    await hass.services.async_call("todo", "remove_item", {"item": "Batterijen AA"}, target={"entity_id": eid}, blocking=True)
    items = (await hass.services.async_call("todo", "get_items", {"status": ["needs_action", "completed"]}, target={"entity_id": eid}, blocking=True, return_response=True))[eid]["items"]
    assert not any(i["summary"].startswith("Batterijen") for i in items)
    print("taken:", [(i["summary"], i["status"]) for i in items])
    assert int(hass.states.get(eid).state) == sum(1 for i in items if i["status"] == "needs_action")

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.fixture(autouse=True)
def allow_local_socket():
    # De testomgeving van Home Assistant blokkeert netwerk; deze test praat met de echte app.
    import pytest_socket

    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    yield


async def test_move(hass: HomeAssistant, hass_ws_client) -> None:
    """Slepen in de takenlijst-kaart gaat via de websocket (todo/item/move)."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": URL, "api_key": KEY})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    eid = "todo.gezinstaken_boodschappen"

    async def open_items():
        resp = await hass.services.async_call("todo", "get_items", {"status": "needs_action"}, target={"entity_id": eid}, blocking=True, return_response=True)
        return resp[eid]["items"]

    before = await open_items()
    assert len(before) >= 2
    last = before[-1]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "todo/item/move", "entity_id": eid, "uid": last["uid"]})
    assert (await client.receive_json())["success"]
    after = await open_items()
    assert after[0]["uid"] == last["uid"]
    # Terugzetten: weer achteraan.
    await client.send_json_auto_id({"type": "todo/item/move", "entity_id": eid, "uid": last["uid"], "previous_uid": after[-1]["uid"]})
    assert (await client.receive_json())["success"]
    assert [i["uid"] for i in await open_items()] == [i["uid"] for i in before]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_retry_after_failed_attempt(hass: HomeAssistant) -> None:
    """Een mislukte poging (open venster) mag een nieuwe poging met hetzelfde adres niet blokkeren."""
    first = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    first = await hass.config_entries.flow.async_configure(first["flow_id"], {"url": URL, "api_key": "gzt_fout"})
    assert first["errors"] == {"base": "invalid_auth"}
    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    second = await hass.config_entries.flow.async_configure(second["flow_id"], {"url": URL, "api_key": KEY})
    assert second["type"] == "create_entry"
    # Hetzelfde adres nog eens: al gekoppeld.
    third = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    third = await hass.config_entries.flow.async_configure(third["flow_id"], {"url": URL, "api_key": KEY})
    assert third["type"] == "abort" and third["reason"] == "already_configured"
