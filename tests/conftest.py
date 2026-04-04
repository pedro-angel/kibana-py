"""Pytest configuration and fixtures for kibana-py tests."""

from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    AsyncTransport,
    ObjectApiResponse,
    Transport,
)


@pytest.fixture
def mock_transport():
    """Create a mock Transport instance for testing."""
    transport = Mock(spec=Transport)
    transport.perform_request = Mock()
    return transport


@pytest.fixture
def mock_async_transport():
    """Create a mock AsyncTransport instance for testing."""
    transport = Mock(spec=AsyncTransport)
    transport.perform_request = AsyncMock()
    transport.close = AsyncMock()
    return transport


@pytest.fixture
def mock_response():
    """Create a mock API response."""

    def _create_response(body=None, status=200, headers=None):
        if body is None:
            body = {}
        if headers is None:
            headers = {}

        meta = ApiResponseMeta(
            status=status,
            headers=headers,
            http_version="1.1",
            duration=0.1,
            node=None,
        )
        return ObjectApiResponse(body=body, meta=meta)

    return _create_response
