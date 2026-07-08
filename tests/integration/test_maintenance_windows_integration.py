"""Integration tests for MaintenanceWindowsClient against a live Kibana instance.

Maintenance windows require a Platinum or higher license (the trial license
used by the local dev stack is sufficient).
"""

import uuid

import pytest

from kibana.exceptions import ApiError, NotFoundError

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

SCHEDULE = {
    "custom": {
        "start": "2030-01-05T00:00:00.000Z",
        "duration": "2h",
        "timezone": "UTC",
    }
}


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
def unique_title():
    """Generate a unique, prefixed maintenance window title for testing."""
    return f"kbnpy-mw-{uuid.uuid4().hex[:12]}"


def _cleanup_maintenance_window(client, mw_id: str, space_id: str | None = None):
    """Delete a maintenance window, ignoring the case where it is already gone."""
    try:
        client.maintenance_windows.delete(id=mw_id, space_id=space_id)
    except NotFoundError:
        pass


def _skip_if_license_issue(error: ApiError):
    """Skip the test if the failure is caused by a missing license."""
    if "license" in str(error).lower():
        pytest.skip(f"Maintenance windows not available with current license: {error}")
    raise error


class TestMaintenanceWindowsLifecycle:
    """Full lifecycle tests for the Maintenance Windows API."""

    def test_create_get_update_delete(self, kibana_client, unique_title):
        """Test the full create/get/update/delete lifecycle."""
        try:
            created = kibana_client.maintenance_windows.create(
                title=unique_title,
                schedule=SCHEDULE,
                scope={"alerting": {"query": {"kql": 'tags: "kbnpy-mw"'}}},
            )
        except ApiError as e:
            _skip_if_license_issue(e)
        mw_id = created.body["id"]
        try:
            assert created.meta.status == 200
            assert created.body["title"] == unique_title
            assert created.body["enabled"] is True
            assert created.body["status"] == "upcoming"
            assert created.body["schedule"]["custom"]["duration"] == "2h"
            assert (
                created.body["scope"]["alerting"]["query"]["kql"] == 'tags: "kbnpy-mw"'
            )

            # Get by ID
            fetched = kibana_client.maintenance_windows.get(id=mw_id)
            assert fetched.body["id"] == mw_id
            assert fetched.body["title"] == unique_title

            # Partial update: rename and disable
            updated = kibana_client.maintenance_windows.update(
                id=mw_id,
                title=f"{unique_title}-renamed",
                enabled=False,
            )
            assert updated.body["title"] == f"{unique_title}-renamed"
            assert updated.body["enabled"] is False
            assert updated.body["status"] == "disabled"

            # Update the schedule only
            new_schedule = {
                "custom": {
                    "start": "2031-01-05T00:00:00.000Z",
                    "duration": "30m",
                }
            }
            rescheduled = kibana_client.maintenance_windows.update(
                id=mw_id, schedule=new_schedule
            )
            assert rescheduled.body["schedule"]["custom"]["duration"] == "30m"
            # Fields not included in the PATCH are preserved
            assert rescheduled.body["title"] == f"{unique_title}-renamed"
        finally:
            _cleanup_maintenance_window(kibana_client, mw_id)

        # After deletion the maintenance window must be gone
        with pytest.raises(NotFoundError):
            kibana_client.maintenance_windows.get(id=mw_id)

    def test_archive_and_unarchive(self, kibana_client, unique_title):
        """Test archiving and unarchiving a maintenance window."""
        try:
            created = kibana_client.maintenance_windows.create(
                title=unique_title, schedule=SCHEDULE
            )
        except ApiError as e:
            _skip_if_license_issue(e)
        mw_id = created.body["id"]
        try:
            archived = kibana_client.maintenance_windows.archive(id=mw_id)
            assert archived.body["id"] == mw_id
            assert archived.body["status"] == "archived"

            restored = kibana_client.maintenance_windows.unarchive(id=mw_id)
            assert restored.body["id"] == mw_id
            # Live Kibana 9.4.3 reports "finished" (not "upcoming") after
            # unarchiving a future-scheduled window; only assert it left the
            # archived state.
            assert restored.body["status"] != "archived"
        finally:
            _cleanup_maintenance_window(kibana_client, mw_id)

    def test_find_with_filters(self, kibana_client, unique_title):
        """Test finding maintenance windows by title and status."""
        try:
            created = kibana_client.maintenance_windows.create(
                title=unique_title, schedule=SCHEDULE
            )
        except ApiError as e:
            _skip_if_license_issue(e)
        mw_id = created.body["id"]
        try:
            # Filter by exact title
            found = kibana_client.maintenance_windows.find(title=unique_title)
            assert found.body["total"] == 1
            assert found.body["maintenanceWindows"][0]["id"] == mw_id

            # Filter by title + status list (upcoming or running matches)
            found = kibana_client.maintenance_windows.find(
                title=unique_title,
                status=["upcoming", "running"],
                page=1,
                per_page=5,
            )
            assert found.body["page"] == 1
            assert found.body["per_page"] == 5
            assert any(mw["id"] == mw_id for mw in found.body["maintenanceWindows"])

            # A non-matching status filter excludes it
            found = kibana_client.maintenance_windows.find(
                title=unique_title, status="archived"
            )
            assert all(mw["id"] != mw_id for mw in found.body["maintenanceWindows"])
        finally:
            _cleanup_maintenance_window(kibana_client, mw_id)

    def test_get_missing_maintenance_window_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent maintenance window raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.maintenance_windows.get(id=f"kbnpy-mw-missing-{uuid.uuid4()}")


class TestMaintenanceWindowsSpaceScoped:
    """Space-scoped tests for the Maintenance Windows API."""

    def test_maintenance_window_is_space_scoped(self, kibana_client, unique_title):
        """Test that a maintenance window created in a space is not visible elsewhere."""
        space_id = f"kbnpy-mw-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        mw_id = None
        try:
            try:
                created = kibana_client.maintenance_windows.create(
                    title=unique_title,
                    schedule=SCHEDULE,
                    space_id=space_id,
                )
            except ApiError as e:
                _skip_if_license_issue(e)
            mw_id = created.body["id"]

            # Visible in its own space
            fetched = kibana_client.maintenance_windows.get(id=mw_id, space_id=space_id)
            assert fetched.body["title"] == unique_title

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.maintenance_windows.get(id=mw_id)
        finally:
            if mw_id is not None:
                _cleanup_maintenance_window(kibana_client, mw_id, space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncMaintenanceWindowsLifecycle:
    """Async round-trip test for the Maintenance Windows API."""

    @pytest.mark.asyncio
    async def test_async_full_lifecycle(self, async_kibana_client, unique_title):
        """Test the full maintenance window lifecycle with the async client."""
        try:
            created = await async_kibana_client.maintenance_windows.create(
                title=unique_title, schedule=SCHEDULE
            )
        except ApiError as e:
            if "license" in str(e).lower():
                pytest.skip(
                    f"Maintenance windows not available with current license: {e}"
                )
            raise
        mw_id = created.body["id"]
        try:
            assert created.body["status"] == "upcoming"

            fetched = await async_kibana_client.maintenance_windows.get(id=mw_id)
            assert fetched.body["id"] == mw_id

            updated = await async_kibana_client.maintenance_windows.update(
                id=mw_id, enabled=False
            )
            assert updated.body["status"] == "disabled"

            found = await async_kibana_client.maintenance_windows.find(
                title=unique_title
            )
            assert any(mw["id"] == mw_id for mw in found.body["maintenanceWindows"])

            archived = await async_kibana_client.maintenance_windows.archive(id=mw_id)
            assert archived.body["id"] == mw_id

            restored = await async_kibana_client.maintenance_windows.unarchive(id=mw_id)
            assert restored.body["id"] == mw_id
        finally:
            try:
                await async_kibana_client.maintenance_windows.delete(id=mw_id)
            except NotFoundError:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.maintenance_windows.get(id=mw_id)
