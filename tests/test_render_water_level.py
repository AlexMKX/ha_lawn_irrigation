"""Tests for render_water_level function."""
import pytest
from unittest.mock import patch, MagicMock
from custom_components.ha_lawn_irrigation.irrigation import render_water_level


def test_valid_template_returns_float(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = "150.5"
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        result = render_water_level(hass, "{{ states('sensor.water') }}")
    assert result == pytest.approx(150.5)


def test_async_render_called_with_parse_result_false(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = "100"
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        render_water_level(hass, "{{ 100 }}")
    mock_tmpl.async_render.assert_called_once_with(parse_result=False)


def test_hass_set_on_template(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = "100"
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        render_water_level(hass, "{{ 100 }}")
    assert mock_tmpl.hass == hass


def test_cv_template_called_with_template_str(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = "100"
    template_str = "{{ states('sensor.water') }}"
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl) as mock_cv:
        render_water_level(hass, template_str)
    mock_cv.assert_called_once_with(template_str)


def test_non_numeric_render_returns_none(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = "unavailable"
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        result = render_water_level(hass, "{{ states('sensor.water') }}")
    assert result is None


def test_empty_render_returns_none(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = ""
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        result = render_water_level(hass, "")
    assert result is None


def test_none_render_returns_none(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.return_value = None
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        result = render_water_level(hass, "{{ none }}")
    assert result is None


def test_exception_returns_none(hass):
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", side_effect=Exception("bad template")):
        result = render_water_level(hass, "{{ bad }}")
    assert result is None


def test_render_exception_returns_none(hass):
    mock_tmpl = MagicMock()
    mock_tmpl.async_render.side_effect = Exception("render error")
    with patch("custom_components.ha_lawn_irrigation.irrigation.cv.template", return_value=mock_tmpl):
        result = render_water_level(hass, "{{ error }}")
    assert result is None
