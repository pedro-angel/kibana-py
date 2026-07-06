"""Unit tests for AsyncListsClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.lists import (
    AsyncListsClient,
    _build_multipart_body,
    _LenientNdjsonSerializer,
    _values_file_bytes,
)
from kibana.exceptions import AuthorizationException, NotFoundError


def _list_body(**overrides):
    """Build a representative value list response body (9.4.3 shape)."""
    body = {
        "id": "kbnpy-lists-unit",
        "type": "ip",
        "name": "kbnpy unit list",
        "description": "unit test list",
        "immutable": False,
        "@timestamp": "2026-07-06T21:31:06.642Z",
        "version": 1,
        "_version": "WzAsMV0=",
        "tie_breaker_id": "4b3e169a-07c2-4579-be76-7f9ead1ff662",
        "created_at": "2026-07-06T21:31:06.642Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T21:31:06.642Z",
        "updated_by": "elastic",
    }
    body.update(overrides)
    return body


def _item_body(**overrides):
    """Build a representative value list item response body (9.4.3 shape)."""
    body = {
        "id": "6d225b25-537b-4ba0-9f7e-fcd45ec36cbe",
        "type": "ip",
        "list_id": "kbnpy-lists-unit",
        "value": "10.7.7.7",
        "@timestamp": "2026-07-06T21:31:06.972Z",
        "_version": "WzAsMV0=",
        "tie_breaker_id": "811ee64a-c5f5-4222-9bfe-017917362bc2",
        "created_at": "2026-07-06T21:31:06.972Z",
        "created_by": "elastic",
        "updated_at": "2026-07-06T21:31:06.972Z",
        "updated_by": "elastic",
    }
    body.update(overrides)
    return body


class TestAsyncListsClientInitialization:
    """Test AsyncListsClient initialization."""

    @pytest.mark.asyncio
    async def test_lists_client_initialization(self, mock_async_transport):
        """Test that AsyncListsClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        lists_client = AsyncListsClient(client)
        assert lists_client._client is client

    @pytest.mark.asyncio
    async def test_lists_property_returns_client(self, mock_async_transport):
        """Test that client.lists returns an AsyncListsClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.lists, AsyncListsClient)

    @pytest.mark.asyncio
    async def test_lists_property_caching(self, mock_async_transport):
        """Test that the lists property returns the same instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert client.lists is client.lists


class TestAsyncListsClientCreate:
    """Test AsyncListsClient.create() method."""

    @pytest.mark.asyncio
    async def test_create_minimal(self, mock_async_transport, mock_response):
        """Test creating a list with only the required parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.create(
            name="kbnpy unit list", description="unit test list", type="ip"
        )

        assert result.body["id"] == "kbnpy-lists-unit"

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/lists"
        assert call_kwargs["body"] == {
            "name": "kbnpy unit list",
            "description": "unit test list",
            "type": "ip",
        }
        assert call_kwargs["headers"]["accept"] == "application/json"
        assert call_kwargs["headers"]["content-type"] == "application/json"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_create_with_all_options(self, mock_async_transport, mock_response):
        """Test creating a list with id, meta and version."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.create(
            name="kbnpy unit list",
            description="unit test list",
            type="keyword",
            id="kbnpy-lists-unit",
            meta={"team": "sec"},
            version=2,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "kbnpy unit list",
            "description": "unit test list",
            "type": "keyword",
            "id": "kbnpy-lists-unit",
            "meta": {"team": "sec"},
            "version": 2,
        }

    @pytest.mark.asyncio
    async def test_create_in_space(self, mock_async_transport, mock_response):
        """Test that space_id builds a /s/<space> path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.create(
            name="n",
            description="d",
            type="ip",
            space_id="marketing",
            validate_spaces=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/lists"


class TestAsyncListsClientGet:
    """Test AsyncListsClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_async_transport, mock_response):
        """Test getting a list by ID (id as query parameter)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.get(id="kbnpy-lists-unit")

        assert result.body["name"] == "kbnpy unit list"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/lists?id=kbnpy-lists-unit"
        assert call_kwargs["headers"] == {"accept": "application/json"}
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_get_encodes_id(self, mock_async_transport, mock_response):
        """Test that the list ID is URL-encoded in the query string."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.get(id="a list/id")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/lists?id=a+list%2Fid"


class TestAsyncListsClientUpdate:
    """Test AsyncListsClient.update() method."""

    @pytest.mark.asyncio
    async def test_update_required_fields(self, mock_async_transport, mock_response):
        """Test updating a list with the required fields only."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.update(
            id="kbnpy-lists-unit", name="new name", description="new description"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/lists"
        assert call_kwargs["body"] == {
            "id": "kbnpy-lists-unit",
            "name": "new name",
            "description": "new description",
        }

    @pytest.mark.asyncio
    async def test_update_with_version_fields(
        self, mock_async_transport, mock_response
    ):
        """Test that _version, meta and version are passed through."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.update(
            id="kbnpy-lists-unit",
            name="n",
            description="d",
            _version="WzEsMV0=",
            meta={"k": "v"},
            version=3,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"]["_version"] == "WzEsMV0="
        assert call_kwargs["body"]["meta"] == {"k": "v"}
        assert call_kwargs["body"]["version"] == 3


class TestAsyncListsClientPatch:
    """Test AsyncListsClient.patch() method."""

    @pytest.mark.asyncio
    async def test_patch_partial_body(self, mock_async_transport, mock_response):
        """Test that patch only sends the provided fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.patch(id="kbnpy-lists-unit", name="patched")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/lists"
        assert call_kwargs["body"] == {"id": "kbnpy-lists-unit", "name": "patched"}


class TestAsyncListsClientDelete:
    """Test AsyncListsClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_async_transport, mock_response):
        """Test deleting a list by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.delete(id="kbnpy-lists-unit")

        assert result.body["id"] == "kbnpy-lists-unit"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/lists?id=kbnpy-lists-unit"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    @pytest.mark.asyncio
    async def test_delete_with_reference_flags(
        self, mock_async_transport, mock_response
    ):
        """Test that reference flags are encoded as lowercase booleans."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.delete(
            id="kbnpy-lists-unit", delete_references=True, ignore_references=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/lists?id=kbnpy-lists-unit"
            "&deleteReferences=true&ignoreReferences=false"
        )


class TestAsyncListsClientFind:
    """Test AsyncListsClient.find() method."""

    @pytest.mark.asyncio
    async def test_find_no_params(self, mock_async_transport, mock_response):
        """Test finding lists without any query parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"data": [], "page": 1, "per_page": 20, "total": 0, "cursor": "WzBd"}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.find()

        assert result.body["total"] == 0

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/lists/_find"

    @pytest.mark.asyncio
    async def test_find_with_params(self, mock_async_transport, mock_response):
        """Test finding lists with pagination, sorting and a filter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "data": [_list_body()],
                "page": 1,
                "per_page": 5,
                "total": 1,
                "cursor": "WzVd",
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.find(
            page=1,
            per_page=5,
            sort_field="name",
            sort_order="asc",
            cursor="WzBd",
            filter="type:ip",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/lists/_find?page=1&per_page=5&sort_field=name"
            "&sort_order=asc&cursor=WzBd&filter=type%3Aip"
        )


class TestAsyncListsClientIndex:
    """Test the value list data stream (index) methods."""

    @pytest.mark.asyncio
    async def test_create_index(self, mock_async_transport, mock_response):
        """Test creating the value list data streams."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"acknowledged": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.create_index()

        assert result.body["acknowledged"] is True

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/lists/index"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_get_index_status(self, mock_async_transport, mock_response):
        """Test reading the value list data stream status."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"list_index": True, "list_item_index": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.get_index_status()

        assert result.body == {"list_index": True, "list_item_index": True}

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/lists/index"

    @pytest.mark.asyncio
    async def test_delete_index(self, mock_async_transport, mock_response):
        """Test the delete-index request shape.

        NOTE: this route is intentionally NOT exercised against the shared
        default-space data streams in integration tests (it would delete
        every value list of the space); the request shape is asserted here.
        """
        mock_async_transport.perform_request.return_value = mock_response(
            body={"acknowledged": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.delete_index()

        assert result.body["acknowledged"] is True

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/lists/index"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_delete_index_in_space(self, mock_async_transport, mock_response):
        """Test deleting the data streams of a specific space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"acknowledged": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.delete_index(space_id="sandbox", validate_spaces=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/sandbox/api/lists/index"


class TestAsyncListsClientItems:
    """Test the value list item methods."""

    @pytest.mark.asyncio
    async def test_create_item(self, mock_async_transport, mock_response):
        """Test creating a list item."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.create_item(
            list_id="kbnpy-lists-unit", value="10.7.7.7", refresh="wait_for"
        )

        assert result.body["value"] == "10.7.7.7"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/lists/items"
        assert call_kwargs["body"] == {
            "list_id": "kbnpy-lists-unit",
            "value": "10.7.7.7",
            "refresh": "wait_for",
        }

    @pytest.mark.asyncio
    async def test_create_item_with_id_and_meta(
        self, mock_async_transport, mock_response
    ):
        """Test creating a list item with explicit id and meta."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.create_item(
            list_id="kbnpy-lists-unit",
            value="10.7.7.7",
            id="item-1",
            meta={"source": "unit"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "list_id": "kbnpy-lists-unit",
            "value": "10.7.7.7",
            "id": "item-1",
            "meta": {"source": "unit"},
        }

    @pytest.mark.asyncio
    async def test_get_item_by_id(self, mock_async_transport, mock_response):
        """Test getting a list item by its ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.get_item(id="item-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/lists/items?id=item-1"

    @pytest.mark.asyncio
    async def test_get_item_by_list_id_and_value(
        self, mock_async_transport, mock_response
    ):
        """Test getting a list item by list_id and value."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.get_item(list_id="kbnpy-lists-unit", value="10.7.7.7")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/lists/items?list_id=kbnpy-lists-unit&value=10.7.7.7"
        )

    @pytest.mark.asyncio
    async def test_get_item_requires_id_or_pair(self, mock_async_transport):
        """Test that get_item validates its selector parameters."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError):
            await client.lists.get_item()
        with pytest.raises(ValueError):
            await client.lists.get_item(list_id="kbnpy-lists-unit")
        with pytest.raises(ValueError):
            await client.lists.get_item(value="10.7.7.7")
        mock_async_transport.perform_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_item(self, mock_async_transport, mock_response):
        """Test updating a list item."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body(value="10.7.7.8")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.update_item(
            id="item-1", value="10.7.7.8", _version="WzEsMV0="
        )

        assert result.body["value"] == "10.7.7.8"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/lists/items"
        assert call_kwargs["body"] == {
            "id": "item-1",
            "value": "10.7.7.8",
            "_version": "WzEsMV0=",
        }

    @pytest.mark.asyncio
    async def test_patch_item(self, mock_async_transport, mock_response):
        """Test patching a list item."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.patch_item(id="item-1", value="10.7.7.9", refresh="true")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/lists/items"
        assert call_kwargs["body"] == {
            "id": "item-1",
            "value": "10.7.7.9",
            "refresh": "true",
        }

    @pytest.mark.asyncio
    async def test_delete_item_by_id(self, mock_async_transport, mock_response):
        """Test deleting a list item by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.delete_item(id="item-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/lists/items?id=item-1"

    @pytest.mark.asyncio
    async def test_delete_item_by_pair_with_refresh(
        self, mock_async_transport, mock_response
    ):
        """Test deleting a list item by list_id/value with refresh."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_item_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.delete_item(
            list_id="kbnpy-lists-unit", value="10.7.7.7", refresh="wait_for"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/lists/items?list_id=kbnpy-lists-unit"
            "&value=10.7.7.7&refresh=wait_for"
        )

    @pytest.mark.asyncio
    async def test_delete_item_requires_id_or_pair(self, mock_async_transport):
        """Test that delete_item validates its selector parameters."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError):
            await client.lists.delete_item()
        with pytest.raises(ValueError):
            await client.lists.delete_item(list_id="kbnpy-lists-unit")
        mock_async_transport.perform_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_items(self, mock_async_transport, mock_response):
        """Test finding list items with all query parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "data": [_item_body()],
                "page": 1,
                "per_page": 20,
                "total": 1,
                "cursor": "WzIwXQ==",
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.find_items(
            list_id="kbnpy-lists-unit",
            page=1,
            per_page=20,
            sort_field="value",
            sort_order="desc",
            cursor="WzBd",
            filter="value:10.7.7.7",
        )

        assert result.body["total"] == 1

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/lists/items/_find?list_id=kbnpy-lists-unit&page=1&per_page=20"
            "&sort_field=value&sort_order=desc&cursor=WzBd&filter=value%3A10.7.7.7"
        )


class TestAsyncListsClientExportItems:
    """Test AsyncListsClient.export_items() method."""

    @pytest.mark.asyncio
    async def test_export_items_request_shape(
        self, mock_async_transport, mock_response
    ):
        """Test the export request (POST with list_id query parameter)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=["10.7.7.7", "10.7.7.8"]
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.export_items(list_id="kbnpy-lists-unit")

        assert list(result.body) == ["10.7.7.7", "10.7.7.8"]

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/lists/items/_export?list_id=kbnpy-lists-unit"
        )
        assert call_kwargs["headers"]["accept"] == "application/ndjson"
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs.get("body") is None

    def test_lenient_ndjson_serializer_mixed_lines(self):
        """Test that the lenient serializer keeps raw lines that aren't JSON.

        The live export body is labeled application/ndjson but contains one
        raw item value per line (e.g. IP addresses, which are not valid
        JSON); JSON-parseable lines keep the strict behavior.
        """
        serializer = _LenientNdjsonSerializer()
        parsed = serializer.loads(b'10.7.7.7\r\n{"a": 1}\n123\nplain text\n')
        assert parsed == ["10.7.7.7", {"a": 1}, 123, "plain text"]

    @pytest.mark.asyncio
    async def test_export_items_registers_lenient_serializer(self, mock_response):
        """Test that export swaps in the lenient application/ndjson serializer."""
        from unittest.mock import AsyncMock, Mock

        from kibana.serializer import KibanaNdjsonSerializer

        registry = {"application/ndjson": KibanaNdjsonSerializer()}
        mock_transport = Mock()
        mock_transport.serializers = Mock(serializers=registry)
        mock_transport.perform_request = AsyncMock(
            return_value=mock_response(body=["10.0.0.1"])
        )

        client = AsyncKibana(_transport=mock_transport)
        await client.lists.export_items(list_id="kbnpy-lists-unit")

        assert isinstance(registry["application/ndjson"], _LenientNdjsonSerializer)


class TestAsyncListsClientImportItems:
    """Test AsyncListsClient.import_items() method."""

    @pytest.mark.asyncio
    async def test_import_items_multipart_body(
        self, mock_async_transport, mock_response
    ):
        """Test the multipart upload built from a list of values."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.import_items(
            file=["10.5.5.5", "10.5.5.6"],
            list_id="kbnpy-lists-unit",
            refresh="wait_for",
        )

        assert result.body["id"] == "kbnpy-lists-unit"

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == (
            "/api/lists/items/_import?list_id=kbnpy-lists-unit&refresh=wait_for"
        )

        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]

        body = call_kwargs["body"]
        assert isinstance(body, bytes)
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"\r\n--{boundary}--\r\n".encode())
        assert b'name="file"; filename="import.txt"' in body
        assert b"10.5.5.5\n10.5.5.6\n" in body

    @pytest.mark.asyncio
    async def test_import_items_new_list_with_type_and_filename(
        self, mock_async_transport, mock_response
    ):
        """Test importing a new list via type + filename."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body(id="bad-ips.txt", name="bad-ips.txt")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.import_items(
            file=b"10.5.5.5\n", type="ip", filename="bad-ips.txt"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/lists/items/_import?type=ip"
        assert b'filename="bad-ips.txt"' in call_kwargs["body"]
        assert b"10.5.5.5\n" in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_import_items_accepts_str_payload(
        self, mock_async_transport, mock_response
    ):
        """Test that a str payload is passed through as UTF-8 bytes."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_list_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.lists.import_items(file="10.5.5.5\n10.5.5.6\n", list_id="x")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert b"10.5.5.5\n10.5.5.6\n" in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_import_items_requires_file(self, mock_async_transport):
        """Test that an empty file payload raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(ValueError):
            await client.lists.import_items(file=b"", list_id="x")
        with pytest.raises(ValueError):
            await client.lists.import_items(file=[], list_id="x")
        mock_async_transport.perform_request.assert_not_called()

    def test_values_file_bytes_helper(self):
        """Test payload normalization for bytes, str and list inputs."""
        assert _values_file_bytes(b"raw\n") == b"raw\n"
        assert _values_file_bytes("a\nb\n") == b"a\nb\n"
        assert _values_file_bytes(["a", "b"]) == b"a\nb\n"

    def test_build_multipart_body_helper(self):
        """Test the multipart body layout and content-type boundary."""
        body, content_type = _build_multipart_body(b"1.2.3.4\n", filename="f.txt")
        boundary = content_type.split("boundary=", 1)[1]
        assert (
            body
            == (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="f.txt"\r\n'
                "Content-Type: text/plain\r\n"
                "\r\n"
            ).encode()
            + b"1.2.3.4\n"
            + f"\r\n--{boundary}--\r\n".encode()
        )


class TestAsyncListsClientPrivileges:
    """Test AsyncListsClient.get_privileges() method."""

    @pytest.mark.asyncio
    async def test_get_privileges(self, mock_async_transport, mock_response):
        """Test reading value list privileges."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"lists": {}, "listItems": {}, "is_authenticated": True}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.lists.get_privileges()

        assert result.body["is_authenticated"] is True

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/lists/privileges"


class TestAsyncListsClientErrorHandling:
    """Test AsyncListsClient error handling."""

    @pytest.mark.asyncio
    async def test_get_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 (SiemErrorResponse shape) raises NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "message": 'list id: "kbnpy-lists-nope" does not exist',
                "status_code": 404,
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError, match="does not exist"):
            await client.lists.get(id="kbnpy-lists-nope")

    @pytest.mark.asyncio
    async def test_create_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that a 403 response raises AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 403,
                "error": "Forbidden",
                "message": "API [POST /api/lists] is unauthorized for user",
            },
            status=403,
        )

        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.lists.create(name="n", description="d", type="ip")
