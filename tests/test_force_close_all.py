"""Tests for force_close_all function."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.ha_lawn_irrigation.irrigation import force_close_all


def mock_state(state_str):
    s = MagicMock()
    s.state = state_str
    return s


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    monkeypatch.setattr("custom_components.ha_lawn_irrigation.irrigation.asyncio.sleep", AsyncMock())


async def test_empty_list_returns_empty(hass):
    result = await force_close_all(hass, [])
    assert result == []
    hass.services.async_call.assert_not_called()


async def test_all_close_successfully(hass):
    hass.states.get.return_value = mock_state("off")
    result = await force_close_all(hass, ["switch.v1", "switch.v2"])
    assert result == []


async def test_one_fails_returned(hass):
    # v1 closes, v2 stays on
    def get_state(entity_id):
        if entity_id == "switch.v1":
            return mock_state("off")
        return mock_state("on")

    hass.states.get.side_effect = get_state
    result = await force_close_all(hass, ["switch.v1", "switch.v2"])
    assert result == ["switch.v2"]


async def test_all_fail_all_returned(hass):
    hass.states.get.return_value = mock_state("on")
    result = await force_close_all(hass, ["switch.v1", "switch.v2"])
    assert set(result) == {"switch.v1", "switch.v2"}


async def test_order_preserved_in_failed(hass):
    hass.states.get.return_value = mock_state("on")
    entities = ["switch.a", "switch.b", "switch.c"]
    result = await force_close_all(hass, entities)
    assert result == entities
