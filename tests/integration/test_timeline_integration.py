"""Integration tests for TimelineClient against a live Kibana instance."""

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

PREFIX = "kbnpy-timeline"


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
    """Generate a unique, prefixed Timeline title for testing."""
    return f"{PREFIX}-{uuid.uuid4().hex[:12]}"


def _timeline_payload(title: str) -> dict:
    """Build a minimal SavedTimeline payload for tests."""
    return {
        "title": title,
        "description": "kibana-py timeline integration test",
        "dateRange": {
            "start": "2026-07-01T00:00:00.000Z",
            "end": "2026-07-02T00:00:00.000Z",
        },
    }


def _cleanup_timelines(client, timeline_ids, space_id=None):
    """Delete Timelines, ignoring the case where they are already gone."""
    ids = [tid for tid in timeline_ids if tid]
    if not ids:
        return
    try:
        client.timeline.delete(saved_object_ids=ids, space_id=space_id)
    except Exception:
        pass


class TestTimelineLifecycle:
    """Full lifecycle tests for Timelines."""

    def test_create_get_resolve_update_delete(self, kibana_client, unique_title):
        """Test the full Timeline lifecycle."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            assert created.meta.status == 200
            assert created.body["title"] == unique_title
            assert created.body["version"]

            # Get by ID
            fetched = kibana_client.timeline.get(id=timeline_id)
            assert fetched.body["savedObjectId"] == timeline_id
            assert fetched.body["title"] == unique_title

            # Resolve (saved-objects resolve semantics)
            resolved = kibana_client.timeline.resolve(id=timeline_id)
            assert resolved.body["outcome"] == "exactMatch"
            assert resolved.body["timeline"]["savedObjectId"] == timeline_id

            # Update the title
            updated = kibana_client.timeline.update(
                timeline_id=timeline_id,
                version=fetched.body["version"],
                timeline={"title": f"{unique_title}-renamed"},
            )
            assert updated.body["title"] == f"{unique_title}-renamed"
            assert updated.body["version"] != fetched.body["version"]

            # List and find it
            listed = kibana_client.timeline.get_all(
                search=unique_title, page_size=25, page_index=1
            )
            listed_ids = [t["savedObjectId"] for t in listed.body["timeline"]]
            assert timeline_id in listed_ids
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])

        # After deletion the Timeline must be gone
        with pytest.raises(NotFoundError, match="Could not find timeline"):
            kibana_client.timeline.get(id=timeline_id)

    def test_get_without_id_raises_value_error(self, kibana_client):
        """Test the client-side guard for the documented live 500 quirk."""
        with pytest.raises(ValueError, match="template_timeline_id"):
            kibana_client.timeline.get()

    def test_get_without_id_server_quirk(self, kibana_client):
        """Test the raw route: GET /api/timeline without params returns 500.

        Documented live quirk in 9.4.3: the server responds with HTTP 500 and
        the message "please provide id or template_timeline_id".
        """
        with pytest.raises(ApiError) as exc_info:
            kibana_client.perform_request("GET", "/api/timeline")
        assert exc_info.value.status_code == 500
        assert "please provide id or template_timeline_id" in str(exc_info.value)

    def test_get_missing_timeline_raises_not_found(self, kibana_client):
        """Test that getting a nonexistent Timeline raises NotFoundError."""
        with pytest.raises(NotFoundError, match="Could not find timeline"):
            kibana_client.timeline.get(id=f"{PREFIX}-missing-{uuid.uuid4()}")


class TestTimelineFavoriteAndCopy:
    """Tests for favorite toggling and Timeline copies."""

    def test_favorite_toggle(self, kibana_client, unique_title):
        """Test that favoriting a Timeline toggles per user."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            favorited = kibana_client.timeline.favorite(
                timeline_id=timeline_id, timeline_type="default"
            )
            assert favorited.body["savedObjectId"] == timeline_id
            assert len(favorited.body["favorite"]) == 1
            assert favorited.body["favorite"][0]["userName"]

            # Calling it again removes the favorite mark
            unfavorited = kibana_client.timeline.favorite(
                timeline_id=timeline_id, timeline_type="default"
            )
            assert unfavorited.body["favorite"] == []
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])

    def test_copy(self, kibana_client, unique_title):
        """Test copying a Timeline produces a new saved object."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        copy_id = None
        try:
            copied = kibana_client.timeline.copy(
                timeline_id_to_copy=timeline_id,
                timeline={"title": f"{unique_title}-copy"},
            )
            copy_id = copied.body["savedObjectId"]
            assert copy_id and copy_id != timeline_id
            assert copied.body["title"] == f"{unique_title}-copy"

            fetched_copy = kibana_client.timeline.get(id=copy_id)
            assert fetched_copy.body["title"] == f"{unique_title}-copy"
        finally:
            _cleanup_timelines(kibana_client, [timeline_id, copy_id])


class TestTimelineDraft:
    """Tests for the per-user draft Timeline."""

    def test_draft_roundtrip(self, kibana_client):
        """Test getting and cleaning the current user's draft Timeline."""
        draft_id = None
        try:
            draft = kibana_client.timeline.get_draft(timeline_type="default")
            draft_id = draft.body["savedObjectId"]
            assert draft.body["status"] == "draft"

            cleaned = kibana_client.timeline.clean_draft(timeline_type="default")
            assert cleaned.body["status"] == "draft"
            draft_id = cleaned.body["savedObjectId"]
        finally:
            _cleanup_timelines(kibana_client, [draft_id])


class TestTimelineExportImport:
    """Tests for NDJSON export and multipart import."""

    def test_export_import_roundtrip(self, kibana_client, unique_title):
        """Test exporting a Timeline and importing it back as a new object."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        imported_id = None
        imported_title = f"{unique_title}-imported"
        try:
            exported = kibana_client.timeline.export(
                file_name="timelines.ndjson", ids=[timeline_id]
            )
            lines = list(exported)
            assert len(lines) == 1
            assert lines[0]["savedObjectId"] == timeline_id

            # Re-import under a different ID and title
            lines[0]["savedObjectId"] = f"{PREFIX}-import-{uuid.uuid4().hex[:12]}"
            lines[0]["title"] = imported_title
            result = kibana_client.timeline.import_timelines(file=lines)
            assert result.body["success"] is True
            assert result.body["timelines_installed"] == 1

            # The server assigns a fresh savedObjectId on import; find it by title
            listed = kibana_client.timeline.get_all(
                search=imported_title, page_size=25, page_index=1
            )
            matches = [
                t for t in listed.body["timeline"] if t["title"] == imported_title
            ]
            assert len(matches) == 1
            imported_id = matches[0]["savedObjectId"]
        finally:
            _cleanup_timelines(kibana_client, [timeline_id, imported_id])

    def test_import_duplicate_id_reports_conflict(self, kibana_client, unique_title):
        """Test that re-importing an existing savedObjectId reports a 409 error."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            exported = kibana_client.timeline.export(
                file_name="timelines.ndjson", ids=[timeline_id]
            )
            result = kibana_client.timeline.import_timelines(file=list(exported))
            assert result.body["success"] is False
            assert result.body["errors"][0]["error"]["status_code"] == 409
            assert "already exists" in result.body["errors"][0]["error"]["message"]
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])


class TestTimelinePrepackaged:
    """Tests for prepackaged Timeline installation."""

    def test_install_prepackaged(self, kibana_client):
        """Test installing/updating the Elastic prepackaged Timelines."""
        result = kibana_client.timeline.install_prepackaged()
        assert result.meta.status == 200
        assert result.body["success"] is True
        assert result.body["errors"] == []
        # Idempotent: on a stack where they are already installed both
        # counters may be zero.
        assert "timelines_installed" in result.body
        assert "timelines_updated" in result.body


class TestTimelineNotes:
    """Tests for Timeline notes."""

    def test_note_lifecycle(self, kibana_client, unique_title):
        """Test creating, listing, updating and deleting notes."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            note = kibana_client.timeline.create_note(
                note={"timelineId": timeline_id, "note": f"{unique_title} note"}
            )
            note_id = note.body["note"]["noteId"]
            note_version = note.body["note"]["version"]
            assert note.body["note"]["note"] == f"{unique_title} note"

            # Notes attached to the Timeline (savedObjectIds mode)
            by_timeline = kibana_client.timeline.get_notes(saved_object_ids=timeline_id)
            assert by_timeline.body["totalCount"] == 1
            assert by_timeline.body["notes"][0]["noteId"] == note_id

            # List mode with pagination
            listed = kibana_client.timeline.get_notes(page=1, per_page=100)
            assert listed.body["totalCount"] >= 1

            # documentIds mode: this note has no eventId, so no matches
            by_document = kibana_client.timeline.get_notes(
                document_ids=f"{PREFIX}-no-such-event"
            )
            assert by_document.body["totalCount"] == 0

            # Update the note text
            updated = kibana_client.timeline.update_note(
                note_id=note_id,
                note={"timelineId": timeline_id, "note": "updated text"},
                version=note_version,
            )
            assert updated.body["note"]["note"] == "updated text"
            assert updated.body["note"]["noteId"] == note_id

            # Delete it (single mode)
            kibana_client.timeline.delete_notes(note_id=note_id)
            after = kibana_client.timeline.get_notes(saved_object_ids=timeline_id)
            assert after.body["totalCount"] == 0
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])

    def test_bulk_delete_notes(self, kibana_client, unique_title):
        """Test deleting multiple notes at once with note_ids."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            note_ids = []
            for i in range(2):
                note = kibana_client.timeline.create_note(
                    note={"timelineId": timeline_id, "note": f"bulk note {i}"}
                )
                note_ids.append(note.body["note"]["noteId"])

            kibana_client.timeline.delete_notes(note_ids=note_ids)
            after = kibana_client.timeline.get_notes(saved_object_ids=timeline_id)
            assert after.body["totalCount"] == 0
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])


class TestTimelinePinnedEvents:
    """Tests for pinning and unpinning events."""

    def test_pin_and_unpin_event(self, kibana_client, unique_title):
        """Test pinning an event to a Timeline and unpinning it again."""
        created = kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        event_id = f"{PREFIX}-event-{uuid.uuid4().hex[:12]}"
        try:
            pinned = kibana_client.timeline.pin_event(
                event_id=event_id, timeline_id=timeline_id
            )
            assert pinned.body["eventId"] == event_id
            assert pinned.body["timelineId"] == timeline_id
            pinned_event_id = pinned.body["pinnedEventId"]
            assert pinned_event_id

            unpinned = kibana_client.timeline.unpin_event(
                event_id=event_id,
                timeline_id=timeline_id,
                pinned_event_id=pinned_event_id,
            )
            assert unpinned.body == {"unpinned": True}
        finally:
            _cleanup_timelines(kibana_client, [timeline_id])


class TestTimelineSpaceScoped:
    """Space-scoped tests for the Timeline API."""

    def test_timeline_is_space_scoped(self, kibana_client, unique_title):
        """Test that a Timeline created in a space is not visible elsewhere."""
        space_id = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        timeline_id = None
        try:
            created = kibana_client.timeline.create(
                timeline=_timeline_payload(unique_title), space_id=space_id
            )
            timeline_id = created.body["savedObjectId"]

            # Visible in its own space
            fetched = kibana_client.timeline.get(id=timeline_id, space_id=space_id)
            assert fetched.body["title"] == unique_title

            # Not visible in the default space
            with pytest.raises(NotFoundError):
                kibana_client.timeline.get(id=timeline_id)
        finally:
            if timeline_id is not None:
                _cleanup_timelines(kibana_client, [timeline_id], space_id=space_id)
            kibana_client.spaces.delete(id=space_id)


class TestAsyncTimelineLifecycle:
    """Async round-trip test for the Timeline API."""

    @pytest.mark.asyncio
    async def test_async_timeline_and_note_roundtrip(
        self, async_kibana_client, unique_title
    ):
        """Test the Timeline + note lifecycle with the async client."""
        created = await async_kibana_client.timeline.create(
            timeline=_timeline_payload(unique_title)
        )
        timeline_id = created.body["savedObjectId"]
        try:
            assert created.body["title"] == unique_title

            fetched = await async_kibana_client.timeline.get(id=timeline_id)
            assert fetched.body["savedObjectId"] == timeline_id

            note = await async_kibana_client.timeline.create_note(
                note={"timelineId": timeline_id, "note": "async note"}
            )
            note_id = note.body["note"]["noteId"]

            notes = await async_kibana_client.timeline.get_notes(
                saved_object_ids=timeline_id
            )
            assert notes.body["totalCount"] == 1

            await async_kibana_client.timeline.delete_notes(note_id=note_id)
        finally:
            try:
                await async_kibana_client.timeline.delete(
                    saved_object_ids=[timeline_id]
                )
            except Exception:
                pass

        with pytest.raises(NotFoundError):
            await async_kibana_client.timeline.get(id=timeline_id)
