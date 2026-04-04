"""Unit tests for AsyncBaseClient."""

from unittest.mock import AsyncMock, patch

import pytest
from elastic_transport import HttpHeaders

from kibana.exceptions import (
    ApiError,
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class TestAsyncBaseClientInitialization:
    """Tests for AsyncBaseClient initialization."""

    @pytest.mark.asyncio
    async def test_init_with_transport(self, mock_async_transport):
        """Test AsyncBaseClient initialization with a Transport instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)

        assert client._transport is mock_async_transport
        assert isinstance(client._headers, HttpHeaders)


class TestAsyncPerformRequest:
    """Tests for AsyncBaseClient.perform_request() method."""

    @pytest.mark.asyncio
    async def test_perform_request_calls_transport(
        self, mock_async_transport, mock_response
    ):
        """Test that perform_request calls transport.perform_request."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        response = await client.perform_request("GET", "/api/status")

        mock_async_transport.perform_request.assert_called_once()
        assert response.body == {"result": "success"}

    @pytest.mark.asyncio
    async def test_perform_request_with_params(
        self, mock_async_transport, mock_response
    ):
        """Test perform_request with query parameters."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"items": []}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        await client.perform_request(
            "GET", "/api/saved_objects/_find", params={"type": "dashboard"}
        )

        call_args = mock_async_transport.perform_request.call_args
        # Params should be encoded in the target URL
        assert "target" in call_args[1]
        assert "type=dashboard" in call_args[1]["target"]

    @pytest.mark.asyncio
    async def test_perform_request_with_body(self, mock_async_transport, mock_response):
        """Test perform_request with request body."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"id": "test-id"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        body_data = {"attributes": {"title": "Test"}}
        await client.perform_request(
            "POST", "/api/saved_objects/dashboard", body=body_data
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["body"] == body_data

    @pytest.mark.asyncio
    async def test_perform_request_with_headers(
        self, mock_async_transport, mock_response
    ):
        """Test perform_request with custom headers."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        headers = {"X-Custom-Header": "value"}
        await client.perform_request("GET", "/api/status", headers=headers)

        call_args = mock_async_transport.perform_request.call_args
        assert "headers" in call_args[1]

    @pytest.mark.asyncio
    async def test_perform_request_processes_successful_response(
        self, mock_async_transport, mock_response
    ):
        """Test that successful responses are returned without raising exceptions."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"status": "green"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        response = await client.perform_request("GET", "/api/status")

        assert response.body == {"status": "green"}
        assert response.meta.status == 200


class TestAsyncErrorResponseProcessing:
    """Tests for async error response processing."""

    @pytest.mark.asyncio
    async def test_400_raises_bad_request_error(
        self, mock_async_transport, mock_response
    ):
        """Test that 400 status raises BadRequestError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Invalid request"}, status=400)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(BadRequestError) as exc_info:
            await client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 400
        assert exc_info.value.body == {"error": "Invalid request"}

    @pytest.mark.asyncio
    async def test_401_raises_authentication_exception(
        self, mock_async_transport, mock_response
    ):
        """Test that 401 status raises AuthenticationException."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Unauthorized"}, status=401)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(AuthenticationException) as exc_info:
            await client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_403_raises_authorization_exception(
        self, mock_async_transport, mock_response
    ):
        """Test that 403 status raises AuthorizationException."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Forbidden"}, status=403)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException) as exc_info:
            await client.perform_request("GET", "/api/spaces/space")

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_404_raises_not_found_error(
        self, mock_async_transport, mock_response
    ):
        """Test that 404 status raises NotFoundError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError) as exc_info:
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_409_raises_conflict_error(self, mock_async_transport, mock_response):
        """Test that 409 status raises ConflictError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Conflict"}, status=409)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(ConflictError) as exc_info:
            await client.perform_request("POST", "/api/saved_objects/dashboard")

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_500_raises_generic_api_error(
        self, mock_async_transport, mock_response
    ):
        """Test that unmapped status codes raise generic ApiError."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": "Internal server error"}, status=500
            )
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(ApiError) as exc_info:
            await client.perform_request("GET", "/api/status")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_error_includes_response_meta(
        self, mock_async_transport, mock_response
    ):
        """Test that errors include response metadata."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError) as exc_info:
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert exc_info.value.meta is not None
        assert exc_info.value.meta.status == 404


class TestAsyncOptionsMethod:
    """Tests for AsyncBaseClient.options() method."""

    @pytest.mark.asyncio
    async def test_options_creates_new_instance(self, mock_async_transport):
        """Test that options() creates a new client instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=30)

        assert new_client is not client
        assert isinstance(new_client, AsyncBaseClient)

    @pytest.mark.asyncio
    async def test_options_with_api_key_string(self, mock_async_transport):
        """Test options() stores API key string on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(api_key="test_api_key")

        assert new_client is not client
        assert new_client._api_key == "test_api_key"

    @pytest.mark.asyncio
    async def test_options_with_api_key_tuple(self, mock_async_transport):
        """Test options() stores API key tuple on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(api_key=("id", "key"))

        assert new_client is not client
        assert new_client._api_key == ("id", "key")

    @pytest.mark.asyncio
    async def test_options_with_basic_auth(self, mock_async_transport):
        """Test options() stores basic auth on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(basic_auth=("username", "password"))

        assert new_client is not client
        assert new_client._basic_auth == ("username", "password")

    @pytest.mark.asyncio
    async def test_options_with_bearer_auth(self, mock_async_transport):
        """Test options() stores bearer token on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(bearer_auth="bearer_token")

        assert new_client is not client
        assert new_client._bearer_auth == "bearer_token"

    @pytest.mark.asyncio
    async def test_options_with_headers(self, mock_async_transport):
        """Test options() stores custom headers on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(headers={"X-Custom": "value"})

        assert new_client is not client
        assert new_client._custom_headers == {"X-Custom": "value"}

    @pytest.mark.asyncio
    async def test_options_with_request_timeout(self, mock_async_transport):
        """Test options() stores request timeout on new client."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=60.0)

        assert new_client is not client
        assert new_client._request_timeout == 60.0

    @pytest.mark.asyncio
    async def test_options_preserves_transport(self, mock_async_transport):
        """Test that options() preserves the transport instance."""
        from kibana._async.client._base import AsyncBaseClient

        client = AsyncBaseClient(_transport=mock_async_transport)
        new_client = client.options(request_timeout=30)

        # Both should reference the same transport
        assert new_client._transport is mock_async_transport


class TestAsyncLogging:
    """Tests for async logging functionality."""

    @pytest.mark.asyncio
    @patch("kibana._async.client._base.logger")
    async def test_perform_request_logs_debug(
        self, mock_logger, mock_async_transport, mock_response
    ):
        """Test that perform_request logs at DEBUG level."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"result": "success"}, status=200)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)
        await client.perform_request("GET", "/api/status")

        # Verify debug logging was called
        assert mock_logger.debug.called

    @pytest.mark.asyncio
    @patch("kibana._async.client._base.logger")
    async def test_error_response_logs_at_debug_level(
        self, mock_logger, mock_async_transport, mock_response
    ):
        """Test that error responses are logged at DEBUG level."""
        from kibana._async.client._base import AsyncBaseClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={"error": "Not found"}, status=404)
        )

        client = AsyncBaseClient(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.perform_request("GET", "/api/saved_objects/dashboard/missing")

        assert mock_logger.debug.called
