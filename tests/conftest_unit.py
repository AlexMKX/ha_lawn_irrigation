"""Unit test fixtures."""
import pytest
from unittest.mock import MagicMock, AsyncMock
@pytest.fixture
def hass():
    mock = MagicMock()
    mock.services.async_call = AsyncMock()
    mock.states.get = MagicMock(return_value=None)
    return mock
