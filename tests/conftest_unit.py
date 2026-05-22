"""Unit test fixtures."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def hass():
    mock = MagicMock()
    mock.services.async_call = AsyncMock()
    mock.states.get = MagicMock(return_value=None)
    return mock


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    async def _no_sleep(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
