"""Unit tests for AsyncUptimeClient."""

from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.uptime import AsyncUptimeClient
from kibana.exceptions import AuthorizationException, NotFoundError


def _settings_body() -> dict:
    """Kibana 9.4.3 GET/PUT /api/uptime/settings response body."""
    return {
        "heartbeatIndices": "heartbeat-*",
        "certExpirationThreshold": 30,
        "certAgeThreshold": 730,
        "defaultConnectors": [],
        "defaultEmail": {"to": [], "cc": [], "bcc": []},
    }


def _mock_ok(mock_async_transport, body: dict) -> None:
    """Configure the mock transport to return a 200 ObjectApiResponse."""
    mock_async_transport.perform_request = AsyncMock(
        return_value=ObjectApiResponse(
            body=body,
            meta=Mock(status=200, headers={}),
        )
    )


class TestAsyncUptimeClientInitialization:
    """Test AsyncUptimeClient initialization."""

    @pytest.mark.asyncio
    async def test_uptime_client_initialization(self, mock_async_transport):
        """Test that AsyncUptimeClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        uptime_client = AsyncUptimeClient(client)
        assert uptime_client._client is client

    @pytest.mark.asyncio
    async def test_uptime_property_returns_uptime_client(self, mock_async_transport):
        """Test that client.uptime returns an AsyncUptimeClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.uptime, AsyncUptimeClient)

    @pytest.mark.asyncio
    async def test_uptime_property_caching(self, mock_async_transport):
        """Test that the uptime property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.uptime is client.uptime


class TestAsyncUptimeClientGetSettings:
    """Test AsyncUptimeClient.get_settings() method."""

    @pytest.mark.asyncio
    async def test_get_settings_success(self, mock_async_transport):
        """Test successful settings retrieval."""
        _mock_ok(mock_async_transport, _settings_body())

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.uptime.get_settings()

        assert result.body["heartbeatIndices"] == "heartbeat-*"
        assert result.body["certExpirationThreshold"] == 30
        assert result.body["certAgeThreshold"] == 730
        assert result.body["defaultConnectors"] == []
        assert result.body["defaultEmail"] == {"to": [], "cc": [], "bcc": []}

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/uptime/settings"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_settings_space_scoped(self, mock_async_transport):
        """Test that space_id prefixes the path with /s/{space_id}."""
        _mock_ok(mock_async_transport, _settings_body())

        client = AsyncKibana(_transport=mock_async_transport)
        await client.uptime.get_settings(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/s/marketing/api/uptime/settings"


class TestAsyncUptimeClientUpdateSettings:
    """Test AsyncUptimeClient.update_settings() method."""

    @pytest.mark.asyncio
    async def test_update_settings_all_fields(self, mock_async_transport):
        """Test full update: snake_case args map to camelCase body keys."""
        body = _settings_body()
        body.update(
            {
                "heartbeatIndices": "heartbeat-8*",
                "certExpirationThreshold": 14,
                "certAgeThreshold": 365,
                "defaultConnectors": ["conn-1", "conn-2"],
                "defaultEmail": {"to": ["ops@example.com"], "cc": [], "bcc": []},
            }
        )
        _mock_ok(mock_async_transport, body)

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.uptime.update_settings(
            heartbeat_indices="heartbeat-8*",
            cert_expiration_threshold=14,
            cert_age_threshold=365,
            default_connectors=["conn-1", "conn-2"],
            default_email={"to": ["ops@example.com"], "cc": [], "bcc": []},
        )

        assert result.body["heartbeatIndices"] == "heartbeat-8*"
        assert result.body["defaultConnectors"] == ["conn-1", "conn-2"]

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/uptime/settings"
        assert call_kwargs["body"] == {
            "heartbeatIndices": "heartbeat-8*",
            "certExpirationThreshold": 14,
            "certAgeThreshold": 365,
            "defaultConnectors": ["conn-1", "conn-2"],
            "defaultEmail": {"to": ["ops@example.com"], "cc": [], "bcc": []},
        }

    @pytest.mark.asyncio
    async def test_update_settings_partial_body_only_provided_keys(
        self, mock_async_transport
    ):
        """Test partial update: omitted args are excluded from the body."""
        _mock_ok(mock_async_transport, _settings_body())

        client = AsyncKibana(_transport=mock_async_transport)
        await client.uptime.update_settings(cert_age_threshold=365)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/uptime/settings"
        assert call_kwargs["body"] == {"certAgeThreshold": 365}

    @pytest.mark.asyncio
    async def test_update_settings_space_scoped(self, mock_async_transport):
        """Test that space_id prefixes the path with /s/{space_id}."""
        _mock_ok(mock_async_transport, _settings_body())

        client = AsyncKibana(_transport=mock_async_transport)
        await client.uptime.update_settings(
            heartbeat_indices="heartbeat-*",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/s/marketing/api/uptime/settings"
        assert call_kwargs["body"] == {"heartbeatIndices": "heartbeat-*"}


class TestAsyncUptimeClientErrorHandling:
    """Test AsyncUptimeClient error handling."""

    @pytest.mark.asyncio
    async def test_get_settings_not_found_error(self, mock_async_transport):
        """Test 404 error mapping to NotFoundError."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=ObjectApiResponse(
                body={
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Not Found",
                },
                meta=Mock(status=404, headers={}),
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.uptime.get_settings()

    @pytest.mark.asyncio
    async def test_update_settings_authorization_error(self, mock_async_transport):
        """Test 403 error mapping to AuthorizationException."""
        mock_async_transport.perform_request = AsyncMock(
            return_value=ObjectApiResponse(
                body={
                    "statusCode": 403,
                    "error": "Forbidden",
                    "message": "Insufficient privileges",
                },
                meta=Mock(status=403, headers={}),
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.uptime.update_settings(cert_age_threshold=365)
