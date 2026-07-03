"""Integration tests for SavedObjectsClient against a live Kibana instance.

Covers CRUD, find (list/dict query params), resolve, bulk lifecycle,
export -> import NDJSON round trip, resolve_import_errors and the
encrypted-saved-objects key rotation endpoint. All created resources are
prefixed with ``kbnpy-savedobj-`` and cleaned up.
"""

import uuid

import pytest

from kibana.exceptions import BadRequestError, ConflictError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-savedobj"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_saved_objects(kibana_client):
    """Track saved objects created during tests for automatic cleanup."""
    saved_objects: list[tuple[str, str]] = []  # List of (type, id) tuples
    yield saved_objects

    for obj_type, obj_id in saved_objects:
        try:
            kibana_client.saved_objects.delete(type=obj_type, id=obj_id, force=True)
        except NotFoundError:
            pass  # Already deleted by the test itself
        except Exception as e:  # pragma: no cover - cleanup best effort
            print(f"Warning: failed to clean up {obj_type}/{obj_id}: {e}")


@pytest.fixture
def unique_suffix():
    """Generate a unique suffix for resource IDs."""
    return uuid.uuid4().hex[:8]


def tag_attributes(name: str) -> dict:
    """Minimal valid attributes for a tag saved object."""
    return {
        "name": name,
        "description": "kibana-py integration test",
        "color": "#00bfb3",
    }


class TestSavedObjectsCRUD:
    """Test basic CRUD + resolve operations for saved objects."""

    def test_create_get_update_delete_lifecycle(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Full single-object lifecycle with explicit ID."""
        obj_id = f"{PREFIX}-crud-{unique_suffix}"

        created = kibana_client.saved_objects.create(
            type="tag",
            id=obj_id,
            attributes=tag_attributes(f"{PREFIX}-crud-{unique_suffix}"),
        )
        created_saved_objects.append(("tag", obj_id))

        assert created["id"] == obj_id
        assert created["type"] == "tag"
        assert "version" in created.body

        retrieved = kibana_client.saved_objects.get(type="tag", id=obj_id)
        assert retrieved["id"] == obj_id
        assert retrieved["attributes"]["name"] == f"{PREFIX}-crud-{unique_suffix}"

        updated = kibana_client.saved_objects.update(
            type="tag",
            id=obj_id,
            attributes={"description": "updated by kibana-py"},
        )
        assert updated["id"] == obj_id

        after_update = kibana_client.saved_objects.get(type="tag", id=obj_id)
        assert after_update["attributes"]["description"] == "updated by kibana-py"
        # Partial update must not clobber other attributes
        assert after_update["attributes"]["name"] == f"{PREFIX}-crud-{unique_suffix}"

        delete_resp = kibana_client.saved_objects.delete(type="tag", id=obj_id)
        assert delete_resp.meta.status == 200

        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(type="tag", id=obj_id)

    def test_create_conflict_and_overwrite(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Creating twice conflicts; overwrite=True succeeds."""
        obj_id = f"{PREFIX}-conflict-{unique_suffix}"

        kibana_client.saved_objects.create(
            type="tag", id=obj_id, attributes=tag_attributes(f"{PREFIX}-a")
        )
        created_saved_objects.append(("tag", obj_id))

        with pytest.raises(ConflictError):
            kibana_client.saved_objects.create(
                type="tag", id=obj_id, attributes=tag_attributes(f"{PREFIX}-b")
            )

        overwritten = kibana_client.saved_objects.create(
            type="tag",
            id=obj_id,
            attributes=tag_attributes(f"{PREFIX}-c"),
            overwrite=True,
        )
        assert overwritten["id"] == obj_id

    def test_resolve_saved_object(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """resolve() returns the object with an exactMatch outcome."""
        obj_id = f"{PREFIX}-resolve-{unique_suffix}"

        kibana_client.saved_objects.create(
            type="tag", id=obj_id, attributes=tag_attributes(f"{PREFIX}-resolve")
        )
        created_saved_objects.append(("tag", obj_id))

        resolved = kibana_client.saved_objects.resolve(type="tag", id=obj_id)
        assert resolved["outcome"] == "exactMatch"
        assert resolved["saved_object"]["id"] == obj_id


class TestSavedObjectsFind:
    """Test find() query parameter serialization against the live server."""

    def test_find_with_search_and_search_fields_list(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """search_fields lists are sent as repeated keys and actually match."""
        name = f"{PREFIX}-find-{unique_suffix}"
        created = kibana_client.saved_objects.create(
            type="tag", attributes=tag_attributes(name)
        )
        created_saved_objects.append(("tag", created["id"]))

        results = kibana_client.saved_objects.find(
            type="tag",
            search=f"{name}*",
            search_fields=["name", "description"],
            per_page=10,
        )
        found_ids = [obj["id"] for obj in results["saved_objects"]]
        assert created["id"] in found_ids

    def test_find_with_type_list(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Multiple types are sent as repeated keys, not a Python repr."""
        name = f"{PREFIX}-multitype-{unique_suffix}"
        created = kibana_client.saved_objects.create(
            type="tag", attributes=tag_attributes(name)
        )
        created_saved_objects.append(("tag", created["id"]))

        results = kibana_client.saved_objects.find(
            type=["tag", "dashboard"],
            search=f"{name}*",
            search_fields=["name"],
        )
        found = [(o["type"], o["id"]) for o in results["saved_objects"]]
        assert ("tag", created["id"]) in found

    def test_find_with_fields_list_strips_attributes(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """fields lists are sent as repeated keys and limit returned attributes."""
        name = f"{PREFIX}-fields-{unique_suffix}"
        created = kibana_client.saved_objects.create(
            type="tag", attributes=tag_attributes(name)
        )
        created_saved_objects.append(("tag", created["id"]))

        results = kibana_client.saved_objects.find(
            type="tag",
            search=f"{name}*",
            search_fields=["name"],
            fields=["name", "color"],
        )
        matching = [o for o in results["saved_objects"] if o["id"] == created["id"]]
        assert matching, "created tag not returned by find with fields filter"
        attrs = matching[0]["attributes"]
        assert attrs["name"] == name
        assert "description" not in attrs  # excluded by the fields filter

    def test_find_with_has_reference_dict(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """has_reference dicts are JSON-encoded and filter by reference."""
        tag = kibana_client.saved_objects.create(
            type="tag", attributes=tag_attributes(f"{PREFIX}-ref-{unique_suffix}")
        )
        created_saved_objects.append(("tag", tag["id"]))

        dash_id = f"{PREFIX}-refdash-{unique_suffix}"
        kibana_client.saved_objects.create(
            type="dashboard",
            id=dash_id,
            attributes={"title": f"{PREFIX}-refdash-{unique_suffix}"},
            references=[{"type": "tag", "id": tag["id"], "name": "tag-ref"}],
        )
        created_saved_objects.append(("dashboard", dash_id))

        results = kibana_client.saved_objects.find(
            type="dashboard",
            has_reference={"type": "tag", "id": tag["id"]},
        )
        found_ids = [obj["id"] for obj in results["saved_objects"]]
        assert found_ids == [dash_id]


class TestSavedObjectsBulk:
    """Test the bulk_* lifecycle against the live server."""

    def test_bulk_lifecycle(self, kibana_client, created_saved_objects, unique_suffix):
        """bulk_create -> bulk_get -> bulk_update -> bulk_resolve -> bulk_delete."""
        ids = [f"{PREFIX}-bulk-{unique_suffix}-{i}" for i in range(2)]
        for obj_id in ids:
            created_saved_objects.append(("tag", obj_id))

        # bulk_create
        created = kibana_client.saved_objects.bulk_create(
            objects=[
                {
                    "type": "tag",
                    "id": obj_id,
                    "attributes": tag_attributes(obj_id),
                }
                for obj_id in ids
            ]
        )
        assert [o["id"] for o in created["saved_objects"]] == ids
        assert all("error" not in o for o in created["saved_objects"])

        # bulk_create without overwrite reports per-object conflicts
        conflicted = kibana_client.saved_objects.bulk_create(
            objects=[
                {"type": "tag", "id": ids[0], "attributes": tag_attributes(ids[0])}
            ]
        )
        assert conflicted["saved_objects"][0]["error"]["statusCode"] == 409

        # bulk_get
        fetched = kibana_client.saved_objects.bulk_get(
            objects=[{"type": "tag", "id": obj_id} for obj_id in ids]
        )
        assert [o["id"] for o in fetched["saved_objects"]] == ids
        assert fetched["saved_objects"][0]["attributes"]["name"] == ids[0]

        # bulk_resolve
        resolved = kibana_client.saved_objects.bulk_resolve(
            objects=[{"type": "tag", "id": obj_id} for obj_id in ids]
        )
        outcomes = [r["outcome"] for r in resolved["resolved_objects"]]
        assert outcomes == ["exactMatch", "exactMatch"]

        # bulk_delete
        deleted = kibana_client.saved_objects.bulk_delete(
            objects=[{"type": "tag", "id": obj_id} for obj_id in ids]
        )
        assert all(status["success"] for status in deleted["statuses"])

        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(type="tag", id=ids[0])

    def test_bulk_update_route_removed_on_9_4_3(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Spec/live discrepancy: _bulk_update is in the 9.4.3 OAS but the
        route is not registered on the live server; the request falls through
        to the create-saved-object route and fails with 400."""
        obj_id = f"{PREFIX}-bulkupd-{unique_suffix}"
        kibana_client.saved_objects.create(
            type="tag", id=obj_id, attributes=tag_attributes(obj_id)
        )
        created_saved_objects.append(("tag", obj_id))

        with pytest.raises(BadRequestError, match="plain object value"):
            kibana_client.saved_objects.bulk_update(
                objects=[
                    {
                        "type": "tag",
                        "id": obj_id,
                        "attributes": {"description": "bulk updated"},
                    }
                ]
            )


class TestSavedObjectsExportImport:
    """Test export -> import NDJSON round trip and error resolution."""

    def test_export_import_round_trip(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Create a dashboard, export it, delete it, re-import, verify restored."""
        dash_id = f"{PREFIX}-roundtrip-{unique_suffix}"
        title = f"{PREFIX}-roundtrip-{unique_suffix}"

        kibana_client.saved_objects.create(
            type="dashboard", id=dash_id, attributes={"title": title}
        )
        created_saved_objects.append(("dashboard", dash_id))

        # Export as NDJSON (parsed to a list of dicts by the client)
        exported = kibana_client.saved_objects.export(
            objects=[{"type": "dashboard", "id": dash_id}]
        )
        lines = list(exported)
        assert lines[-1]["exportedCount"] == 1
        exported_objects = lines[:-1]
        assert exported_objects[0]["id"] == dash_id
        assert exported_objects[0]["attributes"]["title"] == title

        # Delete the dashboard
        kibana_client.saved_objects.delete(type="dashboard", id=dash_id)
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(type="dashboard", id=dash_id)

        # Re-import from the exported payload
        result = kibana_client.saved_objects.import_objects(file=lines)
        assert result["success"] is True
        assert result["successCount"] == 1

        # Verify the dashboard is restored with the same content
        restored = kibana_client.saved_objects.get(type="dashboard", id=dash_id)
        assert restored["attributes"]["title"] == title

    def test_export_by_type_with_exclude_details(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """Exporting by type honors excludeExportDetails."""
        tag = kibana_client.saved_objects.create(
            type="tag", attributes=tag_attributes(f"{PREFIX}-exp-{unique_suffix}")
        )
        created_saved_objects.append(("tag", tag["id"]))

        exported = kibana_client.saved_objects.export(
            type="tag", exclude_export_details=True
        )
        lines = list(exported)
        assert lines, "expected at least the created tag in the export"
        # No export-details line when excluded
        assert all("exportedCount" not in line for line in lines)
        assert any(line["id"] == tag["id"] for line in lines)

    def test_import_conflict_and_resolve_import_errors(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """An import conflict is reported, then fixed via resolve_import_errors."""
        tag_id = f"{PREFIX}-imperr-{unique_suffix}"
        kibana_client.saved_objects.create(
            type="tag", id=tag_id, attributes=tag_attributes(tag_id)
        )
        created_saved_objects.append(("tag", tag_id))

        exported = kibana_client.saved_objects.export(
            objects=[{"type": "tag", "id": tag_id}], exclude_export_details=True
        )
        ndjson_lines = list(exported)

        # Importing over the existing object without overwrite reports a conflict
        result = kibana_client.saved_objects.import_objects(file=ndjson_lines)
        assert result["success"] is False
        assert result["errors"][0]["id"] == tag_id
        assert result["errors"][0]["error"]["type"] == "conflict"

        # Resolve by retrying with overwrite
        resolved = kibana_client.saved_objects.resolve_import_errors(
            file=ndjson_lines,
            retries=[{"type": "tag", "id": tag_id, "overwrite": True}],
        )
        assert resolved["success"] is True
        assert resolved["successCount"] == 1

    def test_import_create_new_copies(
        self, kibana_client, created_saved_objects, unique_suffix
    ):
        """createNewCopies imports the object under a fresh ID."""
        tag_id = f"{PREFIX}-copy-{unique_suffix}"
        kibana_client.saved_objects.create(
            type="tag", id=tag_id, attributes=tag_attributes(tag_id)
        )
        created_saved_objects.append(("tag", tag_id))

        exported = kibana_client.saved_objects.export(
            objects=[{"type": "tag", "id": tag_id}], exclude_export_details=True
        )

        result = kibana_client.saved_objects.import_objects(
            file=list(exported), create_new_copies=True
        )
        assert result["success"] is True
        new_id = result["successResults"][0]["destinationId"]
        created_saved_objects.append(("tag", new_id))
        assert new_id != tag_id

        copy = kibana_client.saved_objects.get(type="tag", id=new_id)
        assert copy["attributes"]["name"] == tag_id


class TestRotateEncryptionKey:
    """Test the encrypted saved objects key rotation endpoint."""

    def test_rotate_encryption_key_endpoint_reachable(self, kibana_client):
        """The endpoint responds; without decryptionOnlyKeys configured it 400s."""
        try:
            result = kibana_client.saved_objects.rotate_encryption_key(batch_size=100)
            # If the stack is configured for rotation, a summary is returned.
            assert "successful" in result.body
            assert "failed" in result.body
        except BadRequestError as e:
            # Expected on stacks without keyRotation.decryptionOnlyKeys configured
            assert "not configured to support encryption key rotation" in str(e)


class TestAsyncSavedObjectsIntegration:
    """Async client round trip against the live server."""

    async def test_async_export_import_round_trip(self, unique_suffix):
        """Async create -> find -> export -> delete -> import -> get lifecycle."""
        client = create_test_async_kibana_client(auth_method="auto")
        tag_id = f"{PREFIX}-async-{unique_suffix}"
        try:
            created = await client.saved_objects.create(
                type="tag", id=tag_id, attributes=tag_attributes(tag_id)
            )
            assert created["id"] == tag_id

            results = await client.saved_objects.find(
                type="tag", search=f"{tag_id}*", search_fields=["name"]
            )
            assert tag_id in [o["id"] for o in results["saved_objects"]]

            exported = await client.saved_objects.export(
                objects=[{"type": "tag", "id": tag_id}]
            )
            lines = list(exported)
            assert lines[-1]["exportedCount"] == 1

            await client.saved_objects.delete(type="tag", id=tag_id)

            imported = await client.saved_objects.import_objects(file=lines)
            assert imported["success"] is True

            restored = await client.saved_objects.get(type="tag", id=tag_id)
            assert restored["attributes"]["name"] == tag_id

            resolved = await client.saved_objects.resolve(type="tag", id=tag_id)
            assert resolved["outcome"] == "exactMatch"
        finally:
            try:
                await client.saved_objects.delete(type="tag", id=tag_id, force=True)
            except NotFoundError:
                pass
            await client.close()
