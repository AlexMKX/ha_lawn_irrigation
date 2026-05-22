"""Tests for run_irrigation finally block behavior."""
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


async def test_force_close_all_called_in_finally(hass):
    call_data = {
        "water_level_sensor": "sensor.water_level",
        "water_level_min": 10.0,
        "zones": [{"entity_id": "switch.valve_0", "moisture_sensor": "sensor.m0"}],
    }

    def get_state(eid):
        if "valve" in eid:
            return mock_state("off")
        return mock_state("50")

    hass.states.get.side_effect = get_state
    with patch("custom_components.ha_lawn_irrigation.irrigation.read_water_level", return_value=200.0), \
         patch("custom_components.ha_lawn_irrigation.irrigation.force_close_all", new_callable=AsyncMock) as mock_fca:
        mock_fca.return_value = []
        with patch("custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state", new_callable=AsyncMock, side_effect=Exception("boom")):
            with pytest.raises(Exception, match="boom"):
                await run_irrigation(hass, call_data)
    mock_fca.assert_called_once()
    called_valve_ids = mock_fca.call_args[0][1]
    assert called_valve_ids == ["switch.valve_0"]
