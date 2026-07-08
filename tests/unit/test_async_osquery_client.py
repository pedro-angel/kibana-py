"""Unit tests for AsyncOsqueryClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.osquery import AsyncOsqueryClient
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


class TestAsyncOsqueryClientInitialization:
    """Test AsyncOsqueryClient initialization."""

    @pytest.mark.asyncio
    async def test_osquery_client_initialization(self, mock_async_transport):
        """Test that AsyncOsqueryClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        osquery_client = AsyncOsqueryClient(client)
        assert osquery_client._client is client

    @pytest.mark.asyncio
    async def test_osquery_property_returns_client(self, mock_async_transport):
        """Test that client.osquery returns an AsyncOsqueryClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.osquery, AsyncOsqueryClient)

    @pytest.mark.asyncio
    async def test_osquery_property_caching(self, mock_async_transport):
        """Test that the osquery property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.osquery is client.osquery


class TestAsyncOsqueryClientPacks:
    """Test async pack methods."""

    @pytest.mark.asyncio
    async def test_create_pack(self, mock_async_transport, mock_response):
        """Test creating a pack with all fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_pack_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.create_pack(
            name="kbnpy-osquery-pack",
            description="My pack",
            enabled=False,
            policy_ids=["policy-1"],
            queries={"uptime": {"query": "select * from uptime;", "interval": 3600}},
            shards={"policy-1": 50},
        )

        assert result.body["data"]["saved_object_id"] == PACK_ID

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
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

    @pytest.mark.asyncio
    async def test_find_packs_param_encoding(self, mock_async_transport, mock_response):
        """Test that pagination params are encoded with spec names."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"page": 1, "per_page": 10, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.find_packs(
            page=1, page_size=10, sort="updated_at", sort_order="desc"
        )

        assert result.body["total"] == 0

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/packs?page=1&pageSize=10&sort=updated_at&sortOrder=desc"
        )
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_pack(self, mock_async_transport, mock_response):
        """Test getting a pack by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_pack_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.get_pack(id=PACK_ID)

        assert result.body["data"]["name"] == "kbnpy-osquery-pack"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_pack_url_encodes_id(self, mock_async_transport, mock_response):
        """Test that the pack ID is URL-encoded in the path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_pack_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.get_pack(id="id with/special")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/osquery/packs/id%20with%2Fspecial"

    @pytest.mark.asyncio
    async def test_update_pack(self, mock_async_transport, mock_response):
        """Test updating a pack sends only the provided fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_pack_body(name="renamed")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.update_pack(
            id=PACK_ID,
            name="renamed",
            enabled=True,
        )

        assert result.body["data"]["name"] == "renamed"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["body"] == {"name": "renamed", "enabled": True}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_delete_pack(self, mock_async_transport, mock_response):
        """Test deleting a pack by ID."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.delete_pack(id=PACK_ID)

        assert result.body == {}

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/osquery/packs/{PACK_ID}"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_create_pack_in_space(self, mock_async_transport, mock_response):
        """Test that space_id builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_pack_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.create_pack(
            name="kbnpy-osquery-pack",
            queries={"uptime": {"query": "select * from uptime;", "interval": 3600}},
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/osquery/packs"


class TestAsyncOsqueryClientSavedQueries:
    """Test async saved query methods."""

    @pytest.mark.asyncio
    async def test_create_saved_query(self, mock_async_transport, mock_response):
        """Test creating a saved query with all fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_saved_query_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.create_saved_query(
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

        call_kwargs = mock_async_transport.perform_request.call_args[1]
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
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_find_saved_queries_param_encoding(
        self, mock_async_transport, mock_response
    ):
        """Test that pagination params are encoded with spec names."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"page": 2, "per_page": 5, "total": 0, "data": []}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.find_saved_queries(
            page=2, page_size=5, sort="updated_at", sort_order="asc"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/saved_queries"
            "?page=2&pageSize=5&sort=updated_at&sortOrder=asc"
        )

    @pytest.mark.asyncio
    async def test_get_saved_query(self, mock_async_transport, mock_response):
        """Test getting a saved query by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_saved_query_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.get_saved_query(id=SAVED_QUERY_ID)

        assert result.body["data"]["query"] == "select * from uptime;"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_update_saved_query(self, mock_async_transport, mock_response):
        """Test updating a saved query includes the required body id."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_saved_query_body(interval="120")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.update_saved_query(
            id=SAVED_QUERY_ID,
            new_id="kbnpy_osquery_saved_query",
            query="select * from uptime;",
            interval="120",
        )

        assert result.body["data"]["interval"] == "120"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["body"] == {
            "id": "kbnpy_osquery_saved_query",
            "query": "select * from uptime;",
            "interval": "120",
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_delete_saved_query(self, mock_async_transport, mock_response):
        """Test deleting a saved query by ID."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.delete_saved_query(id=SAVED_QUERY_ID)

        assert result.body == {}

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == f"/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_get_saved_query_in_space(self, mock_async_transport, mock_response):
        """Test that space_id builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_saved_query_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.get_saved_query(
            id=SAVED_QUERY_ID, space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            f"/s/marketing/api/osquery/saved_queries/{SAVED_QUERY_ID}"
        )


class TestAsyncOsqueryClientLiveQueries:
    """Test async live query methods."""

    @pytest.mark.asyncio
    async def test_create_live_query(self, mock_async_transport, mock_response):
        """Test creating a live query with a single query and agent list."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "data": {
                    "action_id": LIVE_QUERY_ID,
                    "agents": ["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
                    "queries": [{"action_id": ACTION_ID}],
                }
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.create_live_query(
            query="select * from uptime;",
            agent_ids=["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
            ecs_mapping={"host.uptime": {"field": "total_seconds"}},
            metadata={"source": "kbnpy"},
        )

        assert result.body["data"]["action_id"] == LIVE_QUERY_ID

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/osquery/live_queries"
        assert call_kwargs["body"] == {
            "query": "select * from uptime;",
            "agent_ids": ["16d7caf5-efd2-4212-9b62-73dafc91fa13"],
            "ecs_mapping": {"host.uptime": {"field": "total_seconds"}},
            "metadata": {"source": "kbnpy"},
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_find_live_queries_param_encoding(
        self, mock_async_transport, mock_response
    ):
        """Test that kuery and pagination params are encoded."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": {"items": [], "total": 0}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.find_live_queries(
            kuery="user_id:elastic",
            page=1,
            page_size=10,
            sort="@timestamp",
            sort_order="desc",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/osquery/live_queries"
            "?kuery=user_id%3Aelastic&page=1&pageSize=10"
            "&sort=%40timestamp&sortOrder=desc"
        )

    @pytest.mark.asyncio
    async def test_get_live_query(self, mock_async_transport, mock_response):
        """Test getting live query details by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": {"action_id": LIVE_QUERY_ID, "status": "completed"}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.get_live_query(id=LIVE_QUERY_ID)

        assert result.body["data"]["status"] == "completed"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == f"/api/osquery/live_queries/{LIVE_QUERY_ID}"
        assert call_kwargs["headers"] == {"accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_live_query_results(self, mock_async_transport, mock_response):
        """Test getting live query results by query and action ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": {"edges": [], "total": 0}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.osquery.get_live_query_results(
            id=LIVE_QUERY_ID,
            action_id=ACTION_ID,
            page=1,
            page_size=100,
        )

        assert result.body["data"]["total"] == 0

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            f"/api/osquery/live_queries/{LIVE_QUERY_ID}/results/{ACTION_ID}"
            "?page=1&pageSize=100"
        )

    @pytest.mark.asyncio
    async def test_find_live_queries_in_space(
        self, mock_async_transport, mock_response
    ):
        """Test that space_id builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": {"items": [], "total": 0}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.osquery.find_live_queries(
            space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/osquery/live_queries"


class TestAsyncOsqueryClientErrorHandling:
    """Test AsyncOsqueryClient error handling."""

    @pytest.mark.asyncio
    async def test_get_pack_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 response raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Pack nope not found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.osquery.get_pack(id="nope")

    @pytest.mark.asyncio
    async def test_create_pack_bad_request_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 400 response raises BadRequestError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": '[request body]: Invalid value "undefined" '
                'supplied to "name"',
            },
            status=400,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(BadRequestError):
            await client.osquery.create_pack(name="", queries={})

    @pytest.mark.asyncio
    async def test_create_live_query_api_error_without_agents(
        self, mock_async_transport, mock_response
    ):
        """Test the live 500 (missing .fleet-agents index) maps to ApiError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 500,
                "error": "Internal Server Error",
                "message": "Error occurred while processing ResponseError: "
                "index_not_found_exception: no such index [.fleet-agents]",
            },
            status=500,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ApiError) as exc_info:
            await client.osquery.create_live_query(query="select 1;", agent_all=True)
        assert "no such index [.fleet-agents]" in str(exc_info.value)
