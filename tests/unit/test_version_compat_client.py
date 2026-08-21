"""Unit tests for the client-side wiring of multi-version support.

``tests/unit/test_compat.py`` covers the pure functions. This file covers the wiring:
that the endpoints actually call them, that ``server_version()`` costs one request and
caches it, and that the two version-gated methods refuse (or do not refuse) exactly when
they should.

Everything here runs against a mocked transport, so it asserts what the client *sends*
and what it *does with what it gets back* -- neither of which a live run can isolate.
That the mocked bodies match what the real servers return is established live, in
``tests/integration/test_version_compat_integration.py`` and the evidence file.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from kibana._async.client import AsyncKibana
from kibana._sync.client import Kibana
from kibana.exceptions import ApiError, KibanaVersionError

# The two servers' real answers to GET /api/dashboards, and to the significant-events
# read. Taken from the live probes recorded in docs/evidence/multi-version-9.4.5-9.5.2.md.
DASHBOARDS_94 = {"dashboards": [{"id": "d1"}], "page": 1, "total": 1}
DASHBOARDS_95 = {"data": [{"id": "d1"}], "meta": {"total": 1, "page": 1, "per_page": 20}}
SIG_EVENTS_94 = {"significant_events": [{"id": "q1"}], "aggregated_occurrences": []}
SIG_EVENTS_95 = {"queries": [{"id": "q1"}], "aggregated_occurrences": []}

STATUS_94 = {"version": {"number": "9.4.5"}, "status": {"overall": {"level": "available"}}}
STATUS_95 = {"version": {"number": "9.5.2"}, "status": {"overall": {"level": "available"}}}


def _response(body, status=200):
    return ObjectApiResponse(body=body, meta=Mock(status=status, headers={}))


def _target(call):
    """The request path of a recorded transport call."""
    return call[1]["target"].split("?")[0]


@pytest.fixture
def client(mock_transport):
    return Kibana(_transport=mock_transport)


@pytest.fixture
def async_client(mock_async_transport):
    return AsyncKibana(_transport=mock_async_transport)


def _on_version(mock_transport, status_body, *bodies):
    """Answer /api/status with *status_body*, then each later call from *bodies*."""
    remaining = list(bodies)

    def respond(*_args, **kwargs):
        if kwargs.get("target", "").startswith("/api/status"):
            return _response(status_body)
        return _response(remaining.pop(0) if remaining else {})

    mock_transport.perform_request.side_effect = respond


class TestServerVersion:
    """Resolved lazily, once, and shared with clones."""

    def test_not_requested_until_asked(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(DASHBOARDS_94)
        client.dashboards.get_all()
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/status" not in targets

    def test_reads_the_version_number(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(STATUS_95)
        assert client.server_version() == "9.5.2"

    def test_resolved_once(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(STATUS_95)
        client.server_version()
        client.server_version()
        client.server_version()
        status_calls = [
            call
            for call in mock_transport.perform_request.call_args_list
            if _target(call) == "/api/status"
        ]
        assert len(status_calls) == 1

    def test_a_server_without_a_version_resolves_to_none_and_stops_asking(
        self, client, mock_transport
    ):
        mock_transport.perform_request.return_value = _response({"status": {}})
        assert client.server_version() is None
        assert client.server_version() is None
        assert mock_transport.perform_request.call_count == 1

    def test_a_non_string_version_is_rejected_rather_than_returned(
        self, client, mock_transport
    ):
        mock_transport.perform_request.return_value = _response({"version": {"number": 95}})
        assert client.server_version() is None

    def test_options_clone_shares_the_resolved_value(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(STATUS_95)
        assert client.server_version() == "9.5.2"
        clone = client.options(request_timeout=5.0)
        assert clone.server_version() == "9.5.2"
        assert mock_transport.perform_request.call_count == 1

    def test_a_failed_lookup_is_not_cached(self, client, mock_transport):
        """A transient /api/status failure must not poison the client for its lifetime."""
        mock_transport.perform_request.side_effect = [
            _response({"message": "nope"}, status=503),
            _response(STATUS_94),
        ]
        with pytest.raises(ApiError):
            client.server_version()
        assert client.server_version() == "9.4.5"

    async def test_async_reads_the_version(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(STATUS_95)
        assert await async_client.server_version() == "9.5.2"


class TestDashboardsSearchNormalization:
    """get_all() adds the missing spelling, whichever server answered."""

    def test_95_body_gains_the_94_spelling(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(DASHBOARDS_95))
        body = client.dashboards.get_all().body
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["per_page"] == 20
        assert body["dashboards"] == [{"id": "d1"}]

    def test_94_body_gains_the_95_spelling(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(DASHBOARDS_94))
        body = client.dashboards.get_all().body
        assert body["data"] == [{"id": "d1"}]
        assert body["meta"]["total"] == 1

    def test_nothing_the_server_sent_is_lost(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(DASHBOARDS_95))
        body = client.dashboards.get_all().body
        assert body["data"] == DASHBOARDS_95["data"]
        assert body["meta"] == DASHBOARDS_95["meta"]

    def test_normalization_does_not_change_the_request(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(DASHBOARDS_95))
        client.dashboards.get_all(query="sales*", per_page=5)
        call = mock_transport.perform_request.call_args
        assert call[1]["method"] == "GET"
        assert _target(call) == "/api/dashboards"

    async def test_async_normalizes_too(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(dict(DASHBOARDS_95))
        body = (await async_client.dashboards.get_all()).body
        assert body["total"] == 1
        assert body["dashboards"] == [{"id": "d1"}]


class TestSignificantEventsNormalization:
    """get_significant_events() likewise."""

    def _call(self, client):
        return client.streams.get_significant_events(
            name="logs.ecs.app",
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
            bucket_size="1h",
        )

    def test_95_body_gains_the_94_spelling(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(SIG_EVENTS_95))
        body = self._call(client).body
        assert body["significant_events"] == [{"id": "q1"}]
        assert body["queries"] == [{"id": "q1"}]

    def test_94_body_gains_the_95_spelling(self, client, mock_transport):
        mock_transport.perform_request.return_value = _response(dict(SIG_EVENTS_94))
        body = self._call(client).body
        assert body["queries"] == [{"id": "q1"}]
        assert body["significant_events"] == [{"id": "q1"}]

    async def test_async_normalizes_too(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(dict(SIG_EVENTS_95))
        body = (
            await async_client.streams.get_significant_events(
                name="logs.ecs.app",
                from_="2026-07-01T00:00:00.000Z",
                to="2026-07-02T00:00:00.000Z",
                bucket_size="1h",
            )
        ).body
        assert body["significant_events"] == [{"id": "q1"}]


class TestStreamUpsertBody:
    """`queries`: required by 9.4, rejected by 9.5, so the body depends on the server.

    Measured live (docs/evidence/multi-version-9.4.5-9.5.2.md): a 9.4.5 upsert without
    ``queries`` is a 400 naming that field, and a 9.5.2 upsert with it is a 400 calling
    it an excess key. This is the only request in the client that varies by version.
    """

    STREAM = {"type": "wired", "ingest": {}}

    def test_defaulted_on_94(self, client, mock_transport):
        _on_version(mock_transport, STATUS_94, {"acknowledged": True})
        client.streams.upsert(name="logs.ecs.app", stream=self.STREAM)
        body = mock_transport.perform_request.call_args[1]["body"]
        assert body["queries"] == []
        assert body["dashboards"] == []
        assert body["rules"] == []

    def test_omitted_on_95(self, client, mock_transport):
        _on_version(mock_transport, STATUS_95, {"acknowledged": True})
        client.streams.upsert(name="logs.ecs.app", stream=self.STREAM)
        body = mock_transport.perform_request.call_args[1]["body"]
        assert "queries" not in body
        # The two fields BOTH lines require are still sent.
        assert body["dashboards"] == []
        assert body["rules"] == []

    def test_defaulted_when_the_version_is_unknown(self, client, mock_transport):
        """Fails open to the pre-existing behaviour, like every other gate."""
        _on_version(mock_transport, {"status": {}}, {"acknowledged": True})
        client.streams.upsert(name="logs.ecs.app", stream=self.STREAM)
        assert mock_transport.perform_request.call_args[1]["body"]["queries"] == []

    def test_sent_when_passed_on_94(self, client, mock_transport):
        _on_version(mock_transport, STATUS_94, {"acknowledged": True})
        queries = [{"id": "q1", "title": "t", "esql": {"query": "FROM x"}}]
        client.streams.upsert(name="logs.ecs.app", stream=self.STREAM, queries=queries)
        assert mock_transport.perform_request.call_args[1]["body"]["queries"] == queries

    def test_passing_queries_on_95_is_refused_not_dropped(self, client, mock_transport):
        """Silently discarding a caller's input would be the worst of the options."""
        _on_version(mock_transport, STATUS_95)
        queries = [{"id": "q1", "title": "t", "esql": {"query": "FROM x"}}]
        with pytest.raises(KibanaVersionError) as excinfo:
            client.streams.upsert(
                name="logs.ecs.app", stream=self.STREAM, queries=queries
            )
        assert excinfo.value.capability == "streams.upsert.queries"
        assert excinfo.value.available_on == ("9.4",)
        # The refusal has to be actionable, or it is just a nicer 400.
        assert "upsert_query()" in str(excinfo.value)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert targets == ["/api/status"]

    def test_an_explicit_empty_list_is_still_sent_on_94(self, client, mock_transport):
        """Passing [] is a caller decision, not an absence -- do not second-guess it."""
        _on_version(mock_transport, STATUS_94, {"acknowledged": True})
        client.streams.upsert(name="logs.ecs.app", stream=self.STREAM, queries=[])
        assert mock_transport.perform_request.call_args[1]["body"]["queries"] == []

    async def test_async_omits_it_on_95(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.side_effect = [
            _response(STATUS_95),
            _response({"acknowledged": True}),
        ]
        await async_client.streams.upsert(name="logs.ecs.app", stream=self.STREAM)
        assert "queries" not in mock_async_transport.perform_request.call_args[1]["body"]

    async def test_async_defaults_it_on_94(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.side_effect = [
            _response(STATUS_94),
            _response({"acknowledged": True}),
        ]
        await async_client.streams.upsert(name="logs.ecs.app", stream=self.STREAM)
        assert mock_async_transport.perform_request.call_args[1]["body"]["queries"] == []


class TestCapabilityGate:
    """Removed endpoints: refused where proven absent, attempted everywhere else."""

    def _generate(self, client):
        return client.streams.generate_significant_events(
            name="logs.ecs.app",
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
        )

    def _preview(self, client):
        return client.streams.preview_significant_events(
            name="logs.ecs.app",
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
            bucket_size="1h",
            esql="FROM logs.ecs.app METADATA _id, _source",
        )

    def test_generate_refused_on_95(self, client, mock_transport):
        _on_version(mock_transport, STATUS_95)
        with pytest.raises(KibanaVersionError) as excinfo:
            self._generate(client)
        assert excinfo.value.capability == "streams.generate_significant_events"
        assert excinfo.value.server_version == "9.5.2"
        assert excinfo.value.available_on == ("9.4",)

    def test_nothing_is_sent_when_refused(self, client, mock_transport):
        _on_version(mock_transport, STATUS_95)
        with pytest.raises(KibanaVersionError):
            self._generate(client)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert targets == ["/api/status"]

    def test_generate_allowed_on_94(self, client, mock_transport):
        _on_version(mock_transport, STATUS_94, {"queries": []})
        self._generate(client)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/streams/logs.ecs.app/significant_events/_generate" in targets

    def test_preview_refused_on_95(self, client, mock_transport):
        _on_version(mock_transport, STATUS_95)
        with pytest.raises(KibanaVersionError) as excinfo:
            self._preview(client)
        assert excinfo.value.capability == "streams.preview_significant_events"

    def test_preview_allowed_on_94(self, client, mock_transport):
        _on_version(mock_transport, STATUS_94, {"occurrences": []})
        self._preview(client)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/streams/logs.ecs.app/significant_events/_preview" in targets

    def test_proceeds_when_the_version_is_unknown(self, client, mock_transport):
        """Fails open: an unreadable /api/status must not block a working call."""
        _on_version(mock_transport, {"status": {}}, {"queries": []})
        self._generate(client)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/streams/logs.ecs.app/significant_events/_generate" in targets

    def test_proceeds_when_status_itself_errors(self, client, mock_transport):
        calls = []

        def respond(*_args, **kwargs):
            calls.append(kwargs.get("target", ""))
            if kwargs.get("target", "").startswith("/api/status"):
                raise RuntimeError("status is unreachable")
            return _response({"queries": []})

        mock_transport.perform_request.side_effect = respond
        self._generate(client)
        assert any("_generate" in target for target in calls)

    def test_proceeds_on_a_server_outside_the_supported_set(self, client, mock_transport):
        """The client has measured nothing about 9.3; it must not invent a refusal."""
        _on_version(
            mock_transport,
            {"version": {"number": "9.3.9"}},
            {"queries": []},
        )
        self._generate(client)
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/streams/logs.ecs.app/significant_events/_generate" in targets

    def test_ungated_streams_methods_never_ask_for_the_version(
        self, client, mock_transport
    ):
        """The version lookup stays off every call path that does not need it."""
        mock_transport.perform_request.return_value = _response({"queries": []})
        client.streams.get_queries(name="logs.ecs.app")
        targets = [_target(call) for call in mock_transport.perform_request.call_args_list]
        assert "/api/status" not in targets

    async def test_async_generate_refused_on_95(self, async_client, mock_async_transport):
        mock_async_transport.perform_request.return_value = _response(STATUS_95)
        with pytest.raises(KibanaVersionError):
            await async_client.streams.generate_significant_events(
                name="logs.ecs.app",
                from_="2026-07-01T00:00:00.000Z",
                to="2026-07-02T00:00:00.000Z",
            )
