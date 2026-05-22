"""Tests for run_irrigation zone-level behavior."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def mock_state(state_str):
    s = MagicMock()
    s.state = state_str
    return s


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    monkeypatch.setattr("custom_components.ha_lawn_irrigation.irrigation.asyncio.sleep", AsyncMock())


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
    final_call = hass.services.async_call.call_args_list[-1]
    msg = final_call[0][2]["message"]
    assert "complete" in msg.lower()
