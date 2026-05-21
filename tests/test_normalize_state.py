"""Tests for normalize_state function."""
import pytest
from unittest.mock import MagicMock
from custom_components.ha_lawn_irrigation.irrigation import normalize_state


def test_none_returns_none():
    assert normalize_state(None) is None


def test_string_on_lowercase():
    assert normalize_state("on") == "on"


def test_string_off_uppercase():
    assert normalize_state("OFF") == "off"


def test_string_mixed_case():
    assert normalize_state("Unknown") == "unknown"


def test_string_unavailable():
    assert normalize_state("unavailable") == "unavailable"


def test_empty_string():
    assert normalize_state("") == ""


def test_integer_zero():
    assert normalize_state(0) == "0"


def test_float_value():
    assert normalize_state(3.14) == "3.14"


def test_object_with_state_on():
    obj = MagicMock()
    obj.state = "on"
    assert normalize_state(obj) == "on"


def test_object_with_state_off_uppercase():
    obj = MagicMock()
    obj.state = "OFF"
    assert normalize_state(obj) == "off"


def test_object_with_state_numeric():
    obj = MagicMock()
    obj.state = "42"
    assert normalize_state(obj) == "42"


def test_object_uses_state_attr_not_str():
    obj = MagicMock()
    obj.state = "Active"
    result = normalize_state(obj)
    assert result == "active"


def test_string_numeric_zero():
    assert normalize_state("0") == "0"


def test_boolean_true():
    assert normalize_state(True) == "true"


def test_object_with_state_unavailable():
    obj = MagicMock()
    obj.state = "unavailable"
    assert normalize_state(obj) == "unavailable"
