"""Unit tests for AsyncDashboardsClient."""

from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._async.client.dashboards import AsyncDashboardsClient


def _make_response(body=None, status=200):
    return ObjectApiResponse(
        body=body if body is not None else {},
        meta=Mock(status=status, headers={}),
    )


def _dashboard_envelope(dashboard_id="dash-1", title="My dashboard", **data):
    return {
        "id": dashboard_id,
        "data": {"title": title, **data},
        "meta": {
            "created_at": "2026-07-03T00:00:00.000Z",
            "updated_at": "2026-07-03T00:00:00.000Z",
            "managed": False,
            "version": "WzEsMV0=",
        },
    }


@pytest.fixture
def client(mock_async_transport):
    return AsyncKibana(_transport=mock_async_transport)


class TestAsyncDashboardsClientInitialization:
    """Test AsyncDashboardsClient wiring on the main async client."""

    def test_dashboards_property_returns_dashboards_client(self, client):
        assert isinstance(client.dashboards, AsyncDashboardsClient)

    def test_dashboards_property_caching(self, client):
        assert client.dashboards is client.dashboards


class TestAsyncDashboardsClientGetAll:
    """Test AsyncDashboardsClient.get_all()."""

    @pytest.mark.asyncio
    async def test_get_all_no_params(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response({"dashboards": [], "page": 1, "total": 0})
        )

        result = await client.dashboards.get_all()

        assert result.body["total"] == 0
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/dashboards"
        assert "body" not in call_kwargs

    @pytest.mark.asyncio
    async def test_get_all_with_all_params(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(
                {"dashboards": [_dashboard_envelope()], "page": 2, "total": 21}
            )
        )

        result = await client.dashboards.get_all(
            page=2,
            per_page=10,
            query="sales*",
            tags=["tag-a", "tag-b"],
            excluded_tags=["tag-c"],
        )

        assert result.body["page"] == 2
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        url = urlsplit(call_kwargs["target"])
        assert url.path == "/api/dashboards"
        params = parse_qs(url.query)
        assert params["page"] == ["2"]
        assert params["per_page"] == ["10"]
        assert params["query"] == ["sales*"]
        # Lists are encoded as repeated keys
        assert params["tags"] == ["tag-a", "tag-b"]
        assert params["excluded_tags"] == ["tag-c"]

    @pytest.mark.asyncio
    async def test_get_all_with_space_id(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response({"dashboards": [], "page": 1, "total": 0})
        )

        await client.dashboards.get_all(space_id="marketing", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/dashboards"


class TestAsyncDashboardsClientCreate:
    """Test AsyncDashboardsClient.create()."""

    @pytest.mark.asyncio
    async def test_create_minimal(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope(), status=201)
        )

        result = await client.dashboards.create(title="My dashboard")

        assert result.body["id"] == "dash-1"
        assert result.body["data"]["title"] == "My dashboard"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/dashboards"
        assert call_kwargs["body"] == {"title": "My dashboard"}
        # The server assigns the id: the body must never contain one.
        assert "id" not in call_kwargs["body"]
        # kbn-xsrf is injected by the base client for non-GET requests
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope(), status=201)
        )

        panels = [
            {
                "type": "markdown",
                "grid": {"x": 0, "y": 0, "w": 24, "h": 15},
                "config": {"content": "# Hi", "settings": {}},
            }
        ]
        await client.dashboards.create(
            title="Full dashboard",
            description="All fields",
            panels=panels,
            options={"hide_panel_titles": True},
            filters=[{"field": "status", "exists": True}],
            query={"expression": "status:active", "language": "kql"},
            time_range={"from": "now-7d", "to": "now", "mode": "relative"},
            refresh_interval={"pause": True, "value": 60000},
            tags=["tag-a"],
            pinned_panels=[],
            access_control={"access_mode": "default"},
            project_routing="_alias:*",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "title": "Full dashboard",
            "description": "All fields",
            "panels": panels,
            "options": {"hide_panel_titles": True},
            "filters": [{"field": "status", "exists": True}],
            "query": {"expression": "status:active", "language": "kql"},
            "time_range": {"from": "now-7d", "to": "now", "mode": "relative"},
            "refresh_interval": {"pause": True, "value": 60000},
            "tags": ["tag-a"],
            "pinned_panels": [],
            "access_control": {"access_mode": "default"},
            "project_routing": "_alias:*",
        }

    @pytest.mark.asyncio
    async def test_create_with_space_id(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope(), status=201)
        )

        await client.dashboards.create(
            title="Spaced", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/dashboards"

    @pytest.mark.asyncio
    async def test_create_requires_title(self, client):
        with pytest.raises(ValueError, match="title"):
            await client.dashboards.create(title="")


class TestAsyncDashboardsClientGet:
    """Test AsyncDashboardsClient.get()."""

    @pytest.mark.asyncio
    async def test_get_success(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope())
        )

        result = await client.dashboards.get(id="dash-1")

        assert result.body["data"]["title"] == "My dashboard"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/dashboards/dash-1"

    @pytest.mark.asyncio
    async def test_get_url_encodes_id(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope())
        )

        await client.dashboards.get(id="my dashboard/1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/dashboards/my%20dashboard%2F1"

    @pytest.mark.asyncio
    async def test_get_with_space_id(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope())
        )

        await client.dashboards.get(
            id="dash-1", space_id="team-a", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/team-a/api/dashboards/dash-1"

    @pytest.mark.asyncio
    async def test_get_requires_id(self, client):
        with pytest.raises(ValueError, match="id"):
            await client.dashboards.get(id="")

    @pytest.mark.asyncio
    async def test_get_not_found(self, client, mock_async_transport):
        from kibana.exceptions import NotFoundError

        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(
                {
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": (
                        "A dashboard with saved object ID missing was not found."
                    ),
                },
                status=404,
            )
        )

        with pytest.raises(NotFoundError):
            await client.dashboards.get(id="missing")


class TestAsyncDashboardsClientUpdate:
    """Test AsyncDashboardsClient.update() (PUT upsert)."""

    @pytest.mark.asyncio
    async def test_update_minimal(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope(title="Renamed"))
        )

        result = await client.dashboards.update(id="dash-1", title="Renamed")

        assert result.body["data"]["title"] == "Renamed"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/dashboards/dash-1"
        assert call_kwargs["body"] == {"title": "Renamed"}

    @pytest.mark.asyncio
    async def test_update_with_fields_and_space(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response(_dashboard_envelope(), status=201)
        )

        await client.dashboards.update(
            id="custom-id",
            title="Upserted",
            description="Created via PUT",
            tags=["tag-a"],
            time_range={"from": "now-1d", "to": "now"},
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/dashboards/custom-id"
        assert call_kwargs["body"] == {
            "title": "Upserted",
            "description": "Created via PUT",
            "tags": ["tag-a"],
            "time_range": {"from": "now-1d", "to": "now"},
        }

    @pytest.mark.asyncio
    async def test_update_requires_id(self, client):
        with pytest.raises(ValueError, match="id"):
            await client.dashboards.update(id="", title="x")

    @pytest.mark.asyncio
    async def test_update_requires_title(self, client):
        with pytest.raises(ValueError, match="title"):
            await client.dashboards.update(id="dash-1", title="")

    @pytest.mark.asyncio
    async def test_update_rejects_access_control(self, client):
        # PUT /api/dashboards/{id} does not accept access_control
        # (create-only field) — the kwarg must not exist on update().
        with pytest.raises(TypeError, match="access_control"):
            await client.dashboards.update(
                id="dash-1",
                title="x",
                access_control={"access_mode": "default"},
            )


class TestAsyncDashboardsClientDelete:
    """Test AsyncDashboardsClient.delete()."""

    @pytest.mark.asyncio
    async def test_delete_success(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response({}, status=204)
        )

        await client.dashboards.delete(id="dash-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/dashboards/dash-1"
        assert "body" not in call_kwargs

    @pytest.mark.asyncio
    async def test_delete_with_space_id(self, client, mock_async_transport):
        mock_async_transport.perform_request = AsyncMock(
            return_value=_make_response({}, status=204)
        )

        await client.dashboards.delete(
            id="dash-1", space_id="team-a", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/team-a/api/dashboards/dash-1"

    @pytest.mark.asyncio
    async def test_delete_requires_id(self, client):
        with pytest.raises(ValueError, match="id"):
            await client.dashboards.delete(id="")
