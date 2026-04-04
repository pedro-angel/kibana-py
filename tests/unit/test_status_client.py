"""Unit tests for StatusClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.status import StatusClient


class TestStatusClientInitialization:
    """Test StatusClient initialization."""

    def test_status_client_initialization(self, mock_transport):
        """Test that StatusClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        status_client = StatusClient(client)
        assert status_client._client is client


class TestStatusClientGetStatus:
    """Test StatusClient.get_status() method."""

    def test_get_status_success(self, mock_transport):
        """Test successful status retrieval."""
        # Mock response
        mock_response = ObjectApiResponse(
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
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        # Execute
        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        # Verify
        assert result.body["name"] == "kibana-test"
        assert result.body["status"]["overall"]["level"] == "available"

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/status"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_status_degraded(self, mock_transport):
        """Test status retrieval when Kibana is degraded."""
        mock_response = ObjectApiResponse(
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
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "degraded"

    def test_get_status_unavailable(self, mock_transport):
        """Test status retrieval when Kibana is unavailable."""
        # Note: Status API returns 200 even when status is unavailable
        # The status level is in the response body, not the HTTP status code
        mock_response = ObjectApiResponse(
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
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "unavailable"


class TestStatusClientGetStats:
    """Test StatusClient.get_stats() method."""

    def test_get_stats_success(self, mock_transport):
        """Test successful stats retrieval."""
        mock_response = ObjectApiResponse(
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
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_stats()

        assert result.body["kibana"]["name"] == "kibana-test"
        assert result.body["process"]["uptime_in_millis"] == 3600000
        assert result.body["os"]["platform"] == "linux"

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/stats"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_stats_with_extended_metrics(self, mock_transport):
        """Test stats retrieval with extended metrics."""
        mock_response = ObjectApiResponse(
            body={
                "kibana": {"uuid": "test-uuid-123", "name": "kibana-test"},
                "process": {"uptime_in_millis": 3600000},
                "metrics": {
                    "requests": {"total": 1000},
                    "collection_interval_in_millis": 5000,
                },
            },
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_stats()

        assert "metrics" in result.body
        assert result.body["metrics"]["collection_interval_in_millis"] == 5000


class TestStatusClientErrorHandling:
    """Test StatusClient error handling."""

    def test_get_status_authentication_error(self, mock_transport):
        """Test get_status with authentication error."""
        from kibana.exceptions import AuthenticationException

        mock_response = ObjectApiResponse(
            body={
                "statusCode": 401,
                "error": "Unauthorized",
                "message": "Authentication required",
            },
            meta=Mock(status=401, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(AuthenticationException):
            client.status.get_status()

    def test_get_stats_authorization_error(self, mock_transport):
        """Test get_stats with authorization error."""
        from kibana.exceptions import AuthorizationException

        mock_response = ObjectApiResponse(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            meta=Mock(status=403, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(AuthorizationException):
            client.status.get_stats()


class TestStatusClientIntegration:
    """Test StatusClient integration with main Kibana client."""

    def test_status_property_returns_status_client(self, mock_transport):
        """Test that client.status returns a StatusClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.status, StatusClient)

    def test_status_property_caching(self, mock_transport):
        """Test that status property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        status1 = client.status
        status2 = client.status
        assert status1 is status2
