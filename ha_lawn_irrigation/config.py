from __future__ import annotations

import appdaemon.plugins.hass.hassapi as hass

from pydantic import Field, field_validator, ValidationInfo, BaseModel, model_validator
from typing import cast, Optional, Any, ClassVar

import queue
import asyncio
import nest_asyncio

nest_asyncio.apply()

#todo: rewrite to have the sensors either template or entity_id

class Config(BaseModel):
    sensor_template: str = Field(description='Sensor Template')
    _app: Any

    def model_post_init(self, __context: Any) -> None:
        self._app = __context['app']

    class ZoneConfig(BaseModel):
        valve: str
        moisture: str
        _app: hass.Hass
        height: Optional[float] = Field(None)
        done: Optional[bool] = Field(False)

        @property
        def valve_state(self) -> str:
            return asyncio.get_event_loop().run_until_complete(self._async_valve_state())

        async def _async_valve_state(self):
            #todo: rewrite to get timeout from config
            async with asyncio.timeout(180):
                try:
                    if (x := (await self._app.get_state(self.valve)).lower()) in ('on', 'off'):
                        return x
                    else:
                        await asyncio.sleep(1)
                except Exception as e:
                    await asyncio.sleep(1)

        @property
        def moisture_state(self) -> float:
            x = float(asyncio.get_event_loop().run_until_complete((self._async_moisture_state())))
            return x

        async def _async_moisture_state(self):
            #todo: rewrite to get timeout from config
            async with asyncio.timeout(180):
                while True:
                    try:
                        x = float(await self._app.get_state(self.moisture))
                        return x
                    except:
                        await asyncio.sleep(1)

        def model_post_init(self, __context: Any) -> None:
            self._app = __context['app']

    zones: list[ZoneConfig] = Field()
    min_duration_sec: int = Field(60, description="Minimum duration of valve opening in seconds")
    max_duration_sec: int = Field(600, description="Minimum duration of valve opening in seconds")
    action_timeout_sec: int = Field(120, description="The timeout to wait if entity is unavailable")

    @field_validator('zones', mode='before')
    @classmethod
    def _set_zones(cls, v, info: ValidationInfo):
        rv = []
        for x in v:
            try:
                rv.append(cls.ZoneConfig.model_validate(x, context=info.context))
            except Exception as e:
                info.context['app'].error(f'Error in zone {x}: {e}')
        return rv

    def distribute_water(self, total_water_height):
        # Adjust moisture_state to avoid division by zero and treat zero as lowest moisture
        adjusted_moisture_states = [max(zone.moisture_state, 0.01) for zone in
                                    self.zones]  # Using 0.01 as a minimal value

        # Calculate total of inverse adjusted moisture content for all zones
        total_inverse_moisture = sum(1 / moisture for moisture in adjusted_moisture_states)

        # Calculate water height to distribute to each zone based on adjusted moisture states
        for zone, adjusted_moisture in zip(self.zones, adjusted_moisture_states):
            inverse_moisture_factor = (1 / adjusted_moisture) / total_inverse_moisture
            water_height_for_zone = total_water_height * inverse_moisture_factor
            zone.height = water_height_for_zone
            print(f'Zone with adjusted moisture {adjusted_moisture} gets water of height: {water_height_for_zone}')
    # def distribute_water(self, total_water_height):
    #     # Calculate total of inverse moisture content for all zones.
    #     total_inverse_moisture = sum(1 / zone.moisture_state for zone in self.zones)
    #
    #     # Calculate water height to distribute to each zone
    #     for zone in self.zones:
    #         inverse_moisture_factor = (1 / zone.moisture_state) / total_inverse_moisture
    #         water_height_for_zone = total_water_height * inverse_moisture_factor
    #         zone.height = water_height_for_zone
    #         print(f'Zone with moisture {zone.moisture_state} gets water of height: {water_height_for_zone}')


event = """
config:
  sensor_template: "{{states('sensor.out_irr_tank_level_level')}}"
  max_duration_sec: 5
  zones:
   - valve: switch.out_irr_out_irr_relay_relay_0
     moisture: sensor.out_lawn_sensor_zone1_soil_moisture
   - valve: switch.out_irr_out_irr_relay_relay_1
     moisture: sensor.out_lawn_sensor_zone2_soil_moisture
   - valve: switch.out_irr_out_irr_relay_relay_2
     moisture: sensor.out_lawn_sensor_zone3_soil_moisture
   - valve: switch.out_irr_out_irr_relay_relay_3
     moisture: sensor.out_lawn_sensor_zone4_soil_moisture
   - valve: switch.out_irr_out_irr_relay_relay_4
     moisture: sensor.out_lawn_sensor_zone5_soil_moisture
   - valve: switch.out_irr_out_irr_relay_relay_5
     moisture: sensor.out_lawn_sensor_zone6_soil_moisture
     """
