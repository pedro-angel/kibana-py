"""Unit tests for OsqueryClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.osquery import OsqueryClient
from kibana.exceptions import ApiError, BadRequestError, NotFoundError

PACK_ID = "3c42c847-eb30-4452-80e0-728584042334"
SAVED_QUERY_ID = "42ba9c50-0cc5-11ed-aa1d-2b27890bc90d"
LIVE_QUERY_ID = "3c42c847-eb30-4452-80e0-728584042334"
ACTION_ID = "609c4c66-ba3d-43fa-afdd-53e244577aa0"


def _pack_body(**overrides):
    """Build a representative pack response body (Kibana 9.4.3 shape)."""
    data = {
        "name": "kbnpy-osquery-pack",
        "description": "My pack",
        "enabled": False,
        "queries": {
            "uptime": {"query": "select * from uptime;", "interval": 3600},
        },
        "created_at": "2026-07-06T00:00:00.000Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T00:00:00.000Z",
        "updated_by": "elastic",
        "shards": [],
        "saved_object_id": PACK_ID,
    }
    data.update(overrides)
    return {"data": data}


def _saved_query_body(**overrides):
    """Build a representative saved query response body (9.4.3 shape)."""
    data = {
        "id": "kbnpy_osquery_saved_query",
        "query": "select * from uptime;",
        "interval": "60",
        "description": "Saved query description",
        "created_at": "2026-07-06T00:00:00.000Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T00:00:00.000Z",
        "updated_by": "elastic",
        "saved_object_id": SAVED_QUERY_ID,
    }
    data.update(overrides)
    return {"data": data}


def _mock_json_response(mock_transport, body):
    """Configure the mock transport to return an ObjectApiResponse."""
    mock_transport.perform_request.return_value = ObjectApiResponse(
        body=body,
        meta=Mock(status=200, headers={}),
    )


class TestOsqueryClientInitialization:
    """Test OsqueryClient initialization."""

    def test_osquery_client_initialization(self, mock_transport):
        """Test that OsqueryClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        osquery_client = OsqueryClient(client)
        assert osquery_client._client is client

    def test_osquery_property_returns_client(self, mock_transport):
        """Test that client.osquery returns an OsqueryClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.osquery, OsqueryClient)

    def test_osquery_property_caching(self, mock_transport):
        """Test that the osquery property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.osquery is client.osquery


class TestOsqueryClientPacks:
    """Test pack methods."""

    def test_create_pack(self, mock_transport):
        """Test creating a pack with all fields."""
        _mock_json_response(mock_transport, _pack_body())

        client = Kibana(_transport=mock_transport)
        result = client.osquery.create_pack(
            name="kbnpy-osquery-pack",
            description="My pack",
            enabled=False,
            policy_ids=["policy-1"],
            queries={"uptime": {"query": "select * from uptime;", "interval": 3600}},
            shards={"policy-1": 50},
        )

        assert result.body["data"]["saved_object_id"] == PACK_ID

        mock_transport.perform_request.assert_called_once()
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/osquery/packs"
        assert call_kwargs["body"] == {
            "name": "kbnpy-osquery-pack",
            "queries": {"uptime": {"query": "select * from uptime;", "interval": 3600}},
            "description": "My pack",
            "enabled": False,
            "policy_ids": ["policy-1"],
            "shards": {"policy-1": 50},
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_pack_minimal_body(self, mock_transport):
        """Test that optional pack fields are omitted from the body."""
        _mock_json_response(mock_transport, _pack_body())

        client = Kibana(_transport=mock_transport)
        client.osquery.create_pack(
            name="kbnpy-osquery-pack",
            queries={"uptime": {"query": "select * from uptime;", "interval": 3600}},
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "kbnpy-osquery-pack",
            "queries": {"uptime": {"query": "select * from uptime;", "interval": 3600}},
        }

    def test_find_packs_param_encoding(self, mock_transport):
        """Test that pagination params are encoded with spec names."""
        _mock_json_response(
            mock_transport, {"page": 1, "per_page": 10, "total": 0, "data": []}
        )

        client = Kibana(_transport=mock_transport)
        result = client.osquery.find_packs(
            page=1, page_size=10, sort="updated_at", sort_order="desc"
        )

        assert result.body["total"] == 0

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/packs?page=1&pageSize=10&sort=updated_at&sortOrder=desc"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    def test_find_packs_no_params(self, mock_transport):
        """Test that find_packs without params has a bare target."""
        _mock_json_response(
            mock_transport, {"page": 1, "per_page": 20, "total": 0, "data": []}
        )

        client = Kibana(_transport=mock_transport)
        client.osquery.find_packs()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/osquery/packs"

    def test_get_pack(self, mock_transport):
        """Test getting a pack by ID."""
        _mock_json_response(mock_transport, _pack_body())

        client = Kibana(_transport=mock_transport)
        result = client.osquery.get_pack(id=PACK_ID)

        assert result.body["data"]["name"] == "kbnpy-osquery-pack"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_pack_url_encodes_id(self, mock_transport):
        """Test that the pack ID is URL-encoded in the path."""
        _mock_json_response(mock_transport, _pack_body())

        client = Kibana(_transport=mock_transport)
        client.osquery.get_pack(id="id with/special")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/osquery/packs/id%20with%2Fspecial"

    def test_update_pack(self, mock_transport):
        """Test updating a pack sends only the provided fields."""
        _mock_json_response(mock_transport, _pack_body(name="renamed"))

        client = Kibana(_transport=mock_transport)
        result = client.osquery.update_pack(
            id=PACK_ID,
            name="renamed",
            enabled=True,
        )

        assert result.body["data"]["name"] == "renamed"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["body"] == {"name": "renamed", "enabled": True}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_delete_pack(self, mock_transport):
        """Test deleting a pack by ID."""
        _mock_json_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        result = client.osquery.delete_pack(id=PACK_ID)

        assert result.body == {}

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    def test_create_pack_in_space(self, mock_transport):
        """Test that space_id builds a space-scoped path."""
        _mock_json_response(mock_transport, _pack_body())

        client = Kibana(_transport=mock_transport)
        client.osquery.create_pack(
            name="kbnpy-osquery-pack",
            queries={"uptime": {"query": "select * from uptime;", "interval": 3600}},
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/osquery/packs"


class TestOsqueryClientSavedQueries:
    """Test saved query methods."""

    def test_create_saved_query(self, mock_transport):
        """Test creating a saved query with all fields."""
        _mock_json_response(mock_transport, _saved_query_body())

        client = Kibana(_transport=mock_transport)
        result = client.osquery.create_saved_query(
            id="kbnpy_osquery_saved_query",
            query="select * from uptime;",
            interval="60",
            description="Saved query description",
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
            platform="linux,darwin",
            removed=False,
            snapshot=True,
            version="2.8.0",
        )

        assert result.body["data"]["saved_object_id"] == SAVED_QUERY_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/osquery/saved_queries"
        assert call_kwargs["body"] == {
            "id": "kbnpy_osquery_saved_query",
            "query": "select * from uptime;",
            "interval": "60",
            "description": "Saved query description",
            "ecs_mapping": {"host.uptime": {"field": "total_seconds"}},
            "platform": "linux,darwin",
            "removed": False,
            "snapshot": True,
            "version": "2.8.0",
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_saved_query_minimal_body(self, mock_transport):
        """Test that optional saved query fields are omitted from the body."""
        _mock_json_response(mock_transport, _saved_query_body())

        client = Kibana(_transport=mock_transport)
        client.osquery.create_saved_query(
            id="kbnpy_osquery_saved_query",
            query="select * from uptime;",
            interval="60",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "id": "kbnpy_osquery_saved_query",
            "query": "select * from uptime;",
            "interval": "60",
        }

    def test_find_saved_queries_param_encoding(self, mock_transport):
        """Test that pagination params are encoded with spec names."""
        _mock_json_response(
            mock_transport, {"page": 2, "per_page": 5, "total": 0, "data": []}
        )

        client = Kibana(_transport=mock_transport)
        client.osquery.find_saved_queries(
            page=2, page_size=5, sort="updated_at", sort_order="asc"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/saved_queries"
            "?page=2&pageSize=5&sort=updated_at&sortOrder=asc"
        )

    def test_get_saved_query(self, mock_transport):
        """Test getting a saved query by ID."""
        _mock_json_response(mock_transport, _saved_query_body())

        client = Kibana(_transport=mock_transport)
        result = client.osquery.get_saved_query(id=SAVED_QUERY_ID)

        assert result.body["data"]["query"] == "select * from uptime;"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_update_saved_query(self, mock_transport):
        """Test updating a saved query includes the required body id."""
        _mock_json_response(mock_transport, _saved_query_body(interval="120"))

        client = Kibana(_transport=mock_transport)
        result = client.osquery.update_saved_query(
            id=SAVED_QUERY_ID,
            new_id="kbnpy_osquery_saved_query",
            query="select * from uptime;",
            interval="120",
        )

        assert result.body["data"]["interval"] == "120"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["body"] == {
            "id": "kbnpy_osquery_saved_query",
            "query": "select * from uptime;",
            "interval": "120",
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_delete_saved_query(self, mock_transport):
        """Test deleting a saved query by ID."""
        _mock_json_response(mock_transport, {})

        client = Kibana(_transport=mock_transport)
        result = client.osquery.delete_saved_query(id=SAVED_QUERY_ID)

        assert result.body == {}

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_get_saved_query_in_space(self, mock_transport):
        """Test that space_id builds a space-scoped path."""
        _mock_json_response(mock_transport, _saved_query_body())

        client = Kibana(_transport=mock_transport)
        client.osquery.get_saved_query(
            id=SAVED_QUERY_ID, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            f"/s/marketing/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        )


class TestOsqueryClientLiveQueries:
    """Test live query methods."""

    def test_create_live_query(self, mock_transport):
        """Test creating a live query with a single query and agent list."""
        _mock_json_response(
            mock_transport,
            {
                "data": {
                    "action_id": LIVE_QUERY_ID,
                    "agents": ["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
                    "queries": [{"action_id": ACTION_ID}],
                }
            },
        )

        client = Kibana(_transport=mock_transport)
        result = client.osquery.create_live_query(
            query="select * from uptime;",
            agent_ids=["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
            metadata={"source": "kbnpy"},
        )

        assert result.body["data"]["action_id"] == LIVE_QUERY_ID

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/osquery/live_queries"
        assert call_kwargs["body"] == {
            "query": "select * from uptime;",
            "agent_ids": ["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
            "ecs_mapping": {"host.uptime": {"field": "total_seconds"}},
            "metadata": {"source": "kbnpy"},
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_live_query_full_body(self, mock_transport):
        """Test that all live query selectors are passed through."""
        _mock_json_response(mock_transport, {"data": {"action_id": LIVE_QUERY_ID}})

        client = Kibana(_transport=mock_transport)
        client.osquery.create_live_query(
            queries=[{"id": "uptime", "query": "select * from uptime;"}],
            saved_query_id="my_saved_query",
            pack_id=PACK_ID,
            agent_all=True,
            agent_platforms=["linux"],
            agent_policy_ids=["policy-1"],
            alert_ids=["alert-1"],
            case_ids=["case-1"],
            event_ids=["event-1"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "queries": [{"id": "uptime", "query": "select * from uptime;"}],
            "saved_query_id": "my_saved_query",
            "pack_id": PACK_ID,
            "agent_all": True,
            "agent_platforms": ["linux"],
            "agent_policy_ids": ["policy-1"],
            "alert_ids": ["alert-1"],
            "case_ids": ["case-1"],
            "event_ids": ["event-1"],
        }

    def test_find_live_queries_param_encoding(self, mock_transport):
        """Test that kuery and pagination params are encoded."""
        _mock_json_response(mock_transport, {"data": {"items": [], "total": 0}})

        client = Kibana(_transport=mock_transport)
        client.osquery.find_live_queries(
            kuery="user_id:elastic",
            page=1,
            page_size=10,
            sort="@timestamp",
            sort_order="desc",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/live_queries"
            "?kuery=user_id%3Aelastic&page=1&pageSize=10"
            "&sort=%40timestamp&sortOrder=desc"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_live_query(self, mock_transport):
        """Test getting live query details by ID."""
        _mock_json_response(
            mock_transport,
            {"data": {"action_id": LIVE_QUERY_ID, "status": "completed"}},
        )

        client = Kibana(_transport=mock_transport)
        result = client.osquery.get_live_query(id=LIVE_QUERY_ID)

        assert result.body["data"]["status"] == "completed"

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/live_queries/{LIVE_QUERY_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_live_query_results(self, mock_transport):
        """Test getting live query results by query and action ID."""
        _mock_json_response(mock_transport, {"data": {"edges": [], "total": 0}})

        client = Kibana(_transport=mock_transport)
        result = client.osquery.get_live_query_results(
            id=LIVE_QUERY_ID,
            action_id=ACTION_ID,
            page=1,
            page_size=100,
        )

        assert result.body["data"]["total"] == 0

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            f"/api/osquery/live_queries/{LIVE_QUERY_ID}/results/{ACTION_ID}"
            "?page=1&pageSize=100"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}

    def test_get_live_query_results_url_encodes_ids(self, mock_transport):
        """Test that both path params are URL-encoded."""
        _mock_json_response(mock_transport, {"data": {"edges": [], "total": 0}})

        client = Kibana(_transport=mock_transport)
        client.osquery.get_live_query_results(id="a b", action_id="c/d")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/osquery/live_queries/a%20b/results/c%2Fd"

    def test_find_live_queries_in_space(self, mock_transport):
        """Test that space_id builds a space-scoped path."""
        _mock_json_response(mock_transport, {"data": {"items": [], "total": 0}})

        client = Kibana(_transport=mock_transport)
        client.osquery.find_live_queries(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/osquery/live_queries"


class TestOsqueryClientErrorHandling:
    """Test OsqueryClient error handling."""

    def test_get_pack_not_found_error(self, mock_transport):
        """Test that a 404 response raises NotFoundError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Pack nope not found",
            },
            meta=Mock(status=404, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.osquery.get_pack(id="nope")

    def test_create_pack_bad_request_error(self, mock_transport):
        """Test that a 400 response raises BadRequestError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": '[request body]: Invalid value "undefined" '
                'supplied to "name"',
            },
            meta=Mock(status=400, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(BadRequestError):
            client.osquery.create_pack(name="", queries={})

    def test_create_live_query_api_error_without_agents(self, mock_transport):
        """Test the live 500 (missing .fleet-agents index) maps to ApiError."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={
                "statusCode": 500,
                "error": "Internal Server Error",
                "message": "Error occurred while processing ResponseError: "
                "index_not_found_exception: no such index [.fleet-agents]",
            },
            meta=Mock(status=500, headers={}),
        )

        client = Kibana(_transport=mock_transport)

        with pytest.raises(ApiError) as exc_info:
            client.osquery.create_live_query(query="select 1;", agent_all=True)
        assert "no such index [.fleet-agents]" in str(exc_info.value)
