"""Integration tests for ListsClient against a live Kibana instance."""

import time
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


@pytest.fixture
def unique_list_id():
    """Generate a unique, prefixed value list ID for testing."""
    return f"kbnpy-lists-{uuid.uuid4().hex[:12]}"


def _cleanup_list(client, list_id: str, space_id: str | None = None) -> None:
    """Delete a value list, ignoring the case where it is already gone."""
    try:
        client.lists.delete(id=list_id, space_id=space_id)
    except NotFoundError:
        pass


def _wait_for_item_gone(client, item_id: str, timeout: float = 15.0) -> None:
    """Poll get_item until the deleted item stops being returned.

    Item deletions become visible slightly asynchronously on the live stack,
    even when the delete request uses refresh=wait_for.
    """
    deadline = time.time() + timeout
    while True:
        try:
            client.lists.get_item(id=item_id)
        except NotFoundError:
            return
        if time.time() >= deadline:
            with pytest.raises(NotFoundError, match="does not exist"):
                client.lists.get_item(id=item_id)
            return
        time.sleep(0.5)


def _wait_for_item_total(client, list_id: str, expected: int, timeout: float = 15.0):
    """Poll find_items until the list holds the expected number of items.

    Kibana processes list item imports slightly asynchronously (items land
    ~1s after the import response, even with refresh=wait_for), so tests
    poll instead of asserting immediately.
    """
    deadline = time.time() + timeout
    found = client.lists.find_items(list_id=list_id)
    while found.body["total"] != expected and time.time() < deadline:
        time.sleep(0.5)
        found = client.lists.find_items(list_id=list_id)
    return found


class TestListsIndexStatus:
    """Tests for the value list data stream endpoints (shared index).

    NOTE: DELETE /api/lists/index is deliberately NOT exercised against the
    shared default-space data streams (it would delete every value list of
    the space and break other tests); the full create/status/delete index
    lifecycle is exercised in an isolated space in
    TestListsIndexLifecycleInOwnSpace instead.
    """

    @pytest.fixture(autouse=True)
    def _ensure_index(self, kibana_client):
        """Ensure the shared value list data streams exist before these tests.

        On a fresh stack the ``.lists-default``/``.items-default`` data streams
        do not exist until ``create_index()`` runs, so ``get_index_status``
        would 404 depending on test order. ``create_index`` is idempotent on
        9.4.3 (``{"acknowledged": true}`` whether or not they already exist),
        so this makes the status assertions independent of stack freshness.
        """
        kibana_client.lists.create_index()

    def test_get_index_status(self, kibana_client):
        """Test that the shared value list data streams exist."""
        status = kibana_client.lists.get_index_status()
        assert status.meta.status == 200
        assert status.body["list_index"] is True
        assert status.body["list_item_index"] is True

    def test_create_index_is_idempotent(self, kibana_client):
        """Test that creating the already-existing data streams succeeds.

        On Kibana 9.4.3 POST /api/lists/index responds with
        {"acknowledged": true} even when the data streams already exist
        (older versions responded 409).
        """
        result = kibana_client.lists.create_index()
        assert result.body == {"acknowledged": True}

    def test_get_privileges(self, kibana_client):
        """Test reading value list privileges."""
        privileges = kibana_client.lists.get_privileges()
        assert privileges.body["is_authenticated"] is True
        assert "lists" in privileges.body
        assert "listItems" in privileges.body


class TestListsLifecycle:
    """Full lifecycle tests for value lists."""

    def test_create_get_update_patch_find_delete(self, kibana_client, unique_list_id):
        """Test the full value list lifecycle."""
        created = kibana_client.lists.create(
            name="kbnpy lists integration",
            description="created by kibana-py integration tests",
            type="ip",
            id=unique_list_id,
            meta={"origin": "kibana-py-tests"},
        )
        try:
            assert created.meta.status == 200
            assert created.body["id"] == unique_list_id
            assert created.body["type"] == "ip"
            assert created.body["version"] == 1
            assert created.body["meta"] == {"origin": "kibana-py-tests"}

            # Get
            fetched = kibana_client.lists.get(id=unique_list_id)
            assert fetched.body["name"] == "kbnpy lists integration"

            # Update (full replace) with optimistic concurrency
            updated = kibana_client.lists.update(
                id=unique_list_id,
                name="kbnpy lists integration - updated",
                description="updated description",
                _version=fetched.body["_version"],
            )
            assert updated.body["name"] == "kbnpy lists integration - updated"
            assert updated.body["description"] == "updated description"
            assert updated.body["version"] > created.body["version"]

            # Patch (partial update)
            patched = kibana_client.lists.patch(
                id=unique_list_id, name="kbnpy lists integration - patched"
            )
            assert patched.body["name"] == "kbnpy lists integration - patched"
            # description untouched by the patch
            assert patched.body["description"] == "updated description"

            # Find with a filter on the list name
            found = kibana_client.lists.find(
                filter=f"name:{patched.body['name']}", per_page=100
            )
            assert found.body["total"] >= 1
            assert any(entry["id"] == unique_list_id for entry in found.body["data"])
        finally:
            _cleanup_list(kibana_client, unique_list_id)

        # After deletion the list must be gone
        with pytest.raises(NotFoundError, match="does not exist"):
            kibana_client.lists.get(id=unique_list_id)

    def test_get_missing_list_raises_not_found(self, kibana_client):
        """Test the live 404 message for a missing list."""
        missing_id = f"kbnpy-lists-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError, match="does not exist"):
            kibana_client.lists.get(id=missing_id)


class TestListItemsLifecycle:
    """Full lifecycle tests for value list items."""

    def test_item_crud_and_find(self, kibana_client, unique_list_id):
        """Test create/get/update/patch/find/delete for list items."""
        kibana_client.lists.create(
            name="kbnpy lists items",
            description="items lifecycle",
            type="ip",
            id=unique_list_id,
        )
        try:
            # Create
            item = kibana_client.lists.create_item(
                list_id=unique_list_id, value="192.0.2.1", refresh="wait_for"
            )
            item_id = item.body["id"]
            assert item.body["list_id"] == unique_list_id
            assert item.body["type"] == "ip"

            # Get by ID -> single object
            by_id = kibana_client.lists.get_item(id=item_id)
            assert by_id.body["value"] == "192.0.2.1"

            # Get by list_id + value -> array of matching items
            by_pair = kibana_client.lists.get_item(
                list_id=unique_list_id, value="192.0.2.1"
            )
            assert isinstance(by_pair.body, list)
            assert by_pair.body[0]["id"] == item_id

            # Update (full replace)
            updated = kibana_client.lists.update_item(id=item_id, value="192.0.2.2")
            assert updated.body["value"] == "192.0.2.2"

            # Patch
            patched = kibana_client.lists.patch_item(
                id=item_id, value="192.0.2.3", refresh="wait_for"
            )
            assert patched.body["value"] == "192.0.2.3"

            # Find
            found = _wait_for_item_total(kibana_client, unique_list_id, 1)
            assert found.body["total"] == 1
            assert found.body["data"][0]["value"] == "192.0.2.3"

            # Delete by list_id + value -> array of deleted items
            deleted = kibana_client.lists.delete_item(
                list_id=unique_list_id, value="192.0.2.3", refresh="wait_for"
            )
            assert isinstance(deleted.body, list)
            assert deleted.body[0]["id"] == item_id

            # Deletion visibility lags slightly on the live stack; poll
            _wait_for_item_gone(kibana_client, item_id)
        finally:
            _cleanup_list(kibana_client, unique_list_id)

    def test_get_missing_item_raises_not_found(self, kibana_client):
        """Test the live 404 message for a missing list item."""
        missing_id = f"kbnpy-lists-missing-item-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError, match="does not exist"):
            kibana_client.lists.get_item(id=missing_id)


class TestListItemsImportExport:
    """Import/export round-trip tests for value list items."""

    def test_import_into_existing_list_and_export(self, kibana_client, unique_list_id):
        """Test importing values into an existing list and exporting them."""
        kibana_client.lists.create(
            name="kbnpy lists import",
            description="import/export round trip",
            type="ip",
            id=unique_list_id,
        )
        try:
            values = ["198.51.100.1", "198.51.100.2", "198.51.100.3"]
            imported = kibana_client.lists.import_items(
                file=values, list_id=unique_list_id, refresh="wait_for"
            )
            assert imported.body["id"] == unique_list_id

            # Imported items land slightly asynchronously; poll until visible
            found = _wait_for_item_total(kibana_client, unique_list_id, len(values))
            assert found.body["total"] == len(values)

            exported = kibana_client.lists.export_items(list_id=unique_list_id)
            assert sorted(str(value) for value in exported.body) == values
        finally:
            _cleanup_list(kibana_client, unique_list_id)

    def test_import_creates_new_list_from_filename(self, kibana_client, unique_list_id):
        """Test that importing without list_id creates a list from the filename."""
        filename = f"{unique_list_id}.txt"
        try:
            imported = kibana_client.lists.import_items(
                file="203.0.113.1\n203.0.113.2\n",
                type="ip",
                filename=filename,
                refresh="wait_for",
            )
            # The new list id and name are taken from the uploaded filename
            assert imported.body["id"] == filename
            assert imported.body["name"] == filename
            assert imported.body["type"] == "ip"

            found = _wait_for_item_total(kibana_client, filename, 2)
            assert found.body["total"] == 2
        finally:
            _cleanup_list(kibana_client, filename)


class TestListsIndexLifecycleInOwnSpace:
    """Exercise the full index lifecycle in an isolated, test-owned space.

    This covers DELETE /api/lists/index live without touching the shared
    default-space data streams that other tests rely on.
    """

    def test_index_lifecycle_in_own_space(self, kibana_client):
        """Test create/status/delete of value list data streams in a new space."""
        space_id = f"kbnpy-lists-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        list_id = f"kbnpy-lists-{uuid.uuid4().hex[:8]}"
        try:
            # No data streams yet in the new space
            with pytest.raises(NotFoundError, match="does not exist"):
                kibana_client.lists.get_index_status(space_id=space_id)

            # Create them
            created = kibana_client.lists.create_index(space_id=space_id)
            assert created.body == {"acknowledged": True}

            status = kibana_client.lists.get_index_status(space_id=space_id)
            assert status.body == {"list_index": True, "list_item_index": True}

            # Lists are space-scoped: a list created here is invisible elsewhere
            kibana_client.lists.create(
                name="space scoped",
                description="space scoped",
                type="keyword",
                id=list_id,
                space_id=space_id,
            )
            fetched = kibana_client.lists.get(id=list_id, space_id=space_id)
            assert fetched.body["id"] == list_id
            with pytest.raises(NotFoundError):
                kibana_client.lists.get(id=list_id)

            _cleanup_list(kibana_client, list_id, space_id=space_id)

            # Delete the space's own data streams (NOT the shared ones)
            deleted = kibana_client.lists.delete_index(space_id=space_id)
            assert deleted.body == {"acknowledged": True}

            with pytest.raises(NotFoundError, match="does not exist"):
                kibana_client.lists.get_index_status(space_id=space_id)
        finally:
            try:
                kibana_client.lists.delete_index(space_id=space_id)
            except NotFoundError:
                pass
            kibana_client.spaces.delete(id=space_id)


class TestAsyncListsLifecycle:
    """Async round-trip test for the Lists API."""

    @pytest.mark.asyncio
    async def test_async_list_and_items_round_trip(
        self, async_kibana_client, unique_list_id
    ):
        """Test list + item lifecycle and export with the async client."""
        created = await async_kibana_client.lists.create(
            name="kbnpy async lists",
            description="async round trip",
            type="ip",
            id=unique_list_id,
        )
        try:
            assert created.body["id"] == unique_list_id

            status = await async_kibana_client.lists.get_index_status()
            assert status.body["list_index"] is True

            item = await async_kibana_client.lists.create_item(
                list_id=unique_list_id, value="192.0.2.10", refresh="wait_for"
            )
            assert item.body["value"] == "192.0.2.10"

            patched = await async_kibana_client.lists.patch(
                id=unique_list_id, name="kbnpy async lists - patched"
            )
            assert patched.body["name"] == "kbnpy async lists - patched"

            found = await async_kibana_client.lists.find_items(list_id=unique_list_id)
            assert found.body["total"] == 1

            exported = await async_kibana_client.lists.export_items(
                list_id=unique_list_id
            )
            assert [str(value) for value in exported.body] == ["192.0.2.10"]
        finally:
            try:
                await async_kibana_client.lists.delete(id=unique_list_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError, match="does not exist"):
            await async_kibana_client.lists.get(id=unique_list_id)
