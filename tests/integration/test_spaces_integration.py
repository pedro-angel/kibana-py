"""Integration tests for SpacesClient / AsyncSpacesClient against a live Kibana.

Every resource created here is prefixed ``kbnpy-spaces-`` and cleaned up in
fixture finalizers or try/finally blocks so parallel test runs on the shared
stack do not interfere with each other.
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


def _unique_id(suffix: str = "") -> str:
    """Generate a unique, namespaced resource id."""
    base = f"kbnpy-spaces-{uuid.uuid4().hex[:8]}"
    return f"{base}-{suffix}" if suffix else base


def _safe_delete_space(client, space_id: str) -> None:
    """Delete a space, ignoring errors (used in cleanup paths)."""
    try:
        client.spaces.delete(id=space_id)
    except Exception:
        pass


def _safe_delete_saved_object(client, type: str, id: str) -> None:
    """Delete a saved object (with force for shared objects), ignoring errors."""
    try:
        client.saved_objects.delete(type=type, id=id, force=True)
    except Exception:
        pass


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


class TestSpacesLifecycleIntegration:
    """Live CRUD lifecycle for the /api/spaces/space endpoints."""

    def test_space_full_lifecycle_with_solution(self, kibana_client):
        """Create, get, list, update, and delete a space with a solution view."""
        space_id = _unique_id()
        try:
            # Create with the full 9.4.3 body surface
            created = kibana_client.spaces.create(
                id=space_id,
                name="kbnpy spaces lifecycle",
                description="kibana-py spaces integration test",
                color="#2E7D32",
                initials="KS",
                disabled_features=["ml"],
                solution="oblt",
            )
            assert created.body["id"] == space_id
            assert created.body["name"] == "kbnpy spaces lifecycle"
            assert created.body["color"] == "#2E7D32"
            assert created.body["solution"] == "oblt"

            # Get it back
            fetched = kibana_client.spaces.get(id=space_id)
            assert fetched.body["id"] == space_id
            assert fetched.body["solution"] == "oblt"
            assert fetched.body["description"] == "kibana-py spaces integration test"

            # It shows up in the full listing
            all_spaces = kibana_client.spaces.get_all()
            assert space_id in [s["id"] for s in all_spaces.body]

            # Update (PUT): name is mandatory, solution can be switched
            updated = kibana_client.spaces.update(
                id=space_id,
                name="kbnpy spaces lifecycle v2",
                color="#AD1457",
                solution="classic",
            )
            assert updated.body["name"] == "kbnpy spaces lifecycle v2"
            assert updated.body["solution"] == "classic"

            refetched = kibana_client.spaces.get(id=space_id)
            assert refetched.body["name"] == "kbnpy spaces lifecycle v2"
            assert refetched.body["color"] == "#AD1457"
            assert refetched.body["solution"] == "classic"
            # Live 9.4.3: omitted description is preserved (partial-merge),
            # while omitted disabledFeatures resets to its schema default [].
            assert refetched.body["description"] == "kibana-py spaces integration test"
            assert refetched.body.get("disabledFeatures") == []

            # Delete and verify it is gone
            kibana_client.spaces.delete(id=space_id)
            with pytest.raises(NotFoundError):
                kibana_client.spaces.get(id=space_id)
        finally:
            _safe_delete_space(kibana_client, space_id)

    def test_create_duplicate_space_conflict(self, kibana_client):
        """Creating the same space twice raises ConflictError."""
        space_id = _unique_id("dup")
        try:
            kibana_client.spaces.create(id=space_id, name="kbnpy dup space")
            with pytest.raises(ConflictError):
                kibana_client.spaces.create(id=space_id, name="kbnpy dup space")
        finally:
            _safe_delete_space(kibana_client, space_id)

    def test_get_nonexistent_space_raises_not_found(self, kibana_client):
        """Getting a space that does not exist raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.spaces.get(id=_unique_id("missing"))

    def test_get_all_purpose_and_authorized_purposes(self, kibana_client):
        """Exercise the purpose / include_authorized_purposes query params."""
        # authorizedPurposes map is returned when requested
        with_purposes = kibana_client.spaces.get_all(include_authorized_purposes=True)
        default_space = next(s for s in with_purposes.body if s["id"] == "default")
        assert "authorizedPurposes" in default_space
        assert isinstance(default_space["authorizedPurposes"], dict)

        # purpose filter is accepted on its own
        copyable = kibana_client.spaces.get_all(purpose="copySavedObjectsIntoSpace")
        assert isinstance(copyable.body, list)
        assert "default" in [s["id"] for s in copyable.body]

        # Live 9.4.3 rejects combining purpose with
        # include_authorized_purposes=true
        with pytest.raises(BadRequestError):
            kibana_client.spaces.get_all(
                purpose="copySavedObjectsIntoSpace",
                include_authorized_purposes=True,
            )


class TestSpacesCopyIntegration:
    """Live tests for the saved-object copy/share endpoints."""

    def test_copy_saved_objects_and_resolve_conflicts(self, kibana_client):
        """Copy a dashboard from default into a space, then resolve a conflict."""
        space_id = _unique_id("copy")
        dash_id = _unique_id("dash")
        try:
            kibana_client.spaces.create(id=space_id, name="kbnpy copy target")
            kibana_client.saved_objects.create(
                type="dashboard",
                id=dash_id,
                attributes={"title": f"kbnpy spaces copy test {dash_id}"},
            )

            # First copy succeeds
            copied = kibana_client.spaces.copy_saved_objects(
                spaces=[space_id],
                objects=[{"type": "dashboard", "id": dash_id}],
                create_new_copies=False,
            )
            result = copied.body[space_id]
            assert result["success"] is True
            assert result["successCount"] == 1
            destination_id = result["successResults"][0].get("destinationId", dash_id)

            # Copying again without overwrite reports a conflict
            conflicted = kibana_client.spaces.copy_saved_objects(
                spaces=[space_id],
                objects=[{"type": "dashboard", "id": dash_id}],
                create_new_copies=False,
            )
            result = conflicted.body[space_id]
            assert result["success"] is False
            assert result["errors"][0]["error"]["type"] == "conflict"

            # Resolve the conflict by overwriting the destination object
            resolved = kibana_client.spaces.resolve_copy_saved_objects_errors(
                objects=[{"type": "dashboard", "id": dash_id}],
                retries={
                    space_id: [
                        {
                            "type": "dashboard",
                            "id": dash_id,
                            "destinationId": destination_id,
                            "overwrite": True,
                        }
                    ]
                },
                create_new_copies=False,
            )
            result = resolved.body[space_id]
            assert result["success"] is True
            assert result["successCount"] == 1
        finally:
            _safe_delete_saved_object(kibana_client, "dashboard", dash_id)
            # Deleting the space also removes the copies inside it
            _safe_delete_space(kibana_client, space_id)

    def test_shareable_references_and_update_objects_spaces_roundtrip(
        self, kibana_client
    ):
        """Share an index-pattern into a space and back via the spaces APIs."""
        space_id = _unique_id("share")
        ip_id = _unique_id("ip")
        try:
            kibana_client.spaces.create(id=space_id, name="kbnpy share target")
            # index-pattern is a share-capable saved object type
            kibana_client.saved_objects.create(
                type="index-pattern",
                id=ip_id,
                attributes={"title": f"{ip_id}-*"},
            )

            refs = kibana_client.spaces.get_shareable_references(
                objects=[{"type": "index-pattern", "id": ip_id}]
            )
            ref = refs.body["objects"][0]
            assert ref["type"] == "index-pattern"
            assert ref["id"] == ip_id
            assert ref["spaces"] == ["default"]

            # Share into the target space
            shared = kibana_client.spaces.update_objects_spaces(
                objects=[{"type": "index-pattern", "id": ip_id}],
                spaces_to_add=[space_id],
                spaces_to_remove=[],
            )
            assert set(shared.body["objects"][0]["spaces"]) == {"default", space_id}

            refs = kibana_client.spaces.get_shareable_references(
                objects=[{"type": "index-pattern", "id": ip_id}]
            )
            assert set(refs.body["objects"][0]["spaces"]) == {"default", space_id}

            # Unshare again
            unshared = kibana_client.spaces.update_objects_spaces(
                objects=[{"type": "index-pattern", "id": ip_id}],
                spaces_to_add=[],
                spaces_to_remove=[space_id],
            )
            assert unshared.body["objects"][0]["spaces"] == ["default"]
        finally:
            _safe_delete_saved_object(kibana_client, "index-pattern", ip_id)
            _safe_delete_space(kibana_client, space_id)

    def test_disable_legacy_url_aliases(self, kibana_client):
        """Disabling a (nonexistent) legacy URL alias returns 204 No Content."""
        space_id = _unique_id("alias")
        try:
            kibana_client.spaces.create(id=space_id, name="kbnpy alias target")
            response = kibana_client.spaces.disable_legacy_url_aliases(
                aliases=[
                    {
                        "targetSpace": space_id,
                        "targetType": "dashboard",
                        "sourceId": _unique_id("no-such-alias"),
                    }
                ]
            )
            assert response.meta.status == 204
        finally:
            _safe_delete_space(kibana_client, space_id)


class TestAsyncSpacesIntegration:
    """Async round-trips against the live stack."""

    @pytest.mark.asyncio
    async def test_async_space_lifecycle(self):
        """Create, get, update, list, and delete a space with the async client."""
        client = create_test_async_kibana_client(auth_method="auto")
        space_id = _unique_id("async")
        try:
            created = await client.spaces.create(
                id=space_id,
                name="kbnpy async space",
                description="async integration test",
                solution="es",
            )
            assert created.body["id"] == space_id
            assert created.body["solution"] == "es"

            fetched = await client.spaces.get(id=space_id)
            assert fetched.body["name"] == "kbnpy async space"

            updated = await client.spaces.update(
                id=space_id,
                name="kbnpy async space v2",
                solution="es",
            )
            assert updated.body["name"] == "kbnpy async space v2"

            all_spaces = await client.spaces.get_all(include_authorized_purposes=True)
            match = next(s for s in all_spaces.body if s["id"] == space_id)
            assert "authorizedPurposes" in match

            await client.spaces.delete(id=space_id)
            with pytest.raises(NotFoundError):
                await client.spaces.get(id=space_id)
        finally:
            try:
                await client.spaces.delete(id=space_id)
            except Exception:
                pass
            await client.close()

    @pytest.mark.asyncio
    async def test_async_get_shareable_references(self):
        """Async round-trip of the _get_shareable_references endpoint."""
        client = create_test_async_kibana_client(auth_method="auto")
        ip_id = _unique_id("aio-ip")
        try:
            await client.saved_objects.create(
                type="index-pattern",
                id=ip_id,
                attributes={"title": f"{ip_id}-*"},
            )
            refs = await client.spaces.get_shareable_references(
                objects=[{"type": "index-pattern", "id": ip_id}]
            )
            assert refs.body["objects"][0]["spaces"] == ["default"]
        finally:
            try:
                await client.saved_objects.delete(
                    type="index-pattern", id=ip_id, force=True
                )
            except Exception:
                pass
            await client.close()
