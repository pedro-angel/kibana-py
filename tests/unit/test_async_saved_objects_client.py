"""Unit tests for AsyncSavedObjectsClient."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from kibana.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


def make_client(mock_async_transport):
    """Build an AsyncSavedObjectsClient around a mocked transport."""
    from kibana._async.client._base import AsyncBaseClient
    from kibana._async.client.saved_objects import AsyncSavedObjectsClient

    base_client = AsyncBaseClient(_transport=mock_async_transport)
    return AsyncSavedObjectsClient(base_client)


def query_of(target: str) -> dict[str, list[str]]:
    """Parse the query string of a request target into a dict of lists."""
    return parse_qs(urlsplit(target).query)


class TestAsyncSavedObjectsClientInitialization:
    """Tests for AsyncSavedObjectsClient initialization."""

    def test_init_with_base_client(self, mock_async_transport):
        """Test AsyncSavedObjectsClient initialization with AsyncBaseClient."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        assert saved_objects_client._client is base_client

    def test_inherits_from_namespace_client(self, mock_async_transport):
        """Test that AsyncSavedObjectsClient inherits from AsyncNamespaceClient."""
        from kibana._async.client.utils import AsyncNamespaceClient

        assert isinstance(make_client(mock_async_transport), AsyncNamespaceClient)


class TestAsyncSavedObjectsClientCreate:
    """Tests for AsyncSavedObjectsClient.create() method."""

    async def test_create_with_required_params(
        self, mock_async_transport, mock_response
    ):
        """Test create() with required parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Test Dashboard"},
            },
            status=200,
        )

        client = make_client(mock_async_transport)
        result = await client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
        )

        mock_async_transport.perform_request.assert_called_once()
        call_args = mock_async_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/dashboard"
        assert call_args[1]["body"] == {"attributes": {"title": "Test Dashboard"}}
        assert result.body["id"] == "test-dashboard-id"

    async def test_create_with_id(self, mock_async_transport, mock_response):
        """Test create() with explicit ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "my-custom-id", "type": "dashboard"}, status=200
        )

        client = make_client(mock_async_transport)
        await client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            id="my-custom-id",
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/dashboard/my-custom-id"

    async def test_create_quotes_type_without_id(
        self, mock_async_transport, mock_response
    ):
        """Test create() URL-quotes the type segment when no ID is given."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.create(type="weird type/slash", attributes={"title": "x"})

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/weird%20type%2Fslash"

    async def test_create_with_overwrite(self, mock_async_transport, mock_response):
        """Test create() with overwrite parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id", "type": "dashboard"}, status=200
        )

        client = make_client(mock_async_transport)
        await client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            id="test-id",
            overwrite=True,
        )

        call_args = mock_async_transport.perform_request.call_args
        assert "/api/saved_objects/dashboard/test-id" in call_args[1]["target"]
        assert "overwrite=true" in call_args[1]["target"]

    async def test_create_with_initial_namespaces_and_migration_versions(
        self, mock_async_transport, mock_response
    ):
        """Test create() forwards initialNamespaces and migration version fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            references=[{"type": "tag", "id": "t1", "name": "ref"}],
            initial_namespaces=["default", "marketing"],
            core_migration_version="8.8.0",
            type_migration_version="8.0.0",
        )

        body = mock_async_transport.perform_request.call_args[1]["body"]
        assert body["references"] == [{"type": "tag", "id": "t1", "name": "ref"}]
        assert body["initialNamespaces"] == ["default", "marketing"]
        assert body["coreMigrationVersion"] == "8.8.0"
        assert body["typeMigrationVersion"] == "8.0.0"

    async def test_create_with_space_id(self, mock_async_transport, mock_response):
        """Test create() with space_id parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id", "type": "dashboard"}, status=200
        )

        client = make_client(mock_async_transport)
        await client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
            validate_space=False,
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard"

    async def test_create_validates_required_params(self, mock_async_transport):
        """Test that create() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await client.create(type="", attributes={"title": "Test"})

        with pytest.raises(ValueError, match="Parameter 'attributes' is required"):
            await client.create(type="dashboard", attributes=None)

    async def test_create_handles_400_error(self, mock_async_transport, mock_response):
        """Test create() handles 400 Bad Request error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Invalid attributes"}}, status=400
        )

        client = make_client(mock_async_transport)
        with pytest.raises(BadRequestError) as exc_info:
            await client.create(type="dashboard", attributes={"invalid": "data"})

        assert exc_info.value.status_code == 400

    async def test_create_handles_409_conflict(
        self, mock_async_transport, mock_response
    ):
        """Test create() handles 409 Conflict error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Saved object already exists"}}, status=409
        )

        client = make_client(mock_async_transport)
        with pytest.raises(ConflictError) as exc_info:
            await client.create(
                type="dashboard", attributes={"title": "Test"}, id="existing-id"
            )

        assert exc_info.value.status_code == 409


class TestAsyncSavedObjectsClientGet:
    """Tests for AsyncSavedObjectsClient.get() method."""

    async def test_get_by_type_and_id(self, mock_async_transport, mock_response):
        """Test get() retrieves saved object by type and ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Test Dashboard"},
            },
            status=200,
        )

        client = make_client(mock_async_transport)
        result = await client.get(type="dashboard", id="test-dashboard-id")

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )
        assert result.body["id"] == "test-dashboard-id"

    async def test_get_with_space_id(self, mock_async_transport, mock_response):
        """Test get() with space_id parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id", "type": "dashboard"}, status=200
        )

        client = make_client(mock_async_transport)
        await client.get(
            type="dashboard", id="test-id", space_id="marketing", validate_space=False
        )

        call_args = mock_async_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard/test-id"
        )

    async def test_get_validates_required_params(self, mock_async_transport):
        """Test that get() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await client.get(type="", id="test-id")

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await client.get(type="dashboard", id="")

    async def test_get_handles_404_error(self, mock_async_transport, mock_response):
        """Test get() handles 404 Not Found error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Saved object not found"}}, status=404
        )

        client = make_client(mock_async_transport)
        with pytest.raises(NotFoundError) as exc_info:
            await client.get(type="dashboard", id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncSavedObjectsClientResolve:
    """Tests for AsyncSavedObjectsClient.resolve() method."""

    async def test_resolve_by_type_and_id(self, mock_async_transport, mock_response):
        """Test resolve() targets the resolve endpoint."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "saved_object": {"id": "test-id", "type": "dashboard"},
                "outcome": "exactMatch",
            },
            status=200,
        )

        client = make_client(mock_async_transport)
        result = await client.resolve(type="dashboard", id="test-id")

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/api/saved_objects/resolve/dashboard/test-id"
        assert result.body["outcome"] == "exactMatch"

    async def test_resolve_validates_required_params(self, mock_async_transport):
        """Test that resolve() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await client.resolve(type="", id="test-id")

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await client.resolve(type="dashboard", id="")


class TestAsyncSavedObjectsClientFind:
    """Tests for AsyncSavedObjectsClient.find() method."""

    async def test_find_with_single_type(self, mock_async_transport, mock_response):
        """Test find() with a single type string."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"page": 1, "per_page": 20, "total": 0, "saved_objects": []},
            status=200,
        )

        client = make_client(mock_async_transport)
        result = await client.find(type="dashboard")

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        target = call_args[1]["target"]
        assert target.startswith("/api/saved_objects/_find?")
        assert query_of(target) == {"type": ["dashboard"]}
        assert result.body["total"] == 0

    async def test_find_with_type_list_sends_repeated_keys(
        self, mock_async_transport, mock_response
    ):
        """Test find() sends list types as repeated query keys, not a Python repr."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.find(type=["dashboard", "tag"])

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert query_of(target)["type"] == ["dashboard", "tag"]

    async def test_find_with_list_fields_and_search_fields(
        self, mock_async_transport, mock_response
    ):
        """Test find() sends fields/search_fields lists as repeated keys."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.find(
            type="dashboard",
            fields=["title", "description"],
            search_fields=["title", "description"],
        )

        query = query_of(mock_async_transport.perform_request.call_args[1]["target"])
        assert query["fields"] == ["title", "description"]
        assert query["search_fields"] == ["title", "description"]
        # Never comma-joined into a single bogus field name
        assert "title,description" not in str(query)

    async def test_find_with_has_reference_dict_json_encoded(
        self, mock_async_transport, mock_response
    ):
        """Test find() JSON-encodes has_reference/has_no_reference dicts."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.find(
            type="dashboard",
            has_reference={"type": "tag", "id": "tag-1"},
            has_reference_operator="OR",
            has_no_reference={"type": "tag", "id": "tag-2"},
            has_no_reference_operator="AND",
        )

        query = query_of(mock_async_transport.perform_request.call_args[1]["target"])
        assert json.loads(query["has_reference"][0]) == {"type": "tag", "id": "tag-1"}
        assert json.loads(query["has_no_reference"][0]) == {
            "type": "tag",
            "id": "tag-2",
        }
        assert query["has_reference_operator"] == ["OR"]
        assert query["has_no_reference_operator"] == ["AND"]

    async def test_find_with_all_scalar_params(
        self, mock_async_transport, mock_response
    ):
        """Test find() forwards every scalar query parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.find(
            type="dashboard",
            aggs='{"count": {"value_count": {"field": "type"}}}',
            default_search_operator="AND",
            filter="dashboard.attributes.title: foo",
            page=2,
            per_page=50,
            search="foo*",
            sort_field="updated_at",
        )

        query = query_of(mock_async_transport.perform_request.call_args[1]["target"])
        assert query["aggs"] == ['{"count": {"value_count": {"field": "type"}}}']
        assert query["default_search_operator"] == ["AND"]
        assert query["filter"] == ["dashboard.attributes.title: foo"]
        assert query["page"] == ["2"]
        assert query["per_page"] == ["50"]
        assert query["search"] == ["foo*"]
        assert query["sort_field"] == ["updated_at"]

    async def test_find_with_space_id(self, mock_async_transport, mock_response):
        """Test find() with space_id parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.find(type="dashboard", space_id="marketing", validate_space=False)

        target = mock_async_transport.perform_request.call_args[1]["target"]
        assert target.startswith("/s/marketing/api/saved_objects/_find?")


class TestAsyncSavedObjectsClientUpdate:
    """Tests for AsyncSavedObjectsClient.update() method."""

    async def test_update_saved_object(self, mock_async_transport, mock_response):
        """Test update() modifies an existing saved object."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Updated Dashboard"},
            },
            status=200,
        )

        client = make_client(mock_async_transport)
        result = await client.update(
            type="dashboard",
            id="test-dashboard-id",
            attributes={"title": "Updated Dashboard"},
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )
        assert call_args[1]["body"] == {"attributes": {"title": "Updated Dashboard"}}
        assert result.body["attributes"]["title"] == "Updated Dashboard"

    async def test_update_with_version_and_references(
        self, mock_async_transport, mock_response
    ):
        """Test update() with version and references parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        references = [{"type": "index-pattern", "id": "pattern-1", "name": "ref1"}]
        await client.update(
            type="dashboard",
            id="test-id",
            attributes={"title": "Updated Dashboard"},
            version="WzEsMV0=",
            references=references,
        )

        body = mock_async_transport.perform_request.call_args[1]["body"]
        assert body["version"] == "WzEsMV0="
        assert body["references"] == references

    async def test_update_validates_required_params(self, mock_async_transport):
        """Test that update() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await client.update(type="", id="test-id", attributes={"title": "Test"})

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await client.update(type="dashboard", id="", attributes={"title": "Test"})

        with pytest.raises(ValueError, match="Parameter 'attributes' is required"):
            await client.update(type="dashboard", id="test-id", attributes=None)

    async def test_update_handles_409_conflict(
        self, mock_async_transport, mock_response
    ):
        """Test update() handles 409 Conflict error (version mismatch)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Version conflict"}}, status=409
        )

        client = make_client(mock_async_transport)
        with pytest.raises(ConflictError) as exc_info:
            await client.update(
                type="dashboard",
                id="test-id",
                attributes={"title": "New Title"},
                version="WzEsMV0=",
            )

        assert exc_info.value.status_code == 409


class TestAsyncSavedObjectsClientDelete:
    """Tests for AsyncSavedObjectsClient.delete() method."""

    async def test_delete_saved_object(self, mock_async_transport, mock_response):
        """Test delete() removes a saved object."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        result = await client.delete(type="dashboard", id="test-dashboard-id")

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )
        assert result.meta.status == 200

    async def test_delete_with_force(self, mock_async_transport, mock_response):
        """Test delete() with force parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.delete(type="dashboard", id="test-id", force=True)

        call_args = mock_async_transport.perform_request.call_args
        assert "force=true" in call_args[1]["target"]

    async def test_delete_validates_required_params(self, mock_async_transport):
        """Test that delete() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await client.delete(type="", id="test-id")

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await client.delete(type="dashboard", id="")

    async def test_delete_handles_404_error(self, mock_async_transport, mock_response):
        """Test delete() handles 404 Not Found error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Saved object not found"}}, status=404
        )

        client = make_client(mock_async_transport)
        with pytest.raises(NotFoundError) as exc_info:
            await client.delete(type="dashboard", id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncSavedObjectsClientBulk:
    """Tests for the async bulk_* methods."""

    async def test_bulk_create(self, mock_async_transport, mock_response):
        """Test bulk_create() posts the objects list as the raw body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"saved_objects": []}, status=200
        )

        client = make_client(mock_async_transport)
        objects = [
            {"type": "tag", "id": "t1", "attributes": {"name": "one"}},
            {"type": "tag", "id": "t2", "attributes": {"name": "two"}},
        ]
        await client.bulk_create(objects=objects, overwrite=True)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert (
            call_args[1]["target"] == "/api/saved_objects/_bulk_create?overwrite=true"
        )
        assert call_args[1]["body"] == objects

    async def test_bulk_get(self, mock_async_transport, mock_response):
        """Test bulk_get() posts descriptors to _bulk_get."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"saved_objects": []}, status=200
        )

        client = make_client(mock_async_transport)
        objects = [{"type": "dashboard", "id": "d1"}]
        await client.bulk_get(objects=objects)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/_bulk_get"
        assert call_args[1]["body"] == objects

    async def test_bulk_resolve(self, mock_async_transport, mock_response):
        """Test bulk_resolve() posts descriptors to _bulk_resolve."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"resolved_objects": []}, status=200
        )

        client = make_client(mock_async_transport)
        objects = [{"type": "dashboard", "id": "d1"}]
        await client.bulk_resolve(objects=objects)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/_bulk_resolve"
        assert call_args[1]["body"] == objects

    async def test_bulk_update(self, mock_async_transport, mock_response):
        """Test bulk_update() posts update descriptors to _bulk_update."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"saved_objects": []}, status=200
        )

        client = make_client(mock_async_transport)
        objects = [{"type": "dashboard", "id": "d1", "attributes": {"title": "New"}}]
        await client.bulk_update(objects=objects)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/_bulk_update"
        assert call_args[1]["body"] == objects

    async def test_bulk_delete_with_force(self, mock_async_transport, mock_response):
        """Test bulk_delete() posts descriptors with the force param."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"statuses": []}, status=200
        )

        client = make_client(mock_async_transport)
        objects = [{"type": "tag", "id": "t1"}]
        await client.bulk_delete(objects=objects, force=True)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/_bulk_delete?force=true"
        assert call_args[1]["body"] == objects

    async def test_bulk_methods_validate_objects(self, mock_async_transport):
        """Test bulk methods reject an empty objects list."""
        client = make_client(mock_async_transport)

        for method in (
            client.bulk_create,
            client.bulk_get,
            client.bulk_resolve,
            client.bulk_update,
            client.bulk_delete,
        ):
            with pytest.raises(ValueError, match="Parameter 'objects' is required"):
                await method(objects=[])

    async def test_bulk_with_space_id(self, mock_async_transport, mock_response):
        """Test bulk methods honor space_id."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.bulk_get(
            objects=[{"type": "tag", "id": "t1"}],
            space_id="marketing",
            validate_space=False,
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/marketing/api/saved_objects/_bulk_get"


class TestAsyncSavedObjectsClientExport:
    """Tests for AsyncSavedObjectsClient.export() method."""

    async def test_export_with_objects(self, mock_async_transport, mock_response):
        """Test export() posts the objects selector and returns the NDJSON list."""
        exported = [
            {"type": "dashboard", "id": "d1", "attributes": {"title": "One"}},
            {"exportedCount": 1, "missingRefCount": 0, "missingReferences": []},
        ]
        mock_async_transport.perform_request.return_value = mock_response(
            body=exported, status=200
        )

        client = make_client(mock_async_transport)
        result = await client.export(objects=[{"type": "dashboard", "id": "d1"}])

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/_export"
        assert call_args[1]["body"] == {"objects": [{"type": "dashboard", "id": "d1"}]}
        assert list(result) == exported

    async def test_export_with_type_and_options(
        self, mock_async_transport, mock_response
    ):
        """Test export() forwards type/search/hasReference and boolean options."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[], status=200
        )

        client = make_client(mock_async_transport)
        await client.export(
            type=["dashboard", "tag"],
            search="foo*",
            has_reference={"type": "tag", "id": "t1"},
            exclude_export_details=True,
            include_references_deep=True,
        )

        body = mock_async_transport.perform_request.call_args[1]["body"]
        assert body == {
            "type": ["dashboard", "tag"],
            "search": "foo*",
            "hasReference": {"type": "tag", "id": "t1"},
            "excludeExportDetails": True,
            "includeReferencesDeep": True,
        }

    async def test_export_requires_selector(self, mock_async_transport):
        """Test export() requires objects or type."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Either 'objects' or 'type'"):
            await client.export()


class TestAsyncSavedObjectsClientImport:
    """Tests for import_objects() and resolve_import_errors()."""

    async def test_import_objects_builds_multipart_body(
        self, mock_async_transport, mock_response
    ):
        """Test import_objects() uploads a multipart body with the NDJSON file."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True, "successCount": 1}, status=200
        )

        client = make_client(mock_async_transport)
        ndjson = b'{"type":"dashboard","id":"d1"}\n'
        result = await client.import_objects(file=ndjson)

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/_import"

        content_type = call_args[1]["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        boundary = content_type.split("boundary=", 1)[1]

        body = call_args[1]["body"]
        assert isinstance(body, bytes)
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"--{boundary}--\r\n".encode())
        assert b'Content-Disposition: form-data; name="file"' in body
        assert b'filename="import.ndjson"' in body
        assert ndjson in body
        assert result.body["success"] is True

    async def test_import_objects_encodes_list_to_ndjson(
        self, mock_async_transport, mock_response
    ):
        """Test import_objects() NDJSON-encodes a list of dicts."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.import_objects(
            file=[{"type": "tag", "id": "t1"}, {"exportedCount": 1}],
        )

        body = mock_async_transport.perform_request.call_args[1]["body"]
        assert b'{"type": "tag", "id": "t1"}\n{"exportedCount": 1}\n' in body

    async def test_import_objects_query_params(
        self, mock_async_transport, mock_response
    ):
        """Test import_objects() forwards the camelCase query params."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.import_objects(
            file=b"{}\n",
            create_new_copies=False,
            overwrite=True,
            compatibility_mode=False,
        )

        query = query_of(mock_async_transport.perform_request.call_args[1]["target"])
        assert query == {
            "createNewCopies": ["false"],
            "overwrite": ["true"],
            "compatibilityMode": ["false"],
        }

    async def test_import_objects_validates_file(self, mock_async_transport):
        """Test import_objects() rejects an empty file."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'file' is required"):
            await client.import_objects(file=b"")

    async def test_resolve_import_errors_includes_retries_field(
        self, mock_async_transport, mock_response
    ):
        """Test resolve_import_errors() sends both retries and file parts."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"success": True, "successCount": 1}, status=200
        )

        client = make_client(mock_async_transport)
        retries = [{"type": "dashboard", "id": "d1", "overwrite": True}]
        await client.resolve_import_errors(
            file=b'{"type":"dashboard"}\n', retries=retries
        )

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/_resolve_import_errors"

        body = call_args[1]["body"]
        assert b'Content-Disposition: form-data; name="retries"' in body
        assert json.dumps(retries).encode() in body
        assert b'Content-Disposition: form-data; name="file"' in body
        assert b'{"type":"dashboard"}\n' in body

    async def test_resolve_import_errors_validates_params(self, mock_async_transport):
        """Test resolve_import_errors() validates required parameters."""
        client = make_client(mock_async_transport)

        with pytest.raises(ValueError, match="Parameter 'file' is required"):
            await client.resolve_import_errors(file=b"", retries=[])

        with pytest.raises(ValueError, match="Parameter 'retries' is required"):
            await client.resolve_import_errors(file=b"{}\n", retries=None)


class TestAsyncSavedObjectsClientRotateEncryptionKey:
    """Tests for rotate_encryption_key()."""

    async def test_rotate_encryption_key(self, mock_async_transport, mock_response):
        """Test rotate_encryption_key() posts to the rotate endpoint."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"total": 0, "successful": 0, "failed": 0}, status=200
        )

        client = make_client(mock_async_transport)
        result = await client.rotate_encryption_key()

        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/encrypted_saved_objects/_rotate_key"
        assert result.body["failed"] == 0

    async def test_rotate_encryption_key_with_params(
        self, mock_async_transport, mock_response
    ):
        """Test rotate_encryption_key() forwards batch_size and type."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        client = make_client(mock_async_transport)
        await client.rotate_encryption_key(batch_size=1000, type="alert")

        query = query_of(mock_async_transport.perform_request.call_args[1]["target"])
        assert query == {"batch_size": ["1000"], "type": ["alert"]}

    async def test_rotate_encryption_key_handles_400(
        self, mock_async_transport, mock_response
    ):
        """Test rotate_encryption_key() maps 400 to BadRequestError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 400,
                "error": "Bad Request",
                "message": "Kibana is not configured to support encryption key rotation.",
            },
            status=400,
        )

        client = make_client(mock_async_transport)
        with pytest.raises(BadRequestError, match="not configured"):
            await client.rotate_encryption_key()


class TestAsyncSavedObjectsClientErrorHandling:
    """Tests for error handling across AsyncSavedObjectsClient methods."""

    async def test_handles_authentication_error(
        self, mock_async_transport, mock_response
    ):
        """Test that methods handle 401 Authentication error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Unauthorized"}}, status=401
        )

        client = make_client(mock_async_transport)

        with pytest.raises(AuthenticationException):
            await client.create(type="dashboard", attributes={"title": "Test"})

        with pytest.raises(AuthenticationException):
            await client.get(type="dashboard", id="test-id")

        with pytest.raises(AuthenticationException):
            await client.update(
                type="dashboard", id="test-id", attributes={"title": "Test"}
            )

        with pytest.raises(AuthenticationException):
            await client.delete(type="dashboard", id="test-id")

        with pytest.raises(AuthenticationException):
            await client.export(type="dashboard")

    async def test_handles_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that methods handle 403 Authorization error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Insufficient privileges"}}, status=403
        )

        client = make_client(mock_async_transport)

        with pytest.raises(AuthorizationException):
            await client.find(type="dashboard")

        with pytest.raises(AuthorizationException):
            await client.bulk_get(objects=[{"type": "dashboard", "id": "x"}])

        with pytest.raises(AuthorizationException):
            await client.import_objects(file=b"{}\n")
