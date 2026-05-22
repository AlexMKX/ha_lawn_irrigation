"""ha_lawn_irrigation integration."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_IRRIGATE
from .irrigation import run_irrigation

_LOGGER = logging.getLogger(__name__)

IRRIGATE_SCHEMA = vol.Schema(
    {
        vol.Required("water_level_template"): cv.string,
        vol.Required("zones"): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required("entity_id"): cv.entity_id,
                        vol.Required("moisture_sensor"): cv.entity_id,
                        vol.Optional("duration_min", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                    }
                )
            ],
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ha_lawn_irrigation from a config entry."""

    async def handle_irrigate(call: ServiceCall) -> None:
        """Handle the irrigate service call."""
        hass.async_create_task(run_irrigation(hass, dict(call.data)))

    hass.services.async_register(DOMAIN, SERVICE_IRRIGATE, handle_irrigate, schema=IRRIGATE_SCHEMA)
    _LOGGER.info("ha_lawn_irrigation: service %s.%s registered", DOMAIN, SERVICE_IRRIGATE)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_IRRIGATE)
    return True
