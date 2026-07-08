"""Unit tests for AsyncTimelineClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.timeline import AsyncTimelineClient
from kibana.exceptions import NotFoundError


def _timeline_body() -> dict:
    """Kibana 9.4.3 timeline response body (abridged)."""
    return {
        "savedObjectId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
        "version": "WzE1LDJd",
        "title": "kbnpy-timeline-test",
        "description": "test timeline",
        "timelineType": "default",
        "status": "active",
        "favorite": [],
        "sort": [],
    }


def _note_response_body() -> dict:
    """Kibana 9.4.3 PATCH /api/note response body."""
    return {
        "code": 200,
        "message": "success",
        "note": {
            "noteId": "af498fe0-0fdc-45e2-89d0-d9fb5349b9a8",
            "version": "WzE5LDJd",
            "timelineId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
            "note": "kbnpy test note",
        },
    }


@pytest.fixture
def async_client(mock_async_transport, mock_response):
    """AsyncKibana client wired to the mocked transport with a 200 response."""
    mock_async_transport.perform_request.return_value = mock_response(
        body=_timeline_body()
    )
    return AsyncKibana(_transport=mock_async_transport)


class TestAsyncTimelineClientInitialization:
    """Test AsyncTimelineClient initialization and wiring."""

    @pytest.mark.asyncio
    async def test_timeline_client_initialization(self, mock_async_transport):
        """Test that AsyncTimelineClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        timeline_client = AsyncTimelineClient(client)
        assert timeline_client._client is client

    @pytest.mark.asyncio
    async def test_timeline_property_returns_timeline_client(
        self, mock_async_transport
    ):
        """Test that client.timeline returns a cached AsyncTimelineClient."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.timeline, AsyncTimelineClient)
        assert client.timeline is client.timeline


class TestAsyncTimelineCrud:
    """Test async Timeline create/get/get_all/update/delete/resolve/copy."""

    @pytest.mark.asyncio
    async def test_create(self, async_client, mock_async_transport):
        """Test creating a Timeline sends POST /api/timeline."""
        result = await async_client.timeline.create(
            timeline={"title": "kbnpy-timeline-test"}
        )

        assert result.body["savedObjectId"] == "d531f531-6b5e-465f-9ab7-380ec17918c1"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {"timeline": {"title": "kbnpy-timeline-test"}}
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(
        self, async_client, mock_async_transport
    ):
        """Test that optional create fields map to their camelCase keys."""
        await async_client.timeline.create(
            timeline={"title": "tmpl"},
            status="active",
            template_timeline_id="tmpl-1",
            template_timeline_version=2,
            timeline_id="tl-1",
            timeline_type="template",
            version="WzE0LDFd",
        )

        body = mock_async_transport.perform_request.call_args[1]["body"]
        assert body == {
            "timeline": {"title": "tmpl"},
            "status": "active",
            "templateTimelineId": "tmpl-1",
            "templateTimelineVersion": 2,
            "timelineId": "tl-1",
            "timelineType": "template",
            "version": "WzE0LDFd",
        }

    @pytest.mark.asyncio
    async def test_get_by_id(self, async_client, mock_async_transport):
        """Test getting a Timeline by its savedObjectId."""
        result = await async_client.timeline.get(
            id="d531f531-6b5e-465f-9ab7-380ec17918c1"
        )

        assert result.body["title"] == "kbnpy-timeline-test"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/timeline?id=d531f531-6b5e-465f-9ab7-380ec17918c1"
        )

    @pytest.mark.asyncio
    async def test_get_requires_an_id(self, async_client):
        """Test that get() without id or template_timeline_id raises."""
        with pytest.raises(ValueError, match="template_timeline_id"):
            await async_client.timeline.get()

    @pytest.mark.asyncio
    async def test_get_all_param_encoding(self, async_client, mock_async_transport):
        """Test that get_all encodes all list-mode query parameters."""
        await async_client.timeline.get_all(
            only_user_favorite=False,
            timeline_type="default",
            sort_field="updated",
            sort_order="desc",
            page_size=10,
            page_index=1,
            search="kbnpy",
            status="active",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == (
            "/api/timelines?only_user_favorite=false&timeline_type=default"
            "&sort_field=updated&sort_order=desc&page_size=10&page_index=1"
            "&search=kbnpy&status=active"
        )

    @pytest.mark.asyncio
    async def test_update(self, async_client, mock_async_transport):
        """Test updating a Timeline sends PATCH /api/timeline."""
        await async_client.timeline.update(
            timeline_id="tl-1", version="WzE1LDJd", timeline={"title": "renamed"}
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {
            "timelineId": "tl-1",
            "version": "WzE1LDJd",
            "timeline": {"title": "renamed"},
        }

    @pytest.mark.asyncio
    async def test_delete(self, async_client, mock_async_transport):
        """Test deleting Timelines sends DELETE /api/timeline with IDs."""
        await async_client.timeline.delete(saved_object_ids=["id-1"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {"savedObjectIds": ["id-1"]}

    @pytest.mark.asyncio
    async def test_resolve(self, async_client, mock_async_transport):
        """Test resolving a Timeline by ID."""
        await async_client.timeline.resolve(id="tl-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/timeline/resolve?id=tl-1"

    @pytest.mark.asyncio
    async def test_copy(self, async_client, mock_async_transport):
        """Test copy sends POST /api/timeline/_copy with the internal header."""
        await async_client.timeline.copy(
            timeline_id_to_copy="tl-1", timeline={"title": "copy"}
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_copy"
        assert call_kwargs["headers"]["x-elastic-internal-origin"] == "kibana-py"
        assert call_kwargs["body"] == {
            "timeline": {"title": "copy"},
            "timelineIdToCopy": "tl-1",
        }


class TestAsyncTimelineDraft:
    """Test async draft Timeline methods."""

    @pytest.mark.asyncio
    async def test_get_draft(self, async_client, mock_async_transport):
        """Test getting the current user's draft Timeline."""
        await async_client.timeline.get_draft(timeline_type="default")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/timeline/_draft?timelineType=default"

    @pytest.mark.asyncio
    async def test_clean_draft(self, async_client, mock_async_transport):
        """Test creating a clean draft Timeline."""
        await async_client.timeline.clean_draft(timeline_type="default")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_draft"
        assert call_kwargs["body"] == {"timelineType": "default"}


class TestAsyncTimelineExportImport:
    """Test async export/import/prepackaged methods."""

    @pytest.mark.asyncio
    async def test_export(self, async_client, mock_async_transport):
        """Test exporting Timelines as NDJSON."""
        await async_client.timeline.export(file_name="timelines.ndjson", ids=["id-1"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/timeline/_export?file_name=timelines.ndjson"
        )
        assert call_kwargs["body"] == {"ids": ["id-1"]}

    @pytest.mark.asyncio
    async def test_import_timelines_multipart_body(
        self, async_client, mock_async_transport
    ):
        """Test that import uploads multipart/form-data with the NDJSON file."""
        await async_client.timeline.import_timelines(
            file=[{"savedObjectId": "id-1"}], is_immutable=True
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_import"
        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        body = call_kwargs["body"]
        assert isinstance(body, bytes)
        assert b'Content-Disposition: form-data; name="isImmutable"' in body
        assert b"\r\ntrue\r\n" in body
        assert b'{"savedObjectId": "id-1"}' in body

    @pytest.mark.asyncio
    async def test_import_timelines_requires_file(self, async_client):
        """Test that an empty file payload raises ValueError."""
        with pytest.raises(ValueError, match="file"):
            await async_client.timeline.import_timelines(file="")

    @pytest.mark.asyncio
    async def test_install_prepackaged_defaults(
        self, async_client, mock_async_transport
    ):
        """Test installing prepackaged Timelines with default empty lists."""
        await async_client.timeline.install_prepackaged()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/timeline/_prepackaged"
        assert call_kwargs["body"] == {
            "timelinesToInstall": [],
            "timelinesToUpdate": [],
            "prepackagedTimelines": [],
        }


class TestAsyncTimelineFavorite:
    """Test the async favorite method."""

    @pytest.mark.asyncio
    async def test_favorite(self, async_client, mock_async_transport):
        """Test favoriting a Timeline sends all four required body fields."""
        await async_client.timeline.favorite(
            timeline_id="tl-1", timeline_type="default"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/timeline/_favorite"
        assert call_kwargs["body"] == {
            "timelineId": "tl-1",
            "templateTimelineId": None,
            "templateTimelineVersion": None,
            "timelineType": "default",
        }


class TestAsyncTimelineNotes:
    """Test async note methods."""

    @pytest.mark.asyncio
    async def test_create_note(self, async_client, mock_async_transport, mock_response):
        """Test creating a note sends PATCH /api/note without noteId."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_note_response_body()
        )
        result = await async_client.timeline.create_note(
            note={"timelineId": "tl-1", "note": "kbnpy test note"}
        )

        assert result.body["note"]["noteId"] == "af498fe0-0fdc-45e2-89d0-d9fb5349b9a8"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/note"
        assert call_kwargs["body"] == {
            "note": {"timelineId": "tl-1", "note": "kbnpy test note"}
        }

    @pytest.mark.asyncio
    async def test_update_note(self, async_client, mock_async_transport):
        """Test updating a note includes noteId and version."""
        await async_client.timeline.update_note(
            note_id="note-1",
            note={"timelineId": "tl-1", "note": "updated"},
            version="WzE5LDJd",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "note": {"timelineId": "tl-1", "note": "updated"},
            "noteId": "note-1",
            "version": "WzE5LDJd",
        }

    @pytest.mark.asyncio
    async def test_get_notes_by_document_ids(self, async_client, mock_async_transport):
        """Test that a list of document IDs becomes repeated query keys."""
        await async_client.timeline.get_notes(document_ids=["ev-1", "ev-2"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/note?documentIds=ev-1&documentIds=ev-2"

    @pytest.mark.asyncio
    async def test_get_notes_list_mode(self, async_client, mock_async_transport):
        """Test listing notes with pagination parameters."""
        await async_client.timeline.get_notes(page=1, per_page=5, search="kbnpy")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/note?page=1&perPage=5&search=kbnpy"

    @pytest.mark.asyncio
    async def test_delete_notes_single(self, async_client, mock_async_transport):
        """Test deleting a single note by noteId."""
        await async_client.timeline.delete_notes(note_id="note-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/note"
        assert call_kwargs["body"] == {"noteId": "note-1"}

    @pytest.mark.asyncio
    async def test_delete_notes_bulk(self, async_client, mock_async_transport):
        """Test deleting multiple notes by noteIds."""
        await async_client.timeline.delete_notes(note_ids=["note-1", "note-2"])

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"noteIds": ["note-1", "note-2"]}

    @pytest.mark.asyncio
    async def test_delete_notes_requires_exactly_one_selector(self, async_client):
        """Test that neither or both of note_id/note_ids raises."""
        with pytest.raises(ValueError, match="Exactly one"):
            await async_client.timeline.delete_notes()
        with pytest.raises(ValueError, match="Exactly one"):
            await async_client.timeline.delete_notes(note_id="a", note_ids=["b"])


class TestAsyncTimelinePinnedEvents:
    """Test async pinned-event methods."""

    @pytest.mark.asyncio
    async def test_pin_event(self, async_client, mock_async_transport):
        """Test pinning an event to a Timeline."""
        await async_client.timeline.pin_event(event_id="ev-1", timeline_id="tl-1")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/pinned_event"
        assert call_kwargs["body"] == {"eventId": "ev-1", "timelineId": "tl-1"}

    @pytest.mark.asyncio
    async def test_unpin_event(self, async_client, mock_async_transport):
        """Test unpinning an event includes the pinnedEventId."""
        await async_client.timeline.unpin_event(
            event_id="ev-1", timeline_id="tl-1", pinned_event_id="pin-1"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "eventId": "ev-1",
            "timelineId": "tl-1",
            "pinnedEventId": "pin-1",
        }


class TestAsyncTimelineSpaceScoping:
    """Test async space-scoped path building."""

    @pytest.mark.asyncio
    async def test_create_in_space(self, async_client, mock_async_transport):
        """Test that space_id prefixes the path with /s/<space>."""
        await async_client.timeline.create(
            timeline={"title": "t"}, space_id="security-team", validate_spaces=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/security-team/api/timeline"


class TestAsyncTimelineErrorHandling:
    """Test async error mapping."""

    @pytest.mark.asyncio
    async def test_get_not_found_error(self, mock_async_transport, mock_response):
        """Test that a 404 body maps to NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Could not find timeline", "status_code": 404},
            status=404,
        )
        client = AsyncKibana(_transport=mock_async_transport)

        with pytest.raises(NotFoundError):
            await client.timeline.get(id="missing-id")
