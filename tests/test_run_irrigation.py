"""Tests for run_irrigation function."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def mock_state(state_str):
    s = MagicMock()
    s.state = state_str
    return s


def make_zones(valve_states=None, moisture_values=None):
    """Build zones list and configure hass.states.get."""
    valve_states = valve_states or ["off"]
    moisture_values = moisture_values or ["50"]
    zones = []
    for i, (vs, mv) in enumerate(zip(valve_states, moisture_values)):
        zones.append({
            "entity_id": f"switch.valve_{i}",
            "moisture_sensor": f"sensor.moisture_{i}",
            "duration_min": 1,
        })
    return zones, valve_states, moisture_values


def make_call_data(valve_states=None, moisture_values=None, water_level_template="{{ 200 }}"):
    valve_states = valve_states or ["off"]
    moisture_values = moisture_values or ["50"]
    zones, _, _ = make_zones(valve_states, moisture_values)
    return {
        "water_level_template": water_level_template,
        "zones": zones,
    }, valve_states, moisture_values


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    monkeypatch.setattr("custom_components.ha_lawn_irrigation.irrigation.asyncio.sleep", AsyncMock())


async def test_preflight_valve_on_sends_notification_and_returns(hass):
    call_data, _, _ = make_call_data(valve_states=["on"], moisture_values=["50"])
    hass.states.get.side_effect = lambda eid: mock_state("on") if "valve" in eid else mock_state("50")
    await run_irrigation(hass, call_data)
    hass.services.async_call.assert_called_once()
    args = hass.services.async_call.call_args
    assert args[0][0] == "persistent_notification"


async def test_no_valid_moisture_sends_notification(hass):
    call_data, _, _ = make_call_data(valve_states=["off"], moisture_values=["unavailable"])
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("unavailable")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=200.0):
        await run_irrigation(hass, call_data)
    hass.services.async_call.assert_called_once()
    msg = hass.services.async_call.call_args[0][2]["message"]
    assert "moisture" in msg.lower() or "aborted" in msg.lower()


async def test_water_level_none_sends_notification(hass):
    call_data, _, _ = make_call_data(valve_states=["off"], moisture_values=["50"])
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=None):
        await run_irrigation(hass, call_data)
    hass.services.async_call.assert_called_once()
    msg = hass.services.async_call.call_args[0][2]["message"]
    assert "water level" in msg.lower()


async def test_water_level_zero_sends_notification(hass):
    call_data, _, _ = make_call_data(valve_states=["off"], moisture_values=["50"])
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=0.0):
        await run_irrigation(hass, call_data)
    hass.services.async_call.assert_called_once()


async def test_force_close_all_called_in_finally(hass):
    call_data, _, _ = make_call_data(valve_states=["off"], moisture_values=["50"])
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=200.0), \
         patch("custom_components.ha_lawn_irrigation.irrigation.force_close_all", new_callable=AsyncMock) as mock_fca:
        mock_fca.return_value = []
        with patch("custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state", new_callable=AsyncMock, side_effect=Exception("boom")):
            with pytest.raises(Exception, match="boom"):
                await run_irrigation(hass, call_data)
    mock_fca.assert_called_once()


async def test_high_moisture_zone_skipped(hass):
    call_data = {
        "water_level_template": "{{ 200 }}",
        "zones": [{"entity_id": "switch.valve_0", "moisture_sensor": "sensor.m0", "duration_min": 1}],
    }
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("99.5")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=200.0), \
         patch("custom_components.ha_lawn_irrigation.irrigation.force_close_all", new_callable=AsyncMock, return_value=[]), \
         patch("custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state", new_callable=AsyncMock) as mock_evs:
        await run_irrigation(hass, call_data)
    # ensure_valve_state for opening should NOT be called (zone skipped)
    open_calls = [c for c in mock_evs.call_args_list if c[0][2] == "on"]
    assert len(open_calls) == 0


async def test_successful_run_sends_summary_notification(hass):
    call_data = {
        "water_level_template": "{{ 200 }}",
        "zones": [{"entity_id": "switch.valve_0", "moisture_sensor": "sensor.m0", "duration_min": 1}],
    }
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")
    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=200.0), \
         patch("custom_components.ha_lawn_irrigation.irrigation.force_close_all", new_callable=AsyncMock, return_value=[]), \
         patch("custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state", new_callable=AsyncMock, return_value=True):
        await run_irrigation(hass, call_data)
    final_call = hass.services.async_call.call_args_list[-1]
    msg = final_call[0][2]["message"]
    assert "complete" in msg.lower()


async def test_zone_fails_to_open_continues_to_next(hass):
    call_data = {
        "water_level_template": "{{ 200 }}",
        "zones": [
            {"entity_id": "switch.valve_0", "moisture_sensor": "sensor.m0", "duration_min": 1},
            {"entity_id": "switch.valve_1", "moisture_sensor": "sensor.m1", "duration_min": 1},
        ],
    }
    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")
    hass.states.get.side_effect = get_state

    open_results = {"switch.valve_0": False, "switch.valve_1": True}

    async def fake_evs(hass, eid, state, **kwargs):
        if state == "on":
            return open_results.get(eid, True)
        return True

    with patch("custom_components.ha_lawn_irrigation.irrigation.render_water_level", return_value=200.0), \
         patch("custom_components.ha_lawn_irrigation.irrigation.force_close_all", new_callable=AsyncMock, return_value=[]), \
         patch("custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state", side_effect=fake_evs):
        await run_irrigation(hass, call_data)
    # Should complete without exception
    final_call = hass.services.async_call.call_args_list[-1]
    msg = final_call[0][2]["message"]
    assert "complete" in msg.lower()
