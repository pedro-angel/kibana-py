"""Unit tests for the Kibana version-compatibility layer (``kibana._compat``).

These cover the pure half of multi-version support: version arithmetic, the
capability table, and the two response normalizers. The normalizers are the
interesting part, and the property under test throughout is **additive-only** --
they may add a key, never remove, rename, or overwrite one the server sent.

The live half (that these shapes are the shapes the servers really return) is
proven in ``tests/integration/test_version_compat_integration.py`` and captured in
``docs/evidence/multi-version-9.4.5-9.5.2.md``. Neither substitutes for the other:
these tests pin the contract, the live run proves it matches reality.
"""

from __future__ import annotations

import pytest

from kibana._compat import (
    CAPABILITIES,
    SUPPORT_DECISIONS,
    SUPPORTED_VERSIONS,
    ServerVersionCache,
    capability_available,
    capability_lines,
    is_supported,
    minor_line,
    normalize_dashboards_search,
    normalize_significant_events,
    parse_version,
    supported_lines,
    supported_pins,
)

# Bodies as the live servers actually returned them -- copied from the probe output
# recorded in docs/evidence/multi-version-9.4.5-9.5.2.md, not invented.
BODY_94_DASHBOARDS = {
    "dashboards": [{"id": "abc", "data": {"title": "t"}, "meta": {}}],
    "page": 1,
    "total": 3,
}
BODY_95_DASHBOARDS = {
    "data": [{"id": "abc", "data": {"title": "t"}, "meta": {}}],
    "meta": {"total": 3, "page": 1, "per_page": 2},
}
BODY_94_SIG_EVENTS = {
    "significant_events": [{"id": "q1", "occurrences": []}],
    "aggregated_occurrences": [],
}
BODY_95_SIG_EVENTS = {
    "queries": [{"id": "q1", "occurrences": [], "rule_backed": True}],
    "aggregated_occurrences": [],
}


class TestParseVersion:
    """Version strings in, comparable tuples out."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("9.5.2", (9, 5, 2)),
            ("9.4.5", (9, 4, 5)),
            ("10.0.0", (10, 0, 0)),
            # Kibana appends build qualifiers on snapshots; they must not break a call.
            ("9.5.2-SNAPSHOT", (9, 5, 2)),
            ("  9.5.2  ", (9, 5, 2)),
        ],
    )
    def test_parses(self, value, expected):
        assert parse_version(value) == expected

    @pytest.mark.parametrize("value", [None, "", "nine", "9.5", "v9.5.2", 952, object()])
    def test_unparseable_is_none(self, value):
        assert parse_version(value) is None

    def test_minor_line(self):
        assert minor_line("9.5.2") == "9.5"
        assert minor_line("9.4.5") == "9.4"
        assert minor_line("garbage") is None


class TestSupportedSet:
    """The declared set is well-formed and self-consistent."""

    def test_pins_belong_to_their_lines(self):
        for line, pin in SUPPORTED_VERSIONS:
            assert minor_line(pin) == line, f"{pin} is not on line {line}"

    def test_newest_first(self):
        parsed = [parse_version(pin) for pin in supported_pins()]
        assert parsed == sorted(parsed, reverse=True)

    def test_every_supported_line_has_a_dated_decision(self):
        decided = {row[0] for row in SUPPORT_DECISIONS}
        assert decided == set(supported_lines())

    def test_oldest_line_was_re_decided_not_merely_added(self):
        """A "kept" verdict is the evidence that the review actually happened."""
        if len(SUPPORTED_VERSIONS) < 2:
            pytest.skip("only one supported line: nothing older to re-decide")
        oldest = SUPPORTED_VERSIONS[-1][0]
        verdict = next(row[1] for row in SUPPORT_DECISIONS if row[0] == oldest)
        assert verdict == "kept"

    @pytest.mark.parametrize("value", ["9.5.2", "9.4.5", "9.5.0", "9.4.0"])
    def test_supported(self, value):
        assert is_supported(value)

    @pytest.mark.parametrize("value", ["9.3.9", "8.19.0", "10.0.0", None, "junk"])
    def test_unsupported(self, value):
        assert not is_supported(value)

    def test_untested_patch_of_a_supported_line_is_supported(self):
        """Membership is by line, not by pin -- the README says so."""
        assert is_supported("9.5.99")


class TestCapabilities:
    """Gating is measured absence, and it fails open."""

    def test_known_absence_is_reported(self):
        assert not capability_available(
            "streams.generate_significant_events", "9.5.2"
        )
        assert capability_available("streams.generate_significant_events", "9.4.5")

    def test_unknown_capability_is_assumed_present(self):
        assert capability_available("streams.does_not_exist", "9.5.2")
        assert capability_lines("streams.does_not_exist") == supported_lines()

    @pytest.mark.parametrize("value", [None, "", "junk", "8.19.0", "10.1.0"])
    def test_fails_open_when_the_version_proves_nothing(self, value):
        """Unknown or off-set versions must not be refused: the server decides."""
        assert capability_available("streams.generate_significant_events", value)

    def test_every_gated_capability_names_real_lines(self):
        for capability, lines in CAPABILITIES.items():
            assert lines, f"{capability} is gated to no line at all"
            for line in lines:
                assert line in supported_lines(), f"{capability} names unsupported {line}"


class TestNormalizeDashboardsSearch:
    """One search contract across both lines, by adding only."""

    def test_95_gains_the_94_spelling(self):
        body = normalize_dashboards_search(dict(BODY_95_DASHBOARDS))
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["per_page"] == 2
        assert body["dashboards"] == BODY_95_DASHBOARDS["data"]

    def test_94_gains_the_95_spelling(self):
        body = normalize_dashboards_search(dict(BODY_94_DASHBOARDS))
        assert body["data"] == BODY_94_DASHBOARDS["dashboards"]
        assert body["meta"] == {"total": 3, "page": 1}

    def test_95_keeps_everything_the_server_sent(self):
        body = normalize_dashboards_search(dict(BODY_95_DASHBOARDS))
        assert body["data"] == BODY_95_DASHBOARDS["data"]
        assert body["meta"] == BODY_95_DASHBOARDS["meta"]

    def test_94_keeps_everything_the_server_sent(self):
        body = normalize_dashboards_search(dict(BODY_94_DASHBOARDS))
        for key, value in BODY_94_DASHBOARDS.items():
            assert body[key] == value

    def test_the_two_spellings_are_the_same_list(self):
        body = normalize_dashboards_search(dict(BODY_95_DASHBOARDS))
        assert body["dashboards"] is body["data"]

    def test_server_value_wins_over_a_derived_one(self):
        """R2: a key the server sent is never overwritten, even by a better guess."""
        body = normalize_dashboards_search(
            {"data": [], "total": 99, "meta": {"total": 3, "page": 1}}
        )
        assert body["total"] == 99

    def test_idempotent(self):
        once = normalize_dashboards_search(dict(BODY_95_DASHBOARDS))
        twice = normalize_dashboards_search(dict(once))
        assert once == twice

    def test_empty_page_normalizes(self):
        body = normalize_dashboards_search({"data": [], "meta": {"total": 0, "page": 1, "per_page": 2}})
        assert body["dashboards"] == []
        assert body["total"] == 0

    def test_no_meta_is_not_invented_from_nothing(self):
        body = normalize_dashboards_search({"data": []})
        assert body["dashboards"] == []
        assert "meta" not in body

    @pytest.mark.parametrize("body", [None, [], "text", 7])
    def test_non_dict_passes_through(self, body):
        """An unexpected payload must not become an exception on a working call."""
        assert normalize_dashboards_search(body) is body

    def test_unrelated_body_is_untouched(self):
        body = {"unrelated": True}
        assert normalize_dashboards_search(dict(body)) == body


class TestNormalizeSignificantEvents:
    """Same rule for the significant-events rename."""

    def test_95_gains_the_94_spelling(self):
        body = normalize_significant_events(dict(BODY_95_SIG_EVENTS))
        assert body["significant_events"] == BODY_95_SIG_EVENTS["queries"]
        assert body["queries"] == BODY_95_SIG_EVENTS["queries"]

    def test_94_gains_the_95_spelling(self):
        body = normalize_significant_events(dict(BODY_94_SIG_EVENTS))
        assert body["queries"] == BODY_94_SIG_EVENTS["significant_events"]
        assert body["significant_events"] == BODY_94_SIG_EVENTS["significant_events"]

    def test_aggregated_occurrences_survives_both_ways(self):
        for source in (BODY_94_SIG_EVENTS, BODY_95_SIG_EVENTS):
            body = normalize_significant_events(dict(source))
            assert body["aggregated_occurrences"] == []

    def test_the_two_spellings_are_the_same_list(self):
        body = normalize_significant_events(dict(BODY_95_SIG_EVENTS))
        assert body["queries"] is body["significant_events"]

    def test_both_present_is_left_alone(self):
        body = normalize_significant_events(
            {"queries": [1], "significant_events": [2], "aggregated_occurrences": []}
        )
        assert body["queries"] == [1]
        assert body["significant_events"] == [2]

    def test_idempotent(self):
        once = normalize_significant_events(dict(BODY_95_SIG_EVENTS))
        twice = normalize_significant_events(dict(once))
        assert once == twice

    @pytest.mark.parametrize("body", [None, [], "text", 7])
    def test_non_dict_passes_through(self, body):
        assert normalize_significant_events(body) is body


class TestServerVersionCache:
    """The holder distinguishes 'not looked up' from 'looked up, answer was nothing'."""

    def test_starts_unresolved(self):
        cache = ServerVersionCache()
        assert cache.resolved is False
        assert cache.value is None

    def test_a_none_answer_is_still_an_answer(self):
        cache = ServerVersionCache()
        cache.resolved = True
        assert cache.value is None and cache.resolved is True

    def test_has_no_dict(self):
        """__slots__: one of these exists per client, so it stays small."""
        with pytest.raises(AttributeError):
            ServerVersionCache().unexpected = 1
