import appdaemon.plugins.hass.hassapi as hass
import threading

import os
import sys
from appdaemon.__main__ import main
from pydantic_settings import BaseSettings
from pydantic import Field
import pandas as pd
import queue

from typing import Any

if __name__ == '__main__':
    cd = os.path.join(os.path.dirname(__file__), '..')
    os.chdir(cd)
    sys.argv.extend(['-c', './', '-C', 'appdaemon-dev.yaml'])
    sys.exit(main())


class Config(BaseSettings):
    class ZoneConfig(BaseSettings):
        valve: str
        moisture: str

    zones: list[ZoneConfig] = Field()
    min_duration_sec: int = Field(60, description="Minimum duration of valve opening in seconds")
    max_duration_sec: int = Field(600, description="Minimum duration of valve opening in seconds")


class ir_data:

    def __init__(self, cfg: Config.ZoneConfig, hass: hass.Hass):
        self.cfg: Config.ZoneConfig = cfg
        self.factor: float
        self.valve_duration = 0
        self.deadline: threading.Timer = threading.Timer(interval=0, function=self.stop)
        self._lock: threading.Lock
        self.factor = 1.0
        self._hass = hass
        self._lock = threading.RLock()

    @property
    def moisture(self) -> float:
        return float(self._hass.get_state(self.cfg.moisture))

    @property
    def is_open(self) -> bool:
        return self._hass.get_state(self.cfg.valve) != 'off'

    def start(self):
        import time
        self._hass.log(f"Starting irrigation via {self.cfg.valve} for {self.valve_duration} seconds")
        while not self.is_open:
            self._hass.turn_on(self.cfg.valve)
            time.sleep(1)
            if not self.is_open:
                time.sleep(5)
        self._hass.log(f"Started irrigation via {self.cfg.valve} for {self.valve_duration} seconds")
        self.set_deadline(self.valve_duration)
        self.valve_duration = 0

    def set_deadline(self, duration: int):
        with self._lock:
            if self.deadline.is_alive():
                self._hass.log(f"Resetting deadline for {self.cfg.valve} to {self.valve_duration} seconds",
                               level="WARNING")
                self.deadline.cancel()
            if self.deadline:
                del self.deadline
            self.deadline = threading.Timer(interval=duration, function=self.stop)
            self.deadline.start()

    def stop(self):
        import time
        self._hass.log(f"Stopping irrigation via {self.cfg.valve}")
        while self.is_open:
            self._hass.turn_off(self.cfg.valve)
            time.sleep(1)
            if self.is_open:
                time.sleep(5)
        self.valve_duration = 0
        self._hass.log(f"Stopped irrigation via {self.cfg.valve}")


def distribute(inp: list[float], duration) -> list[float]:
    s = pd.Series(inp)
    mx = s.max()
    s = s.apply(lambda x: mx - x)
    factor = duration / s.sum()
    workseconds = [x * factor for x in s]
    return workseconds


class ha_lawn_irrigation(hass.Hass):

    def irrigate(self, event_name, data, cbargs):
        class event_config(BaseSettings):
            duration: int
            metadata: Any

        if event_name != 'irrigate_lawn':
            self.log(f'Unknown event {event_name}', severity='WARNING')
            return
        try:
            c: event_config = event_config(**data)
        except Exception as e:
            self.log(f'Invalid event data {data}', severity='ERROR')
            return
        self.log(f'Got irrigate_lawn event with duration {c.duration} seconds')
        with self._lock:
            min_duration = self._settings.min_duration_sec
            left = c.duration - min_duration * len(self._irdata)
            z = distribute([x.moisture for x in self._irdata], left)
            z = [x + min_duration for x in z]
            for x in range(len(self._irdata)):
                self._irdata[x].valve_duration = z[x]

    def sync_state(self, arg):
        if self._lock.locked():
            return
        with self._lock:
            open_valves = [x for x in self._irdata if x.is_open]
            for v in open_valves:
                # set deadline for out of bound running valves
                if not v.deadline.is_alive():
                    self.log(
                        f'Found {v.cfg.valve} is open without deadline. Setting deadline to {self._settings.max_duration_sec} seconds')
                    v.set_deadline(self._settings.max_duration_sec)
            # start irrigation if no valve is open
            open_valves = [x for x in self._irdata if x.is_open]
            if len(open_valves) > 0:
                stropen = ", ".join([x.cfg.valve for x in open_valves])
                #self.log(f"Open valves: {stropen} will not irrigate")
                return
            if len(open_valves) == 1:
                self.log(f"More than 1 valve open {open_valves}", level="WARING")
                return
            to_open = [x for x in self._irdata if x.valve_duration > 0]
            if len(to_open) == 0:
                return
            self.log(f"Starting irrigation for {to_open[0].cfg.valve} valves")
            to_open[0].start()

    def initialize(self):
        self._pending = queue.Queue()
        self._lock = threading.Lock()
        self._settings = Config.model_validate(self.app_config['ha_lawn_irrigation']['config'])
        self._irdata = [ir_data(x, self) for x in self._settings.zones]
        self.run_every(self.sync_state, "now+2", 3)
        self.listen_event(self.irrigate, "irrigate_lawn")
        pass
