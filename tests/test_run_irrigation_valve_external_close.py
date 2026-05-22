"""Valve closed externally mid-cycle → reason='externally_closed', next zone proceeds."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_valve_externally_closed():
    hass = MagicMock()

    # Water stays well above target so we never hit target/min naturally.
    # tick tracks calls to states_get("switch.z1"):
    #   tick==1: preflight check → "off" (valve is closed, ok to proceed)
    #   tick==2,3: monitoring → "on" (valve opened)
    #   tick>=4: monitoring → "off" (externally closed)
    tick = [0]

    def states_get(entity_id):
        if entity_id == "sensor.water":
            return _state("1000")
        if entity_id.startswith("sensor.m"):
            return _state("30")
        if entity_id == "switch.z1":
            tick[0] += 1
            if tick[0] == 1:
                return _state("off")   # preflight: valve is closed
            if tick[0] <= 3:
                return _state("on")    # monitoring: valve opened
            return _state("off")       # monitoring: externally closed
        return _state("off")

    hass.states.get.side_effect = states_get
    captured = []

    async def cap(domain, service, data, blocking=False):
        if domain == "persistent_notification":
            captured.append(data["message"])

    hass.services.async_call = AsyncMock(side_effect=cap)

    call_data = {
        "water_level_sensor": "sensor.water",
        "water_level_min": 100,
        "zone_duration_max_sec": 60,
        "zones": [
            {"entity_id": "switch.z1", "moisture_sensor": "sensor.m1"},
            {"entity_id": "switch.z2", "moisture_sensor": "sensor.m2"},
        ],
    }

    with patch(
        "custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state",
        new=AsyncMock(return_value=True),
    ):
        await run_irrigation(hass, call_data)

    assert any("externally_closed" in m for m in captured)
