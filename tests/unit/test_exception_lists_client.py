"""Unit tests for ExceptionListsClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.exception_lists import ExceptionListsClient
from kibana.exceptions import NotFoundError


def _list_body(**overrides):
    """Build a representative exception list response body (9.4.3)."""
    body = {
        "id": "46c06b89-e347-4e35-823f-194e82ff3bd3",
        "list_id": "trusted-hosts",
        "type": "detection",
        "name": "Trusted hosts",
        "description": "Hosts that never alert",
        "immutable": False,
        "namespace_type": "single",
        "os_types": [],
        "tags": [],
        "version": 1,
        "_version": "WzE2LDJd",
        "tie_breaker_id": "b5a58185-8b99-4b81-a479-bd0dc2aaf1f7",
        "created_at": "2026-07-06T21:30:42.635Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T21:30:42.635Z",
        "updated_by": "elastic",
    }
    body.update(overrides)
    return body


def _item_body(**overrides):
    """Build a representative exception list item response body (9.4.3)."""
    body = {
        "id": "53d8edfc-eebd-41da-986d-9905380537e9",
        "item_id": "trusted-host-item",
        "list_id": "trusted-hosts",
        "type": "simple",
        "name": "Trusted host",
        "description": "Ignore the build server",
        "entries": [
            {
                "type": "match",
                "field": "host.name",
                "value": "build-server-01",
                "operator": "included",
            }
        ],
        "namespace_type": "single",
        "os_types": [],
        "tags": [],
        "comments": [],
        "_version": "WzE4LDJd",
        "tie_breaker_id": "e1926a82-9bb5-4dd2-84d5-7522e0e9ddd0",
        "created_at": "2026-07-06T21:30:55.683Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T21:30:55.683Z",
        "updated_by": "elastic",
    }
    body.update(overrides)
    return body


_ENTRIES = [
    {
        "field": "host.name",
        "operator": "included",
        "type": "match",
        "value": "build-server-01",
    }
]


class TestExceptionListsClientInitialization:
    """Test ExceptionListsClient initialization and wiring."""

    def test_initialization(self, mock_transport):
        """Test that ExceptionListsClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        exception_lists_client = ExceptionListsClient(client)
        assert exception_lists_client._client is client

    def test_property_returns_client(self, mock_transport):
        """Test that client.exception_lists returns an ExceptionListsClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.exception_lists, ExceptionListsClient)

    def test_property_caching(self, mock_transport):
        """Test that the exception_lists property returns the same instance."""
        client = Kibana(_transport=mock_transport)
        assert client.exception_lists is client.exception_lists


class TestExceptionListsCrud:
    """Test exception list container CRUD methods."""

    def test_create_minimal(self, mock_transport, mock_response):
        """Test creating an exception list with only required fields."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create(
            name="Trusted hosts",
            description="Hosts that never alert",
            type="detection",
        )

        assert result.body["list_id"] == "trusted-hosts"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/exception_lists"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["body"] == {
            "name": "Trusted hosts",
            "description": "Hosts that never alert",
            "type": "detection",
        }

    def test_create_full_body(self, mock_transport, mock_response):
        """Test that all optional create fields are passed through."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.create(
            name="Trusted hosts",
            description="Hosts that never alert",
            type="detection",
            list_id="trusted-hosts",
            meta={"team": "sec"},
            namespace_type="agnostic",
            os_types=["linux"],
            tags=["kbnpy"],
            version=2,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "Trusted hosts",
            "description": "Hosts that never alert",
            "type": "detection",
            "list_id": "trusted-hosts",
            "meta": {"team": "sec"},
            "namespace_type": "agnostic",
            "os_types": ["linux"],
            "tags": ["kbnpy"],
            "version": 2,
        }

    def test_create_in_space(self, mock_transport, mock_response):
        """Test that space_id builds a /s/<space>/ prefixed path."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.create(
            name="Trusted hosts",
            description="Hosts that never alert",
            type="detection",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/exception_lists"

    def test_get_by_list_id(self, mock_transport, mock_response):
        """Test getting an exception list by list_id."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.get(
            list_id="trusted-hosts", namespace_type="single"
        )

        assert result.body["name"] == "Trusted hosts"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/exception_lists?list_id=trusted-hosts&namespace_type=single"
        )
        # GET requests must not carry a kbn-xsrf header
        assert "kbn-xsrf" not in call_kwargs.get("headers", {})

    def test_get_requires_id_or_list_id(self, mock_transport):
        """Test that get() raises ValueError without id/list_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'list_id'"):
            client.exception_lists.get()
        mock_transport.perform_request.assert_not_called()

    def test_update(self, mock_transport, mock_response):
        """Test updating an exception list passes the full body."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.update(
            name="Updated",
            description="Updated description",
            type="detection",
            list_id="trusted-hosts",
            _version="WzE2LDJd",
            tags=["updated"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/exception_lists"
        assert call_kwargs["body"] == {
            "name": "Updated",
            "description": "Updated description",
            "type": "detection",
            "list_id": "trusted-hosts",
            "_version": "WzE2LDJd",
            "tags": ["updated"],
        }

    def test_delete_by_id(self, mock_transport, mock_response):
        """Test deleting an exception list by id."""
        mock_transport.perform_request.return_value = mock_response(body=_list_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.delete(
            id="46c06b89-e347-4e35-823f-194e82ff3bd3", namespace_type="single"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/exception_lists"
            "?id=46c06b89-e347-4e35-823f-194e82ff3bd3&namespace_type=single"
        )

    def test_delete_requires_id_or_list_id(self, mock_transport):
        """Test that delete() raises ValueError without id/list_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'list_id'"):
            client.exception_lists.delete()

    def test_get_not_found_error(self, mock_transport, mock_response):
        """Test that a 404 response maps to NotFoundError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": 'exception list list_id: "missing" does not exist',
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.exception_lists.get(list_id="missing")


class TestExceptionListsFindDuplicateExportImport:
    """Test find, duplicate, export, import and summary methods."""

    def test_find_no_params(self, mock_transport, mock_response):
        """Test find() without parameters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [_list_body()], "page": 1, "per_page": 20, "total": 1}
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.find()

        assert result.body["total"] == 1
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/exception_lists/_find"

    def test_find_param_encoding(self, mock_transport, mock_response):
        """Test find() query parameter encoding, including repeated keys."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "page": 2, "per_page": 5, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.exception_lists.find(
            filter="exception-list.attributes.name:Trusted*",
            namespace_type=["single", "agnostic"],
            page=2,
            per_page=5,
            sort_field="name",
            sort_order="asc",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/exception_lists/_find"
            "?filter=exception-list.attributes.name%3ATrusted%2A"
            "&namespace_type=single&namespace_type=agnostic"
            "&page=2&per_page=5&sort_field=name&sort_order=asc"
        )

    def test_duplicate(self, mock_transport, mock_response):
        """Test duplicate() sends required query params with defaults."""
        mock_transport.perform_request.return_value = mock_response(
            body=_list_body(name="Trusted hosts [Duplicate]")
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.duplicate(
            list_id="trusted-hosts", namespace_type="single"
        )

        assert result.body["name"] == "Trusted hosts [Duplicate]"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/exception_lists/_duplicate"
            "?list_id=trusted-hosts&namespace_type=single"
            "&include_expired_exceptions=true"
        )

    def test_export(self, mock_transport, mock_response):
        """Test export() sends all four required query params."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.exception_lists.export(
            id="46c06b89-e347-4e35-823f-194e82ff3bd3",
            list_id="trusted-hosts",
            namespace_type="single",
            include_expired_exceptions=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/exception_lists/_export"
            "?id=46c06b89-e347-4e35-823f-194e82ff3bd3"
            "&list_id=trusted-hosts&namespace_type=single"
            "&include_expired_exceptions=false"
        )

    def test_import_lists_builds_multipart_body(self, mock_transport, mock_response):
        """Test import_lists() uploads NDJSON as multipart/form-data."""
        mock_transport.perform_request.return_value = mock_response(
            body={"success": True, "success_count": 2, "errors": []}
        )
        ndjson = b'{"list_id": "trusted-hosts"}\n'

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.import_lists(file=ndjson)

        assert result.body["success"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/exception_lists/_import"

        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]

        body = call_kwargs["body"]
        assert isinstance(body, bytes)
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"--{boundary}--\r\n".encode())
        assert b'Content-Disposition: form-data; name="file"' in body
        assert b'filename="import.ndjson"' in body
        assert ndjson in body

    def test_import_lists_query_params(self, mock_transport, mock_response):
        """Test import_lists() encodes overwrite/as_new_list query params."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.exception_lists.import_lists(
            file='{"list_id": "x"}\n', overwrite=True, as_new_list=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/exception_lists/_import?overwrite=true&as_new_list=false"
        )

    def test_import_lists_encodes_list_to_ndjson(self, mock_transport, mock_response):
        """Test import_lists() NDJSON-encodes a list of dicts."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.exception_lists.import_lists(
            file=[{"list_id": "a"}, {"item_id": "b"}],
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert b'{"list_id": "a"}\n{"item_id": "b"}\n' in body

    def test_import_lists_validates_file(self, mock_transport):
        """Test import_lists() raises ValueError for an empty file."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'file' is required"):
            client.exception_lists.import_lists(file=b"")
        mock_transport.perform_request.assert_not_called()

    def test_get_summary(self, mock_transport, mock_response):
        """Test get_summary() query parameter encoding."""
        mock_transport.perform_request.return_value = mock_response(
            body={"windows": 0, "linux": 1, "macos": 0, "total": 1}
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.get_summary(
            list_id="trusted-hosts",
            namespace_type="single",
            filter="exception-list.attributes.name:*",
        )

        assert result.body["total"] == 1
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/exception_lists/summary"
            "?list_id=trusted-hosts&namespace_type=single"
            "&filter=exception-list.attributes.name%3A%2A"
        )

    def test_get_summary_requires_id_or_list_id(self, mock_transport):
        """Test that get_summary() raises ValueError without id/list_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'list_id'"):
            client.exception_lists.get_summary()


class TestExceptionListItems:
    """Test exception list item methods."""

    def test_create_item(self, mock_transport, mock_response):
        """Test creating an exception list item."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create_item(
            list_id="trusted-hosts",
            name="Trusted host",
            description="Ignore the build server",
            entries=_ENTRIES,
            item_id="trusted-host-item",
            expire_time="2027-01-01T00:00:00.000Z",
            comments=[{"comment": "added by kbnpy"}],
            os_types=["linux"],
            tags=["kbnpy"],
        )

        assert result.body["item_id"] == "trusted-host-item"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/exception_lists/items"
        assert call_kwargs["body"] == {
            "list_id": "trusted-hosts",
            "name": "Trusted host",
            "description": "Ignore the build server",
            "entries": _ENTRIES,
            "type": "simple",
            "item_id": "trusted-host-item",
            "expire_time": "2027-01-01T00:00:00.000Z",
            "comments": [{"comment": "added by kbnpy"}],
            "os_types": ["linux"],
            "tags": ["kbnpy"],
        }

    def test_get_item_by_item_id(self, mock_transport, mock_response):
        """Test getting an exception list item by item_id."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.get_item(
            item_id="trusted-host-item", namespace_type="single"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/exception_lists/items?item_id=trusted-host-item"
            "&namespace_type=single"
        )

    def test_get_item_requires_id_or_item_id(self, mock_transport):
        """Test that get_item() raises ValueError without id/item_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'item_id'"):
            client.exception_lists.get_item()

    def test_update_item(self, mock_transport, mock_response):
        """Test updating an exception list item."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.update_item(
            item_id="trusted-host-item",
            name="Updated item",
            description="Updated description",
            entries=_ENTRIES,
            _version="WzE4LDJd",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/exception_lists/items"
        assert call_kwargs["body"] == {
            "name": "Updated item",
            "description": "Updated description",
            "entries": _ENTRIES,
            "type": "simple",
            "item_id": "trusted-host-item",
            "_version": "WzE4LDJd",
        }

    def test_delete_item(self, mock_transport, mock_response):
        """Test deleting an exception list item by item_id."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.delete_item(item_id="trusted-host-item")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/exception_lists/items?item_id=trusted-host-item"
        )

    def test_delete_item_requires_id_or_item_id(self, mock_transport):
        """Test that delete_item() raises ValueError without id/item_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'item_id'"):
            client.exception_lists.delete_item()

    def test_find_items_multiple_lists(self, mock_transport, mock_response):
        """Test find_items() encodes repeated list_id/namespace_type keys."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [_item_body()], "page": 1, "per_page": 20, "total": 1}
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.find_items(
            list_id=["list-a", "list-b"],
            namespace_type=["single", "agnostic"],
            search="host",
            page=1,
            per_page=20,
            sort_field="created_at",
            sort_order="desc",
        )

        assert result.body["total"] == 1
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/exception_lists/items/_find"
            "?list_id=list-a&list_id=list-b"
            "&namespace_type=single&namespace_type=agnostic"
            "&search=host&page=1&per_page=20"
            "&sort_field=created_at&sort_order=desc"
        )

    def test_find_items_in_space(self, mock_transport, mock_response):
        """Test find_items() with a space_id."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "page": 1, "per_page": 20, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.exception_lists.find_items(
            list_id="trusted-hosts", space_id="marketing", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/s/marketing/api/exception_lists/items/_find?list_id=trusted-hosts"
        )


class TestSharedAndRuleExceptions:
    """Test shared exception list and rule default exception methods."""

    def test_create_shared_list(self, mock_transport, mock_response):
        """Test creating a shared exception list."""
        mock_transport.perform_request.return_value = mock_response(
            body=_list_body(name="Shared exceptions")
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create_shared_list(
            name="Shared exceptions",
            description="Exceptions shared across rules",
        )

        assert result.body["type"] == "detection"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/exceptions/shared"
        assert call_kwargs["body"] == {
            "name": "Shared exceptions",
            "description": "Exceptions shared across rules",
        }

    def test_create_rule_exceptions(self, mock_transport, mock_response):
        """Test creating rule default exception items."""
        mock_transport.perform_request.return_value = mock_response(body=[_item_body()])
        items = [
            {
                "name": "Rule exception",
                "description": "Suppress the build server",
                "type": "simple",
                "entries": _ENTRIES,
            }
        ]

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create_rule_exceptions(
            id="4656dc92-5832-11ea-8e2d-0242ac130003", items=items
        )

        assert result.body[0]["item_id"] == "trusted-host-item"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/detection_engine/rules"
            "/4656dc92-5832-11ea-8e2d-0242ac130003/exceptions"
        )
        assert call_kwargs["body"] == {"items": items}

    def test_create_rule_exceptions_quotes_rule_id(self, mock_transport, mock_response):
        """Test that the rule id path parameter is URL-encoded."""
        mock_transport.perform_request.return_value = mock_response(body=[])

        client = Kibana(_transport=mock_transport)
        client.exception_lists.create_rule_exceptions(id="rule id/1", items=[])

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/detection_engine/rules/rule%20id%2F1/exceptions"
        )


class TestEndpointList:
    """Test Elastic Endpoint exception list methods."""

    def test_create_endpoint_list(self, mock_transport, mock_response):
        """Test creating the endpoint exception list (idempotent)."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create_endpoint_list()

        assert result.body == {}
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/endpoint_list"
        assert "body" not in call_kwargs

    def test_create_endpoint_item(self, mock_transport, mock_response):
        """Test creating an endpoint exception list item."""
        mock_transport.perform_request.return_value = mock_response(
            body=_item_body(list_id="endpoint_list", namespace_type="agnostic")
        )

        client = Kibana(_transport=mock_transport)
        result = client.exception_lists.create_endpoint_item(
            name="Trusted process",
            description="Ignore the backup agent",
            entries=_ENTRIES,
            item_id="trusted-process",
            os_types=["windows"],
            tags=["kbnpy"],
        )

        assert result.body["list_id"] == "endpoint_list"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/endpoint_list/items"
        assert call_kwargs["body"] == {
            "name": "Trusted process",
            "description": "Ignore the backup agent",
            "entries": _ENTRIES,
            "type": "simple",
            "item_id": "trusted-process",
            "os_types": ["windows"],
            "tags": ["kbnpy"],
        }

    def test_get_endpoint_item(self, mock_transport, mock_response):
        """Test getting an endpoint exception list item."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.get_endpoint_item(item_id="trusted-process")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/endpoint_list/items?item_id=trusted-process"
        )

    def test_get_endpoint_item_requires_id_or_item_id(self, mock_transport):
        """Test that get_endpoint_item() raises ValueError without id/item_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'item_id'"):
            client.exception_lists.get_endpoint_item()

    def test_update_endpoint_item(self, mock_transport, mock_response):
        """Test updating an endpoint exception list item."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.update_endpoint_item(
            id="53d8edfc-eebd-41da-986d-9905380537e9",
            name="Updated",
            description="Updated description",
            entries=_ENTRIES,
            os_types=["windows"],
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/endpoint_list/items"
        assert call_kwargs["body"] == {
            "name": "Updated",
            "description": "Updated description",
            "entries": _ENTRIES,
            "type": "simple",
            "id": "53d8edfc-eebd-41da-986d-9905380537e9",
            "os_types": ["windows"],
        }

    def test_delete_endpoint_item(self, mock_transport, mock_response):
        """Test deleting an endpoint exception list item."""
        mock_transport.perform_request.return_value = mock_response(body=_item_body())

        client = Kibana(_transport=mock_transport)
        client.exception_lists.delete_endpoint_item(item_id="trusted-process")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == (
            "/api/endpoint_list/items?item_id=trusted-process"
        )

    def test_delete_endpoint_item_requires_id_or_item_id(self, mock_transport):
        """Test that delete_endpoint_item() raises ValueError without id/item_id."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' or 'item_id'"):
            client.exception_lists.delete_endpoint_item()

    def test_find_endpoint_items(self, mock_transport, mock_response):
        """Test find_endpoint_items() query parameter encoding."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "page": 1, "per_page": 10, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.exception_lists.find_endpoint_items(
            filter="exception-list-agnostic.attributes.name:Trusted*",
            page=1,
            per_page=10,
            sort_field="name",
            sort_order="asc",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/endpoint_list/items/_find"
            "?filter=exception-list-agnostic.attributes.name%3ATrusted%2A"
            "&page=1&per_page=10&sort_field=name&sort_order=asc"
        )

    def test_find_endpoint_items_no_params(self, mock_transport, mock_response):
        """Test find_endpoint_items() without parameters."""
        mock_transport.perform_request.return_value = mock_response(
            body={"data": [], "page": 1, "per_page": 20, "total": 0}
        )

        client = Kibana(_transport=mock_transport)
        client.exception_lists.find_endpoint_items()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/endpoint_list/items/_find"
