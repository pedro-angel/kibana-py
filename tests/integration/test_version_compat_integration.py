"""Integration tests for multi-version support, against whichever Kibana is running.

This module is the live half of the compatibility layer. Its defining property: **every
test here must pass unchanged on every supported pin**. A test that needs to know which
version it is talking to in order to assert the client's contract would be evidence that
the contract is not actually one contract.

Two tests do read the server version, and only these two -- the ones covering endpoints
Kibana removed between lines (`CAPABILITIES` in ``kibana._compat``). There the *client's*
behavior is legitimately version-dependent, so the assertion is too: the endpoint answers
on the line that routes it, and raises a typed, explanatory error on the line that does
not. Neither is skipped: a skipped path names no failure and proves nothing.

Pure-function coverage of the same layer lives in ``tests/unit/test_compat.py``. The
measurements these assertions encode are in
``docs/evidence/multi-version-9.4.5-9.5.2.md``.
"""

import uuid

import pytest

from kibana._compat import (
    capability_available,
    is_supported,
    minor_line,
    parse_version,
    supported_lines,
)
from kibana.exceptions import BadRequestError, KibanaVersionError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

PREFIX = "kbnpy-vercompat"
ROOT_STREAM = "logs.ecs"

# The Streams preview sub-features are gated behind observability advanced settings that
# default to off (see test_streams_integration.py, which owns the enable/restore
# contract). These tests enable the one they need and put it back.
_SIG_EVENTS_SETTING = "observability:streamsEnableSignificantEvents"
_SETTINGS_PATH = "/internal/kibana/settings"
_SETTINGS_HEADERS = {
    "accept": "application/json",
    "x-elastic-internal-origin": "kibana-py",
}


@pytest.fixture
def kibana_client():
    """A sync client against the live stack."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def unique_suffix():
    """Unique suffix so parallel runs never collide."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def server_line(kibana_client):
    """The supported minor line the live server is on, or skip if it is off the set.

    Skipping here is honest rather than evasive: these tests assert the *supported*
    contract, and the client makes no claim about a server outside the supported set.
    The skip reason names the version so an unexpected stack is visible in the report.
    """
    version = kibana_client.server_version()
    line = minor_line(version)
    if line not in supported_lines():
        pytest.skip(f"live Kibana is {version}, which is outside the supported set")
    return line


@pytest.fixture
def significant_events_stream(kibana_client):
    """A child stream with significant events enabled; restores the prior setting."""
    prior = (
        kibana_client.perform_request("GET", _SETTINGS_PATH, headers=_SETTINGS_HEADERS)
        .body.get("settings", {})
        .get(_SIG_EVENTS_SETTING, {})
        .get("userValue")
    )
    kibana_client.streams.enable()
    kibana_client.perform_request(
        "POST",
        _SETTINGS_PATH,
        headers=_SETTINGS_HEADERS,
        body={"changes": {_SIG_EVENTS_SETTING: True}},
    )
    name = f"{ROOT_STREAM}.kbnpyvercompat{uuid.uuid4().hex[:6]}"
    kibana_client.streams.fork(
        name=ROOT_STREAM,
        stream_name=name,
        where={"field": "service.name", "eq": "kbnpy-vercompat"},
    )
    try:
        yield name
    finally:
        try:
            kibana_client.streams.delete(name=name)
        except NotFoundError:
            pass
        kibana_client.perform_request(
            "POST",
            _SETTINGS_PATH,
            headers=_SETTINGS_HEADERS,
            body={"changes": {_SIG_EVENTS_SETTING: prior}},
        )


def _sig_events_esql(name: str) -> str:
    """The strict ES|QL shape Kibana requires for stream queries."""
    return f"FROM {name}, {name}.* METADATA _id, _source"


class TestServerVersion:
    """The client can say what it is connected to, and it costs nothing until asked."""

    def test_reports_a_parseable_version(self, kibana_client):
        version = kibana_client.server_version()
        assert parse_version(version) is not None, f"unparseable version: {version!r}"

    def test_the_live_stack_is_a_supported_version(self, kibana_client):
        """The stack CI and the cloud environment provision must be in the set.

        If this fails, either the stack template drifted from ``SUPPORTED_VERSIONS``
        (which ``make versions`` would also catch) or someone pointed the suite at an
        unsupported server.
        """
        version = kibana_client.server_version()
        assert is_supported(version), (
            f"live Kibana {version} is not in the supported set; "
            "run `make versions` and check ES_LOCAL_VERSION"
        )

    def test_resolved_once_and_cached(self, kibana_client):
        first = kibana_client.server_version()
        assert kibana_client.server_version() == first
        assert kibana_client._server_version_cache.resolved is True

    def test_clones_share_the_resolved_version(self, kibana_client):
        version = kibana_client.server_version()
        clone = kibana_client.options(request_timeout=30.0)
        # Already resolved, so this returns the cached value without a second request.
        assert clone._server_version_cache.resolved is True
        assert clone.server_version() == version

    async def test_async_reports_the_same_version(self, kibana_client):
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            assert await client.server_version() == kibana_client.server_version()
        finally:
            await client.close()


class TestDashboardsSearchEnvelope:
    """``GET /api/dashboards`` reads the same on both lines, whichever spelling you use."""

    @pytest.fixture
    def one_dashboard(self, kibana_client, unique_suffix):
        title = f"{PREFIX}-{unique_suffix}"
        created = kibana_client.dashboards.create(title=title, panels=[])
        dashboard_id = created.body["id"]
        try:
            yield title, dashboard_id
        finally:
            try:
                kibana_client.dashboards.delete(id=dashboard_id)
            except NotFoundError:
                pass

    def test_both_spellings_are_present_and_agree(self, kibana_client, one_dashboard):
        title, dashboard_id = one_dashboard

        results = kibana_client.dashboards.get_all(query=f"{title}*")

        # The 9.4 spelling.
        assert results.body["total"] == 1
        assert results.body["page"] == 1
        assert [item["id"] for item in results.body["dashboards"]] == [dashboard_id]

        # The 9.5 spelling, on the same response.
        assert results.body["meta"]["total"] == 1
        assert results.body["meta"]["page"] == 1
        assert [item["id"] for item in results.body["data"]] == [dashboard_id]

        # Aliased, not copied.
        assert results.body["dashboards"] is results.body["data"]

    def test_empty_result_normalizes_too(self, kibana_client, unique_suffix):
        results = kibana_client.dashboards.get_all(
            query=f"{PREFIX}-absent-{unique_suffix}*"
        )
        assert results.body["total"] == 0
        assert results.body["dashboards"] == []
        assert results.body["meta"]["total"] == 0
        assert results.body["data"] == []

    def test_pagination_counters_agree(self, kibana_client, one_dashboard):
        title, _dashboard_id = one_dashboard
        results = kibana_client.dashboards.get_all(
            query=f"{title}*", per_page=1, page=1
        )
        assert results.body["page"] == results.body["meta"]["page"] == 1
        assert results.body["total"] == results.body["meta"]["total"]

    async def test_async_gets_the_same_envelope(self, kibana_client, one_dashboard):
        title, dashboard_id = one_dashboard
        client = create_test_async_kibana_client(auth_method="auto")
        try:
            results = await client.dashboards.get_all(query=f"{title}*")
            assert results.body["total"] == 1
            assert results.body["meta"]["total"] == 1
            assert [item["id"] for item in results.body["dashboards"]] == [dashboard_id]
            assert [item["id"] for item in results.body["data"]] == [dashboard_id]
        finally:
            await client.close()


class TestStreamUpsertBody:
    """A stream upsert carries only what the caller passed, so both lines accept it."""

    def test_upsert_without_queries_succeeds(
        self, kibana_client, significant_events_stream
    ):
        """9.5 rejects ``queries`` as an excess key; 9.4 never required it be sent."""
        result = kibana_client.streams.upsert(
            name=significant_events_stream,
            stream={
                "type": "wired",
                "description": "kbnpy version-compat upsert",
                "ingest": {
                    "lifecycle": {"inherit": {}},
                    "processing": {"steps": []},
                    "settings": {},
                    "failure_store": {"inherit": {}},
                    "wired": {"fields": {}, "routing": []},
                },
            },
            dashboards=[],
            rules=[],
        )
        assert result.body["acknowledged"] is True

    def test_the_description_actually_landed(
        self, kibana_client, significant_events_stream
    ):
        """A 200 is not proof of a write: read it back."""
        kibana_client.streams.upsert(
            name=significant_events_stream,
            stream={
                "type": "wired",
                "description": "kbnpy readback",
                "ingest": {
                    "lifecycle": {"inherit": {}},
                    "processing": {"steps": []},
                    "settings": {},
                    "failure_store": {"inherit": {}},
                    "wired": {"fields": {}, "routing": []},
                },
            },
            dashboards=[],
            rules=[],
        )
        fetched = kibana_client.streams.get(name=significant_events_stream)
        assert fetched.body["stream"]["description"] == "kbnpy readback"


class TestSignificantEventsEnvelope:
    """The significant-events read reads the same on both lines."""

    def test_both_spellings_are_present_and_agree(
        self, kibana_client, significant_events_stream
    ):
        kibana_client.streams.upsert_query(
            name=significant_events_stream,
            query_id="kbnpy-vercompat-sig",
            title="kbnpy version compat",
            esql=_sig_events_esql(significant_events_stream),
            description="kbnpy version compat",
        )

        events = kibana_client.streams.get_significant_events(
            name=significant_events_stream,
            from_="2026-07-01T00:00:00.000Z",
            to="2026-07-02T00:00:00.000Z",
            bucket_size="1h",
        )

        assert "aggregated_occurrences" in events.body
        # Both names, same list.
        assert "significant_events" in events.body
        assert "queries" in events.body
        assert events.body["significant_events"] is events.body["queries"]
        ids = [entry["id"] for entry in events.body["significant_events"]]
        assert "kbnpy-vercompat-sig" in ids


class TestRemovedCapabilities:
    """Endpoints Kibana removed between lines: answered where routed, explained where not.

    These are the only version-aware assertions in this module, because the client's
    behavior here is legitimately version-dependent. Both branches drive the real route
    against the live server -- the 9.4 branch asserts the server's own semantic rejection
    rather than a bare status code, so a routing or payload bug still fails the test.
    """

    def test_generate_significant_events(
        self, kibana_client, significant_events_stream, server_line
    ):
        capability = "streams.generate_significant_events"
        available = capability_available(capability, kibana_client.server_version())

        if available:
            # Routed here: the stack has no AI connector, so the server must reject the
            # request on that ground specifically.
            with pytest.raises(BadRequestError, match="connector"):
                kibana_client.streams.generate_significant_events(
                    name=significant_events_stream,
                    from_="2026-07-01T00:00:00.000Z",
                    to="2026-07-02T00:00:00.000Z",
                )
        else:
            with pytest.raises(KibanaVersionError) as excinfo:
                kibana_client.streams.generate_significant_events(
                    name=significant_events_stream,
                    from_="2026-07-01T00:00:00.000Z",
                    to="2026-07-02T00:00:00.000Z",
                )
            assert excinfo.value.capability == capability
            assert excinfo.value.server_version == kibana_client.server_version()
            assert server_line not in excinfo.value.available_on

    def test_preview_significant_events(
        self, kibana_client, significant_events_stream, server_line
    ):
        capability = "streams.preview_significant_events"
        available = capability_available(capability, kibana_client.server_version())
        esql = _sig_events_esql(significant_events_stream)

        if available:
            preview = kibana_client.streams.preview_significant_events(
                name=significant_events_stream,
                from_="2026-07-01T00:00:00.000Z",
                to="2026-07-02T00:00:00.000Z",
                bucket_size="1h",
                esql=esql,
            )
            assert "occurrences" in preview.body
        else:
            with pytest.raises(KibanaVersionError) as excinfo:
                kibana_client.streams.preview_significant_events(
                    name=significant_events_stream,
                    from_="2026-07-01T00:00:00.000Z",
                    to="2026-07-02T00:00:00.000Z",
                    bucket_size="1h",
                    esql=esql,
                )
            assert excinfo.value.capability == capability
            assert server_line not in excinfo.value.available_on

    def test_the_error_names_where_the_capability_does_exist(
        self, kibana_client, significant_events_stream, server_line
    ):
        """A refusal that does not say where to go is barely better than a 404."""
        if capability_available(
            "streams.generate_significant_events", kibana_client.server_version()
        ):
            pytest.skip(f"the endpoint is routed on {server_line}; nothing to refuse")
        with pytest.raises(KibanaVersionError) as excinfo:
            kibana_client.streams.generate_significant_events(
                name=significant_events_stream,
                from_="2026-07-01T00:00:00.000Z",
                to="2026-07-02T00:00:00.000Z",
            )
        message = str(excinfo.value)
        assert excinfo.value.available_on
        for line in excinfo.value.available_on:
            assert line in message
