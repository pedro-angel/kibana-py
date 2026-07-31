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

import asyncio
import threading
import time
from unittest.mock import AsyncMock, Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    AsyncTransport,
    ObjectApiResponse,
    Transport,
)

import kibana._space_cache as space_cache
from kibana import AsyncKibana, Kibana
from kibana._space_cache import SpaceValidationCache
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


def _async_client(double: _SpacesDouble, lookup_latency: float = 0.0) -> AsyncKibana:
    """An async client whose space lookups may answer *late*.

    ``lookup_latency`` delays the space-lookup *reply*, not the server's
    decision: the double answers from the state it saw when the request
    arrived, then the reply lands after the delay. That is what lets a test
    interleave a `spaces.delete` with a validation already in flight.
    """

    async def perform(**kwargs):
        response = double.handle(**kwargs)
        if (
            lookup_latency
            and kwargs.get("method") == "GET"
            and kwargs.get("target") == SPACE_PATH
        ):
            await asyncio.sleep(lookup_latency)
        return response

    transport = Mock(spec=AsyncTransport)
    transport.perform_request = AsyncMock(side_effect=perform)
    return AsyncKibana(_transport=transport)


class TestSpaceValidationCacheUnit:
    """The cache object on its own: atomicity, expiry, invalidation edges."""

    def test_lookup_is_atomic_against_a_concurrent_invalidate(self, monkeypatch):
        """A lookup racing an invalidate returns a verdict, never a KeyError.

        Drives the race deterministically: the clock seam parks the lookup at
        the exact point (between "is it cached?" and reading the value) where an
        unsynchronized lookup used to blow up, and another thread invalidates
        while it is parked.
        """
        cache = SpaceValidationCache()
        cache.remember(SPACE_ID, True)
        parked = threading.Event()
        released = threading.Event()

        def parking_now():
            parked.set()
            released.wait(0.5)  # the invalidator must not be able to slip in
            return time.monotonic()

        monkeypatch.setattr(space_cache, "_now", parking_now)

        def invalidator():
            parked.wait(1.0)
            cache.invalidate(SPACE_ID)
            released.set()

        thread = threading.Thread(target=invalidator)
        thread.start()
        try:
            verdict = cache.lookup(SPACE_ID)
        finally:
            released.set()
            thread.join(2.0)

        assert verdict is True  # coherent, and above all not a KeyError

    def test_expired_entries_are_dropped_on_lookup(self, monkeypatch):
        """An expired verdict is evicted, not left to accumulate."""
        now = {"t": 1_000.0}
        monkeypatch.setattr(space_cache, "_now", lambda: now["t"])
        cache = SpaceValidationCache()
        cache.remember(SPACE_ID, True)

        now["t"] += cache.ttl + 1.0
        assert cache.lookup(SPACE_ID) is None
        assert cache.entries == {}
        assert cache.timestamps == {}

    def test_a_verdict_exactly_at_the_ttl_boundary_is_expired(self, monkeypatch):
        """``elapsed == ttl`` expires: the live window is strictly shorter."""
        now = {"t": 1_000.0}
        monkeypatch.setattr(space_cache, "_now", lambda: now["t"])
        cache = SpaceValidationCache()
        cache.remember(SPACE_ID, True)

        now["t"] += cache.ttl - 0.001
        assert cache.lookup(SPACE_ID) is True
        now["t"] += 0.001  # exactly ttl since the verdict was recorded
        assert cache.lookup(SPACE_ID) is None

    def test_invalidating_an_empty_id_does_not_wipe_the_cache(self):
        """Only ``None`` means "forget everything"."""
        cache = SpaceValidationCache()
        cache.remember(SPACE_ID, True)

        cache.invalidate("")

        assert cache.entries == {SPACE_ID: True}

    def test_a_verdict_outdated_by_an_invalidation_is_discarded(self):
        """A write is dropped when an invalidate landed after its snapshot."""
        cache = SpaceValidationCache()
        generation = cache.generation  # snapshot taken before the "server call"

        cache.invalidate(SPACE_ID)  # ... an explicit invalidation lands ...
        cache.remember(SPACE_ID, True, generation=generation)  # ... reply arrives

        assert cache.lookup(SPACE_ID) is None

    def test_a_parent_that_refuses_attributes_still_gets_a_cache(self):
        """An exotic parent (``__slots__``) cannot be given a cache -- no crash."""

        class Slotted:
            __slots__ = ()

        cache = space_cache.shared_space_cache(Slotted())

        assert isinstance(cache, SpaceValidationCache)


class TestSharedSpaceCacheSync:
    """Sync tree: invalidation on space mutation, sharing, monotonic TTL."""

    def test_a_delete_during_a_validation_is_not_overwritten(self):
        """#72: a validation in flight must not resurrect a deleted space.

        The transport hook deletes the space (and so invalidates the cache)
        while the existence verdict is on its way back, i.e. exactly between the
        cache miss and the write that follows it.
        """
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)

        def delete_while_the_verdict_is_in_flight(**kwargs):
            response = double.handle(**kwargs)  # answered while it still existed
            if kwargs.get("method") == "GET" and kwargs.get("target") == SPACE_PATH:
                client.spaces.delete(id=SPACE_ID)  # ... and then it is deleted
            return response

        client._transport.perform_request = Mock(
            side_effect=delete_while_the_verdict_is_in_flight
        )

        client.dashboards.get_all(space_id=SPACE_ID)

        # The delete's invalidation must win over the late verdict.
        with pytest.raises(SpaceNotFoundError):
            client.dashboards.get_all(space_id=SPACE_ID)

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
        """#73: TTL runs on the monotonic clock, not the steppable wall clock."""
        # The seam the cache reads *is* the monotonic clock; the test drives the
        # seam rather than patching time.monotonic, which asyncio also reads.
        assert space_cache._now is time.monotonic
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)
        now = {"t": 1_000.0}
        monkeypatch.setattr(space_cache, "_now", lambda: now["t"])

        client.dashboards.get_all(space_id=SPACE_ID)
        now["t"] += 299.0  # still inside the 300 s default TTL
        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        now["t"] += 2.0  # past the TTL -> re-validate
        client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    def test_scoped_client_construction_seeds_the_cache(self):
        """#73: client.space(X) + namespace calls cost one lookup in total.

        The constructor keeps its real GET -- a scoped client must fail on a
        space that no longer exists -- but its result seeds the shared cache
        instead of being thrown away.
        """
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)

        scoped = client.space(SPACE_ID)
        scoped.dashboards.get_all()
        scoped.actions.get_all()

        assert double.space_lookups == 1

    def test_scoped_client_construction_seeds_a_missing_space(self):
        """A failed construction seeds the negative verdict too."""
        double = _SpacesDouble()  # space does not exist
        client = _sync_client(double)

        with pytest.raises(SpaceNotFoundError):
            client.space(SPACE_ID)
        with pytest.raises(SpaceNotFoundError):
            client.dashboards.get_all(space_id=SPACE_ID)

        assert double.space_lookups == 1

    def test_options_clone_shares_the_cache(self):
        """An options() clone talks to the same server -- and the same cache."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _sync_client(double)

        client.dashboards.get_all(space_id=SPACE_ID)
        clone = client.options(request_timeout=30.0)
        clone.dashboards.get_all(space_id=SPACE_ID)  # served from the shared cache
        assert double.space_lookups == 1

        # ... and an invalidation on either side is seen by both.
        clone.spaces.delete(id=SPACE_ID)
        with pytest.raises(SpaceNotFoundError):
            client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2


class TestSharedSpaceCacheAsync:
    """Async twin of :class:`TestSharedSpaceCacheSync`."""

    async def test_a_delete_during_a_validation_is_not_overwritten(self):
        """#72: a validation in flight must not resurrect a deleted space.

        Two concurrent tasks: one validates the space (its lookup is answered
        while the space still exists, but the reply lands late), the other
        deletes it. The delete's invalidation must survive the late verdict.
        """
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double, lookup_latency=0.05)

        await asyncio.gather(
            client.dashboards.get_all(space_id=SPACE_ID),
            client.spaces.delete(id=SPACE_ID),
        )

        with pytest.raises(SpaceNotFoundError):
            await client.dashboards.get_all(space_id=SPACE_ID)

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
        """#73: TTL runs on the monotonic clock, not the steppable wall clock."""
        assert space_cache._now is time.monotonic
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)
        now = {"t": 1_000.0}
        monkeypatch.setattr(space_cache, "_now", lambda: now["t"])

        await client.dashboards.get_all(space_id=SPACE_ID)
        now["t"] += 299.0  # still inside the 300 s default TTL
        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        now["t"] += 2.0  # past the TTL -> re-validate
        await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2

    async def test_scoped_client_construction_seeds_the_cache(self):
        """#73: client.space(X) + namespace calls cost one lookup in total."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)

        scoped = await client.space(SPACE_ID)
        await scoped.dashboards.get_all()
        await scoped.actions.get_all()

        assert double.space_lookups == 1

    async def test_scoped_client_construction_seeds_a_missing_space(self):
        """A failed construction seeds the negative verdict too."""
        double = _SpacesDouble()  # space does not exist
        client = _async_client(double)

        with pytest.raises(SpaceNotFoundError):
            await client.space(SPACE_ID)
        with pytest.raises(SpaceNotFoundError):
            await client.dashboards.get_all(space_id=SPACE_ID)

        assert double.space_lookups == 1

    async def test_options_clone_shares_the_cache(self):
        """An options() clone talks to the same server -- and the same cache."""
        double = _SpacesDouble(existing=[SPACE_ID])
        client = _async_client(double)

        await client.dashboards.get_all(space_id=SPACE_ID)
        clone = client.options(request_timeout=30.0)
        await clone.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 1

        # ... and an invalidation on either side is seen by both.
        await clone.spaces.delete(id=SPACE_ID)
        with pytest.raises(SpaceNotFoundError):
            await client.dashboards.get_all(space_id=SPACE_ID)
        assert double.space_lookups == 2
