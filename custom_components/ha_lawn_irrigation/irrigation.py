"""Lawn irrigation core logic for ha_lawn_irrigation integration."""

import asyncio
import logging

from .const import NOTIFICATION_ID

_LOGGER = logging.getLogger(__name__)

RETRY_BACKOFF = [1, 2, 4, 8, 16]
TICK_SEC = 2


def normalize_state(value) -> "str | None":
    """Normalize a state value to lowercase string or None."""
    if value is None:
        return None
    if hasattr(value, "state"):
        return str(value.state).lower()
    return str(value).lower()


def distribute_water(moisture_values: list, total: float) -> list:
    """Distribute total water inverse-proportionally to moisture values."""
    if not moisture_values:
        return []
    adjusted = [max(m, 0.01) for m in moisture_values]
    weights = [1.0 / m for m in adjusted]
    weight_sum = sum(weights)
    return [total * w / weight_sum for w in weights]


def read_water_level(hass, entity_id: str):
    """Read a numeric sensor state; return float or None on missing/non-numeric."""
    raw = hass.states.get(entity_id)
    norm = normalize_state(raw)
    if norm in (None, "unknown", "unavailable", "none", ""):
        return None
    try:
        return float(norm)
    except (TypeError, ValueError):
        _LOGGER.debug("read_water_level: non-numeric %r for %s", norm, entity_id)
        return None


async def ensure_valve_state(hass, entity_id: str, desired_state: str, retries: list = None) -> bool:
    """Ensure a valve entity reaches the desired state with retry backoff."""
    if retries is None:
        retries = RETRY_BACKOFF
    if desired_state not in ("on", "off"):
        raise ValueError(f"desired_state must be 'on' or 'off', got {desired_state!r}")

    current = normalize_state(hass.states.get(entity_id))
    if current == desired_state:
        return True

    service = "turn_on" if desired_state == "on" else "turn_off"

    for delay in retries:
        try:
            await hass.services.async_call(
                "homeassistant",
                service,
                {"entity_id": entity_id},
                blocking=False,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Service call failed for %s: %s", entity_id, exc)

        await asyncio.sleep(delay)

        current = normalize_state(hass.states.get(entity_id))
        if current == desired_state:
            return True

    _LOGGER.error("Failed to set %s to %s after all retries", entity_id, desired_state)
    return False


async def force_close_all(hass, zone_entities: list) -> list:
    """Force-close all valves; return list of entity_ids that failed to close."""
    failed = []
    for entity_id in zone_entities:
        success = await ensure_valve_state(hass, entity_id, "off")
        if not success:
            failed.append(entity_id)
    return failed


async def _send_notification(hass, message: str, title: str = "Lawn Irrigation") -> None:
    """Send a persistent notification via HA services."""
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "message": message,
            "title": title,
            "notification_id": NOTIFICATION_ID,
        },
        blocking=True,
    )


async def run_irrigation(hass, call_data: dict) -> None:
    """Execute v2 irrigation sequence."""
    water_level_sensor = call_data["water_level_sensor"]
    water_level_min = float(call_data["water_level_min"])
    zone_duration_max_sec = int(call_data.get("zone_duration_max_sec", 600))
    zones = call_data["zones"]

    all_valve_ids = [z["entity_id"] for z in zones]

    # Preflight: ensure no valve is already open
    for zone in zones:
        entity_id = zone["entity_id"]
        state = normalize_state(hass.states.get(entity_id))
        if state == "on":
            await _send_notification(
                hass,
                f"Irrigation aborted: valve {entity_id} is already open.",
            )
            return

    # Collect moisture readings into valid_zones [(entity_id, moisture)]
    valid_zones = []
    for zone in zones:
        raw = hass.states.get(zone["moisture_sensor"])
        norm = normalize_state(raw)
        try:
            moisture = float(norm)
        except (TypeError, ValueError):
            _LOGGER.warning("Invalid moisture for %s: %s", zone["moisture_sensor"], norm)
            continue
        valid_zones.append((zone["entity_id"], moisture))

    if not valid_zones:
        await _send_notification(hass, "Irrigation aborted: no valid moisture data.")
        return

    initial_level = read_water_level(hass, water_level_sensor)
    if initial_level is None or initial_level <= water_level_min:
        await _send_notification(
            hass,
            f"Irrigation aborted: insufficient water (level={initial_level}, min={water_level_min}).",
        )
        return

    await _send_notification(hass, f"Irrigation started: {len(valid_zones)} zone(s).")

    remaining_moistures = [m for (_, m) in valid_zones]
    summary_lines = []

    try:
        for entity_id, moisture in valid_zones:
            # Rebalance for remaining zones
            level = read_water_level(hass, water_level_sensor)
            if level is None or level <= water_level_min:
                summary_lines.append(f"{entity_id}: skipped (level={level})")
                remaining_moistures.pop(0)
                break

            budget = level - water_level_min
            heights = distribute_water(remaining_moistures, budget)
            height = heights[0]
            target_level = level - height

            opened = await ensure_valve_state(hass, entity_id, "on")
            if not opened:
                summary_lines.append(f"{entity_id}: failed to open")
                remaining_moistures.pop(0)
                continue

            elapsed = 0
            reason = "safety_cap"
            while elapsed < zone_duration_max_sec:
                await asyncio.sleep(TICK_SEC)
                elapsed += TICK_SEC

                current = read_water_level(hass, water_level_sensor)
                if current is None:
                    continue
                if current <= water_level_min:
                    reason = "min_reached"
                    break
                if current <= target_level:
                    reason = "target_reached"
                    break

                valve_state = normalize_state(hass.states.get(entity_id))
                if valve_state == "off":
                    reason = "externally_closed"
                    break

            await ensure_valve_state(hass, entity_id, "off")
            summary_lines.append(f"{entity_id}: {reason} (moisture={moisture:.1f}, height={height:.2f})")
            remaining_moistures.pop(0)

            if reason == "min_reached":
                break
    finally:
        failed = await force_close_all(hass, all_valve_ids)
        if failed:
            _LOGGER.error("Failed to close valves: %s", failed)
            summary_lines.append(f"failed_to_close={failed}")

    summary = "\n".join(summary_lines) if summary_lines else "No zones irrigated."
    await _send_notification(hass, f"Irrigation complete:\n{summary}")
