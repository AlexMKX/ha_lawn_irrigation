from __future__ import annotations
import appdaemon.plugins.hass.hassapi as hass

import os
import sys
from appdaemon.__main__ import main
import queue
import asyncio
from typing import Any, ClassVar
from collections import deque
from statemachine import StateMachine, State
from config import Config

MY_EVENT = 'irrigate_lawn2'
APP: Any

if __name__ == '__main__':
    cd = os.path.join(os.path.dirname(__file__), '..')
    os.chdir(cd)
    sys.argv.extend(['-c', './', '-C', 'appdaemon-dev.yaml'])
    sys.exit(main())


class WorkItem(StateMachine):
    created = State('created', initial=True)
    start = State('start')
    open = State('open')
    opened = State('opened')
    close = State('close')
    closed = State('closed', final=True)
    do_work = (created.to(start) |
               start.to(open, validators="check_timeout") |
               open.to(opened, cond="is_open", validators="check_timeout") |
               opened.to(close, cond="can_close") |
               close.to(closed, cond="is_closed", validators="check_timeout"))
    state_timeout = 60

    async def on_enter_created(self):
        self._app.log(f"Entering 'created' state.")

    async def on_enter_start(self):
        async with asyncio.timeout(self._config.action_timeout_sec):
            while not self.is_closed():
                try:
                    self._app.error(f"Valve {self.zone.valve} is already open, closing it")
                    await self._app.call_service('homeassistant/turn_off', entity_id=self.zone.valve)
                    await asyncio.sleep(1)
                except Exception as e:
                    self._app.error(
                        f"Error {e} in {self.zone.valve} {self.zone.moisture} "
                        f"the valve status is {self.zone.valve_state}")
                    await asyncio.sleep(1)

    def on_enter_state(self, event, state):
        self._reset_timer(self.state_timeout)
        self._app.log(
            f"Entering '{state.id}' state from '{event}' event for {self.zone.valve} and {self.zone.moisture}.")

    async def cleanup(self):
        try:
            async with asyncio.timeout(self._config.action_timeout_sec):
                while not self.is_closed():
                    try:
                        self._app.log(f'Closing valve {self.zone.valve} during cleanup')
                        await self._app.call_service('homeassistant/turn_off', entity_id=self.zone.valve)
                        await asyncio.sleep(1)
                    except Exception as e:
                        self._app.error(
                            f"Error {e} in {self.zone.valve} {self.zone.moisture} "
                            f"the valve status is {self.zone.valve_state}")
                        await asyncio.sleep(1)
        except Exception as e:
            self._app.error(
                f"Error {e} in {self.zone.valve} {self.zone.moisture} "
                f"the valve status is {self.zone.valve_state}")
        finally:
            self._app.error(
                f"Error in {self.zone.valve} {self.zone.moisture} the valve status is {self.zone.valve_state}")

    def _reset_timer(self, deadline: int = 60):
        self._enter_time = asyncio.get_running_loop().time() + deadline

    def check_timeout(self):
        if self._expired:
            raise TimeoutError(f"Timeout in {self.zone.valve} in state {self.current_state}")

    async def on_enter_open(self):
        self._app.log("Opening valve")
        self._lower_bound = self._app.current - self.zone.height
        await self._app.call_service('homeassistant/turn_on', entity_id=self.zone.valve)

    async def on_enter_opened(self):
        self._app.log("Valve opened")
        self._reset_timer(self._config.max_duration_sec)

    async def on_enter_close(self):
        self._app.log("Closing valve")
        await self._app.call_service('homeassistant/turn_off', entity_id=self.zone.valve)

    def is_closed(self) -> bool:
        return self.zone.valve_state == "off"

    def can_close(self) -> bool:
        if self._expired:
            self._app.log("Closing valve because expired=True")
            return True
        i = self._app.current
        if i < self._lower_bound:
            self._app.log(f"Closing valve because current={i} < lower_bound={self._lower_bound}")
            return True
        return False

    @property
    def _expired(self) -> bool:
        return asyncio.get_running_loop().time() > self._enter_time

    def __init__(self, app: ha_lawn_irrigation, config: Config, zone: Config.ZoneConfig):
        super().__init__(allow_event_without_transition=True)
        self.zone: Config.ZoneConfig = zone
        self._lower_bound = None
        self._config = config
        self._app: ha_lawn_irrigation = app

    def is_open(self) -> bool:
        self._app.log(f"is_open {self._expired}")
        return "on" == self.zone.valve_state


class ha_lawn_irrigation(hass.Hass):
    # todo add retries on template
    # todo add ensure valves closed on start and on finish

    def __init__(self, *args):
        super().__init__(*args)
        self._pending = queue.Queue()
        self._lock = asyncio.Lock()
        self._settings: Config | None = None
        global APP
        APP = self
        self.event_handle = self.listen_event(self.irrigate, MY_EVENT)
        self.work_items = deque()
        self.work_items_lock = asyncio.Lock()

        self.run_every(self.worker, "now+2", 3)

    @property
    def current(self) -> float:
        return asyncio.get_running_loop().run_until_complete(self._async_current)

    @property
    async def _async_current(self):
        async with asyncio.timeout(self._settings.action_timeout_sec):
            while True:
                x = None
                try:
                    x = await self.render_template(self._settings.sensor_template)
                    rv = float(x)
                    return rv
                except:
                    self.error(
                        f"The template {self._settings.sensor_template} is unable to produce float output. Result is {x}")
                    await asyncio.sleep(1)

    async def irrigate(self, event_name, data, cbargs):
        self._settings = Config.model_validate(data['config'], context={'app': self})
        current = self.current
        self._settings.distribute_water(current)
        async with self.work_items_lock:
            for zone in self._settings.zones:
                if zone.moisture_state < 99:
                    self.work_items.append(WorkItem(self, self._settings, zone))

    async def worker(self, arg):
        async with self.work_items_lock:
            if self.work_items:
                work_item: WorkItem = self.work_items.popleft()
                try:
                    await work_item.send('do_work')
                    if not work_item.current_state in work_item.final_states:
                        self.work_items.appendleft(work_item)
                    else:
                        self.log(
                            f"Zone {work_item.zone.valve}/{work_item.zone.moisture_state} "
                            f"reached final state {work_item.current_state}")
                except Exception as e:
                    self.error(
                        f"Error in {work_item.zone.valve}/{work_item.zone.moisture_state} "
                        f"at state {work_item.current_state}: {e}")
                    await work_item.cleanup()
