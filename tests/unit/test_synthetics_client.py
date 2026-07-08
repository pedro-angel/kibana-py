"""Unit tests for SyntheticsClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ListApiResponse, ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.synthetics import SyntheticsClient
from kibana.exceptions import BadRequestError, NotFoundError

MONITOR_ID = "a4cb5867-d14f-45ec-b8b0-94742d192e97"
LOCATION_ID = "91305abb-f0e1-40fc-b706-4f23f31d4349"
PARAM_ID = "95d428f5-8a34-492a-b73c-4663ba62dfd5"


def _monitor_body() -> dict:
    """Kibana 9.4.3 synthetics monitor response body (abridged)."""
    return {
        "type": "http",
        "enabled": True,
        "alert": {"status": {"enabled": True}, "tls": {"enabled": True}},
        "schedule": {"number": "10", "unit": "m"},
        "config_id": MONITOR_ID,
        "tags": ["kbnpy-synthetics"],
        "timeout": "16",
        "name": "kbnpy-synthetics-probe-mon",
        "locations": [
            {
                "id": LOCATION_ID,
                "label": "kbnpy-synthetics-probe-loc",
                "isServiceManaged": False,
                "agentPolicyId": "policy-1",
            }
        ],
        "namespace": "default",
        "origin": "ui",
        "id": MONITOR_ID,
        "max_attempts": 2,
        "spaces": ["default"],
        "revision": 1,
        "url": "https://example.com",
    }


def _param_body() -> dict:
    """Kibana 9.4.3 synthetics parameter response body."""
    return {
        "id": PARAM_ID,
        "key": "kbnpy-synthetics-key",
        "description": "probe",
        "tags": ["kbnpy"],
        "namespaces": ["default"],
    }


def _private_location_body() -> dict:
    """Kibana 9.4.3 synthetics private location response body."""
    return {
        "label": "kbnpy-synthetics-loc",
        "id": LOCATION_ID,
        "agentPolicyId": "policy-1",
        "isServiceManaged": False,
        "isInvalid": False,
        "spaces": ["default"],
    }


def _mock_ok(mock_transport, body) -> None:
    """Configure the mock transport to return a 200 response."""
    response_cls = ListApiResponse if isinstance(body, list) else ObjectApiResponse
    mock_transport.perform_request.return_value = response_cls(
        body=body,
        meta=Mock(status=200, headers={}),
    )


class TestSyntheticsClientInitialization:
    """Test SyntheticsClient initialization."""

    def test_synthetics_client_initialization(self, mock_transport):
        """Test that SyntheticsClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        synthetics_client = SyntheticsClient(client)
        assert synthetics_client._client is client

    def test_synthetics_property_returns_synthetics_client(self, mock_transport):
        """Test that client.synthetics returns a SyntheticsClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.synthetics, SyntheticsClient)

    def test_synthetics_property_caching(self, mock_transport):
        """Test that the synthetics property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.synthetics is client.synthetics


class TestSyntheticsClientMonitors:
    """Test monitor CRUD methods."""

    def test_get_monitors_no_params(self, mock_transport):
        """Test listing monitors without filters."""
        _mock_ok(
            mock_transport,
            {
                "page": 1,
                "total": 0,
                "monitors": [],
                "absoluteTotal": 0,
                "perPage": 50,
                "syncErrors": [],
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_monitors()

        assert result.body["monitors"] == []
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/synthetics/monitors"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert "body" not in call_kwargs

    def test_get_monitors_query_param_encoding(self, mock_transport):
        """Test camelCase query keys, list encoding, and perPage mapping."""
        _mock_ok(
            mock_transport,
            {
                "page": 2,
                "total": 0,
                "monitors": [],
                "absoluteTotal": 0,
                "perPage": 5,
                "syncErrors": [],
            },
        )

        client = Kibana(_transport=mock_transport)
        client.synthetics.get_monitors(
            filter='synthetics-monitor.attributes.tags:"kbnpy"',
            locations=["loc-1", "loc-2"],
            monitor_types=["http", "tcp"],
            page=2,
            per_page=5,
            projects="my-project",
            query="kbnpy",
            schedules=["10"],
            sort_field="name.keyword",
            sort_order="asc",
            status=["up"],
            tags=["kbnpy"],
            use_logical_and_for=["tags"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        target = call_kwargs["target"]
        path, _, query = target.partition("?")
        assert path == "/api/synthetics/monitors"
        pairs = query.split("&")
        assert "filter=synthetics-monitor.attributes.tags%3A%22kbnpy%22" in pairs
        assert "locations=loc-1" in pairs
        assert "locations=loc-2" in pairs
        assert "monitorTypes=http" in pairs
        assert "monitorTypes=tcp" in pairs
        assert "page=2" in pairs
        assert "perPage=5" in pairs
        assert "projects=my-project" in pairs
        assert "query=kbnpy" in pairs
        assert "schedules=10" in pairs
        assert "sortField=name.keyword" in pairs
        assert "sortOrder=asc" in pairs
        assert "status=up" in pairs
        assert "tags=kbnpy" in pairs
        assert "useLogicalAndFor=tags" in pairs

    def test_get_monitors_space_scoped(self, mock_transport):
        """Test that space_id prefixes the path with /s/{space_id}."""
        _mock_ok(mock_transport, {"monitors": []})

        client = Kibana(_transport=mock_transport)
        client.synthetics.get_monitors(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/synthetics/monitors"

    def test_get_monitor(self, mock_transport):
        """Test getting a monitor by config ID."""
        _mock_ok(mock_transport, _monitor_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_monitor(id=MONITOR_ID)

        assert result.body["id"] == MONITOR_ID
        assert result.body["type"] == "http"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/synthetics/monitors/{MONITOR_ID}"

    def test_get_monitor_id_url_encoded(self, mock_transport):
        """Test that the monitor ID is URL-encoded in the path."""
        _mock_ok(mock_transport, _monitor_body())

        client = Kibana(_transport=mock_transport)
        client.synthetics.get_monitor(id="my monitor/1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/synthetics/monitors/my%20monitor%2F1"

    def test_create_monitor(self, mock_transport):
        """Test creating an HTTP monitor builds the documented body."""
        _mock_ok(mock_transport, _monitor_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.create_monitor(
            type="http",
            name="kbnpy-synthetics-probe-mon",
            url="https://example.com",
            private_locations=["kbnpy-synthetics-probe-loc"],
            schedule={"number": "10", "unit": "m"},
            enabled=False,
            tags=["kbnpy-synthetics"],
            alert={"status": {"enabled": True}},
            labels={"team": "obs"},
            namespace="default",
            params={"token": "abc"},
            retest_on_failure=False,
            service_name="my-apm-service",
            timeout=16,
            fields={"max_redirects": 3, "ssl.verification_mode": "none"},
        )

        assert result.body["config_id"] == MONITOR_ID
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/monitors"
        assert call_kwargs["headers"] == {
            "accept": "application/json",
            "content-type": "application/json",
            "kbn-xsrf": "true",
        }
        assert call_kwargs["body"] == {
            "type": "http",
            "name": "kbnpy-synthetics-probe-mon",
            "url": "https://example.com",
            "private_locations": ["kbnpy-synthetics-probe-loc"],
            "schedule": {"number": "10", "unit": "m"},
            "enabled": False,
            "tags": ["kbnpy-synthetics"],
            "alert": {"status": {"enabled": True}},
            "labels": {"team": "obs"},
            "namespace": "default",
            "params": {"token": "abc"},
            "retest_on_failure": False,
            "service.name": "my-apm-service",
            "timeout": 16,
            "max_redirects": 3,
            "ssl.verification_mode": "none",
        }

    def test_update_monitor_partial_body(self, mock_transport):
        """Test that a partial update only sends the provided fields."""
        _mock_ok(mock_transport, _monitor_body())

        client = Kibana(_transport=mock_transport)
        client.synthetics.update_monitor(id=MONITOR_ID, name="renamed")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/synthetics/monitors/{MONITOR_ID}"
        assert call_kwargs["body"] == {"name": "renamed"}

    def test_delete_monitor(self, mock_transport):
        """Test deleting a monitor returns the deletion result list."""
        _mock_ok(mock_transport, [{"id": MONITOR_ID, "deleted": True}])

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.delete_monitor(id=MONITOR_ID)

        assert result.body[0]["deleted"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/synthetics/monitors/{MONITOR_ID}"
        assert "body" not in call_kwargs

    def test_bulk_delete_monitors(self, mock_transport):
        """Test bulk-deleting monitors sends the ids body."""
        _mock_ok(
            mock_transport,
            {"result": [{"id": "id-1", "deleted": True}]},
        )

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.bulk_delete_monitors(ids=["id-1", "id-2"])

        assert result.body["result"][0]["deleted"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/monitors/_bulk_delete"
        assert call_kwargs["body"] == {"ids": ["id-1", "id-2"]}

    def test_test_monitor(self, mock_transport):
        """Test triggering an on-demand test run."""
        _mock_ok(mock_transport, {"testRunId": "run-1"})

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.test_monitor(monitor_id=MONITOR_ID)

        assert result.body["testRunId"] == "run-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == f"/api/synthetics/monitor/test/{MONITOR_ID}"
        assert "body" not in call_kwargs


class TestSyntheticsClientParams:
    """Test global parameter CRUD methods."""

    def test_get_params(self, mock_transport):
        """Test listing parameters (body is a JSON array)."""
        _mock_ok(mock_transport, [_param_body()])

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_params()

        assert result.body[0]["key"] == "kbnpy-synthetics-key"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/synthetics/params"

    def test_get_param(self, mock_transport):
        """Test getting a parameter by ID."""
        _mock_ok(mock_transport, _param_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_param(id=PARAM_ID)

        assert result.body["id"] == PARAM_ID
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/synthetics/params/{PARAM_ID}"

    def test_create_param(self, mock_transport):
        """Test creating a single parameter."""
        _mock_ok(mock_transport, _param_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.create_param(
            key="kbnpy-synthetics-key",
            value="s3cret",
            description="probe",
            tags=["kbnpy"],
            share_across_spaces=True,
        )

        assert result.body["id"] == PARAM_ID
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/params"
        assert call_kwargs["body"] == {
            "key": "kbnpy-synthetics-key",
            "value": "s3cret",
            "description": "probe",
            "tags": ["kbnpy"],
            "share_across_spaces": True,
        }

    def test_create_param_minimal_body(self, mock_transport):
        """Test that omitted optional args are excluded from the body."""
        _mock_ok(mock_transport, _param_body())

        client = Kibana(_transport=mock_transport)
        client.synthetics.create_param(key="k", value="v")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"key": "k", "value": "v"}

    def test_bulk_create_params(self, mock_transport):
        """Test that bulk create sends a JSON array body."""
        _mock_ok(
            mock_transport,
            [
                {"id": "p1", "key": "k1", "namespaces": ["default"]},
                {"id": "p2", "key": "k2", "namespaces": ["default"]},
            ],
        )

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.bulk_create_params(
            parameters=[
                {"key": "k1", "value": "v1"},
                {"key": "k2", "value": "v2"},
            ]
        )

        assert len(result.body) == 2
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/params"
        assert call_kwargs["body"] == [
            {"key": "k1", "value": "v1"},
            {"key": "k2", "value": "v2"},
        ]

    def test_update_param(self, mock_transport):
        """Test updating a parameter sends only the provided fields."""
        body = _param_body()
        body["description"] = "rotated"
        _mock_ok(mock_transport, body)

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.update_param(
            id=PARAM_ID, value="new-value", description="rotated"
        )

        assert result.body["description"] == "rotated"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/synthetics/params/{PARAM_ID}"
        assert call_kwargs["body"] == {"value": "new-value", "description": "rotated"}

    def test_delete_param(self, mock_transport):
        """Test deleting a parameter."""
        _mock_ok(mock_transport, [{"id": PARAM_ID, "deleted": True}])

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.delete_param(id=PARAM_ID)

        assert result.body[0]["deleted"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/synthetics/params/{PARAM_ID}"

    def test_bulk_delete_params(self, mock_transport):
        """Test bulk-deleting parameters sends the ids body."""
        _mock_ok(
            mock_transport,
            [
                {"id": "p1", "deleted": True},
                {"id": "p2", "deleted": True},
            ],
        )

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.bulk_delete_params(ids=["p1", "p2"])

        assert [item["deleted"] for item in result.body] == [True, True]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/params/_bulk_delete"
        assert call_kwargs["body"] == {"ids": ["p1", "p2"]}


class TestSyntheticsClientPrivateLocations:
    """Test private location CRUD methods."""

    def test_get_private_locations(self, mock_transport):
        """Test listing private locations (body is a JSON array)."""
        _mock_ok(mock_transport, [_private_location_body()])

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_private_locations()

        assert result.body[0]["id"] == LOCATION_ID
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/synthetics/private_locations"

    def test_get_private_location(self, mock_transport):
        """Test getting a private location by ID."""
        _mock_ok(mock_transport, _private_location_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.get_private_location(id=LOCATION_ID)

        assert result.body["agentPolicyId"] == "policy-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"] == f"/api/synthetics/private_locations/{LOCATION_ID}"
        )

    def test_create_private_location(self, mock_transport):
        """Test creating a private location maps args to camelCase keys."""
        _mock_ok(mock_transport, _private_location_body())

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.create_private_location(
            label="kbnpy-synthetics-loc",
            agent_policy_id="policy-1",
            tags=["kbnpy"],
            geo={"lat": 40.4, "lon": -3.7},
            spaces=["default"],
        )

        assert result.body["label"] == "kbnpy-synthetics-loc"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/synthetics/private_locations"
        assert call_kwargs["body"] == {
            "label": "kbnpy-synthetics-loc",
            "agentPolicyId": "policy-1",
            "tags": ["kbnpy"],
            "geo": {"lat": 40.4, "lon": -3.7},
            "spaces": ["default"],
        }

    def test_update_private_location(self, mock_transport):
        """Test updating a private location label."""
        body = _private_location_body()
        body["label"] = "new-label"
        _mock_ok(mock_transport, body)

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.update_private_location(
            id=LOCATION_ID, label="new-label"
        )

        assert result.body["label"] == "new-label"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert (
            call_kwargs["target"] == f"/api/synthetics/private_locations/{LOCATION_ID}"
        )
        assert call_kwargs["body"] == {"label": "new-label"}

    def test_delete_private_location(self, mock_transport):
        """Test deleting a private location."""
        _mock_ok(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        result = client.synthetics.delete_private_location(id=LOCATION_ID)

        assert result.body == {}
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert (
            call_kwargs["target"] == f"/api/synthetics/private_locations/{LOCATION_ID}"
        )

    def test_create_private_location_space_scoped(self, mock_transport):
        """Test that space_id prefixes the path for a write operation."""
        _mock_ok(mock_transport, _private_location_body())

        client = Kibana(_transport=mock_transport)
        client.synthetics.create_private_location(
            label="loc",
            agent_policy_id="policy-1",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/synthetics/private_locations"


class TestSyntheticsClientErrorHandling:
    """Test SyntheticsClient error handling."""

    def test_get_monitor_not_found_error(self, mock_transport):
        """Test 404 error mapping to NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Monitor id does-not-exist not found!",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.synthetics.get_monitor(id="does-not-exist")

    def test_create_monitor_bad_request_error(self, mock_transport):
        """Test 400 error mapping (e.g. missing locations) to BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": (
                    "At least one location is required, either "
                    "elastic managed or private"
                ),
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError):
            client.synthetics.create_monitor(
                type="http", name="no-locations", url="https://example.com"
            )
