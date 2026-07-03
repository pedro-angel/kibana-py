"""Unit tests for AsyncDataViewsClient."""

from unittest.mock import AsyncMock

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.data_views import AsyncDataViewsClient
from kibana.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio


@pytest.fixture
def client(mock_async_transport, mock_response):
    """AsyncKibana client whose transport returns an empty 200 response."""
    mock_async_transport.perform_request = AsyncMock(
        return_value=mock_response(body={"ok": True})
    )
    return AsyncKibana(_transport=mock_async_transport)


def _call_kwargs(mock_async_transport):
    return mock_async_transport.perform_request.call_args[1]


class TestAsyncDataViewsClientInitialization:
    """Test AsyncDataViewsClient wiring."""

    async def test_initialization(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        data_views = AsyncDataViewsClient(client)
        assert data_views._client is client

    async def test_namespace_attribute(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.data_views, AsyncDataViewsClient)


class TestAsyncDataViewCrud:
    """Test data view CRUD methods."""

    async def test_get_all(self, client, mock_async_transport):
        await client.data_views.get_all()
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views"

    async def test_get_all_with_space_id(self, client, mock_async_transport):
        await client.data_views.get_all(space_id="marketing", validate_spaces=False)
        call = _call_kwargs(mock_async_transport)
        assert call["target"] == "/s/marketing/api/data_views"

    async def test_create(self, client, mock_async_transport):
        await client.data_views.create(
            data_view={"title": "logs-*", "timeFieldName": "@timestamp"},
            override=True,
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view"
        assert call["body"] == {
            "data_view": {"title": "logs-*", "timeFieldName": "@timestamp"},
            "override": True,
        }
        # Kibana CSRF and JSON headers injected by the base client
        assert call["headers"]["kbn-xsrf"] == "true"
        assert call["headers"]["content-type"] == "application/json"

    async def test_create_omits_unset_override(self, client, mock_async_transport):
        await client.data_views.create(data_view={"title": "logs-*"})
        call = _call_kwargs(mock_async_transport)
        assert call["body"] == {"data_view": {"title": "logs-*"}}

    async def test_create_requires_data_view(self, client):
        with pytest.raises(ValueError, match="data_view"):
            await client.data_views.create(data_view=None)

    async def test_get(self, client, mock_async_transport):
        await client.data_views.get(view_id="my-view")
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views/data_view/my-view"

    async def test_get_quotes_view_id(self, client, mock_async_transport):
        await client.data_views.get(view_id="a view/with:odd chars")
        call = _call_kwargs(mock_async_transport)
        assert (
            call["target"] == "/api/data_views/data_view/a%20view%2Fwith%3Aodd%20chars"
        )

    async def test_get_requires_view_id(self, client):
        with pytest.raises(ValueError, match="view_id"):
            await client.data_views.get(view_id="")

    async def test_update(self, client, mock_async_transport):
        await client.data_views.update(
            view_id="my-view",
            data_view={"name": "renamed"},
            refresh_fields=True,
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view"
        assert call["body"] == {
            "data_view": {"name": "renamed"},
            "refresh_fields": True,
        }

    async def test_update_requires_data_view(self, client):
        with pytest.raises(ValueError, match="data_view"):
            await client.data_views.update(view_id="my-view", data_view=None)

    async def test_delete(self, client, mock_async_transport):
        await client.data_views.delete(view_id="my-view")
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "DELETE"
        assert call["target"] == "/api/data_views/data_view/my-view"

    async def test_delete_with_space_id(self, client, mock_async_transport):
        await client.data_views.delete(
            view_id="my-view", space_id="team-a", validate_spaces=False
        )
        call = _call_kwargs(mock_async_transport)
        assert call["target"] == "/s/team-a/api/data_views/data_view/my-view"


class TestAsyncFieldsMetadata:
    """Test update_fields_metadata."""

    async def test_update_fields_metadata(self, client, mock_async_transport):
        await client.data_views.update_fields_metadata(
            view_id="my-view",
            fields={"price": {"customLabel": "Price (USD)", "count": 2}},
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view/fields"
        assert call["body"] == {
            "fields": {"price": {"customLabel": "Price (USD)", "count": 2}}
        }

    async def test_update_fields_metadata_requires_fields(self, client):
        with pytest.raises(ValueError, match="fields"):
            await client.data_views.update_fields_metadata(
                view_id="my-view", fields=None
            )


class TestAsyncRuntimeFields:
    """Test runtime field methods."""

    async def test_create_runtime_field(self, client, mock_async_transport):
        await client.data_views.create_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"type": "keyword", "script": {"source": "emit('a')"}},
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view/runtime_field"
        assert call["body"] == {
            "name": "rt_field",
            "runtimeField": {"type": "keyword", "script": {"source": "emit('a')"}},
        }

    async def test_create_runtime_field_requires_name(self, client):
        with pytest.raises(ValueError, match="name"):
            await client.data_views.create_runtime_field(
                view_id="my-view", name="", runtime_field={"type": "keyword"}
            )

    async def test_create_or_update_runtime_field(self, client, mock_async_transport):
        await client.data_views.create_or_update_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"type": "keyword", "script": {"source": "emit('b')"}},
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "PUT"
        assert call["target"] == "/api/data_views/data_view/my-view/runtime_field"
        assert call["body"] == {
            "name": "rt_field",
            "runtimeField": {"type": "keyword", "script": {"source": "emit('b')"}},
        }

    async def test_get_runtime_field(self, client, mock_async_transport):
        await client.data_views.get_runtime_field(view_id="my-view", name="rt field")
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "GET"
        assert (
            call["target"]
            == "/api/data_views/data_view/my-view/runtime_field/rt%20field"
        )

    async def test_update_runtime_field(self, client, mock_async_transport):
        await client.data_views.update_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"script": {"source": "emit('c')"}},
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert (
            call["target"] == "/api/data_views/data_view/my-view/runtime_field/rt_field"
        )
        assert call["body"] == {"runtimeField": {"script": {"source": "emit('c')"}}}

    async def test_update_runtime_field_requires_runtime_field(self, client):
        with pytest.raises(ValueError, match="runtime_field"):
            await client.data_views.update_runtime_field(
                view_id="my-view", name="rt_field", runtime_field=None
            )

    async def test_delete_runtime_field(self, client, mock_async_transport):
        await client.data_views.delete_runtime_field(view_id="my-view", name="rt_field")
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "DELETE"
        assert (
            call["target"] == "/api/data_views/data_view/my-view/runtime_field/rt_field"
        )


class TestAsyncDefaultDataView:
    """Test default data view methods."""

    async def test_get_default(self, client, mock_async_transport):
        await client.data_views.get_default()
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views/default"

    async def test_set_default(self, client, mock_async_transport):
        await client.data_views.set_default(data_view_id="my-view", force=True)
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/default"
        assert call["body"] == {"data_view_id": "my-view", "force": True}

    async def test_set_default_none_unsets(self, client, mock_async_transport):
        await client.data_views.set_default(data_view_id=None, force=True)
        call = _call_kwargs(mock_async_transport)
        assert call["body"] == {"data_view_id": None, "force": True}


class TestAsyncSwapReferences:
    """Test swap_references and preview_swap_references."""

    async def test_swap_references(self, client, mock_async_transport):
        await client.data_views.swap_references(
            from_id="old-view",
            to_id="new-view",
            from_type="index-pattern",
            for_id=["dash-1", "dash-2"],
            for_type="dashboard",
            delete=True,
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/swap_references"
        assert call["body"] == {
            "fromId": "old-view",
            "toId": "new-view",
            "fromType": "index-pattern",
            "forId": ["dash-1", "dash-2"],
            "forType": "dashboard",
            "delete": True,
        }

    async def test_swap_references_minimal_body(self, client, mock_async_transport):
        await client.data_views.swap_references(from_id="old-view", to_id="new-view")
        call = _call_kwargs(mock_async_transport)
        assert call["body"] == {"fromId": "old-view", "toId": "new-view"}

    async def test_swap_references_requires_ids(self, client):
        with pytest.raises(ValueError, match="from_id"):
            await client.data_views.swap_references(from_id="", to_id="new-view")
        with pytest.raises(ValueError, match="to_id"):
            await client.data_views.swap_references(from_id="old-view", to_id="")

    async def test_preview_swap_references(self, client, mock_async_transport):
        await client.data_views.preview_swap_references(
            from_id="old-view", to_id="new-view", for_id="dash-1"
        )
        call = _call_kwargs(mock_async_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/swap_references/_preview"
        assert call["body"] == {
            "fromId": "old-view",
            "toId": "new-view",
            "forId": "dash-1",
        }


class TestAsyncErrorHandling:
    """Test error mapping."""

    async def test_get_missing_view_raises_not_found(
        self, client, mock_async_transport, mock_response
    ):
        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "statusCode": 404,
                    "error": "Not Found",
                    "message": "Saved object [index-pattern/missing] not found",
                },
                status=404,
            )
        )
        with pytest.raises(NotFoundError, match="not found"):
            await client.data_views.get(view_id="missing")
