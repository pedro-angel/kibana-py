"""Space-existence cache shared by all namespaces of one Kibana client.

Validating ``space_id`` costs a ``GET /api/spaces/space/{id}`` per call, so the
verdict is cached. The cache hangs off the *top-level* client rather than each
namespace client, which buys two things:

- one lookup per space per TTL window for the whole client, instead of one per
  namespace (~40 namespaces would otherwise repeat the same GET);
- a single place for :class:`~kibana._sync.client.spaces.SpacesClient` to
  invalidate when ``create``/``delete`` changes whether a space exists.

The TTL is measured with :func:`time.monotonic` (as :mod:`kibana._rate_limiter`
does) so an NTP step or a DST change cannot stretch or shrink a cached verdict.
It is read through the module-level ``_now`` seam so tests can drive it without
patching the process-wide clock that asyncio's event loop also reads.

Concurrency
-----------

Every operation holds a :class:`threading.Lock` (the same precedent as
:mod:`kibana._rate_limiter`, and the sync client documents itself as
thread-safe). The lock closes two races that plain dict operations do not:

- a ``lookup`` that had checked membership, then found the entry gone when it
  read the value, raised ``KeyError`` out of an ordinary client call;
- an ``invalidate`` landing between a validator's cache miss and its post-GET
  write was silently overwritten -- an explicit ``spaces.delete`` undone for the
  whole TTL. Writers therefore snapshot :attr:`SpaceValidationCache.generation`
  *before* asking the server and pass it to :meth:`SpaceValidationCache.remember`,
  which drops a verdict that an invalidation has already outdated. The generation
  is global rather than per-space: an unrelated invalidation can discard a
  concurrent verdict, and the price of that is one extra lookup.

What the lock does *not* buy is single-flight: two callers that miss
simultaneously still both ask the server (no await or blocking I/O ever happens
under the lock), which costs a redundant request and never an incorrect verdict.
"""

from __future__ import annotations

import threading
import time
from typing import Any

# Clock seam: tests patch this module attribute instead of ``time.monotonic``
# itself, which asyncio's event loop also reads.
_now = time.monotonic

DEFAULT_SPACE_CACHE_TTL = 300.0  # seconds
"""How long a space-existence verdict stays valid (5 minutes)."""


class SpaceValidationCache:
    """Cache of "does this space exist?" verdicts, keyed by space id.

    ``ttl`` is a plain attribute: callers that want a different window (tests,
    mostly) assign to it, directly or through a namespace client's
    ``_cache_ttl``.
    """

    def __init__(self) -> None:
        self.entries: dict[str, bool] = {}
        self.timestamps: dict[str, float] = {}
        self.ttl: float = DEFAULT_SPACE_CACHE_TTL
        self._lock = threading.Lock()
        self._generation = 0

    @property
    def generation(self) -> int:
        """Counter bumped by every :meth:`invalidate`.

        Snapshot it before asking the server, then hand it to :meth:`remember`
        so a verdict that an invalidation has outdated is dropped instead of
        overwriting the invalidation. Read without the lock on purpose: reading
        an ``int`` attribute is atomic, and taking the (non-reentrant) lock here
        would deadlock callers that already hold it.
        """
        return self._generation

    def lookup(self, space_id: str) -> bool | None:
        """Return the cached verdict, or ``None`` when absent or expired.

        :param space_id: Space ID to look up
        :return: ``True``/``False`` for a live verdict, ``None`` for a miss
        """
        with self._lock:
            if space_id not in self.entries:
                return None
            # A missing timestamp is treated as expired (-inf), never as "just
            # now": monotonic() is small right after boot, so a 0.0 default
            # would make an entry with no timestamp look fresh.
            stamp = self.timestamps.get(space_id, float("-inf"))
            if _now() - stamp >= self.ttl:
                # Drop it here rather than leaving it for a re-validation that
                # may never come, so ids validated once cannot accumulate.
                self.entries.pop(space_id, None)
                self.timestamps.pop(space_id, None)
                return None
            return self.entries[space_id]

    def remember(
        self, space_id: str, exists: bool, generation: int | None = None
    ) -> None:
        """Record a verdict and start its TTL window.

        :param space_id: Space ID the verdict is about
        :param exists: Whether the space exists
        :param generation: :attr:`generation` as read *before* the server was
            asked. When it no longer matches, an invalidation has landed in the
            meantime and this (now outdated) verdict is discarded. ``None``
            writes unconditionally.
        """
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self.entries[space_id] = exists
            self.timestamps[space_id] = _now()

    def invalidate(self, space_id: str | None = None) -> None:
        """Drop a cached verdict, or all of them.

        :param space_id: Space ID to forget. If ``None``, forget everything.
            An empty string forgets nothing (it is not a valid space id) rather
            than clearing the cache.
        """
        with self._lock:
            self._generation += 1
            if space_id is not None:
                self.entries.pop(space_id, None)
                self.timestamps.pop(space_id, None)
            else:
                self.entries.clear()
                self.timestamps.clear()


def shared_space_cache(client: Any) -> SpaceValidationCache:
    """Return the space-validation cache belonging to ``client``.

    Namespace clients never own a cache; they borrow the one every real client
    builds in ``BaseClient.__init__``, so that all namespaces -- and
    ``SpacesClient``, which invalidates it -- see the same entries.

    The isinstance check and the attach below exist for namespace clients built
    on a *test double* parent (``NamespaceClient(Mock())``, used throughout the
    unit suite), where the attribute lookup yields an auto-created mock rather
    than a cache. Attaching a real cache on first use keeps those doubles
    sharing one cache too, so tests observe production caching semantics.

    :param client: The parent client a namespace client delegates to
    :return: The parent's shared cache
    """
    cache = getattr(client, "_space_validation_cache", None)
    if isinstance(cache, SpaceValidationCache):
        return cache
    cache = SpaceValidationCache()
    try:
        client._space_validation_cache = cache
    except (AttributeError, TypeError):
        # An exotic parent that refuses attributes (``__slots__``, a frozen
        # dataclass, a read-only proxy): fall back to a cache this namespace
        # client alone uses, rather than failing the call it was asked to make.
        pass
    return cache
