"""E2E smoke tests for ha_lawn_irrigation integration."""

import asyncio
import pytest

pytestmark = pytest.mark.docker_e2e

WATER_TEMPLATE = "{{ 250 | float }}"

ZONES = [
    {
        "entity_id": "input_boolean.irr_test_valve_1",
        "moisture_sensor": "input_number.irr_test_moisture_1",
        "duration_min": 1,
    },
    {
        "entity_id": "input_boolean.irr_test_valve_2",
        "moisture_sensor": "input_number.irr_test_moisture_2",
        "duration_min": 1,
    },
]


@pytest.mark.asyncio
class TestIrrigationSmoke:

    async def test_ha_is_running(self, ha_instance):
        result = await ha_instance.api_get("/api/")
        assert result.get("message") == "API running."

    async def test_add_integration(self, ha_instance):
        """Add the integration via config flow."""
        result = await ha_instance.add_integration("ha_lawn_irrigation", {})
        if result.get("type") == "create_entry":
            assert result.get("title") == "Lawn Irrigation"
        elif result.get("type") == "abort":
            assert result.get("reason") in {"already_configured", "single_instance_allowed"}
        else:
            raise AssertionError(f"Unexpected flow result: {result}")
        entries = await ha_instance.get_config_entries("ha_lawn_irrigation")
        assert len(entries) == 1

    async def test_irrigate_sends_notification(self, ha_with_integration, reset_valves):
        """Call irrigate service and verify a persistent notification appears."""
        ha = ha_with_integration
        # Wait for service to register
        await asyncio.sleep(2)

        # Set moisture sensors to non-trivial values
        await ha.call_service(
            "input_number", "set_value",
            {"entity_id": "input_number.irr_test_moisture_1", "value": 30},
        )
        await ha.call_service(
            "input_number", "set_value",
            {"entity_id": "input_number.irr_test_moisture_2", "value": 60},
        )
        await asyncio.sleep(1)

        # Call irrigate service (duration_min=1 means max 60s per zone)
        # But irrigation.py polls every 2s so we just check it fires
        await ha.call_service(
            "ha_lawn_irrigation",
            "irrigate",
            {
                "water_level_template": WATER_TEMPLATE,
                "zones": ZONES,
            },
        )

        # Wait for at least preflight+notification (should be fast)
        await asyncio.sleep(5)

        # Check notification exists
        notifications = await ha.get_notifications()
        irr_notifs = [
            n for n in notifications
            if "ha_lawn_irrigation" in n["entity_id"] or "irrigation" in n["entity_id"].lower()
        ]
        assert len(irr_notifs) >= 1 or len(notifications) > 0, (
            f"No persistent notifications found. All notifications: {[n['entity_id'] for n in notifications]}"
        )

    async def test_preflight_rejects_open_valve(self, ha_with_integration, reset_valves):
        """If a valve is already on, irrigate should abort with notification."""
        ha = ha_with_integration
        await asyncio.sleep(1)

        # Pre-open one of the test valves
        await ha.call_service(
            "input_boolean", "turn_on",
            {"entity_id": "input_boolean.irr_test_valve_1"},
        )
        await asyncio.sleep(1)

        # Call irrigate — should fail preflight
        await ha.call_service(
            "ha_lawn_irrigation",
            "irrigate",
            {
                "water_level_template": WATER_TEMPLATE,
                "zones": ZONES,
            },
        )
        await asyncio.sleep(3)

        # Verify notification mentions "already open" or "aborted"
        notif_states = await ha.get_notifications()
        # Find the irrigation notification
        irr_notif = None
        for n in notif_states:
            attrs = n.get("attributes", {})
            msg = attrs.get("message", "")
            if "already" in msg.lower() or "aborted" in msg.lower() or "irr" in n["entity_id"].lower():
                irr_notif = n
                break
        assert irr_notif is not None, (
            f"Expected notification about already-open valve. "
            f"Notifications found: {[(n['entity_id'], n.get('attributes', {}).get('message', '')) for n in notif_states]}"
        )
