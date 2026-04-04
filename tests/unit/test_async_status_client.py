"""Unit tests for AsyncStatusClient."""

from unittest.mock import AsyncMock

import pytest

from kibana.exceptions import AuthenticationException, AuthorizationException


class TestAsyncStatusClientInitialization:
    """Test AsyncStatusClient initialization."""

    @pytest.mark.asyncio
    async def test_status_client_initialization(self, mock_async_transport):
        """Test that AsyncStatusClient can be initialized with a parent client."""
        from kibana._async.client import AsyncKibana
        from kibana._async.client.status import AsyncStatusClient

        client = AsyncKibana(_transport=mock_async_transport)
        status_client = AsyncStatusClient(client)
        assert status_client._client is client


class TestAsyncStatusClientGetStatus:
    """Test AsyncStatusClient.get_status() method."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, mock_async_transport, mock_response):
        """Test successful status retrieval."""
        from kibana._async.client import AsyncKibana

        # Mock response
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "name": "kibana-test",
                    "uuid": "test-uuid-123",
                    "version": {
                        "number": "9.0.0",
                        "build_hash": "abc123",
                        "build_number": 12345,
                        "build_snapshot": False,
                    },
                    "status": {
                        "overall": {
                            "level": "available",
                            "summary": "All services are available",
                        },
                        "core": {
                            "elasticsearch": {
                                "level": "available",
                                "summary": "Elasticsearch is available",
                            },
                            "savedObjects": {
                                "level": "available",
                                "summary": "SavedObjects service is available",
                            },
                        },
                    },
                },
                status=200,
            )
        )

        # Execute
        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.status.get_status()

        # Verify
        assert result.body["name"] == "kibana-test"
        assert result.body["status"]["overall"]["level"] == "available"

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/status"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_status_degraded(self, mock_async_transport, mock_response):
        """Test status retrieval when Kibana is degraded."""
        from kibana._async.client import AsyncKibana

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "name": "kibana-test",
                    "uuid": "test-uuid-123",
                    "version": {"number": "9.0.0"},
                    "status": {
                        "overall": {
                            "level": "degraded",
                            "summary": "Some services are degraded",
                        },
                    },
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "degraded"

    @pytest.mark.asyncio
    async def test_get_status_unavailable(self, mock_async_transport, mock_response):
        """Test status retrieval when Kibana is unavailable."""
        from kibana._async.client import AsyncKibana

        # Note: Status API returns 200 even when status is unavailable
        # The status level is in the response body, not the HTTP status code
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "name": "kibana-test",
                    "uuid": "test-uuid-123",
                    "version": {"number": "9.0.0"},
                    "status": {
                        "overall": {
                            "level": "unavailable",
                            "summary": "Kibana is unavailable",
                        },
                    },
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "unavailable"


class TestAsyncStatusClientGetStats:
    """Test AsyncStatusClient.get_stats() method."""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, mock_async_transport, mock_response):
        """Test successful stats retrieval."""
        from kibana._async.client import AsyncKibana

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "kibana": {
                        "uuid": "test-uuid-123",
                        "name": "kibana-test",
                        "index": ".kibana",
                        "host": "localhost",
                        "transport_address": "localhost:5601",
                        "version": "9.0.0",
                        "snapshot": False,
                        "status": "green",
                    },
                    "process": {
                        "memory": {
                            "heap": {
                                "total_in_bytes": 1073741824,
                                "used_in_bytes": 536870912,
                                "size_limit": 1073741824,
                            },
                            "resident_set_size_in_bytes": 805306368,
                        },
                        "uptime_in_millis": 3600000,
                    },
                    "os": {
                        "platform": "linux",
                        "platformRelease": "5.10.0",
                        "load": {"1m": 1.5, "5m": 1.2, "15m": 1.0},
                        "memory": {
                            "total_in_bytes": 8589934592,
                            "free_in_bytes": 2147483648,
                            "used_in_bytes": 6442450944,
                        },
                    },
                    "response_times": {
                        "avg_in_millis": 50,
                        "max_in_millis": 500,
                    },
                    "requests": {
                        "total": 1000,
                        "disconnects": 5,
                    },
                    "concurrent_connections": 10,
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.status.get_stats()

        assert result.body["kibana"]["name"] == "kibana-test"
        assert result.body["process"]["uptime_in_millis"] == 3600000
        assert result.body["os"]["platform"] == "linux"

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/stats"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_stats_with_extended_metrics(
        self, mock_async_transport, mock_response
    ):
        """Test stats retrieval with extended metrics."""
        from kibana._async.client import AsyncKibana

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "kibana": {"uuid": "test-uuid-123", "name": "kibana-test"},
                    "process": {"uptime_in_millis": 3600000},
                    "metrics": {
                        "requests": {"total": 1000},
                        "collection_interval_in_millis": 5000,
                    },
                },
                status=200,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.status.get_stats()

        assert "metrics" in result.body
        assert result.body["metrics"]["collection_interval_in_millis"] == 5000


class TestAsyncStatusClientErrorHandling:
    """Test AsyncStatusClient error handling."""

    @pytest.mark.asyncio
    async def test_get_status_authentication_error(
        self, mock_async_transport, mock_response
    ):
        """Test get_status with authentication error."""
        from kibana._async.client import AsyncKibana

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 401,
                    "error": "Unauthorized",
                    "message": "Authentication required",
                },
                status=401,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthenticationException):
            await client.status.get_status()

    @pytest.mark.asyncio
    async def test_get_stats_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test get_stats with authorization error."""
        from kibana._async.client import AsyncKibana

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 403,
                    "error": "Forbidden",
                    "message": "Insufficient privileges",
                },
                status=403,
            )
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.status.get_stats()


class TestAsyncStatusClientIntegration:
    """Test AsyncStatusClient integration with main AsyncKibana client."""

    @pytest.mark.asyncio
    async def test_status_property_returns_status_client(self, mock_async_transport):
        """Test that client.status returns an AsyncStatusClient instance."""
        from kibana._async.client import AsyncKibana
        from kibana._async.client.status import AsyncStatusClient

        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.status, AsyncStatusClient)

    @pytest.mark.asyncio
    async def test_status_property_caching(self, mock_async_transport):
        """Test that status property returns the same instance."""
        from kibana._async.client import AsyncKibana

        client = AsyncKibana(_transport=mock_async_transport)
        status1 = client.status
        status2 = client.status
        assert status1 is status2
