"""Unit tests for TaskManagerClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.task_manager import TaskManagerClient

SAMPLE_HEALTH_BODY = {
    "id": "330bbc6a-56cd-44d5-88e3-e3229f14d619",
    "timestamp": "2025-03-21T21:30:04.780Z",
    "status": "OK",
    "last_update": "2025-03-21T21:30:04.455Z",
    "stats": {
        "configuration": {
            "timestamp": "2025-03-21T21:26:10.002Z",
            "status": "OK",
            "value": {
                "request_capacity": 1000,
                "poll_interval": 500,
                "claim_strategy": "mget",
                "capacity": {"config": 10, "as_workers": 10, "as_cost": 20},
            },
        },
        "runtime": {
            "timestamp": "2025-03-21T21:30:04.455Z",
            "status": "OK",
            "value": {
                "polling": {
                    "last_successful_poll": "2025-03-21T21:30:04.455Z",
                },
                "drift": {"p50": 2089, "p90": 3037, "p95": 3037, "p99": 3037},
            },
        },
        "workload": {
            "timestamp": "2025-03-21T21:29:24.912Z",
            "status": "OK",
            "value": {"count": 26, "cost": 52},
        },
        "capacity_estimation": {
            "timestamp": "2025-03-21T21:30:04.779Z",
            "status": "OK",
            "value": {"observed": {}, "proposed": {}},
        },
    },
}


class TestTaskManagerClientInitialization:
    """Test TaskManagerClient initialization."""

    def test_task_manager_client_initialization(self, mock_transport):
        """Test that TaskManagerClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        task_manager_client = TaskManagerClient(client)
        assert task_manager_client._client is client

    def test_task_manager_property_returns_task_manager_client(self, mock_transport):
        """Test that client.task_manager returns a TaskManagerClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.task_manager, TaskManagerClient)

    def test_task_manager_property_caching(self, mock_transport):
        """Test that the task_manager attribute returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.task_manager is client.task_manager


class TestTaskManagerClientHealth:
    """Test TaskManagerClient.health() method."""

    def test_health_success(self, mock_transport, mock_response):
        """Test successful health retrieval."""
        mock_transport.perform_request.return_value = mock_response(
            body=SAMPLE_HEALTH_BODY, status=200
        )

        client = Kibana(_transport=mock_transport)
        result = client.task_manager.health()

        assert isinstance(result, ObjectApiResponse)
        assert result.body["status"] == "OK"
        assert result.body["id"] == "330bbc6a-56cd-44d5-88e3-e3229f14d619"
        assert set(result.body["stats"]) == {
            "configuration",
            "runtime",
            "workload",
            "capacity_estimation",
        }

        # Verify the call was made with correct parameters (ignoring otel_span)
        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/task_manager/_health"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    def test_health_warn_status(self, mock_transport, mock_response):
        """Test health retrieval when the task manager reports a warning."""
        body = dict(SAMPLE_HEALTH_BODY, status="warn")
        mock_transport.perform_request.return_value = mock_response(
            body=body, status=200
        )

        client = Kibana(_transport=mock_transport)
        result = client.task_manager.health()

        assert result.body["status"] == "warn"

    def test_health_takes_no_positional_arguments(self, mock_transport):
        """Test that health() rejects positional arguments."""
        client = Kibana(_transport=mock_transport)

        with pytest.raises(TypeError):
            client.task_manager.health("unexpected")  # type: ignore[call-arg]


class TestTaskManagerClientErrorHandling:
    """Test TaskManagerClient error handling."""

    def test_health_not_found_error(self, mock_transport):
        """Test health() with a 404 response (e.g. task manager route disabled)."""
        from kibana.exceptions import NotFoundError

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Not Found",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.task_manager.health()

    def test_health_authorization_error(self, mock_transport):
        """Test health() with an authorization error."""
        from kibana.exceptions import AuthorizationException

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "Insufficient privileges",
            },
            meta=Mock(status=403, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(AuthorizationException):
            client.task_manager.health()
