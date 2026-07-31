"""Space-existence cache shared by all namespaces of one Kibana client.

Validating ``space_id`` costs a ``GET /api/spaces/space/{id}`` per call, so the
verdict is cached. The cache hangs off the *top-level* client rather than each
namespace client, which buys two things:

- one lookup per space per TTL window for the whole client, instead of one per
  namespace (~40 namespaces would otherwise repeat the same GET);
- a single place for :class:`~kibana._sync.client.spaces.SpacesClient` to
  invalidate when ``create``/``delete`` changes whether a space exists.

The TTL is measured with :func:`time.monotonic` (as
:mod:`kibana._rate_limiter` does) so an NTP step or a DST change cannot stretch
or shrink a cached verdict.

Concurrency: entries are plain ``dict`` items, and every operation here is a
single get/set/pop, so concurrent callers can duplicate a lookup or race a
verdict against an invalidation but never corrupt the mapping. That matches the
rest of the client, which takes no lock on this path; the cost of a lost race is
one redundant HTTP request, and a stale verdict already bounded by the TTL.
"""

from __future__ import annotations

import time
from typing import Any

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

    def lookup(self, space_id: str) -> bool | None:
        """Return the cached verdict, or ``None`` when absent or expired.

        :param space_id: Space ID to look up
        :return: ``True``/``False`` for a live verdict, ``None`` for a miss
        """
        if space_id not in self.entries:
            return None
        # A missing timestamp is treated as expired (-inf), never as "just now":
        # monotonic() is small right after boot, so a 0.0 default would make an
        # entry with no timestamp look fresh.
        stamp = self.timestamps.get(space_id, float("-inf"))
        if time.monotonic() - stamp >= self.ttl:
            return None
        return self.entries[space_id]

    def remember(self, space_id: str, exists: bool) -> None:
        """Record a verdict and start its TTL window.

        :param space_id: Space ID the verdict is about
        :param exists: Whether the space exists
        """
        self.entries[space_id] = exists
        self.timestamps[space_id] = time.monotonic()

    def invalidate(self, space_id: str | None = None) -> None:
        """Drop a cached verdict, or all of them.

        :param space_id: Space ID to forget. If ``None``, forget everything.
        """
        if space_id:
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
    client._space_validation_cache = cache
    return cache
