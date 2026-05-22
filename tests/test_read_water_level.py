"""Tests for read_water_level helper."""

from unittest.mock import MagicMock

from custom_components.ha_lawn_irrigation.irrigation import read_water_level


def _hass_with_state(value):
    hass = MagicMock()
    state = MagicMock()
    state.state = value
    hass.states.get.return_value = state
    return hass


def test_read_water_level_numeric():
    hass = _hass_with_state("742.5")
    assert read_water_level(hass, "sensor.water") == 742.5


def test_read_water_level_integer_string():
    hass = _hass_with_state("1000")
    assert read_water_level(hass, "sensor.water") == 1000.0


def test_read_water_level_unknown_returns_none():
    hass = _hass_with_state("unknown")
    assert read_water_level(hass, "sensor.water") is None


def test_read_water_level_unavailable_returns_none():
    hass = _hass_with_state("unavailable")
    assert read_water_level(hass, "sensor.water") is None


def test_read_water_level_missing_state_returns_none():
    hass = MagicMock()
    hass.states.get.return_value = None
    assert read_water_level(hass, "sensor.water") is None


def test_read_water_level_non_numeric_returns_none():
    hass = _hass_with_state("not a number")
    assert read_water_level(hass, "sensor.water") is None
