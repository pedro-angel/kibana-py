"""Tests for the space-validation cache shared by one client's namespaces.

Covers the two companion bugs found by the 2026-07-31 review:

- **#72** ``spaces.create``/``spaces.delete`` never invalidated the validation
  cache, so a space created after a failed lookup stayed "missing" (and a
  deleted space stayed "present") for the whole TTL window.
- **#73** every namespace client kept its *own* cache -- one space was
  re-validated once per namespace -- and the TTL was measured against the wall
  clock instead of a monotonic one.

The transport is a double, so the assertions count the space-lookup requests
that would have gone on the wire.
"""

import time
from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    AsyncTransport,
    ObjectApiResponse,
    Transport,
)

from kibana import AsyncKibana, Kibana
from kibana.exceptions import SpaceNotFoundError

SPACE_ID = "team-a"
SPACE_PATH = f"/api/spaces/space/{SPACE_ID}"


def _response(body=None, status=200):
    meta = ApiResponseMeta(
        status=status, headers={}, http_version="1.1", duration=0.0, node=None
    )
    return ObjectApiResponse(body={} if body is None else body, meta=meta)


class _SpacesDouble:
    """Minimal Kibana stand-in: tracks which spaces exist and counts lookups."""

    def __init__(self, existing=()):
        self.spaces = set(existing)
        self.calls: list[tuple[str, str]] = []

    @property
    def space_lookups(self) -> int:
        """Number of ``GET /api/spaces/space/team-a`` requests performed."""
        return sum(
            1
            for method, target in self.calls
            if method == "GET" and target == SPACE_PATH
        )

    def handle(self, *, method, target, body=None, **_kwargs):
        self.calls.append((method, target))
        if target == SPACE_PATH:
            if method == "GET":
                if SPACE_ID not in self.spaces:
                    return _response({"message": "Space not found"}, status=404)
                return _response({"id": SPACE_ID, "name": "Team A"})
            if method == "DELETE":
                self.spaces.discard(SPACE_ID)
                return _response(status=204)
        if method == "POST" and target == "/api/spaces/space":
            self.spaces.add(body["id"])
            return _response(body)
        # Any other space-scoped namespace call
        return _response({"dashboards": [], "total": 0})


def _sync_client(double: _SpacesDouble) -> Kibana:
    transport = Mock(spec=Transport)
    transport.perform_request = Mock(side_effect=lambda **kw: double.handle(**kw))
    return Kibana(_transport=transport)


def _async_client(double: _SpacesDouble) -> AsyncKibana:
    transport = Mock(spec=AsyncTransport)
    transport.perform_request = AsyncMock(side_effect=lambda **kw: double.handle(**kw))
    return AsyncKibana(_transport=transport)


class TestSharedSpaceCacheSync:
    """Sync tree: invalidation on space mutation, sharing, monotonic TTL."""

    def test_create_invalidates_the_negative_cache(self):
        """#72: a failed lookup must not outlive the create that fixes it."""
        double = _SpacesDouble()  # space does not exist yet
        client = _sync_client(double)

        with pytest.raises(SpaceNotFoundError):
            client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        client.spaces.create(id=SPACE_ID, name="Team A")

        # No TTL wait: the next call must perform a REAL lookup and succeed.
        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    def test_delete_invalidates_the_positive_cache(self):
        """#72: a successful lookup must not outlive the delete that voids it."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)

        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        client.spaces.delete(id=SPACE_ID)

        with pytest.raises(SpaceNotFoundError):
            client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    def test_cache_is_shared_across_namespace_clients(self):
        """#73: two namespaces of one client validate a space exactly once."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)

        client.dashboards.get_all(space_id=SPACE_ID)
        client.actions.get_all(space_id=SPACE_ID)

        assert double.space_lookups == 1

    def test_ttl_is_measured_with_the_monotonic_clock(self, monkeypatch):
        """#73: TTL follows ``time.monotonic``, not the steppable wall clock."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)
        now = {"monotonic": 1_000.0}
        monkeypatch.setattr(time, "monotonic", lambda: now["monotonic"])
        # Wall clock frozen: a time.time()-based TTL could never expire here.
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)

        client.dashboards.get_all(space_id=SPACE_ID)
        now["monotonic"] += 299.0  # still inside the 300 s default TTL
        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        now["monotonic"] += 2.0  # past the TTL -> re-validate
        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2


class TestSharedSpaceCacheAsync:
    """Async twin of :class:`TestSharedSpaceCacheSync`."""

    async def test_create_invalidates_the_negative_cache(self):
        """#72: a failed lookup must not outlive the create that fixes it."""
        double = _SpacesDouble()  # space does not exist yet
        client = _async_client(double)

        with pytest.raises(SpaceNotFoundError):
            await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        await client.spaces.create(id=SPACE_ID, name="Team A")

        # No TTL wait: the next call must perform a REAL lookup and succeed.
        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    async def test_delete_invalidates_the_positive_cache(self):
        """#72: a successful lookup must not outlive the delete that voids it."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)

        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        await client.spaces.delete(id=SPACE_ID)

        with pytest.raises(SpaceNotFoundError):
            await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    async def test_cache_is_shared_across_namespace_clients(self):
        """#73: two namespaces of one client validate a space exactly once."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)

        await client.dashboards.get_all(space_id=SPACE_ID)
        await client.actions.get_all(space_id=SPACE_ID)

        assert double.space_lookups == 1

    async def test_ttl_is_measured_with_the_monotonic_clock(self, monkeypatch):
        """#73: TTL follows ``time.monotonic``, not the steppable wall clock."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)
        now = {"monotonic": 1_000.0}
        monkeypatch.setattr(time, "monotonic", lambda: now["monotonic"])
        # Wall clock frozen: a time.time()-based TTL could never expire here.
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)

        await client.dashboards.get_all(space_id=SPACE_ID)
        now["monotonic"] += 299.0  # still inside the 300 s default TTL
        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        now["monotonic"] += 2.0  # past the TTL -> re-validate
        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2
