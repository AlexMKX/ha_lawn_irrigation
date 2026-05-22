"""Verify per-zone rebalancing recomputes budget over remaining zones."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_lawn_irrigation.irrigation import run_irrigation


def _state(value):
    s = MagicMock()
    s.state = value
    return s


@pytest.mark.asyncio
async def test_rebalance_after_first_zone_overshoots():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()

    # Zone1 sequence:
    #   - preflight check: 1000 (initial)
    #   - rebalance read: 1000, budget=900, heights=[450,450], target=550
    #   - monitoring tick1: 549 → target_reached
    # Zone2 sequence:
    #   - rebalance read: 500, budget=400 (only 1 zone left), heights=[400], target=100
    #   - monitoring tick1: 99 → min_reached (current <= water_level_min)
    level_sequence = [1000.0, 1000.0, 549.0, 500.0, 99.0]
    it = iter(level_sequence)
    last = [1000.0]

    def water_value():
        try:
            v = next(it)
            last[0] = v
            return v
        except StopIteration:
            return last[0]

    def states_get(entity_id):
        if entity_id == "sensor.water":
            return _state(str(water_value()))
        if entity_id.startswith("sensor.m"):
            return _state("30")
        return _state("off")

    hass.states.get.side_effect = states_get

    call_data = {
        "water_level_sensor": "sensor.water",
        "water_level_min": 100,
        "zone_duration_max_sec": 60,
        "zones": [
            {"entity_id": "switch.z1", "moisture_sensor": "sensor.m1"},
            {"entity_id": "switch.z2", "moisture_sensor": "sensor.m2"},
        ],
    }

    captured = []

    async def _capture_notification(domain, service, data, blocking=False):
        if domain == "persistent_notification":
            captured.append(data["message"])

    hass.services.async_call.side_effect = _capture_notification

    with patch(
        "custom_components.ha_lawn_irrigation.irrigation.ensure_valve_state",
        new=AsyncMock(return_value=True),
    ):
        await run_irrigation(hass, call_data)

    final = captured[-1]
    # Zone2 rebalanced: level=500, min=100, budget=400, 1 remaining zone → height=400.00
    assert "height=400.00" in final
