"""Integration tests for ExceptionListsClient against a live Kibana instance."""

import uuid

import pytest

from kibana.exceptions import NotFoundError

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

PREFIX = "kbnpy-exception_lists"

ENTRIES = [
    {
        "field": "host.name",
        "operator": "included",
        "type": "match",
        "value": f"{PREFIX}-host",
    }
]


def _unique(suffix: str) -> str:
    """Generate a unique, prefixed resource identifier."""
    return f"{PREFIX}-{suffix}-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


def _cleanup_list(client, *, id=None, list_id=None, namespace_type=None) -> None:
    """Delete an exception list, ignoring the case where it is already gone."""
    try:
        client.exception_lists.delete(
            id=id, list_id=list_id, namespace_type=namespace_type
        )
    except NotFoundError:
        pass


def _cleanup_endpoint_item(client, *, item_id) -> None:
    """Delete an endpoint list item, ignoring the case where it is already gone."""
    try:
        client.exception_lists.delete_endpoint_item(item_id=item_id)
    except NotFoundError:
        pass


class TestExceptionListLifecycle:
    """Full lifecycle tests for exception list containers."""

    def test_create_get_update_delete(self, kibana_client):
        """Test the full exception list lifecycle."""
        list_id = _unique("list")
        created = kibana_client.exception_lists.create(
            name="kbnpy exception list",
            description="Created by kibana-py integration tests",
            type="detection",
            list_id=list_id,
            tags=["kbnpy"],
            os_types=["linux"],
        )
        try:
            assert created.body["list_id"] == list_id
            assert created.body["type"] == "detection"
            assert created.body["tags"] == ["kbnpy"]
            assert created.body["os_types"] == ["linux"]

            # Get by list_id and by id
            fetched = kibana_client.exception_lists.get(list_id=list_id)
            assert fetched.body["id"] == created.body["id"]
            fetched_by_id = kibana_client.exception_lists.get(id=created.body["id"])
            assert fetched_by_id.body["list_id"] == list_id

            # Update (name/description are replaced)
            updated = kibana_client.exception_lists.update(
                list_id=list_id,
                name="kbnpy exception list (updated)",
                description="Updated by kibana-py integration tests",
                type="detection",
            )
            assert updated.body["name"] == "kbnpy exception list (updated)"
        finally:
            _cleanup_list(kibana_client, list_id=list_id)

        # After deletion the list must be gone
        with pytest.raises(NotFoundError):
            kibana_client.exception_lists.get(list_id=list_id)

    def test_get_missing_list_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent list raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.exception_lists.get(list_id=_unique("missing"))
        assert "does not exist" in str(exc_info.value)

    def test_find_filters_by_name(self, kibana_client):
        """Test find() returns the created list."""
        list_id = _unique("find")
        created = kibana_client.exception_lists.create(
            name=f"kbnpy find target {list_id}",
            description="find test",
            type="detection",
            list_id=list_id,
        )
        try:
            found = kibana_client.exception_lists.find(
                filter=f"exception-list.attributes.list_id:{list_id}",
                namespace_type="single",
                per_page=10,
            )
            assert found.body["total"] == 1
            assert found.body["data"][0]["id"] == created.body["id"]
        finally:
            _cleanup_list(kibana_client, list_id=list_id)

    def test_duplicate(self, kibana_client):
        """Test duplicating an exception list along with its items."""
        list_id = _unique("dup")
        kibana_client.exception_lists.create(
            name="kbnpy duplicate source",
            description="duplicate test",
            type="detection",
            list_id=list_id,
        )
        duplicate_id = None
        try:
            kibana_client.exception_lists.create_item(
                list_id=list_id,
                name="kbnpy duplicate item",
                description="item to be duplicated",
                entries=ENTRIES,
            )
            duplicated = kibana_client.exception_lists.duplicate(
                list_id=list_id, namespace_type="single"
            )
            duplicate_id = duplicated.body["id"]
            assert duplicated.body["name"] == "kbnpy duplicate source [Duplicate]"
            assert duplicated.body["list_id"] != list_id

            # The item travelled with the duplicate
            items = kibana_client.exception_lists.find_items(
                list_id=duplicated.body["list_id"]
            )
            assert items.body["total"] == 1
        finally:
            _cleanup_list(kibana_client, list_id=list_id)
            if duplicate_id is not None:
                _cleanup_list(kibana_client, id=duplicate_id)


class TestExceptionListItems:
    """Full lifecycle tests for exception list items."""

    def test_item_lifecycle(self, kibana_client):
        """Test create/get/update/find/delete for exception items."""
        list_id = _unique("items")
        item_id = _unique("item")
        kibana_client.exception_lists.create(
            name="kbnpy item host list",
            description="item lifecycle test",
            type="detection",
            list_id=list_id,
        )
        try:
            created = kibana_client.exception_lists.create_item(
                list_id=list_id,
                item_id=item_id,
                name="kbnpy item",
                description="item lifecycle test",
                entries=ENTRIES,
                os_types=["linux"],
                tags=["kbnpy"],
                comments=[{"comment": "created by kibana-py tests"}],
            )
            assert created.body["item_id"] == item_id
            assert created.body["entries"] == ENTRIES
            assert created.body["comments"][0]["comment"] == (
                "created by kibana-py tests"
            )

            # Get by item_id
            fetched = kibana_client.exception_lists.get_item(item_id=item_id)
            assert fetched.body["id"] == created.body["id"]

            # Summary counts the item under its os_type (before the update
            # below resets os_types to its default [])
            summary = kibana_client.exception_lists.get_summary(list_id=list_id)
            assert summary.body["linux"] == 1
            assert summary.body["total"] == 1

            # Update replaces name/entries (and resets omitted fields such as
            # os_types to their defaults - the PUT is a full replace)
            new_entries = [
                {
                    "field": "host.name",
                    "operator": "included",
                    "type": "match_any",
                    "value": [f"{PREFIX}-host-a", f"{PREFIX}-host-b"],
                }
            ]
            updated = kibana_client.exception_lists.update_item(
                item_id=item_id,
                name="kbnpy item (updated)",
                description="updated",
                entries=new_entries,
            )
            assert updated.body["name"] == "kbnpy item (updated)"
            assert updated.body["entries"][0]["type"] == "match_any"

            # Find items of the list
            found = kibana_client.exception_lists.find_items(list_id=list_id)
            assert found.body["total"] == 1
            assert found.body["data"][0]["item_id"] == item_id

            # Delete the item
            kibana_client.exception_lists.delete_item(item_id=item_id)
            with pytest.raises(NotFoundError):
                kibana_client.exception_lists.get_item(item_id=item_id)
        finally:
            _cleanup_list(kibana_client, list_id=list_id)


class TestExceptionListExportImport:
    """Export / import round-trip tests."""

    def test_export_import_round_trip(self, kibana_client):
        """Test exporting a list and re-importing it as a new list."""
        list_id = _unique("export")
        created = kibana_client.exception_lists.create(
            name="kbnpy export list",
            description="export test",
            type="detection",
            list_id=list_id,
        )
        imported_ids: list[str] = []
        try:
            kibana_client.exception_lists.create_item(
                list_id=list_id,
                name="kbnpy export item",
                description="export test item",
                entries=ENTRIES,
            )

            exported = kibana_client.exception_lists.export(
                id=created.body["id"],
                list_id=list_id,
                namespace_type="single",
            )
            # NDJSON parses to a list: container, item, export details
            lines = list(exported.body)
            assert lines[0]["list_id"] == list_id
            assert lines[1]["list_id"] == list_id
            assert lines[-1]["exported_exception_list_count"] == 1
            assert lines[-1]["exported_exception_list_item_count"] == 1

            # Re-import as a new list (new list_id/item_id generated)
            result = kibana_client.exception_lists.import_lists(
                file=exported.body, as_new_list=True
            )
            assert result.body["success"] is True
            assert result.body["success_count_exception_lists"] == 1
            assert result.body["success_count_exception_list_items"] == 1

            # Track the imported copy for cleanup
            found = kibana_client.exception_lists.find(
                filter='exception-list.attributes.name:"kbnpy export list"',
                per_page=100,
            )
            imported_ids = [
                lst["id"]
                for lst in found.body["data"]
                if lst["id"] != created.body["id"]
            ]
            assert len(imported_ids) == 1
        finally:
            _cleanup_list(kibana_client, list_id=list_id)
            for imported_id in imported_ids:
                _cleanup_list(kibana_client, id=imported_id)


class TestSharedAndRuleExceptions:
    """Tests for shared exception lists and rule default exceptions."""

    def test_create_shared_list(self, kibana_client):
        """Test creating a shared exception list."""
        name = _unique("shared")
        created = kibana_client.exception_lists.create_shared_list(
            name=name, description="shared exception list test"
        )
        try:
            assert created.body["name"] == name
            assert created.body["type"] == "detection"
            assert created.body["list_id"]  # generated
        finally:
            _cleanup_list(kibana_client, id=created.body["id"])

    def test_create_rule_exceptions(self, kibana_client):
        """Test creating exception items on a throwaway detection rule."""
        rule_id = _unique("rule")
        # Create a throwaway detection rule via raw perform_request
        # (the detection_engine namespace is owned by another implementer).
        rule = kibana_client.perform_request(
            "POST",
            "/api/detection_engine/rules",
            body={
                "rule_id": rule_id,
                "name": f"kbnpy exception_lists rule {rule_id}",
                "description": "throwaway rule for rule-exceptions test",
                "risk_score": 21,
                "severity": "low",
                "type": "query",
                "query": "host.name:kbnpy-none",
                "index": ["logs-kbnpy-none-*"],
                "enabled": False,
            },
        )
        default_list_id = None
        try:
            created = kibana_client.exception_lists.create_rule_exceptions(
                id=rule.body["id"],
                items=[
                    {
                        "name": "kbnpy rule exception",
                        "description": "suppress the kbnpy host",
                        "type": "simple",
                        "entries": ENTRIES,
                    }
                ],
            )
            assert isinstance(created.body, list)
            assert created.body[0]["name"] == "kbnpy rule exception"
            default_list_id = created.body[0]["list_id"]

            # The items landed in the rule's default exception list
            items = kibana_client.exception_lists.find_items(list_id=default_list_id)
            assert items.body["total"] == 1
        finally:
            kibana_client.perform_request(
                "DELETE", f"/api/detection_engine/rules?rule_id={rule_id}"
            )
            if default_list_id is not None:
                _cleanup_list(kibana_client, list_id=default_list_id)

    def test_create_rule_exceptions_missing_rule(self, kibana_client):
        """Test the semantic 500 for an unknown rule id."""
        from kibana.exceptions import ApiError

        missing_rule_uuid = str(uuid.uuid4())
        with pytest.raises(ApiError) as exc_info:
            kibana_client.exception_lists.create_rule_exceptions(
                id=missing_rule_uuid,
                items=[
                    {
                        "name": "kbnpy rule exception",
                        "description": "should not be created",
                        "type": "simple",
                        "entries": ENTRIES,
                    }
                ],
            )
        assert missing_rule_uuid in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()


class TestEndpointList:
    """Tests for the Elastic Endpoint exception list endpoints."""

    def test_create_endpoint_list_is_idempotent(self, kibana_client):
        """Test that creating the endpoint list twice succeeds."""
        first = kibana_client.exception_lists.create_endpoint_list()
        second = kibana_client.exception_lists.create_endpoint_list()
        # Once the list exists the API returns {} (already-existed marker);
        # a fresh creation returns the list body with list_id endpoint_list.
        for response in (first, second):
            assert response.meta.status == 200
            if response.body:
                assert response.body["list_id"] == "endpoint_list"
        assert second.body == {}

    def test_endpoint_item_lifecycle(self, kibana_client):
        """Test create/get/update/find/delete for endpoint list items."""
        kibana_client.exception_lists.create_endpoint_list()
        item_id = _unique("ep-item")
        entries = [
            {
                "field": "process.executable.caseless",
                "operator": "included",
                "type": "match",
                "value": "/opt/kbnpy/trusted",
            }
        ]
        try:
            created = kibana_client.exception_lists.create_endpoint_item(
                item_id=item_id,
                name="kbnpy endpoint item",
                description="endpoint item lifecycle test",
                entries=entries,
                os_types=["linux"],
            )
            assert created.body["list_id"] == "endpoint_list"
            assert created.body["namespace_type"] == "agnostic"
            assert created.body["item_id"] == item_id

            fetched = kibana_client.exception_lists.get_endpoint_item(item_id=item_id)
            assert fetched.body["id"] == created.body["id"]

            updated = kibana_client.exception_lists.update_endpoint_item(
                item_id=item_id,
                name="kbnpy endpoint item (updated)",
                description="updated",
                entries=entries,
                os_types=["linux"],
            )
            assert updated.body["name"] == "kbnpy endpoint item (updated)"

            found = kibana_client.exception_lists.find_endpoint_items(
                filter=f"exception-list-agnostic.attributes.item_id:{item_id}"
            )
            assert found.body["total"] == 1
            assert found.body["data"][0]["item_id"] == item_id

            kibana_client.exception_lists.delete_endpoint_item(item_id=item_id)
            with pytest.raises(NotFoundError):
                kibana_client.exception_lists.get_endpoint_item(item_id=item_id)
        finally:
            _cleanup_endpoint_item(kibana_client, item_id=item_id)


class TestExceptionListsSpaceScoped:
    """Space-scoped behavior for exception lists."""

    def test_list_is_space_scoped(self, kibana_client):
        """Test that a single-namespace list is not visible in another space."""
        space_id = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
        list_id = _unique("space")
        kibana_client.spaces.create(id=space_id, name=space_id)
        try:
            kibana_client.exception_lists.create(
                name="kbnpy space list",
                description="space scoping test",
                type="detection",
                list_id=list_id,
                space_id=space_id,
            )
            # Visible in its own space
            fetched = kibana_client.exception_lists.get(
                list_id=list_id, space_id=space_id
            )
            assert fetched.body["list_id"] == list_id

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.exception_lists.get(list_id=list_id)
        finally:
            _cleanup_list(kibana_client, list_id=list_id)  # no-op safety
            try:
                kibana_client.exception_lists.delete(list_id=list_id, space_id=space_id)
            except NotFoundError:
                pass
            kibana_client.spaces.delete(id=space_id)


class TestAsyncExceptionLists:
    """Async round-trip tests for the exception lists API."""

    async def test_async_list_and_item_round_trip(self, async_kibana_client):
        """Test the async client end to end: list + item lifecycle."""
        list_id = _unique("async")
        item_id = _unique("async-item")
        created = await async_kibana_client.exception_lists.create(
            name="kbnpy async list",
            description="async round-trip test",
            type="detection",
            list_id=list_id,
        )
        try:
            assert created.body["list_id"] == list_id

            item = await async_kibana_client.exception_lists.create_item(
                list_id=list_id,
                item_id=item_id,
                name="kbnpy async item",
                description="async round-trip item",
                entries=ENTRIES,
            )
            assert item.body["item_id"] == item_id

            fetched = await async_kibana_client.exception_lists.get(list_id=list_id)
            assert fetched.body["id"] == created.body["id"]

            found = await async_kibana_client.exception_lists.find_items(
                list_id=list_id
            )
            assert found.body["total"] == 1
        finally:
            try:
                await async_kibana_client.exception_lists.delete(list_id=list_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.exception_lists.get(list_id=list_id)
