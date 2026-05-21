"""Unit test fixtures."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from homeassistant.core import HomeAssistant

@pytest.fixture
def hass():
    mock = MagicMock(spec=HomeAssistant)
    mock.services.async_call = AsyncMock()
    mock.states.get = MagicMock(return_value=None)
    return mock
