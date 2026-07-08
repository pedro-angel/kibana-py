"""Unit tests for TimelineClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._sync.client import Kibana
from kibana._sync.client.timeline import TimelineClient


def _timeline_body() -> dict:
    """Kibana 9.4.3 timeline response body (abridged)."""
    return {
        "savedObjectId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
        "version": "WzE1LDJd",
        "title": "kbnpy-timeline-test",
        "description": "test timeline",
        "timelineType": "default",
        "status": "active",
        "dateRange": {
            "start": "2026-07-01T00:00:00.000Z",
            "end": "2026-07-02T00:00:00.000Z",
        },
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
            "createdBy": "elastic",
            "updatedBy": "elastic",
        },
    }


@pytest.fixture
def client(mock_transport):
    """Kibana client wired to the mocked transport with a 200 response."""
    mock_transport.perform_request.return_value = ObjectApiResponse(
        body=_timeline_body(),
        meta=Mock(status=200, headers={}),
    )
    return Kibana(_transport=mock_transport)


class TestTimelineClientInitialization:
    """Test TimelineClient initialization and wiring."""

    def test_timeline_client_initialization(self, mock_transport):
        """Test that TimelineClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        timeline_client = TimelineClient(client)
        assert timeline_client._client is client

    def test_timeline_property_returns_timeline_client(self, mock_transport):
        """Test that client.timeline returns a cached TimelineClient."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.timeline, TimelineClient)
        assert client.timeline is client.timeline


class TestTimelineCrud:
    """Test Timeline create/get/get_all/update/delete/resolve methods."""

    def test_create(self, client, mock_transport):
        """Test creating a Timeline sends POST /api/timeline."""
        result = client.timeline.create(
            timeline={"title": "kbnpy-timeline-test", "description": "test timeline"}
        )

        assert result.body["savedObjectId"] == "d531f531-6b5e-465f-9ab7-380ec17918c1"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {
            "timeline": {
                "title": "kbnpy-timeline-test",
                "description": "test timeline",
            }
        }
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"

    def test_create_with_optional_fields(self, client, mock_transport):
        """Test that optional create fields map to their camelCase keys."""
        client.timeline.create(
            timeline={"title": "tmpl"},
            status="active",
            template_timeline_id="tmpl-1",
            template_timeline_version=2,
            timeline_id="tl-1",
            timeline_type="template",
            version="WzE0LDFd",
        )

        body = mock_transport.perform_request.call_args[1]["body"]
        assert body == {
            "timeline": {"title": "tmpl"},
            "status": "active",
            "templateTimelineId": "tmpl-1",
            "templateTimelineVersion": 2,
            "timelineId": "tl-1",
            "timelineType": "template",
            "version": "WzE0LDFd",
        }

    def test_get_by_id(self, client, mock_transport):
        """Test getting a Timeline by its savedObjectId."""
        result = client.timeline.get(id="d531f531-6b5e-465f-9ab7-380ec17918c1")

        assert result.body["title"] == "kbnpy-timeline-test"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/timeline?id=d531f531-6b5e-465f-9ab7-380ec17918c1"
        )
        assert "body" not in call_kwargs

    def test_get_by_template_timeline_id(self, client, mock_transport):
        """Test getting a Timeline template by template_timeline_id."""
        client.timeline.get(template_timeline_id="tmpl-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/timeline?template_timeline_id=tmpl-1"

    def test_get_requires_an_id(self, client):
        """Test that get() without id or template_timeline_id raises."""
        with pytest.raises(ValueError, match="template_timeline_id"):
            client.timeline.get()

    def test_get_all_param_encoding(self, client, mock_transport):
        """Test that get_all encodes all list-mode query parameters."""
        client.timeline.get_all(
            only_user_favorite=False,
            timeline_type="default",
            sort_field="updated",
            sort_order="desc",
            page_size=10,
            page_index=1,
            search="kbnpy",
            status="active",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/timelines?only_user_favorite=false&timeline_type=default"
            "&sort_field=updated&sort_order=desc&page_size=10&page_index=1"
            "&search=kbnpy&status=active"
        )

    def test_get_all_without_params(self, client, mock_transport):
        """Test that get_all without filters targets the bare path."""
        client.timeline.get_all()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/timelines"

    def test_update(self, client, mock_transport):
        """Test updating a Timeline sends PATCH /api/timeline."""
        client.timeline.update(
            timeline_id="d531f531-6b5e-465f-9ab7-380ec17918c1",
            version="WzE1LDJd",
            timeline={"title": "renamed"},
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {
            "timelineId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
            "version": "WzE1LDJd",
            "timeline": {"title": "renamed"},
        }

    def test_delete(self, client, mock_transport):
        """Test deleting Timelines sends DELETE /api/timeline with IDs."""
        client.timeline.delete(
            saved_object_ids=["id-1", "id-2"], search_ids=["search-1"]
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/timeline"
        assert call_kwargs["body"] == {
            "savedObjectIds": ["id-1", "id-2"],
            "searchIds": ["search-1"],
        }

    def test_resolve(self, client, mock_transport):
        """Test resolving a Timeline by ID."""
        client.timeline.resolve(id="d531f531-6b5e-465f-9ab7-380ec17918c1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert (
            call_kwargs["target"]
            == "/api/timeline/resolve?id=d531f531-6b5e-465f-9ab7-380ec17918c1"
        )

    def test_resolve_requires_an_id(self, client):
        """Test that resolve() without id or template_timeline_id raises."""
        with pytest.raises(ValueError, match="template_timeline_id"):
            client.timeline.resolve()

    def test_copy(self, client, mock_transport):
        """Test copy sends POST /api/timeline/_copy with the internal header.

        The 9.4.3 OpenAPI spec documents GET, but the live server only
        accepts POST from internal origins.
        """
        client.timeline.copy(
            timeline_id_to_copy="d531f531-6b5e-465f-9ab7-380ec17918c1",
            timeline={"title": "copy"},
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_copy"
        assert call_kwargs["headers"]["x-elastic-internal-origin"] == "kibana-py"
        assert call_kwargs["body"] == {
            "timeline": {"title": "copy"},
            "timelineIdToCopy": "d531f531-6b5e-465f-9ab7-380ec17918c1",
        }


class TestTimelineDraft:
    """Test draft Timeline methods."""

    def test_get_draft(self, client, mock_transport):
        """Test getting the current user's draft Timeline."""
        client.timeline.get_draft(timeline_type="default")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/timeline/_draft?timelineType=default"

    def test_clean_draft(self, client, mock_transport):
        """Test creating a clean draft Timeline."""
        client.timeline.clean_draft(timeline_type="template")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_draft"
        assert call_kwargs["body"] == {"timelineType": "template"}


class TestTimelineExportImport:
    """Test export/import/prepackaged methods."""

    def test_export(self, client, mock_transport):
        """Test exporting Timelines as NDJSON."""
        client.timeline.export(file_name="timelines.ndjson", ids=["id-1"])

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/timeline/_export?file_name=timelines.ndjson"
        )
        assert call_kwargs["body"] == {"ids": ["id-1"]}

    def test_import_timelines_multipart_body(self, client, mock_transport):
        """Test that import uploads multipart/form-data with the NDJSON file."""
        client.timeline.import_timelines(
            file=[{"savedObjectId": "id-1", "title": "t"}],
            is_immutable=False,
            filename="kbnpy.ndjson",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_import"
        content_type = call_kwargs["headers"]["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        body = call_kwargs["body"]
        assert isinstance(body, bytes)
        boundary = content_type.split("boundary=")[1]
        assert body.startswith(f"--{boundary}\r\n".encode())
        assert body.endswith(f"--{boundary}--\r\n".encode())
        assert b'Content-Disposition: form-data; name="isImmutable"' in body
        assert b"\r\nfalse\r\n" in body
        assert (
            b'Content-Disposition: form-data; name="file"; filename="kbnpy.ndjson"'
            in body
        )
        assert b'{"savedObjectId": "id-1", "title": "t"}' in body

    def test_import_timelines_accepts_raw_bytes(self, client, mock_transport):
        """Test that raw NDJSON bytes are passed through unchanged."""
        client.timeline.import_timelines(file=b'{"savedObjectId": "id-1"}\n')

        body = mock_transport.perform_request.call_args[1]["body"]
        assert b'{"savedObjectId": "id-1"}\n' in body
        assert b"isImmutable" not in body

    def test_import_timelines_requires_file(self, client):
        """Test that an empty file payload raises ValueError."""
        with pytest.raises(ValueError, match="file"):
            client.timeline.import_timelines(file=b"")

    def test_install_prepackaged_defaults(self, client, mock_transport):
        """Test installing prepackaged Timelines with default empty lists."""
        client.timeline.install_prepackaged()

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/timeline/_prepackaged"
        assert call_kwargs["body"] == {
            "timelinesToInstall": [],
            "timelinesToUpdate": [],
            "prepackagedTimelines": [],
        }


class TestTimelineFavorite:
    """Test the favorite method."""

    def test_favorite(self, client, mock_transport):
        """Test favoriting a Timeline sends all four required body fields."""
        client.timeline.favorite(
            timeline_id="d531f531-6b5e-465f-9ab7-380ec17918c1",
            timeline_type="default",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/timeline/_favorite"
        assert call_kwargs["body"] == {
            "timelineId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
            "templateTimelineId": None,
            "templateTimelineVersion": None,
            "timelineType": "default",
        }


class TestTimelineNotes:
    """Test note methods."""

    def test_create_note(self, client, mock_transport):
        """Test creating a note sends PATCH /api/note without noteId."""
        mock_transport.perform_request.return_value = ObjectApiResponse(
            body=_note_response_body(),
            meta=Mock(status=200, headers={}),
        )
        result = client.timeline.create_note(
            note={
                "timelineId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
                "note": "kbnpy test note",
            }
        )

        assert result.body["note"]["noteId"] == "af498fe0-0fdc-45e2-89d0-d9fb5349b9a8"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/note"
        assert call_kwargs["body"] == {
            "note": {
                "timelineId": "d531f531-6b5e-465f-9ab7-380ec17918c1",
                "note": "kbnpy test note",
            }
        }

    def test_update_note(self, client, mock_transport):
        """Test updating a note includes noteId and version."""
        client.timeline.update_note(
            note_id="af498fe0-0fdc-45e2-89d0-d9fb5349b9a8",
            note={"timelineId": "tl-1", "note": "updated"},
            version="WzE5LDJd",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/note"
        assert call_kwargs["body"] == {
            "note": {"timelineId": "tl-1", "note": "updated"},
            "noteId": "af498fe0-0fdc-45e2-89d0-d9fb5349b9a8",
            "version": "WzE5LDJd",
        }

    def test_get_notes_list_mode(self, client, mock_transport):
        """Test listing notes with pagination and filters."""
        client.timeline.get_notes(
            page=1,
            per_page=5,
            search="kbnpy",
            sort_field="created",
            sort_order="desc",
            filter='note.attributes.note: "x"',
            created_by_filter="f1c2d3e4-uid",
            associated_filter="all",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == (
            "/api/note?page=1&perPage=5&search=kbnpy&sortField=created"
            "&sortOrder=desc&filter=note.attributes.note%3A+%22x%22"
            "&createdByFilter=f1c2d3e4-uid&associatedFilter=all"
        )

    def test_get_notes_by_document_ids(self, client, mock_transport):
        """Test that a list of document IDs becomes repeated query keys."""
        client.timeline.get_notes(document_ids=["ev-1", "ev-2"])

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/note?documentIds=ev-1&documentIds=ev-2"

    def test_get_notes_by_saved_object_ids(self, client, mock_transport):
        """Test fetching notes for a single Timeline saved object ID."""
        client.timeline.get_notes(saved_object_ids="tl-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/note?savedObjectIds=tl-1"

    def test_delete_notes_single(self, client, mock_transport):
        """Test deleting a single note by noteId."""
        client.timeline.delete_notes(note_id="note-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/note"
        assert call_kwargs["body"] == {"noteId": "note-1"}

    def test_delete_notes_bulk(self, client, mock_transport):
        """Test deleting multiple notes by noteIds."""
        client.timeline.delete_notes(note_ids=["note-1", "note-2"])

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"noteIds": ["note-1", "note-2"]}

    def test_delete_notes_requires_exactly_one_selector(self, client):
        """Test that neither or both of note_id/note_ids raises."""
        with pytest.raises(ValueError, match="Exactly one"):
            client.timeline.delete_notes()
        with pytest.raises(ValueError, match="Exactly one"):
            client.timeline.delete_notes(note_id="a", note_ids=["b"])


class TestTimelinePinnedEvents:
    """Test pinned-event methods."""

    def test_pin_event(self, client, mock_transport):
        """Test pinning an event to a Timeline."""
        client.timeline.pin_event(event_id="ev-1", timeline_id="tl-1")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["target"] == "/api/pinned_event"
        assert call_kwargs["body"] == {"eventId": "ev-1", "timelineId": "tl-1"}

    def test_unpin_event(self, client, mock_transport):
        """Test unpinning an event includes the pinnedEventId."""
        client.timeline.unpin_event(
            event_id="ev-1", timeline_id="tl-1", pinned_event_id="pin-1"
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "eventId": "ev-1",
            "timelineId": "tl-1",
            "pinnedEventId": "pin-1",
        }


class TestTimelineSpaceScoping:
    """Test space-scoped path building."""

    def test_create_in_space(self, client, mock_transport):
        """Test that space_id prefixes the path with /s/<space>."""
        client.timeline.create(
            timeline={"title": "t"}, space_id="security-team", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/security-team/api/timeline"

    def test_get_notes_in_space(self, client, mock_transport):
        """Test that note routes are space-scoped too."""
        client.timeline.get_notes(
            saved_object_ids="tl-1", space_id="security-team", validate_spaces=False
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/security-team/api/note?savedObjectIds=tl-1"


class TestTimelineErrorHandling:
    """Test error mapping."""

    def test_get_not_found_error(self, mock_transport):
        """Test that a 404 body maps to NotFoundError."""
        from kibana.exceptions import NotFoundError

        mock_transport.perform_request.return_value = ObjectApiResponse(
            body={"message": "Could not find timeline", "status_code": 404},
            meta=Mock(status=404, headers={}),
        )
        client = Kibana(_transport=mock_transport)

        with pytest.raises(NotFoundError):
            client.timeline.get(id="missing-id")
