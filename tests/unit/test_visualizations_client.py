"""Unit tests for VisualizationsClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.visualizations import VisualizationsClient, _string_array
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


class TestVisualizationsClientInitialization:
    """Test VisualizationsClient initialization and wiring."""

    def test_visualizations_property_returns_client(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.visualizations, VisualizationsClient)

    def test_visualizations_property_caching(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        assert client.visualizations is client.visualizations

    def test_string_array_encoding(self):
        assert _string_array("title") == '["title"]'
        assert _string_array(["title"]) == '["title"]'
        assert _string_array(["title", "description"]) == '["title","description"]'


class TestVisualizationsGetAll:
    """Test VisualizationsClient.get_all()."""

    def test_get_all_no_params(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = Kibana(_transport=mock_transport)

        result = client.visualizations.get_all()

        assert result.body["meta"]["total"] == 0
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/visualizations"
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert "body" not in call_kwargs

    def test_get_all_with_params(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 2, "per_page": 50, "total": 0}}
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.get_all(
            query="kbnpy*",
            search_fields=["title"],
            fields=["title", "description"],
            page=2,
            per_page=50,
        )

        target = mock_transport.perform_request.call_args[1]["target"]
        path, _, qs = target.partition("?")
        assert path == "/api/visualizations"
        assert "query=kbnpy%2A" in qs or "query=kbnpy*" in qs
        # Array params are encoded as JSON array strings (live 9.4.3 rejects
        # single bare values with a 400).
        assert "search_fields=%5B%22title%22%5D" in qs
        assert "fields=%5B%22title%22%2C%22description%22%5D" in qs
        assert "page=2" in qs
        assert "per_page=50" in qs

    def test_get_all_string_search_fields_wrapped(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.get_all(query="x", search_fields="title")

        target = mock_transport.perform_request.call_args[1]["target"]
        assert "search_fields=%5B%22title%22%5D" in target

    def test_get_all_space_scoped(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "meta": {"page": 1, "per_page": 20, "total": 0}}
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.get_all(space_id="marketing", validate_spaces=False)

        target = mock_transport.perform_request.call_args[1]["target"]
        assert target == "/s/marketing/api/visualizations"


class TestVisualizationsCreate:
    """Test VisualizationsClient.create()."""

    def test_create_passes_body(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = Kibana(_transport=mock_transport)
        config = _viz_config()

        result = client.visualizations.create(data=config)

        assert result.body["id"] == "viz-1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/visualizations"
        assert call_kwargs["body"] == config
        # CSRF header injected by the base client for non-GET requests
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    def test_create_with_overwrite(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.create(data=_viz_config(), overwrite=True)

        target = mock_transport.perform_request.call_args[1]["target"]
        assert target == "/api/visualizations?overwrite=true"

    def test_create_space_scoped(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope(), status=201
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.create(
            data=_viz_config(), space_id="team-a", validate_spaces=False
        )

        target = mock_transport.perform_request.call_args[1]["target"]
        assert target == "/s/team-a/api/visualizations"


class TestVisualizationsGet:
    """Test VisualizationsClient.get()."""

    def test_get_by_id(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope("abc-123")
        )
        client = Kibana(_transport=mock_transport)

        result = client.visualizations.get(id="abc-123")

        assert result.body["id"] == "abc-123"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/visualizations/abc-123"

    def test_get_url_encodes_id(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope()
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.get(id="my viz/1")

        target = mock_transport.perform_request.call_args[1]["target"]
        assert target == "/api/visualizations/my%20viz%2F1"

    def test_get_requires_id(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.visualizations.get(id="")

    def test_get_not_found(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "A visualization with saved object id missing was not found.",
            },
            status=404,
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.visualizations.get(id="missing")


class TestVisualizationsUpdate:
    """Test VisualizationsClient.update()."""

    def test_update_passes_body(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope("viz-1", "renamed")
        )
        client = Kibana(_transport=mock_transport)
        config = _viz_config("renamed")

        result = client.visualizations.update(id="viz-1", data=config)

        assert result.body["data"]["title"] == "renamed"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/visualizations/viz-1"
        assert call_kwargs["body"] == config

    def test_update_requires_id(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.visualizations.update(id="", data=_viz_config())

    def test_update_space_scoped(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(
            body=_viz_envelope()
        )
        client = Kibana(_transport=mock_transport)

        client.visualizations.update(
            id="viz-1",
            data=_viz_config(),
            space_id="team-a",
            validate_spaces=False,
        )

        target = mock_transport.perform_request.call_args[1]["target"]
        assert target == "/s/team-a/api/visualizations/viz-1"


class TestVisualizationsDelete:
    """Test VisualizationsClient.delete()."""

    def test_delete_by_id(self, mock_transport, mock_response):
        mock_transport.perform_request.return_value = mock_response(body={}, status=204)
        client = Kibana(_transport=mock_transport)

        client.visualizations.delete(id="viz-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/visualizations/viz-1"
        assert "body" not in call_kwargs
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_delete_requires_id(self, mock_transport):
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.visualizations.delete(id="")
