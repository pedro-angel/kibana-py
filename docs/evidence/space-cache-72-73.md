# Evidence — shared, invalidated space-validation cache (issues #72, #73)

**Date:** 2026-07-31
**Change under test:** new `kibana/_space_cache.py`; `NamespaceClient` /
`AsyncNamespaceClient` (`kibana/_sync/client/utils.py`,
`kibana/_async/client/utils.py`); `BaseClient` / `AsyncBaseClient`
(`kibana/_sync/client/_base.py`, `kibana/_async/client/_base.py`);
`SpacesClient.create` / `.delete` (`kibana/_sync/client/spaces.py`,
`kibana/_async/client/spaces.py`), on branch `fix/space-cache-72-73`.
**Base commit (pre-fix):** `fb845d4`.
**Runner:** local developer workstation (macOS, Python 3.11.15) against the
local `elastic-start-local` stack (Elasticsearch + Kibana 9.x + APM server).

## Why

Two companion bugs from the 2026-07-31 adversarial deep review (code-quality
lens):

- **#72** — `_clear_space_cache` had zero production callers and
  `SpacesClient.create`/`delete` never touched the caches. A space validated as
  missing stayed missing for the 300 s TTL even after `spaces.create` succeeded;
  a space validated as present stayed present after `spaces.delete`.
- **#73** — the cache lived on each *namespace client instance*, so one space
  was re-validated once per namespace (`~40` namespaces per client), and the TTL
  was measured with the wall clock (`time.time()`) rather than the monotonic
  clock the codebase already uses in `kibana/_rate_limiter.py`.

## Fix summary

One `SpaceValidationCache` (`kibana/_space_cache.py`) is created by
`BaseClient.__init__` / `AsyncBaseClient.__init__`, i.e. one per top-level
`Kibana` / `AsyncKibana`. Every namespace client *borrows* it via
`shared_space_cache(client)` instead of allocating its own, so all namespaces
(and sub-clients such as `alerting.rule`, and the namespaces of a
`client.space(...)`-scoped client, which are constructed against the same parent)
read and write one set of verdicts. `SpacesClient.create` and `.delete` call
`self._clear_space_cache(id)` after the request succeeds — create drops a stale
negative entry, delete drops a stale positive one; clearing unconditionally is
correct for both directions and simpler than branching. TTL comparisons use
`time.monotonic()`. `NamespaceClient._space_cache`, `._cache_timestamps` and
`._cache_ttl` remain as views onto the shared cache, so `_clear_space_cache` and
existing cache-inspecting tests keep working against the new structure.

**Dispositioned, deliberately NOT invalidating:** `spaces.update` (PUT cannot
change a space id, only its presentation/features — existence is unaffected),
`copy_saved_objects`, `resolve_copy_saved_objects_errors`,
`disable_legacy_url_aliases`, `get_shareable_references`,
`update_objects_spaces` (all move or read saved objects *between existing
spaces*; none creates or deletes a space).

**Concurrency stance (unchanged by design):** entries are plain `dict` items and
every cache operation is a single get/set/pop, matching the rest of the client,
which takes no lock on this path. Two threads or tasks can duplicate a lookup or
race a verdict against an invalidation; the cost is one redundant HTTP request
or a verdict already bounded by the TTL. Documented in the module docstring of
`kibana/_space_cache.py`.

## TDD — RED then GREEN

New unit module `tests/unit/test_space_cache_sharing.py` (8 tests: 4 scenarios ×
sync/async), driving real `Kibana` / `AsyncKibana` clients over a transport
double that tracks which spaces exist and counts
`GET /api/spaces/space/team-a` requests.

**RED (against pre-fix code, watched fail for the right reason):**

```
$ .venv/bin/pytest tests/unit/test_space_cache_sharing.py -p no:randomly -o addopts="" -q --tb=line
E   kibana.exceptions.SpaceNotFoundError: Space not found: team-a
/Users/.../kibana/_sync/client/utils.py:122: kibana.exceptions.SpaceNotFoundError: Space not found: team-a
E   Failed: DID NOT RAISE SpaceNotFoundError
/Users/.../tests/unit/test_space_cache_sharing.py:112: Failed: DID NOT RAISE SpaceNotFoundError
E   assert 2 == 1
/Users/.../tests/unit/test_space_cache_sharing.py:124: assert 2 == 1
E   assert 1 == 2
/Users/.../tests/unit/test_space_cache_sharing.py:142: assert 1 == 2
E   kibana.exceptions.SpaceNotFoundError: Space not found: team-a
/Users/.../kibana/_async/client/utils.py:131: kibana.exceptions.SpaceNotFoundError: Space not found: team-a
E   Failed: DID NOT RAISE SpaceNotFoundError
E   assert 2 == 1
E   assert 1 == 2
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheSync::test_create_invalidates_the_negative_cache
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheSync::test_delete_invalidates_the_positive_cache
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheSync::test_cache_is_shared_across_namespace_clients
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheSync::test_ttl_is_measured_with_the_monotonic_clock
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheAsync::test_create_invalidates_the_negative_cache
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheAsync::test_delete_invalidates_the_positive_cache
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheAsync::test_cache_is_shared_across_namespace_clients
FAILED tests/unit/test_space_cache_sharing.py::TestSharedSpaceCacheAsync::test_ttl_is_measured_with_the_monotonic_clock
8 failed in 0.06s
```

Each failure is the bug, not a broken test: create leaves the negative verdict
(`SpaceNotFoundError` after a successful create), delete leaves the positive one
(`DID NOT RAISE`), two namespaces cost two lookups (`assert 2 == 1`), and a
299 s→301 s monotonic step does not expire a wall-clock-timed entry
(`assert 1 == 2`).

**GREEN (after the fix):**

```
$ .venv/bin/pytest tests/unit/test_space_cache_sharing.py tests/unit/test_sync_async_parity.py -p no:randomly -o addopts="" -q
147 passed in 0.67s
```

Four existing unit tests that froze `time.time` to exercise TTL expiry now
freeze `time.monotonic` (`test_namespace_client_space_support.py`,
`test_async_namespace_client_space_support.py`,
`test_space_validation_comprehensive.py` ×2). Their asserted semantics — first
call validates, a call inside the TTL is a cache hit, a call past the TTL
re-validates, and entries of mixed ages expire independently — are unchanged;
only the clock they steer moved.

## Battle test — live stack

New live tests in `tests/integration/test_space_validation_integration.py`:

- `TestSpaceCacheInvalidationOnMutation` (sync + async) replays #72's exact
  sequence with **no TTL wait anywhere**: `dashboards.get_all(space_id=X)` →
  `SpaceNotFoundError` → `spaces.create(id=X)` → the same call returns 200
  immediately → `spaces.delete(id=X)` → the same call raises
  `SpaceNotFoundError` immediately.
- `TestSpaceLookupDeduplication` (sync + async) proves #73's dedup claim by
  wrapping the **live** transport with a counter (nothing is stubbed; every
  request still reaches Kibana) and driving six distinct namespace clients —
  `dashboards`, `actions`, `saved_objects`, `data_views`, `cases`, and the
  `alerting.rule` sub-client — against one space, asserting exactly **one**
  `GET /api/spaces/space/{id}`.

Both classes track created spaces in the `created_spaces` fixture before
creating them (so a mid-test failure still tears down) and drop the id from that
list when the test deletes the space itself.

**(a) Pre-fix — the live tests catch both bugs** (`git stash push -- kibana/`,
tests unchanged):

```
$ .venv/bin/pytest tests/integration/test_space_validation_integration.py::TestSpaceCacheInvalidationOnMutation \
                   tests/integration/test_space_validation_integration.py::TestSpaceLookupDeduplication \
                   -p no:randomly -o addopts="" -q --tb=line
E   kibana.exceptions.SpaceNotFoundError: Space not found: test-space-581c0db0
/Users/.../kibana/_sync/client/utils.py:122: kibana.exceptions.SpaceNotFoundError: Space not found: test-space-581c0db0
E   kibana.exceptions.SpaceNotFoundError: Space not found: test-space-2bcd00d0
/Users/.../kibana/_async/client/utils.py:131: kibana.exceptions.SpaceNotFoundError: Space not found: test-space-2bcd00d0
E   assert 6 == 1
/Users/.../tests/integration/test_space_validation_integration.py:722: assert 6 == 1
E   assert 6 == 1
/Users/.../tests/integration/test_space_validation_integration.py:744: assert 6 == 1
FAILED ...::TestSpaceCacheInvalidationOnMutation::test_create_then_delete_take_effect_immediately
FAILED ...::TestSpaceCacheInvalidationOnMutation::test_create_then_delete_take_effect_immediately_async
FAILED ...::TestSpaceLookupDeduplication::test_many_namespaces_trigger_one_space_lookup
FAILED ...::TestSpaceLookupDeduplication::test_many_namespaces_trigger_one_space_lookup_async
4 failed in 7.26s
```

Live confirmation of both issues as filed: `spaces.create` on a
negatively-cached space did not make the next namespace call work, and six
namespaces cost **six** identical `GET /api/spaces/space/{id}` requests where
one suffices.

**(b) Post-fix — the same live tests pass:**

```
$ .venv/bin/pytest tests/integration/test_space_validation_integration.py::TestSpaceCacheInvalidationOnMutation \
                   tests/integration/test_space_validation_integration.py::TestSpaceLookupDeduplication \
                   -p no:randomly -o addopts="" -v
tests/integration/test_space_validation_integration.py::TestSpaceCacheInvalidationOnMutation::test_create_then_delete_take_effect_immediately PASSED [ 25%]
tests/integration/test_space_validation_integration.py::TestSpaceCacheInvalidationOnMutation::test_create_then_delete_take_effect_immediately_async PASSED [ 50%]
tests/integration/test_space_validation_integration.py::TestSpaceLookupDeduplication::test_many_namespaces_trigger_one_space_lookup PASSED [ 75%]
tests/integration/test_space_validation_integration.py::TestSpaceLookupDeduplication::test_many_namespaces_trigger_one_space_lookup_async PASSED [100%]
4 passed in 7.83s
```

**(c) The whole space-related live surface, unchanged behavior:**

```
$ .venv/bin/pytest tests/integration/test_space_validation_integration.py \
                   tests/integration/test_space_scoped_operations_integration.py \
                   tests/integration/test_spaces_integration.py -p no:randomly -o addopts="" -q
43 passed in 139.73s (0:02:19)

$ .venv/bin/pytest tests/benchmark/test_space_performance.py -p no:randomly -o addopts="" -q
10 passed in 126.48s (0:02:06)
```

The benchmark suite exercises `_clear_space_cache()`, `_cache_ttl` mutation and
direct `_space_cache` / `_cache_timestamps` inspection on a namespace client —
all still work, now against the shared cache.

**(d) Teardown verified — no test space left on the stack:**

```
$ python - <<'PY'
from tests.integration.utils import create_test_kibana_client
c = create_test_kibana_client(); print([s['id'] for s in c.spaces.get_all().body]); c.close()
PY
spaces on stack: ['default']
```

## Gates

```
$ .venv/bin/pre-commit run --all-files            # exit 0 (black, isort, ruff, pin/secret/identifier checks)
$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files
$ .venv/bin/bandit -r kibana/ -ll -q              # exit 0, no findings
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3207 passed
Required test coverage of 90% reached. Total coverage: 94.22%   (kibana/_space_cache.py: 100%)
$ .venv/bin/sphinx-build -W --keep-going -b html docs/source docs/build/html   # exit 0
```

The sync/async parity guard (`tests/unit/test_sync_async_parity.py`, included in
the unit run above) passes: the twin edits to `spaces.create`/`delete` and the
namespace-client cache plumbing are body-identical across the two trees, and no
entry was added to `_BODY_DRIFT_ALLOWLIST`.

## Scoped out (not regressions, no behavior change)

- `SpaceScopedKibana.__init__` / its async twin still validate the space with a
  direct `spaces.get()` that neither reads nor writes the cache — the same
  as before this change. Routing that one call through the shared cache would
  save a lookup per `client.space(...)`, but it sits on the sync/async-divergent
  construction path already in `_BODY_DRIFT_ALLOWLIST`; left for a separate
  change.
- `client.options(...)` returns a *new* top-level client, which therefore gets
  its own cache — as it did before (caches were per namespace instance, so an
  options clone never shared them either).
