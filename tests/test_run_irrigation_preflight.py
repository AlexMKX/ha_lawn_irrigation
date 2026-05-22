"""Input valve already on → abort with notification."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_preflight_rejects_open_valve():
    hass = MagicMock()

    def states_get(eid):
        if eid == "switch.z1":
            return _state("on")
        if eid.startswith("sensor.m"):
            return _state("30")
        if eid == "sensor.water":
            return _state("1000")
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
        "zones": [{"entity_id": "switch.z1", "moisture_sensor": "sensor.m1"}],
    }

    await run_irrigation(hass, call_data)
    assert any("already open" in m for m in captured)
