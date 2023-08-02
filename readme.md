# HA Lawn irrigation
The purpose of this addon is to manage the lawn irrigation valves in tandem with soil moisture sensors.

It distributes the irrigation time across the zones taking in account the soil moisture of each zone.

Configuration example:

```yaml
ha_lawn_irrigation:
  class: ha_lawn_irrigation
  module: ha_lawn_irrigation
  config:
    # minimum valve duration despite the moisture level in seconds
    min_duration_sec: 6
    # out of bound (when opened not by the addon) maximum valve open duration in seconds 
    max_duration_sec: 10
    zones:
      # zone1 configuration
      - valve: switch.out_lawn_zone1_valve #valve for zone 1
        moisture: sensor.out_lawn_sensor_zone1_soil_moisture # moisture sensor for zone 1
      - valve: switch.out_lawn_zone2_valve
        moisture: sensor.out_lawn_sensor_zone2_soil_moisture
      - valve: switch.out_lawn_zone3_valve
        moisture: sensor.out_lawn_sensor_zone3_soil_moisture
      - valve: switch.out_lawn_zone4_valve
        moisture: sensor.out_lawn_sensor_zone4_soil_moisture
      - valve: switch.out_lawn_zone5_valve
        moisture: sensor.out_lawn_sensor_zone5_soil_moisture
      - valve: switch.out_lawn_zone6_valve
        moisture: sensor.out_lawn_sensor_zone6_soil_moisture

```

To trigger irrigation send the event ```irrigate_lawn``` with parameter ```duration: <duration in seconds>```
