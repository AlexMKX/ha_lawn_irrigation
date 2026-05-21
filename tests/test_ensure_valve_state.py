"""Tests for ensure_valve_state function."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.ha_lawn_irrigation.irrigation import ensure_valve_state


def mock_state(state_str):
    s = MagicMock()
    s.state = state_str
    return s


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    monkeypatch.setattr("custom_components.ha_lawn_irrigation.irrigation.asyncio.sleep", AsyncMock())


async def test_already_at_desired_state_returns_true(hass):
    hass.states.get.return_value = mock_state("on")
    result = await ensure_valve_state(hass, "switch.valve", "on")
    assert result is True
    hass.services.async_call.assert_not_called()


async def test_invalid_desired_state_raises(hass):
    with pytest.raises(ValueError):
        await ensure_valve_state(hass, "switch.valve", "open")


async def test_first_retry_succeeds(hass):
    hass.states.get.side_effect = [mock_state("off"), mock_state("on")]
    result = await ensure_valve_state(hass, "switch.valve", "on", retries=[1])
    assert result is True


async def test_all_retries_fail_returns_false(hass):
    hass.states.get.return_value = mock_state("off")
    result = await ensure_valve_state(hass, "switch.valve", "on", retries=[1, 2])
    assert result is False


async def test_desired_on_uses_turn_on(hass):
    hass.states.get.side_effect = [mock_state("off"), mock_state("on")]
    await ensure_valve_state(hass, "switch.valve", "on", retries=[1])
    hass.services.async_call.assert_called_once_with(
        "homeassistant", "turn_on", {"entity_id": "switch.valve"}, blocking=False
    )


async def test_desired_off_uses_turn_off(hass):
    hass.states.get.side_effect = [mock_state("on"), mock_state("off")]
    await ensure_valve_state(hass, "switch.valve", "off", retries=[1])
    hass.services.async_call.assert_called_once_with(
        "homeassistant", "turn_off", {"entity_id": "switch.valve"}, blocking=False
    )


async def test_service_exception_continues_retries(hass):
    hass.services.async_call.side_effect = Exception("service error")
    hass.states.get.return_value = mock_state("off")
    # Should not raise, just return False after all retries
    result = await ensure_valve_state(hass, "switch.valve", "on", retries=[1])
    assert result is False


async def test_sleep_called_with_delays(hass, monkeypatch):
    sleep_mock = AsyncMock()
    monkeypatch.setattr("custom_components.ha_lawn_irrigation.irrigation.asyncio.sleep", sleep_mock)
    hass.states.get.return_value = mock_state("off")
    await ensure_valve_state(hass, "switch.valve", "on", retries=[3, 7])
    calls = [c.args[0] for c in sleep_mock.call_args_list]
    assert calls == [3, 7]


async def test_default_retries_used_when_none(hass):
    hass.states.get.return_value = mock_state("off")
    result = await ensure_valve_state(hass, "switch.valve", "on")
    assert result is False


async def test_succeeds_on_second_retry(hass):
    hass.states.get.side_effect = [
        mock_state("off"),  # initial check
        mock_state("off"),  # after first retry
        mock_state("on"),   # after second retry
    ]
    result = await ensure_valve_state(hass, "switch.valve", "on", retries=[1, 1])
    assert result is True
