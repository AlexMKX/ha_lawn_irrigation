"""Basic happy-path test for run_irrigation v2."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_run_irrigation_basic_three_zones():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()

    # initial water level 1000, drops to 700 after each zone
    levels = iter([1000.0, 1000.0, 700.0, 400.0, 100.0])
    valve_states = {"switch.z1": "off", "switch.z2": "off", "switch.z3": "off"}

    def states_get(entity_id):
        if entity_id == "sensor.water":
            try:
                return _state(str(next(levels)))
            except StopIteration:
                return _state("100.0")
        if entity_id.startswith("sensor.m"):
            return _state("30")
        if entity_id.startswith("switch."):
            return _state(valve_states[entity_id])
        return None

    hass.states.get.side_effect = states_get

    call_data = {
        "water_level_sensor": "sensor.water",
        "water_level_min": 50,
        "zone_duration_max_sec": 600,
        "zones": [
            {"entity_id": "switch.z1", "moisture_sensor": "sensor.m1"},
            {"entity_id": "switch.z2", "moisture_sensor": "sensor.m2"},
            {"entity_id": "switch.z3", "moisture_sensor": "sensor.m3"},
        ],
    }

    with patch(
        "custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state",
        new=AsyncMock(return_value=True),
    ):
        await run_irrigation(hass, call_data)

    # at least one notification was sent
    calls = [c for c in hass.services.async_call.call_args_list if c.args[0] == "persistent_notification"]
    assert len(calls) >= 1
