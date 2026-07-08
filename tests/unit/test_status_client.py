"""Unit tests for StatusClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ListApiResponse, ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.status import StatusClient


def _status_body_v8() -> dict:
    """Kibana 9.4.3 GET /api/status (v8 format) response body."""
    return {
        "name": "kibana-test",
        "uuid": "test-uuid-123",
        "version": {
            "number": "9.4.3",
            "build_hash": "abc123",
            "build_number": 102392,
            "build_snapshot": False,
            "build_flavor": "traditional",
            "build_date": "2026-06-25T15:55:49.194Z",
        },
        "status": {
            "overall": {
                "level": "available",
                "summary": "All services and plugins are available",
            },
            "core": {
                "elasticsearch": {
                    "level": "available",
                    "summary": "Elasticsearch is available",
                    "meta": {"warningNodes": [], "incompatibleNodes": []},
                },
                "savedObjects": {
                    "level": "available",
                    "summary": "SavedObjects service has completed migrations",
                },
            },
            "plugins": {
                "alerting": {"level": "available", "summary": "Alerting is available"},
            },
        },
        "metrics": {"collection_interval_in_millis": 5000},
    }


def _stats_body() -> dict:
    """Kibana 9.4.3 GET /api/stats response body (9.x field names)."""
    return {
        "process": {
            "memory": {
                "heap": {
                    "total_bytes": 748359680,
                    "used_bytes": 621025824,
                    "size_limit": 4496293888,
                },
                "resident_set_size_bytes": 1096683520,
                "array_buffers_bytes": 957876,
                "external_bytes": 5135128,
            },
            "pid": 7,
            "event_loop_delay": 13.95,
            "uptime_ms": 2278283.38,
        },
        "os": {
            "platform": "linux",
            "platform_release": "linux-6.12.76-linuxkit",
            "load": {"1m": 1.5, "5m": 1.2, "15m": 1.0},
            "memory": {
                "total_bytes": 8319213568,
                "free_bytes": 2570534912,
                "used_bytes": 5748678656,
            },
            "uptime_ms": 2336460,
        },
        "elasticsearch_client": {
            "total_active_sockets": 0,
            "total_idle_sockets": 11,
            "total_queued_requests": 0,
        },
        "response_times": {"avg_ms": 45.7, "max_ms": 87},
        "requests": {"total": 1000, "disconnects": 5, "status_codes": {"200": 1000}},
        "concurrent_connections": 10,
        "kibana": {
            "uuid": "test-uuid-123",
            "name": "kibana-test",
            "index": ".kibana",
            "host": "0.0.0.0",
            "locale": "en",
            "transport_address": "0.0.0.0:5601",
            "version": "9.4.3",
            "snapshot": False,
            "status": "green",
        },
        "last_updated": "2026-07-03T18:37:49.080Z",
        "collection_interval_ms": 5000,
    }


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
        """Test successful status retrieval with the 9.x v8 response shape."""
        mock_response = ObjectApiResponse(
            body=_status_body_v8(),
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        assert result.body["name"] == "kibana-test"
        assert result.body["status"]["overall"]["level"] == "available"
        # v8 format: core + plugins dicts (no "statuses" key)
        assert result.body["status"]["core"]["elasticsearch"]["level"] == "available"
        assert result.body["status"]["core"]["savedObjects"]["level"] == "available"
        assert "plugins" in result.body["status"]
        assert "statuses" not in result.body["status"]

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/status"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_status_v7format_param_encoding(self, mock_transport):
        """Test that v7format=True is encoded as a lowercase query param."""
        mock_response = ObjectApiResponse(
            body={
                "name": "kibana-test",
                "uuid": "test-uuid-123",
                "version": {"number": "9.4.3"},
                "status": {
                    "overall": {"state": "green", "title": "Green"},
                    # v7 format: statuses is a LIST of service entries
                    "statuses": [
                        {
                            "id": "core:elasticsearch@9.4.3",
                            "message": "Elasticsearch is available",
                            "state": "green",
                        },
                    ],
                },
            },
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status(v7format=True)

        assert result.body["status"]["overall"]["state"] == "green"
        assert isinstance(result.body["status"]["statuses"], list)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/status?v7format=true"

    def test_get_status_v8format_param_encoding(self, mock_transport):
        """Test that v8format=True is encoded as a lowercase query param."""
        mock_response = ObjectApiResponse(
            body=_status_body_v8(),
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        client.status.get_status(v8format=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/status?v8format=true"

    def test_get_status_degraded(self, mock_transport):
        """Test status retrieval when Kibana is degraded."""
        body = _status_body_v8()
        body["status"]["overall"] = {
            "level": "degraded",
            "summary": "Some services are degraded",
        }
        mock_response = ObjectApiResponse(
            body=body,
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "degraded"

    def test_get_status_redacted_for_anonymous(self, mock_transport):
        """Test the redacted body an unauthenticated caller receives.

        In 9.4.3, GET /api/status is anonymously accessible: unauthorized
        callers get HTTP 200 with only status.overall.level in the body
        (no name/uuid/version keys). When Kibana itself is unavailable, the
        spec defines an HTTP 503 response instead (mapped to ApiError).
        """
        mock_response = ObjectApiResponse(
            body={"status": {"overall": {"level": "available"}}},
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_status()

        assert result.body["status"]["overall"]["level"] == "available"
        assert "name" not in result.body
        assert "uuid" not in result.body
        assert "version" not in result.body


class TestStatusClientGetStats:
    """Test StatusClient.get_stats() method."""

    def test_get_stats_success(self, mock_transport):
        """Test successful stats retrieval with 9.x field names."""
        mock_response = ObjectApiResponse(
            body=_stats_body(),
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_stats()

        assert result.body["kibana"]["name"] == "kibana-test"
        assert result.body["process"]["uptime_ms"] == 2278283.38
        assert result.body["process"]["memory"]["heap"]["used_bytes"] == 621025824
        assert result.body["os"]["platform"] == "linux"
        assert result.body["os"]["platform_release"] == "linux-6.12.76-linuxkit"
        assert result.body["response_times"]["avg_ms"] == 45.7

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/stats"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_stats_extended_param_encoding(self, mock_transport):
        """Test stats retrieval with the extended payload query params."""
        body = _stats_body()
        body["usage"] = {}
        body["cluster_uuid"] = "cluster-uuid-123"
        mock_response = ObjectApiResponse(
            body=body,
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_stats(extended=True, exclude_usage=False)

        assert result.body["cluster_uuid"] == "cluster-uuid-123"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/stats?extended=true&exclude_usage=false"


class TestStatusClientGetFeatures:
    """Test StatusClient.get_features() method."""

    def test_get_features_success(self, mock_transport):
        """Test successful features retrieval (body is a JSON array)."""
        mock_response = ListApiResponse(
            body=[
                {
                    "id": "dashboard",
                    "name": "Dashboard",
                    "category": {"id": "kibana", "label": "Analytics"},
                    "app": ["dashboards", "kibana"],
                    "catalogue": ["dashboard"],
                    "privileges": {"all": {}, "read": {}},
                },
                {
                    "id": "discover",
                    "name": "Discover",
                    "category": {"id": "kibana", "label": "Analytics"},
                    "app": ["discover", "kibana"],
                    "catalogue": ["discover"],
                    "privileges": {"all": {}, "read": {}},
                },
            ],
            meta=Mock(status=200, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)
        result = client.status.get_features()

        assert isinstance(result.body, list)
        assert len(result.body) == 2
        assert result.body[0]["id"] == "dashboard"
        assert result.body[1]["name"] == "Discover"

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/features"
        assert call_kwargs["headers"] == {"accept": "application/json"}


class TestStatusClientErrorHandling:
    """Test StatusClient error handling."""

    def test_get_status_bad_request_error(self, mock_transport):
        """Test get_status with conflicting format params (400 mapping)."""
        from kibana.exceptions import BadRequestError

        mock_response = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "[request query]: provide only one format option: "
                    "v7format or v8format"
                ),
            },
            meta=Mock(status=400, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError):
            client.status.get_status(v7format=True, v8format=True)

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

    def test_get_features_not_found_error(self, mock_transport):
        """Test get_features 404 error mapping."""
        from kibana.exceptions import NotFoundError

        mock_response = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Not Found",
            },
            meta=Mock(status=404, headers={}),
        )
        mock_transport.perform_request.return_value = mock_response

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.status.get_features()


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
