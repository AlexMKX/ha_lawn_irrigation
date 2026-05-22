"""Water never drops below target within cap → reason='safety_cap'."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_safety_cap_exhaust():
    hass = MagicMock()

    # Constant water at 1000, never reaches target.
    # preflight_done tracks whether preflight check has run (once per valve)
    preflight_done = [False]

    def states_get(eid):
        if eid == "sensor.water":
            return _state("1000")
        if eid.startswith("sensor.m"):
            return _state("30")
        if eid == "switch.z1":
            if not preflight_done[0]:
                preflight_done[0] = True
                return _state("off")  # preflight: valve is closed
            return _state("on")       # monitoring: valve stays open (never externally closed)
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
        "zone_duration_max_sec": 60,  # short cap
        "zones": [{"entity_id": "switch.z1", "moisture_sensor": "sensor.m1"}],
    }

    with patch(
        "custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state",
        new=AsyncMock(return_value=True),
    ):
        await run_irrigation(hass, call_data)

    assert any("safety_cap" in m for m in captured)
