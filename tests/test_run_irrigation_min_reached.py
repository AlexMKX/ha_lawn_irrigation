"""Water level drops to min mid-cycle → reason='min_reached', loop breaks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_min_reached_breaks_loop():
    hass = MagicMock()

    # initial 500, then immediately drop to 50 (below min=100)
    levels = iter([500.0, 500.0, 50.0, 50.0, 50.0, 50.0])
    last = [500.0]

    def water():
        try:
            v = next(levels)
            last[0] = v
            return v
        except StopIteration:
            return last[0]

    def states_get(eid):
        if eid == "sensor.water":
            return _state(str(water()))
        if eid.startswith("sensor.m"):
            return _state("30")
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

    assert any("min_reached" in m for m in captured)
    # z2 should not appear with a reason since loop broke
    assert not any("switch.z2: min_reached" in m or "switch.z2: target_reached" in m for m in captured)
