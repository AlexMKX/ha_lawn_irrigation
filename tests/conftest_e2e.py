"""
Pytest fixtures for Docker-based E2E tests.

ha-test-kit handles provisioning and exports:
  - HA_BASE_URL
  - HASS_LONG_LIVED_TOKEN
"""

import asyncio
import json
import os

import aiohttp
import pytest_asyncio

HA_BASE_URL = os.environ.get("HA_BASE_URL", "http://homeassistant:8123").rstrip("/")
HASS_TOKEN = os.environ.get("HASS_LONG_LIVED_TOKEN", "")


class HAInstance:
    """Thin REST-API wrapper for E2E tests."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self._headers = {"Authorization": f"Bearer {token}"}

    def _connector(self) -> aiohttp.TCPConnector:
        resolver = aiohttp.resolver.ThreadedResolver()
        return aiohttp.TCPConnector(resolver=resolver)

    async def api_get(self, path: str) -> dict:
        async with (
            aiohttp.ClientSession(connector=self._connector()) as s,
            s.get(f"{self.base_url}{path}", headers=self._headers) as r,
        ):
            r.raise_for_status()
            return await r.json()

    async def api_post(self, path: str, json: dict | None = None) -> dict:
        async with (
            aiohttp.ClientSession(connector=self._connector()) as s,
            s.post(f"{self.base_url}{path}", headers=self._headers, json=json or {}) as r,
        ):
            r.raise_for_status()
            return await r.json()

    async def call_service(self, domain: str, service: str, data: dict | None = None) -> None:
        async with (
            aiohttp.ClientSession(connector=self._connector()) as s,
            s.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self._headers,
                json=data or {},
            ) as r,
        ):
            if r.status >= 400:
                text = await r.text()
                raise RuntimeError(f"Service call {domain}.{service} failed: {text}")

    async def get_state(self, entity_id: str) -> dict:
        return await self.api_get(f"/api/states/{entity_id}")

    async def get_states(self) -> list:
        return await self.api_get("/api/states")

    async def get_notifications(self) -> list:
        """Return all persistent notifications via WebSocket API (HA 2023.9+)."""
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
        async with aiohttp.ClientSession(connector=self._connector()) as s:
            async with s.ws_connect(ws_url) as ws:
                # Receive auth_required
                await ws.receive_json()
                # Send auth
                await ws.send_json({"type": "auth", "access_token": self.token})
                # Receive auth_ok
                msg = await ws.receive_json()
                if msg.get("type") != "auth_ok":
                    raise RuntimeError(f"WebSocket auth failed: {msg}")
                # Request notifications
                await ws.send_json({"id": 1, "type": "persistent_notification/get"})
                result = await ws.receive_json()
                if result.get("type") == "result" and result.get("success"):
                    notifs = result.get("result", [])
                    # Normalize to look like state dicts for test compatibility
                    return [
                        {
                            "entity_id": f"persistent_notification.{n['notification_id']}",
                            "attributes": {
                                "message": n.get("message", ""),
                                "title": n.get("title", ""),
                            },
                            "state": "notifying",
                        }
                        for n in notifs
                    ]
                return []

    async def get_config_entries(self, domain: str) -> list:
        entries = await self.api_get("/api/config/config_entries/entry")
        return [e for e in entries if e.get("domain") == domain]

    async def add_integration(self, domain: str, user_input: dict) -> dict:
        """Add an integration via config flow."""
        flow = await self.api_post(
            "/api/config/config_entries/flow",
            json={"handler": domain},
        )
        if flow.get("type") == "abort":
            return flow
        flow_id = flow.get("flow_id")
        if not flow_id:
            raise RuntimeError(f"Config flow init missing flow_id: {flow}")
        return await self.api_post(
            f"/api/config/config_entries/flow/{flow_id}",
            json=user_input,
        )


@pytest_asyncio.fixture(scope="session")
async def ha_instance() -> HAInstance:
    """Return an authenticated HAInstance."""
    assert HASS_TOKEN, (
        "HASS_LONG_LIVED_TOKEN is not set. "
        "Run tests via ha-test-kit (./ha-test-kit/run_e2e.sh) or set the env var manually."
    )
    return HAInstance(HA_BASE_URL, HASS_TOKEN)


@pytest_asyncio.fixture(scope="session")
async def ha_with_integration(ha_instance: HAInstance) -> HAInstance:
    """Ensure ha_lawn_irrigation integration is installed."""
    entries = await ha_instance.get_config_entries("ha_lawn_irrigation")
    if not entries:
        await ha_instance.add_integration("ha_lawn_irrigation", {})
        await asyncio.sleep(3)
    return ha_instance


@pytest_asyncio.fixture
async def reset_valves(ha_instance: HAInstance):
    """Reset test valves to off state before each test."""
    valves = [
        "input_boolean.irr_test_valve_1",
        "input_boolean.irr_test_valve_2",
        "input_boolean.irr_preflight_valve",
    ]
    for valve in valves:
        try:
            await ha_instance.call_service("input_boolean", "turn_off", {"entity_id": valve})
        except Exception:
            pass
    await asyncio.sleep(1)
    yield
    # Cleanup after test
    for valve in valves:
        try:
            await ha_instance.call_service("input_boolean", "turn_off", {"entity_id": valve})
        except Exception:
            pass
