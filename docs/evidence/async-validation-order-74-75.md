# Evidence — format-first space validation, and a parity guard that can see it (issues #74, #75)

**Date:** 2026-07-31
**Change under test:** `AsyncNamespaceClient._maybe_validate_space` and the
shared `_check_space_id_format`
(`kibana/_async/client/utils.py`, `kibana/_sync/client/utils.py`); statement
order in the four async namespaces that diverged (`connectors.py`,
`data_views.py`, `ml.py`, `saved_objects.py`); construction-time format check in
`SpaceScopedKibana` / `AsyncSpaceScopedKibana` (`kibana/_sync/client/__init__.py`,
`kibana/_async/client/__init__.py`); body normalizer in
`tests/unit/test_sync_async_parity.py` — branch `fix/async-validation-order-74-75`.
**Base commit (pre-fix):** `5c5fe11`.
**Fix commits:** `4b0d0e1` (#74), `1d1aa05` (#75).
**Runner:** local developer workstation (macOS 26.5.2, arm64, Python 3.11.15,
pytest 8.x) against the local `elastic-start-local` stack
(Elasticsearch + Kibana **9.4.3** + APM server) on `http://localhost:5601`.

Two mechanical edits apply to every captured block below, and nothing else:
absolute paths are elided to `/Users/.../` for identity hygiene, and trailing
whitespace is stripped by this repo's own pre-commit hook (which blanks the
indentation-only lines inside pytest's assertion diffs).

## Why

Both bugs come from the 2026-07-31 adversarial deep review (code-quality lens).

- **#74** — sync format-checks a `space_id` inside `_build_space_path`, so a
  malformed id fails locally. Async validated *existence* first
  (`_maybe_validate_space` → `_validate_space_exists`), so
  `await client.slos.get(slo_id="x", space_id="Bad Space!")` issued a real
  `GET /api/spaces/space/Bad%20Space%21`, raised `SpaceNotFoundError` (the wrong
  exception — the id was never a space that could be missing) and, since the
  shared cache landed (#73), negative-cached the malformed key for the TTL.
  Four async files used the opposite statement order from the other 28, and
  `Kibana.space()` / `AsyncKibana.space()` promised `InvalidSpaceIdError` in
  their docstrings without ever checking.
- **#75** — the parity normalizer folded the `_maybe_validate_space` statement
  wherever it appeared and ran `visit_Await` first, so neither the ordering
  divergence nor a dropped `await` could ever fail CI.

## Current reality before the fix (measured, not recalled)

An AST sweep of `kibana/_async/client/` counting, per method, the position of
the `_maybe_validate_space` statement relative to the `_build_space_path` call:

```
$ python .../map_order.py          # pre-fix tree (5c5fe11)
   42  build-BEFORE-validate
  538  validate-immediately-before-build

AFTER kibana/_async/client/connectors.py:99 create v=7 b=6
AFTER kibana/_async/client/connectors.py:191 get v=3 b=2
...
AFTER kibana/_async/client/saved_objects.py:1092 rotate_encryption_key v=2 b=1
```

The 42 are exactly `connectors.py` (9), `data_views.py` (15), `ml.py` (3),
`saved_objects.py` (15). No method had the two statements separated by anything
else, and no call was missing its `await`. The sync tree has no
`_maybe_validate_space` at all (0 occurrences): it format-checks and then
existence-checks inside `_build_space_path`, which is why sync was already
format-first everywhere.

Post-fix, the same sweep:

```
$ python .../map_order.py          # fixed tree
  580  validate-immediately-before-build
```

## Fix summary

`_maybe_validate_space` now resolves the effective space id, returns immediately
when there is none, then runs `self._validate_space_id_format(...)` **before**
consulting `_validate_spaces` or the cache — the same unconditional,
format-first order sync's `_build_space_path` has always used. Because the
format check now lives in the statement that must run *first*, the 42 methods
that built the path before validating were re-ordered to the tree-wide
convention (`await self._maybe_validate_space(...)` immediately before
`path = self._build_space_path(...)`).

The redundant format check inside `_build_space_path` **stays** (both trees). It
is no longer the first check on any current path, but it is the only thing
protecting a future caller that builds a space-scoped path without validating
first — the exact regression class PR #60 fixed — and it costs one regex match
on an already space-scoped call.

`SpaceScopedKibana.__init__` and `AsyncSpaceScopedKibana.__init__` call the
shared `_check_space_id_format` first and regardless of `validate=`, honoring
the docstring promise and keeping `_validate_space_on_creation` (which seeds the
shared cache) from ever being handed a malformed id. The format rule itself was
duplicated in both trees; it is now one private function
(`_check_space_id_format` in `kibana/_sync/client/utils.py`, imported by the async
utils) that both trees and both scoped clients call. It is internal, not new
public API.

For #75 the fold is now narrow: a `_maybe_validate_space` statement is removed
only when it was **genuinely awaited** (marked in `visit_AsyncFunctionDef` while
the `Await` node is still visible, before `generic_visit` unwraps it) **and**
stands immediately before a single `_build_space_path` call **for the same
space**. Anything else stays in the normalized async body, which sync does not
have, and fails the parity assertion.

## RED — the tests fail against the pre-fix tree

**(a) #74, new unit suite (`tests/unit/test_space_id_format_first.py`), pre-fix:**

```
$ .venv/bin/python -m pytest tests/unit/test_space_id_format_first.py -q --no-cov
tests/unit/test_space_id_format_first.py:145: Failed
=========================== short test summary info ============================
FAILED tests/unit/test_space_id_format_first.py::test_async_namespace_rejects_a_malformed_default_space_id[timeline]
FAILED tests/unit/test_space_id_format_first.py::test_sync_space_rejects_a_malformed_id[False]
FAILED tests/unit/test_space_id_format_first.py::test_async_namespace_rejects_a_malformed_default_space_id[slos]
FAILED tests/unit/test_space_id_format_first.py::test_async_space_rejects_a_malformed_id[True]
FAILED tests/unit/test_space_id_format_first.py::test_async_space_rejects_a_malformed_id[False]
FAILED tests/unit/test_space_id_format_first.py::test_async_namespace_rejects_a_malformed_space_id_without_touching_anything[timeline]
FAILED tests/unit/test_space_id_format_first.py::test_async_namespace_rejects_a_malformed_space_id_without_touching_anything[slos]
FAILED tests/unit/test_space_id_format_first.py::test_sync_space_rejects_a_malformed_id[True]
8 failed, 20 passed in 0.10s
```

The failure pattern *is* the bug map: the two async namespaces using the
tree-wide order (`slos`, `timeline`) fail, the four that built the path first
(`connectors`, `data_views`, `ml`, `saved_objects`) pass, every sync namespace
passes, and `space()` fails in both trees. The async namespace failure is
verbatim:

```
E       AssertionError: a malformed space id must not reach the wire, but these requests went out: [call(method='GET', target='/api/spaces/space/Bad%20Space%21')]
E       assert [call(method=...%20Space%21')] == []
E
E         Left contains one more item: call(method='GET', target='/api/spaces/space/Bad%20Space%21')
```

and `space()`'s is `Failed: DID NOT RAISE InvalidSpaceIdError`.

**(b) #75, normalizer self-tests, against the pre-fix normalizer:**

```
$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov -k normalizer
tests/unit/test_sync_async_parity.py:506: AssertionError
=========================== short test summary info ============================
FAILED tests/unit/test_sync_async_parity.py::test_normalizer_surfaces_broken_space_validation[wrong-space]
FAILED tests/unit/test_sync_async_parity.py::test_normalizer_surfaces_broken_space_validation[swapped-order]
FAILED tests/unit/test_sync_async_parity.py::test_normalizer_surfaces_broken_space_validation[dropped-await]
FAILED tests/unit/test_sync_async_parity.py::test_normalizer_surfaces_broken_space_validation[detached]
4 failed, 1 passed, 139 deselected in 0.09s
```

All four mutant shapes normalized to *exactly* their sync twin — the guard could
not see any of them. The one passing test is the canonical fold, which must keep
working.

## GREEN

```
$ .venv/bin/python -m pytest tests/unit/test_space_id_format_first.py -q --no-cov
............................                                             [100%]
28 passed in 0.08s

$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov
........................................................................ [ 50%]
........................................................................ [100%]
144 passed in 0.64s
```

**Zero new `_BODY_DRIFT_ALLOWLIST` entries**: the hardened normalizer accepts
the whole corrected tree as-is.

## Mutation verification — the hardened guard actually bites

Each mutation is applied to the final tree, the parity suite is run, then the
file is restored with `git checkout`.

**(i) Delete the `await` from one async namespace** (`AsyncSlosClient.get`):

```
$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov -vv
E           AssertionError: SlosClient.get body drift (a fix may have landed in only one tree). If this divergence is intentional and async-boundary-driven, add ("SlosClient", "get") to _BODY_DRIFT_ALLOWLIST with a reason.
E             --- normalized sync ---
E             def get(self, *, slo_id, instance_id=None, space_id=None, validate_spaces=None):
E                 path = self._build_space_path(f'{_SLOS_PATH}/{_quote(slo_id)}', space_id, validate_spaces)
E                 params = {}
E                 if instance_id is not None:
E                     params['instanceId'] = instance_id
E                 return self.perform_request(method='GET', path=path, params=params or None)
E             --- normalized async ---
E             def get(self, *, slo_id, instance_id=None, space_id=None, validate_spaces=None):
E                 self._maybe_validate_space(space_id, validate_spaces)
E                 path = self._build_space_path(f'{_SLOS_PATH}/{_quote(slo_id)}', space_id)
E                 params = {}
E                 if instance_id is not None:
E                     params['instanceId'] = instance_id
E                 return self.perform_request(method='GET', path=path, params=params or None)
=========================== short test summary info ============================
FAILED tests/unit/test_sync_async_parity.py::test_public_method_bodies_match[SlosClient]
1 failed, 143 passed in 0.65s
```

**(ii) Swap the statement order back in one of the four formerly-divergent files**
(`AsyncMlClient.sync`):

```
$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov -vv
E           AssertionError: MlClient.sync body drift (a fix may have landed in only one tree). If this divergence is intentional and async-boundary-driven, add ("MlClient", "sync") to _BODY_DRIFT_ALLOWLIST with a reason.
E             --- normalized sync ---
E             def sync(self, *, simulate=None, space_id=None, validate_spaces=None):
E                 params = {}
E                 if simulate is not None:
E                     params['simulate'] = simulate
E                 path = self._build_space_path('/api/ml/saved_objects/sync', space_id, validate_spaces)
E                 return self.perform_request('GET', path, params=params, headers={'accept': 'application/json'})
E             --- normalized async ---
E             def sync(self, *, simulate=None, space_id=None, validate_spaces=None):
E                 params = {}
E                 if simulate is not None:
E                     params['simulate'] = simulate
E                 path = self._build_space_path('/api/ml/saved_objects/sync', space_id)
E                 self._maybe_validate_space(space_id, validate_spaces)
E                 return self.perform_request('GET', path, params=params, headers={'accept': 'application/json'})
=========================== short test summary info ============================
FAILED tests/unit/test_sync_async_parity.py::test_public_method_bodies_match[MlClient]
1 failed, 143 passed in 0.65s
```

**(iii) Restore — green again.** The two mutations were applied one at a time,
each file restored before the next was mutated, so the restore is two separate
checkouts:

```
$ git checkout kibana/_async/client/slos.py     # after (i)
$ git checkout kibana/_async/client/ml.py       # after (ii)
$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov
........................................................................ [ 50%]
........................................................................ [100%]
144 passed in 0.64s
```

Before the #75 fix, both mutations passed the entire parity suite. Note also
that the guard is not merely spotting "a statement sync lacks": in (i) the
normalized async body still *shows* the call — what fails is that an un-awaited
call is no longer eligible for the fold.

## Live battle-test — real stack, real transport

This started as an ad-hoc probe; it is now a committed gate. The claims below
live in `tests/integration/test_space_validation_integration.py` as
`TestMalformedSpaceIdCostsNothing` (sync and async namespaces, plus `space()`
with `validate=` both ways), using a `record_requests` helper that wraps the
live transport — the sibling of the existing `count_space_lookups`. Each test
makes one real call inside the recorder afterwards and asserts it *was* recorded,
so "zero requests" is a measurement and not an unattached hook. The sync
format-validation test in the same file gained the same zero-request and
empty-cache assertions.

```
$ .venv/bin/pytest tests/integration/test_space_validation_integration.py \
                   -o addopts="" -p no:randomly -q -ra
27 passed in 41.42s
```

The original ad-hoc probe's output is kept below because it also pins the server
version and the exact request targets. A counting hook wraps
`client._transport.perform_request`, so the assertions count requests that
actually left the client; the baseline check proves the hook counts (a real
`GET /api/status` against Kibana 9.4.3).

```
$ .venv/bin/python .../live_battle_74.py
Kibana target: http://localhost:5601
[PASS] baseline: status.get_status() reached the live server -- requests=[('GET', '/api/status')] version=9.4.3
[PASS] slos.get(space_id='Bad Space!') -> InvalidSpaceIdError -- raised InvalidSpaceIdError('Bad Space!')
[PASS] slos.get: zero HTTP requests -- requests=[]
[PASS] slos.get: cache untouched -- cache={}
[PASS] saved_objects.get(space_id='Bad Space!') -> InvalidSpaceIdError -- raised InvalidSpaceIdError('Bad Space!')
[PASS] saved_objects.get: zero HTTP requests -- requests=[]
[PASS] saved_objects.get: cache untouched -- cache={}
[PASS] connectors.get_all(space_id='Bad Space!') -> InvalidSpaceIdError -- raised InvalidSpaceIdError('Bad Space!')
[PASS] connectors.get_all: zero HTTP requests -- requests=[]
[PASS] connectors.get_all: cache untouched -- cache={}
[PASS] space('Bad Space!', validate=True) -> InvalidSpaceIdError -- raised InvalidSpaceIdError('Bad Space!')
[PASS] space('Bad Space!', validate=True): zero HTTP requests -- requests=[]
[PASS] space('Bad Space!', validate=False) -> InvalidSpaceIdError -- raised InvalidSpaceIdError('Bad Space!')
[PASS] space('Bad Space!', validate=False): zero HTTP requests -- requests=[]
[PASS] space cache still empty after every malformed id -- cache={}
[PASS] valid space: scoped saved_objects.find() succeeded -- status=200 requests=[('GET', '/s/wu4-live-space/api/saved_objects/_find?type=dashboard&per_page=1')]
[PASS] valid space: verdict cached once (seeded by space()) -- cache={'wu4-live-space': True}

ALL CHECKS PASSED
```

The three namespaces are deliberately mixed: `slos` used the tree-wide order
(it is one of the 28 that *had* the bug), `saved_objects` and `connectors` are
two of the four that were re-ordered.

**Valid space flows are unaffected — the live space suites:**

```
$ .venv/bin/pytest tests/integration/test_space_validation_integration.py \
                   tests/integration/test_space_scoped_operations_integration.py \
                   tests/integration/test_spaces_integration.py -o addopts="" -p no:randomly -q -ra
45 passed in 144.34s (0:02:24)          # before the 6 tests above were added; 51 after

$ .venv/bin/pytest tests/integration/test_async_saved_objects_integration.py \
                   -o addopts="" -p no:randomly -q -ra
20 passed in 45.21s
```

(the async saved-objects suite exercises 15 of the 42 re-ordered methods against
the live server).

**Teardown verified — no test space left on the stack:**

```
$ python - <<'PY'
from tests.integration.utils import create_test_kibana_client
c = create_test_kibana_client()
print("spaces on stack:", [s["id"] for s in c.spaces.get_all().body])
c.close()
PY
spaces on stack: ['default']
```

## Gates

```
$ make hooks            # pre-commit --all-files: black, isort, ruff, secret/pin/identifier checks -- all Passed
$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files
$ make sast
.venv/bin/bandit -r kibana/ -ll -q              # exit 0, no findings
$ make test
TOTAL                                                13131    747    94%
Required test coverage of 90% reached. Total coverage: 94.31%
============================ 3254 passed in 15.03s =============================
```

Unit total moves 3221 → 3254 (+33: 28 in the new `test_space_id_format_first.py`,
5 normalizer self-tests). The parity suite is part of that run.

## What this evidence does not cover

- **Format-checking on a `validate=False` scoped client is a behavior change.**
  `client.space("Bad Space!", validate=False)` used to return a client that then
  failed on every call; it now raises `InvalidSpaceIdError` at construction. That
  is what the docstring always promised, and no test in the repo expected the old
  behavior, but a caller that constructed scoped clients from unvalidated input
  and only handled errors at call sites will now see the error earlier.
- **Non-404 errors and cache semantics are unchanged** by this work; they are
  covered by `docs/evidence/space-cache-72-73.md`.
- The mutation checks prove the guard catches an *ordering* and an *await*
  regression in a method the parity suite compares. Methods on the
  `_BODY_DRIFT_ALLOWLIST` (`Kibana.perform_request`, `Kibana.space`,
  `Kibana.close`, `BaseClient.perform_request`) remain outside body comparison,
  as before this change.
