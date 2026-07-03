"""Unit tests for DataViewsClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.data_views import DataViewsClient
from kibana.exceptions import NotFoundError


@pytest.fixture
def client(mock_transport, mock_response):
    """Kibana client whose transport returns an empty 200 response."""
    mock_transport.perform_request.return_value = mock_response(body={"ok": True})
    return Kibana(_transport=mock_transport)


def _call_kwargs(mock_transport):
    return mock_transport.perform_request.call_args[1]


class TestDataViewsClientInitialization:
    """Test DataViewsClient wiring."""

    def test_initialization(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        data_views = DataViewsClient(client)
        assert data_views._client is client

    def test_namespace_attribute(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.data_views, DataViewsClient)


class TestDataViewCrud:
    """Test data view CRUD methods."""

    def test_get_all(self, client, mock_transport):
        client.data_views.get_all()
        call = _call_kwargs(mock_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views"

    def test_get_all_with_space_id(self, client, mock_transport):
        client.data_views.get_all(space_id="marketing", validate_spaces=False)
        call = _call_kwargs(mock_transport)
        assert call["target"] == "/s/marketing/api/data_views"

    def test_create(self, client, mock_transport):
        client.data_views.create(
            data_view={"title": "logs-*", "timeFieldName": "@timestamp"},
            override=True,
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view"
        assert call["body"] == {
            "data_view": {"title": "logs-*", "timeFieldName": "@timestamp"},
            "override": True,
        }
        # Kibana CSRF and JSON headers injected by the base client
        assert call["headers"]["kbn-xsrf"] == "true"
        assert call["headers"]["content-type"] == "application/json"

    def test_create_omits_unset_override(self, client, mock_transport):
        client.data_views.create(data_view={"title": "logs-*"})
        call = _call_kwargs(mock_transport)
        assert call["body"] == {"data_view": {"title": "logs-*"}}

    def test_create_requires_data_view(self, client):
        with pytest.raises(ValueError, match="data_view"):
            client.data_views.create(data_view=None)

    def test_get(self, client, mock_transport):
        client.data_views.get(view_id="my-view")
        call = _call_kwargs(mock_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views/data_view/my-view"

    def test_get_quotes_view_id(self, client, mock_transport):
        client.data_views.get(view_id="a view/with:odd chars")
        call = _call_kwargs(mock_transport)
        assert (
            call["target"] == "/api/data_views/data_view/a%20view%2Fwith%3Aodd%20chars"
        )

    def test_get_requires_view_id(self, client):
        with pytest.raises(ValueError, match="view_id"):
            client.data_views.get(view_id="")

    def test_update(self, client, mock_transport):
        client.data_views.update(
            view_id="my-view",
            data_view={"name": "renamed"},
            refresh_fields=True,
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view"
        assert call["body"] == {
            "data_view": {"name": "renamed"},
            "refresh_fields": True,
        }

    def test_update_requires_data_view(self, client):
        with pytest.raises(ValueError, match="data_view"):
            client.data_views.update(view_id="my-view", data_view=None)

    def test_delete(self, client, mock_transport):
        client.data_views.delete(view_id="my-view")
        call = _call_kwargs(mock_transport)
        assert call["method"] == "DELETE"
        assert call["target"] == "/api/data_views/data_view/my-view"

    def test_delete_with_space_id(self, client, mock_transport):
        client.data_views.delete(
            view_id="my-view", space_id="team-a", validate_spaces=False
        )
        call = _call_kwargs(mock_transport)
        assert call["target"] == "/s/team-a/api/data_views/data_view/my-view"


class TestFieldsMetadata:
    """Test update_fields_metadata."""

    def test_update_fields_metadata(self, client, mock_transport):
        client.data_views.update_fields_metadata(
            view_id="my-view",
            fields={"price": {"customLabel": "Price (USD)", "count": 2}},
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view/fields"
        assert call["body"] == {
            "fields": {"price": {"customLabel": "Price (USD)", "count": 2}}
        }

    def test_update_fields_metadata_requires_fields(self, client):
        with pytest.raises(ValueError, match="fields"):
            client.data_views.update_fields_metadata(view_id="my-view", fields=None)


class TestRuntimeFields:
    """Test runtime field methods."""

    def test_create_runtime_field(self, client, mock_transport):
        client.data_views.create_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"type": "keyword", "script": {"source": "emit('a')"}},
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/data_view/my-view/runtime_field"
        assert call["body"] == {
            "name": "rt_field",
            "runtimeField": {"type": "keyword", "script": {"source": "emit('a')"}},
        }

    def test_create_runtime_field_requires_name(self, client):
        with pytest.raises(ValueError, match="name"):
            client.data_views.create_runtime_field(
                view_id="my-view", name="", runtime_field={"type": "keyword"}
            )

    def test_create_or_update_runtime_field(self, client, mock_transport):
        client.data_views.create_or_update_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"type": "keyword", "script": {"source": "emit('b')"}},
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "PUT"
        assert call["target"] == "/api/data_views/data_view/my-view/runtime_field"
        assert call["body"] == {
            "name": "rt_field",
            "runtimeField": {"type": "keyword", "script": {"source": "emit('b')"}},
        }

    def test_get_runtime_field(self, client, mock_transport):
        client.data_views.get_runtime_field(view_id="my-view", name="rt field")
        call = _call_kwargs(mock_transport)
        assert call["method"] == "GET"
        assert (
            call["target"]
            == "/api/data_views/data_view/my-view/runtime_field/rt%20field"
        )

    def test_update_runtime_field(self, client, mock_transport):
        client.data_views.update_runtime_field(
            view_id="my-view",
            name="rt_field",
            runtime_field={"script": {"source": "emit('c')"}},
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert (
            call["target"] == "/api/data_views/data_view/my-view/runtime_field/rt_field"
        )
        assert call["body"] == {"runtimeField": {"script": {"source": "emit('c')"}}}

    def test_update_runtime_field_requires_runtime_field(self, client):
        with pytest.raises(ValueError, match="runtime_field"):
            client.data_views.update_runtime_field(
                view_id="my-view", name="rt_field", runtime_field=None
            )

    def test_delete_runtime_field(self, client, mock_transport):
        client.data_views.delete_runtime_field(view_id="my-view", name="rt_field")
        call = _call_kwargs(mock_transport)
        assert call["method"] == "DELETE"
        assert (
            call["target"] == "/api/data_views/data_view/my-view/runtime_field/rt_field"
        )


class TestDefaultDataView:
    """Test default data view methods."""

    def test_get_default(self, client, mock_transport):
        client.data_views.get_default()
        call = _call_kwargs(mock_transport)
        assert call["method"] == "GET"
        assert call["target"] == "/api/data_views/default"

    def test_set_default(self, client, mock_transport):
        client.data_views.set_default(data_view_id="my-view", force=True)
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/default"
        assert call["body"] == {"data_view_id": "my-view", "force": True}

    def test_set_default_none_unsets(self, client, mock_transport):
        client.data_views.set_default(data_view_id=None, force=True)
        call = _call_kwargs(mock_transport)
        assert call["body"] == {"data_view_id": None, "force": True}


class TestSwapReferences:
    """Test swap_references and preview_swap_references."""

    def test_swap_references(self, client, mock_transport):
        client.data_views.swap_references(
            from_id="old-view",
            to_id="new-view",
            from_type="index-pattern",
            for_id=["dash-1", "dash-2"],
            for_type="dashboard",
            delete=True,
        )
        call = _call_kwargs(mock_transport)
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

    def test_swap_references_minimal_body(self, client, mock_transport):
        client.data_views.swap_references(from_id="old-view", to_id="new-view")
        call = _call_kwargs(mock_transport)
        assert call["body"] == {"fromId": "old-view", "toId": "new-view"}

    def test_swap_references_requires_ids(self, client):
        with pytest.raises(ValueError, match="from_id"):
            client.data_views.swap_references(from_id="", to_id="new-view")
        with pytest.raises(ValueError, match="to_id"):
            client.data_views.swap_references(from_id="old-view", to_id="")

    def test_preview_swap_references(self, client, mock_transport):
        client.data_views.preview_swap_references(
            from_id="old-view", to_id="new-view", for_id="dash-1"
        )
        call = _call_kwargs(mock_transport)
        assert call["method"] == "POST"
        assert call["target"] == "/api/data_views/swap_references/_preview"
        assert call["body"] == {
            "fromId": "old-view",
            "toId": "new-view",
            "forId": "dash-1",
        }


class TestErrorHandling:
    """Test error mapping."""

    def test_get_missing_view_raises_not_found(
        self, client, mock_transport, mock_response
    ):
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [index-pattern/missing] not found",
            },
            status=404,
        )
        with pytest.raises(NotFoundError, match="not found"):
            client.data_views.get(view_id="missing")
