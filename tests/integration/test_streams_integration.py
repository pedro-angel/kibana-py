"""Integration tests for StreamsClient against a live Kibana instance.

The Streams APIs are a technical preview in Kibana 9.4. These tests enable
streams (idempotent), work only on ``kbnpy``-prefixed child/query streams,
clean up everything they create, and restore the original enabled/disabled
state at the end of the session.
"""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

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

# Wired root stream managed by Kibana 9.4 once streams are enabled
ROOT_STREAM = "logs.ecs"


def _streams_enabled(client) -> bool:
    """Return True when the wired root stream exists (streams enabled)."""
    try:
        client.streams.get(name=ROOT_STREAM)
        return True
    except NotFoundError:
        return False


# The Streams technical-preview sub-features (significant events, attachments,
# content packs, query streams) are each gated behind an ``observability:``
# advanced (UI) setting that defaults to off. Until enabled, their endpoints
# reject calls with 400/403/422. The settings are runtime-toggleable through the
# internal settings API, so the session fixture switches them on and restores the
# prior values afterwards -- the same enable/restore contract used for streams.
_STREAMS_FEATURE_SETTINGS = (
    "observability:streamsEnableSignificantEvents",
    "observability:streamsEnableAttachments",
    "observability:streamsEnableContentPacks",
    "observability:streamsEnableQueryStreams",
)

# The settings routes are internal, so they need the internal-origin header
# (mirrors the pattern in kibana/_sync/client/timeline.py).
_SETTINGS_PATH = "/internal/kibana/settings"
_SETTINGS_HEADERS = {
    "accept": "application/json",
    "x-elastic-internal-origin": "kibana-py",
}


def _get_feature_settings(client) -> dict:
    """Return each feature setting's current user value (None when unset/default)."""
    resp = client.perform_request("GET", _SETTINGS_PATH, headers=_SETTINGS_HEADERS)
    settings = resp.body.get("settings", {})
    return {
        key: settings.get(key, {}).get("userValue") for key in _STREAMS_FEATURE_SETTINGS
    }


def _apply_feature_settings(client, changes: dict) -> None:
    """Set (value) or clear (None) advanced settings via the internal API."""
    client.perform_request(
        "POST", _SETTINGS_PATH, headers=_SETTINGS_HEADERS, body={"changes": changes}
    )


@pytest.fixture(scope="session")
def streams_enabled_session():
    """Enable streams + preview sub-features for the session; restore prior state."""
    client = create_test_kibana_client(auth_method="auto")
    was_enabled = _streams_enabled(client)
    prior_settings = _get_feature_settings(client)
    client.streams.enable()
    _apply_feature_settings(client, dict.fromkeys(_STREAMS_FEATURE_SETTINGS, True))
    try:
        yield
    finally:
        # Best-effort teardown: isolate the restore/disable steps so a hiccup can't
        # leave the shared live stack dirty or the session transport open --
        # client.close() must always run.
        try:
            # Restore advanced settings to their pre-test values (None clears them).
            _apply_feature_settings(client, prior_settings)
            # Restore the pre-test streams state: only disable if we enabled it.
            if not was_enabled:
                client.streams.disable()
        finally:
            client.close()


@pytest.fixture
def kibana_client(streams_enabled_session):
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client(streams_enabled_session):
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture
def child_stream(kibana_client):
    """Fork a uniquely named child stream off the root and delete it after."""
    # Wired stream path segments and ES|QL FROM clauses are friendliest with
    # plain alphanumeric segments, so avoid hyphens in the leaf name.
    name = f"{ROOT_STREAM}.kbnpystreams{uuid.uuid4().hex[:6]}"
    kibana_client.streams.fork(
        name=ROOT_STREAM,
        stream_name=name,
        where={"field": "service.name", "eq": "kbnpy-streams-it"},
    )
    yield name
    try:
        kibana_client.streams.delete(name=name)
    except NotFoundError:
        pass


def _sig_events_esql(name: str) -> str:
    """Build the strict ES|QL shape Kibana requires for stream queries."""
    return f"FROM {name}, {name}.* METADATA _id, _source"


class TestStreamsGlobalOperations:
    """Enable/list/resync behaviour on the live stack."""

    def test_enable_is_idempotent(self, kibana_client):
        result = kibana_client.streams.enable()
        assert result.body["acknowledged"] is True
        # Session fixture already enabled streams, so this is a no-op
        assert result.body["result"] == "noop"

    def test_get_all_contains_wired_roots(self, kibana_client):
        result = kibana_client.streams.get_all()
        names = [s["name"] for s in result.body["streams"]]
        assert ROOT_STREAM in names
        root = next(s for s in result.body["streams"] if s["name"] == ROOT_STREAM)
        assert root["type"] == "wired"

    def test_get_root_stream(self, kibana_client):
        result = kibana_client.streams.get(name=ROOT_STREAM)
        assert result.body["stream"]["name"] == ROOT_STREAM
        assert result.body["stream"]["type"] == "wired"
        assert "privileges" in result.body

    def test_get_ingest_of_root(self, kibana_client):
        result = kibana_client.streams.get_ingest(name=ROOT_STREAM)
        assert "lifecycle" in result.body["ingest"]
        assert "wired" in result.body["ingest"]

    def test_resync(self, kibana_client):
        result = kibana_client.streams.resync()
        assert result.body["acknowledged"] is True

    def test_get_missing_stream_raises_not_found(self, kibana_client):
        with pytest.raises(NotFoundError):
            kibana_client.streams.get(name="logs.ecs.kbnpystreamsmissing")


class TestStreamsLifecycle:
    """Fork/upsert/update/delete lifecycle for wired child streams."""

    def test_fork_get_update_ingest_delete(self, kibana_client, child_stream):
        fetched = kibana_client.streams.get(name=child_stream)
        assert fetched.body["stream"]["type"] == "wired"

        # Add a field mapping through the ingest settings endpoint.
        # Live 9.4.3 rejects the read-only processing.updated_at field that
        # get_ingest returns, so it must be stripped before the round trip.
        ingest = kibana_client.streams.get_ingest(name=child_stream).body["ingest"]
        ingest["processing"].pop("updated_at", None)
        ingest["wired"]["fields"]["attributes.kbnpy.label"] = {"type": "keyword"}
        updated = kibana_client.streams.update_ingest(name=child_stream, ingest=ingest)
        assert updated.body["acknowledged"] is True

        refreshed = kibana_client.streams.get_ingest(name=child_stream)
        assert (
            refreshed.body["ingest"]["wired"]["fields"]["attributes.kbnpy.label"][
                "type"
            ]
            == "keyword"
        )

    def test_upsert_wired_child_stream(self, kibana_client):
        name = f"{ROOT_STREAM}.kbnpystreams{uuid.uuid4().hex[:6]}"
        # A stream created via PUT needs a routing rule on the parent to be
        # reachable, but the API accepts a standalone definition too.
        kibana_client.streams.fork(
            name=ROOT_STREAM,
            stream_name=name,
            where={"field": "service.name", "eq": "kbnpy-streams-upsert"},
        )
        try:
            stream = {
                "type": "wired",
                "description": "kbnpy streams integration test",
                "ingest": {
                    "lifecycle": {"inherit": {}},
                    "processing": {"steps": []},
                    "settings": {},
                    "failure_store": {"inherit": {}},
                    "wired": {"fields": {}, "routing": []},
                },
            }
            result = kibana_client.streams.upsert(name=name, stream=stream)
            assert result.body["acknowledged"] is True
            assert result.body["result"] == "updated"

            fetched = kibana_client.streams.get(name=name)
            assert (
                fetched.body["stream"]["description"]
                == "kbnpy streams integration test"
            )
        finally:
            kibana_client.streams.delete(name=name)

        with pytest.raises(NotFoundError):
            kibana_client.streams.get(name=name)


class TestStreamsQueries:
    """Significant-events queries lifecycle on a live child stream."""

    def test_query_crud_and_bulk(self, kibana_client, child_stream, elser_ready):
        esql = _sig_events_esql(child_stream)
        query_id = "kbnpy-streams-q1"

        created = kibana_client.streams.upsert_query(
            name=child_stream,
            query_id=query_id,
            title="kbnpy error spike",
            esql=esql,
            description="kbnpy integration test query",
            severity_score=25,
            evidence=["created by kibana-py integration tests"],
        )
        assert created.body["acknowledged"] is True

        queries = kibana_client.streams.get_queries(name=child_stream)
        assert [q["id"] for q in queries.body["queries"]] == [query_id]
        assert queries.body["queries"][0]["esql"]["query"] == esql

        # Bulk: add a second query and remove the first in one request
        bulk = kibana_client.streams.bulk_queries(
            name=child_stream,
            operations=[
                {
                    "index": {
                        "id": "kbnpy-streams-q2",
                        "title": "kbnpy bulk query",
                        "description": "added via bulk",
                        "esql": {"query": esql},
                    }
                },
                {"delete": {"id": query_id}},
            ],
        )
        assert bulk.body["acknowledged"] is True

        queries = kibana_client.streams.get_queries(name=child_stream)
        assert [q["id"] for q in queries.body["queries"]] == ["kbnpy-streams-q2"]

        deleted = kibana_client.streams.delete_query(
            name=child_stream, query_id="kbnpy-streams-q2"
        )
        assert deleted.body["acknowledged"] is True
        assert (
            kibana_client.streams.get_queries(name=child_stream).body["queries"] == []
        )

    def test_significant_events_read_and_preview(self, kibana_client, child_stream):
        esql = _sig_events_esql(child_stream)
        kibana_client.streams.upsert_query(
            name=child_stream,
            query_id="kbnpy-streams-sig",
            title="kbnpy significant",
            esql=esql,
            description="kbnpy significant events",
        )

        events = kibana_client.streams.get_significant_events(
            name=child_stream,
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
            bucket_size="1h",
        )
        assert "significant_events" in events.body
        assert "aggregated_occurrences" in events.body
        ids = [e["id"] for e in events.body["significant_events"]]
        assert "kbnpy-streams-sig" in ids

        preview = kibana_client.streams.preview_significant_events(
            name=child_stream,
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
            bucket_size="1h",
            esql=esql,
        )
        assert "occurrences" in preview.body
        assert "change_points" in preview.body

    def test_generate_significant_events_requires_ai_connector(
        self, kibana_client, child_stream
    ):
        # The trial stack has no AI connector configured: the endpoint must
        # be reachable and reject the request with a clear 400 error.
        with pytest.raises(BadRequestError, match="connector"):
            kibana_client.streams.generate_significant_events(
                name=child_stream,
                from_="2026-07-01T00:00:00.000Z",
                to="2026-07-02T00:00:00.000Z",
            )


class TestStreamsContentPacks:
    """Content pack export/import round trip."""

    def test_export_import_roundtrip(self, kibana_client, child_stream):
        exported = kibana_client.streams.export_content(
            name=child_stream,
            content_name="kbnpy-streams-pack",
            description="kibana-py integration test content pack",
            version="1.0.0",
        )
        archive = bytes(exported.body)
        assert archive.startswith(b"PK")  # ZIP magic bytes

        imported = kibana_client.streams.import_content(
            name=child_stream,
            content=archive,
            filename="kbnpy-streams-pack-1.0.0.zip",
        )
        assert imported.body["acknowledged"] is True
        result = imported.body["result"]
        assert child_stream in result["created"] + result["updated"]


class TestQueryStreams:
    """Query stream settings lifecycle (added in 9.4)."""

    def test_query_stream_settings_lifecycle(self, kibana_client):
        name = f"kbnpy-streams-qs-{uuid.uuid4().hex[:6]}"
        esql = f"FROM {ROOT_STREAM}, {ROOT_STREAM}.* METADATA _id, _source | LIMIT 5"
        try:
            created = kibana_client.streams.update_query_settings(name=name, esql=esql)
            assert created.body["acknowledged"] is True
            assert created.body["result"] == "created"

            settings = kibana_client.streams.get_query_settings(name=name)
            assert settings.body["query"]["esql"] == esql

            fetched = kibana_client.streams.get(name=name)
            assert fetched.body["stream"]["type"] == "query"
        finally:
            try:
                kibana_client.streams.delete(name=name)
            except NotFoundError:
                pass

    def test_get_query_settings_on_wired_stream_fails(
        self, kibana_client, child_stream
    ):
        with pytest.raises(BadRequestError, match="not a query stream"):
            kibana_client.streams.get_query_settings(name=child_stream)


class TestStreamsAttachments:
    """Attachment link/unlink/bulk lifecycle (added in 9.3)."""

    @pytest.fixture
    def dashboard_id(self, kibana_client):
        """Create a throwaway dashboard saved object for linking."""
        dash_id = f"kbnpy-streams-dash-{uuid.uuid4().hex[:6]}"
        kibana_client.saved_objects.create(
            type="dashboard",
            id=dash_id,
            attributes={
                "title": f"kbnpy streams attachment test {dash_id}",
                "panelsJSON": "[]",
                "optionsJSON": "{}",
            },
        )
        yield dash_id
        try:
            kibana_client.saved_objects.delete(type="dashboard", id=dash_id, force=True)
        except NotFoundError:
            pass

    def test_attachment_lifecycle(self, kibana_client, child_stream, dashboard_id):
        linked = kibana_client.streams.link_attachment(
            name=child_stream,
            attachment_type="dashboard",
            attachment_id=dashboard_id,
        )
        assert linked.body["acknowledged"] is True

        attachments = kibana_client.streams.get_attachments(name=child_stream)
        assert [a["id"] for a in attachments.body["attachments"]] == [dashboard_id]
        assert attachments.body["attachments"][0]["type"] == "dashboard"

        # Filtered read: dashboard type matches, rule type does not
        filtered = kibana_client.streams.get_attachments(
            name=child_stream, attachment_types=["dashboard"]
        )
        assert len(filtered.body["attachments"]) == 1
        none_match = kibana_client.streams.get_attachments(
            name=child_stream, attachment_types=["rule"]
        )
        assert none_match.body["attachments"] == []

        unlinked = kibana_client.streams.unlink_attachment(
            name=child_stream,
            attachment_type="dashboard",
            attachment_id=dashboard_id,
        )
        assert unlinked.body["acknowledged"] is True
        assert (
            kibana_client.streams.get_attachments(name=child_stream).body["attachments"]
            == []
        )

    def test_bulk_attachments(self, kibana_client, child_stream, dashboard_id):
        linked = kibana_client.streams.bulk_attachments(
            name=child_stream,
            operations=[{"index": {"id": dashboard_id, "type": "dashboard"}}],
        )
        assert linked.body["acknowledged"] is True
        attachments = kibana_client.streams.get_attachments(name=child_stream)
        assert [a["id"] for a in attachments.body["attachments"]] == [dashboard_id]

        unlinked = kibana_client.streams.bulk_attachments(
            name=child_stream,
            operations=[{"delete": {"id": dashboard_id, "type": "dashboard"}}],
        )
        assert unlinked.body["acknowledged"] is True
        assert (
            kibana_client.streams.get_attachments(name=child_stream).body["attachments"]
            == []
        )


class TestAsyncStreams:
    """Async client round trips against the live stack."""

    @pytest.mark.asyncio
    async def test_async_list_fork_query_delete(self, async_kibana_client):
        result = await async_kibana_client.streams.enable()
        assert result.body["acknowledged"] is True

        listed = await async_kibana_client.streams.get_all()
        names = [s["name"] for s in listed.body["streams"]]
        assert ROOT_STREAM in names

        name = f"{ROOT_STREAM}.kbnpystreams{uuid.uuid4().hex[:6]}"
        try:
            forked = await async_kibana_client.streams.fork(
                name=ROOT_STREAM,
                stream_name=name,
                where={"field": "service.name", "eq": "kbnpy-streams-async"},
            )
            assert forked.body["result"] == "created"

            esql = _sig_events_esql(name)
            await async_kibana_client.streams.upsert_query(
                name=name,
                query_id="kbnpy-streams-aq",
                title="kbnpy async query",
                esql=esql,
                description="async integration test",
            )
            queries = await async_kibana_client.streams.get_queries(name=name)
            assert [q["id"] for q in queries.body["queries"]] == ["kbnpy-streams-aq"]
        finally:
            deleted = await async_kibana_client.streams.delete(name=name)
            assert deleted.body["result"] == "deleted"

    @pytest.mark.asyncio
    async def test_async_query_stream_settings(self, async_kibana_client):
        name = f"kbnpy-streams-aqs-{uuid.uuid4().hex[:6]}"
        esql = f"FROM {ROOT_STREAM}, {ROOT_STREAM}.* METADATA _id, _source | LIMIT 3"
        try:
            created = await async_kibana_client.streams.update_query_settings(
                name=name, esql=esql
            )
            assert created.body["result"] == "created"

            settings = await async_kibana_client.streams.get_query_settings(name=name)
            assert settings.body["query"]["esql"] == esql
        finally:
            try:
                await async_kibana_client.streams.delete(name=name)
            except NotFoundError:
                pass
