"""Tests for distribute_water function."""
import pytest
from custom_components.ha_lawn_irrigation.irrigation import distribute_water


def test_empty_list():
    assert distribute_water([], 100) == []


def test_single_zone_gets_all():
    assert distribute_water([50.0], 100) == pytest.approx([100.0])


def test_two_zones_equal_moisture():
    result = distribute_water([50, 50], 100)
    assert result == pytest.approx([50.0, 50.0])


def test_two_zones_drier_gets_more():
    result = distribute_water([25, 75], 100)
    # zone 0 is drier, should get more water
    assert result[0] > result[1]


def test_two_zones_sum_to_total():
    result = distribute_water([25, 75], 100)
    assert sum(result) == pytest.approx(100.0)


def test_zero_moisture_uses_floor():
    # moisture=0 should use 0.01 floor, no division by zero
    result = distribute_water([0, 50], 100)
    assert len(result) == 2
    assert sum(result) == pytest.approx(100.0)
    # drier zone (0) gets more
    assert result[0] > result[1]


def test_all_zones_zero_moisture():
    result = distribute_water([0, 0, 0], 90)
    assert len(result) == 3
    assert sum(result) == pytest.approx(90.0)
    # all equal since all have same floor
    assert result[0] == pytest.approx(result[1])
    assert result[1] == pytest.approx(result[2])


def test_three_zones_sum_to_total():
    result = distribute_water([10, 50, 80], 300)
    assert sum(result) == pytest.approx(300.0)


def test_total_zero():
    result = distribute_water([50, 50], 0)
    assert result == pytest.approx([0.0, 0.0])


def test_high_moisture_values():
    result = distribute_water([90, 95], 100)
    assert sum(result) == pytest.approx(100.0)
    assert result[0] > result[1]  # drier gets more


def test_single_zone_zero_moisture():
    result = distribute_water([0], 100)
    assert result == pytest.approx([100.0])


def test_order_preserved():
    result = distribute_water([10, 50, 30], 100)
    assert len(result) == 3
    assert sum(result) == pytest.approx(100.0)
    # lowest moisture (index 0) should get most
    assert result[0] > result[2] > result[1]
