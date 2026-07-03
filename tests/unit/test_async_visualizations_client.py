"""Unit tests for AsyncVisualizationsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.visualizations import (
    AsyncVisualizationsClient,
    _string_array,
)
from kibana.exceptions import NotFoundError


def _viz_config(title: str = "kbnpy test metric") -> dict:
    """Minimal metric visualization config accepted by Kibana 9.4.3."""
    return {
        "type": "metric",
        "title": title,
        "data_source": {
            "type": "data_view_spec",
            "index_pattern": "kbnpy-visualizations-*",
        },
        "query": {"expression": "", "language": "kql"},
        "metrics": [{"type": "primary", "operation": "count"}],
    }


def _viz_envelope(viz_id: str = "viz-1", title: str = "kbnpy test metric") -> dict:
    """Response envelope returned by the Visualizations API."""
    return {
        "id": viz_id,
        "data": _viz_config(title),
        "meta": {
            "created_at": "2026-07-03T00:00:00.000Z",
            "updated_at": "2026-07-03T00:00:00.000Z",
            "managed": False,
            "version": "WzEsMV0=",
        },
    }


class TestAsyncVisualizationsClientInitialization:
    """Test AsyncVisualizationsClient initialization and wiring."""

    async def test_visualizations_property_returns_client(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.visualizations, AsyncVisualizationsClient)

    async def test_visualizations_property_caching(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.visualizations is client.visualizations

    def test_string_array_encoding(self):
        assert _string_array("title") == '["title"]'
        assert _string_array(["title"]) == '["title"]'
        assert _string_array(["title", "description"]) == '["title","description"]'


class TestAsyncVisualizationsGetAll:
    """Test AsyncVisualizationsClient.get_all()."""

    async def test_get_all_no_params(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.visualizations.get_all()

        assert result.body["meta"]["total"] == 0
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/visualizations"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert "body" not in call_kwargs

    async def test_get_all_with_params(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 2, "per_page": 50, "total": 0}}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.get_all(
            query="kbnpy*",
            search_fields=["title"],
            fields=["title", "description"],
            page=2,
            per_page=50,
        )

        target = mock_async_transport.perform_request.call_args[1]["target"]
        path, _, qs = target.partition("?")
        assert path == "/api/visualizations"
        assert "query=kbnpy%2A" in qs or "query=kbnpy*" in qs
        # Array params are encoded as JSON array strings (live 9.4.3 rejects
        # single bare values with a 400).
        assert "search_fields=%5B%22title%22%5D" in qs
        assert "fields=%5B%22title%22%2C%22description%22%5D" in qs
        assert "page=2" in qs
        assert "per_page=50" in qs

    async def test_get_all_string_search_fields_wrapped(
        self, mock_async_transport, mock_response
    ):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.get_all(query="x", search_fields="title")

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert "search_fields=%5B%22title%22%5D" in target

    async def test_get_all_space_scoped(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.get_all(space_id="marketing", validate_spaces=False)

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target == "/s/marketing/api/visualizations"


class TestAsyncVisualizationsCreate:
    """Test AsyncVisualizationsClient.create()."""

    async def test_create_passes_body(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = AsyncKibana(_transport=mock_async_transport)
        config = _viz_config()

        result = await client.visualizations.create(data=config)

        assert result.body["id"] == "viz-1"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/visualizations"
        assert call_kwargs["body"] == config
        # CSRF header injected by the base client for non-GET requests
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    async def test_create_with_overwrite(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.create(data=_viz_config(), overwrite=True)

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target == "/api/visualizations?overwrite=true"

    async def test_create_space_scoped(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.create(
            data=_viz_config(), space_id="team-a", validate_spaces=False
        )

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target == "/s/team-a/api/visualizations"


class TestAsyncVisualizationsGet:
    """Test AsyncVisualizationsClient.get()."""

    async def test_get_by_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope("abc-123")
        )
        client = AsyncKibana(_transport=mock_async_transport)

        result = await client.visualizations.get(id="abc-123")

        assert result.body["id"] == "abc-123"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/visualizations/abc-123"

    async def test_get_url_encodes_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.get(id="my viz/1")

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target == "/api/visualizations/my%20viz%2F1"

    async def test_get_requires_id(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.visualizations.get(id="")

    async def test_get_not_found(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "A visualization with saved object id missing was not found.",
            },
            status=404,
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.visualizations.get(id="missing")


class TestAsyncVisualizationsUpdate:
    """Test AsyncVisualizationsClient.update()."""

    async def test_update_passes_body(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope("viz-1", "renamed")
        )
        client = AsyncKibana(_transport=mock_async_transport)
        config = _viz_config("renamed")

        result = await client.visualizations.update(id="viz-1", data=config)

        assert result.body["data"]["title"] == "renamed"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/visualizations/viz-1"
        assert call_kwargs["body"] == config

    async def test_update_requires_id(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.visualizations.update(id="", data=_viz_config())

    async def test_update_space_scoped(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body=_viz_envelope()
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.update(
            id="viz-1",
            data=_viz_config(),
            space_id="team-a",
            validate_spaces=False,
        )

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target == "/s/team-a/api/visualizations/viz-1"


class TestAsyncVisualizationsDelete:
    """Test AsyncVisualizationsClient.delete()."""

    async def test_delete_by_id(self, mock_async_transport, mock_response):
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )
        client = AsyncKibana(_transport=mock_async_transport)

        await client.visualizations.delete(id="viz-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/visualizations/viz-1"
        assert "body" not in call_kwargs
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    async def test_delete_requires_id(self, mock_async_transport):
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.visualizations.delete(id="")
