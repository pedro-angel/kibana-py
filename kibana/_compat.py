"""Kibana server-version compatibility.

This module is the **single source of truth for the supported Kibana set**, and it
carries the pure functions that make one client contract hold across that set.

Two kinds of thing live here, and they are deliberately in the same file:

- **The declared set** (:data:`SUPPORTED_VERSIONS`, :data:`SUPPORT_DECISIONS`,
  :data:`CAPABILITIES`). Every other statement of the supported versions in this
  repository -- the CI matrixes, the release gate, the stack template, the README
  table, the cloud-environment page -- is a *mirror*, checked against this file by
  ``scripts/checks/supported-versions.py`` (``make versions``). Editing a mirror
  alone fails that gate.
- **The adapters** (:func:`normalize_dashboards_search`,
  :func:`normalize_significant_events`, :func:`capability_available`). They are pure and
  do no I/O, so both the sync and async trees call the same code and the whole
  compatibility layer is unit-testable without a server.

Why the declared set ships inside the package rather than sitting in a data file:
:func:`is_supported` is a runtime question a caller can ask about the server they
just connected to, so the answer has to travel with the installed wheel. The gate
reads this file with :mod:`ast` instead of importing it, so generating a CI matrix
never requires the package to be installed first.

**The normalizers only ever add.** They never remove, rename, or overwrite a key the
server actually sent -- where a key they would add is already present, the server's
value wins. A caller who wants exactly what the server returned still has it.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# The declared supported set
# ---------------------------------------------------------------------------

#: Supported Kibana minor lines, newest first, each with the exact patch this
#: repository provisions and tests against ("the pin").
#:
#: The policy is the two most recent minor lines at the latest patch of each. It is
#: stated in README "Version support" and in
#: ``docs/source/development/version-support.md``; the procedure for moving it
#: forward -- including the decision that must be recorded about the oldest line --
#: is on that page.
SUPPORTED_VERSIONS: tuple[tuple[str, str], ...] = (
    ("9.5", "9.5.2"),
    ("9.4", "9.4.5"),
)

#: Why each supported line is in the set, dated. A line may not enter
#: :data:`SUPPORTED_VERSIONS` without a row here, and dropping a line means moving
#: its row into the page's history table rather than deleting the record.
#:
#: Rows are ``(line, verdict, date, reason)``. ``verdict`` is ``"added"`` when the
#: line joined and ``"kept"`` when it survived a review it could have failed --
#: reviewing the oldest line is mandatory whenever a new one is added, so a "kept"
#: row is the evidence that the review actually happened.
SUPPORT_DECISIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "9.5",
        "added",
        "2026-08-21",
        "Newest released Kibana line. Joined at 9.5.2 once the client's two "
        "divergences from it (the dashboards search envelope and the "
        "significant-events rename) were absorbed and both lines ran green live.",
    ),
    (
        "9.4",
        "kept",
        "2026-08-21",
        "Reviewed when 9.5 joined and kept. It is the older of exactly two lines, "
        "so dropping it would leave the client single-version; and the cost of "
        "keeping it is now bounded -- the compatibility layer is version-free "
        "normalization plus two gated endpoints, not a forked code path.",
    ),
)

#: Endpoints that exist on some supported lines and not others.
#:
#: Keyed by ``"<namespace>.<method>"``; the value is the tuple of supported lines
#: where the endpoint is actually routed, measured live rather than read from
#: release notes (see ``docs/evidence/multi-version-9.4.5-9.5.2.md``).
#:
#: Kibana 9.5 moved significant-events *generation* and *preview* off the public
#: API. The replacement lives under ``/internal/significant_events/*``, which is
#: unversioned and outside this client's public-API remit, so the two methods are
#: gated rather than re-pointed.
#: A request *field* is named the same way as a method when one line requires it and
#: another rejects it -- ``streams.upsert.queries`` is such a case, and the reason the
#: three-mechanism taxonomy in the design doc puts it under version gating rather than
#: request shaping: measured live, 9.4.5 **requires** ``queries`` in a stream upsert body
#: and 9.5.2 **rejects** it as an excess key, so no single body satisfies both.
CAPABILITIES: dict[str, tuple[str, ...]] = {
    "streams.generate_significant_events": ("9.4",),
    "streams.preview_significant_events": ("9.4",),
    "streams.upsert.queries": ("9.4",),
}

_VERSION_RE = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)")


class ServerVersionCache:
    """One resolved-once holder for the connected server's version string.

    Mirrors :class:`kibana._space_cache.SpaceValidationCache` in lifetime: a
    client and every clone ``options()`` makes of it talk to the same server, so
    they share one holder. ``resolved`` is separate from ``value`` so that a
    server which legitimately reports no version is cached as "looked up, and
    the answer was nothing" rather than being re-queried on every call.

    No TTL, unlike the space cache: a Kibana process does not change version
    under a live connection. A rolling upgrade behind a load balancer can serve
    two versions, and this cache will hold whichever answered first -- which is
    also the only honest thing a single string can say about that situation.
    """

    __slots__ = ("resolved", "value")

    def __init__(self) -> None:
        self.resolved: bool = False
        self.value: str | None = None


# ---------------------------------------------------------------------------
# Version arithmetic
# ---------------------------------------------------------------------------


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    """Parse a Kibana version string into a comparable tuple.

    Tolerant on purpose: Kibana reports versions like ``"9.5.2"`` but a
    snapshot or build-qualified string (``"9.5.2-SNAPSHOT"``) must still compare
    as ``(9, 5, 2)`` rather than blowing up a caller's request.

    Args:
        value: A version string, or ``None``.

    Returns:
        ``(major, minor, patch)``, or ``None`` when *value* is missing or does not
        begin with a dotted numeric triple.

    Example:
        >>> parse_version("9.5.2")
        (9, 5, 2)
        >>> parse_version("9.5.2-SNAPSHOT")
        (9, 5, 2)
        >>> parse_version("not a version") is None
        True
    """
    if not value or not isinstance(value, str):
        return None
    match = _VERSION_RE.match(value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def minor_line(value: str | None) -> str | None:
    """Return the minor line of a version string, e.g. ``"9.5.2"`` -> ``"9.5"``.

    Args:
        value: A version string, or ``None``.

    Returns:
        The ``"<major>.<minor>"`` line, or ``None`` when *value* is unparseable.
    """
    parsed = parse_version(value)
    if parsed is None:
        return None
    return f"{parsed[0]}.{parsed[1]}"


def supported_lines() -> tuple[str, ...]:
    """The supported minor lines, newest first."""
    return tuple(line for line, _pin in SUPPORTED_VERSIONS)


def supported_pins() -> tuple[str, ...]:
    """The tested patch of each supported line, newest first."""
    return tuple(pin for _line, pin in SUPPORTED_VERSIONS)


def is_supported(value: str | None) -> bool:
    """Whether a server version falls on a supported line.

    Membership is by *line*, not by pin: other patches of a supported line are
    expected to work and are simply not the patch this repository tests. A version
    that cannot be parsed is not supported -- the honest answer to "is this in the
    set" when the version is unreadable is "no", not "assume so".

    Args:
        value: A version string as reported by ``GET /api/status``.

    Example:
        >>> is_supported("9.5.0")   # a supported line, an untested patch
        True
        >>> is_supported("9.3.9")
        False
    """
    return minor_line(value) in supported_lines()


# ---------------------------------------------------------------------------
# Capability gating
# ---------------------------------------------------------------------------


def capability_lines(capability: str) -> tuple[str, ...]:
    """The supported lines on which *capability* is routed.

    An unknown capability is treated as present everywhere: this table exists to
    record measured absences, and a name missing from it means nothing was measured
    to be absent.
    """
    return CAPABILITIES.get(capability, supported_lines())


def capability_available(capability: str, server_version: str | None) -> bool:
    """Whether *capability* exists on the server at *server_version*.

    Returns ``True`` when the version is unknown or off the supported set. Both are
    deliberate: the client must not refuse a call it cannot prove will fail, and the
    server is the authority on its own routes. The caller then gets whatever the
    server says, which is the pre-existing behavior.
    """
    line = minor_line(server_version)
    if line is None or line not in supported_lines():
        return True
    return line in capability_lines(capability)


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------


def normalize_dashboards_search(body: Any) -> Any:
    """Give a dashboards search response both spellings of its envelope.

    Kibana 9.4 answers ``GET /api/dashboards`` with ``{"dashboards": [...],
    "page": N, "total": N}``. Kibana 9.5 answers the same request with
    ``{"data": [...], "meta": {"total": N, "page": N, "per_page": N}}`` -- the list
    was renamed and the counters moved into a nested object.

    This adds whichever spelling is missing, so a caller reading ``body["total"]``
    and a caller reading ``body["meta"]["total"]`` both work on both lines. Nothing
    the server sent is removed or overwritten.

    The list is *aliased*, not copied: ``body["data"] is body["dashboards"]``. They
    are the same collection, and copying a search page to keep two spellings in sync
    would be both wasteful and a lie about their relationship.

    Args:
        body: The parsed response body. Anything that is not a ``dict`` is returned
            untouched -- normalization never turns an unexpected payload into an
            exception on a call that would otherwise have succeeded.

    Returns:
        The same object, mutated in place.
    """
    if not isinstance(body, dict):
        return body

    # 9.5 -> 9.4 spelling.
    if "data" in body and "dashboards" not in body:
        body["dashboards"] = body["data"]
    meta = body.get("meta")
    if isinstance(meta, dict):
        for key in ("total", "page", "per_page"):
            if key in meta and key not in body:
                body[key] = meta[key]

    # 9.4 -> 9.5 spelling.
    if "dashboards" in body and "data" not in body:
        body["data"] = body["dashboards"]
    if "meta" not in body:
        derived = {key: body[key] for key in ("total", "page", "per_page") if key in body}
        if derived:
            body["meta"] = derived

    return body


def normalize_significant_events(body: Any) -> Any:
    """Give a significant-events response both spellings of its query list.

    Kibana 9.4 returns ``{"significant_events": [...], "aggregated_occurrences":
    [...]}``. Kibana 9.5 renamed the first key to ``"queries"`` and left the second
    alone. This adds whichever name is missing, aliasing the same list.

    Args:
        body: The parsed response body; non-``dict`` payloads pass through.

    Returns:
        The same object, mutated in place.
    """
    if not isinstance(body, dict):
        return body

    if "queries" in body and "significant_events" not in body:
        body["significant_events"] = body["queries"]
    elif "significant_events" in body and "queries" not in body:
        body["queries"] = body["significant_events"]

    return body
