# Evidence — stdlib/orjson request-body JSON serialization parity (issue #79)

**Date:** 2026-08-01
**Change under test:** `kibana/serializer.py` (`JSONSerializer.dumps`, `JSONSerializer._default`)
on branch `fix/serializer-parity-79`.
**Base commit (pre-fix, `main`):** `2e8a654`.

## Why

`kibana/serializer.py` picks one of two backends for `application/json` request bodies
at import time — `OrjsonSerializer` if `orjson` is installed, `JSONSerializer`
(stdlib) otherwise — and, pre-fix, the two diverged on observable JSON semantics:

- **NaN/Infinity/-Infinity:** stdlib's `json.dumps` (default `allow_nan=True`) emitted
  the invalid-JSON tokens `NaN`/`Infinity`/`-Infinity`; a real request with one of these
  reaches Kibana and gets rejected with a 400 for malformed JSON. orjson has no such
  option and always serializes the same values as JSON `null` — a silent, undetectable
  change to the caller's data.
- **UUID:** stdlib's `_default` hook had no case for `uuid.UUID`, so a UUID value
  anywhere in a body raised a bare `TypeError` at serialization time; orjson already
  serializes `uuid.UUID` natively to its canonical string form.

Same input, two different observable outcomes depending on which optional dependency
happened to be installed.

## Scope

- stdlib (`JSONSerializer`): `dumps` now passes `allow_nan=False`, and wraps the
  resulting `ValueError` in `kibana.exceptions.SerializationError` (the package's own,
  pre-existing serialization exception type — reused, not invented) with a fixed
  message shared as one module constant. `_default` gained a `uuid.UUID` case
  (`str(obj)`), alongside the existing `datetime` case.
- orjson (`OrjsonSerializer`): **UUID** already matched (native support, unchanged) —
  pinned here with cross-backend equality tests. **NaN/Infinity** is a **documented,
  tracked gap, not fixed** — see "Overhead measurement and BLOCKED decision" below for
  why, per the task's own accepted-budget rule.
- No change to genuinely-unsupported-type handling (e.g. a plain custom class, a
  `set`) on either backend — both already raise a `TypeError`-family exception there
  and that shape is out of scope for #79.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 25.5.0 |
| Python (unit suite, mypy, hooks, battle-test) | 3.11.15 (`.venv`, editable install) |
| orjson | 3.11.9 (installed via the `orjson` extra) |
| Role | local arm64 macOS dev workstation |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` reachable throughout) |
| Auth | resolved via `tests/integration/utils.py::create_test_kibana_client` (same config the integration suite uses) |

**CRITICAL environment rule honored:** no command in this evidence run touches ports
`4317`/`4318` (unrelated OTel collector ports); every live call targets only
`http://localhost:5601`.

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5601/api/status
200
```

## Environment-research: what does the installed orjson actually emit for NaN/Infinity?

Probed directly (orjson 3.11.9) before designing anything, per environment-research —
the hypothesis was "silently null" per the issue text; confirmed, not assumed:

```
>>> import orjson
>>> orjson.dumps({"v": float("nan")})
b'{"v":null}'
>>> orjson.dumps({"v": float("inf")})
b'{"v":null}'
>>> orjson.dumps({"v": float("-inf")})
b'{"v":null}'
>>> orjson.dumps({"v": [1, 2, float("nan")]})
b'{"v":[1,2,null]}'
>>> [name for name in dir(orjson) if name.startswith("OPT_")]
['OPT_APPEND_NEWLINE', 'OPT_INDENT_2', 'OPT_NAIVE_UTC', 'OPT_NON_STR_KEYS',
 'OPT_OMIT_MICROSECONDS', 'OPT_PASSTHROUGH_DATACLASS', 'OPT_PASSTHROUGH_DATETIME',
 'OPT_PASSTHROUGH_SUBCLASS', 'OPT_SERIALIZE_DATACLASS', 'OPT_SERIALIZE_NUMPY',
 'OPT_SERIALIZE_UUID', 'OPT_SORT_KEYS', 'OPT_STRICT_INTEGER', 'OPT_UTC_Z']
```

No `OPT_*` flag controls non-finite-float handling — confirmed by exhaustive listing,
not inference. A web search corroborated this is a known, deliberate orjson design
choice (strict RFC 8259 conformance: only `true`/`false`/`null` are valid JSON
literals) with an **open, unresolved upstream feature request** for a
serialize-as-string option (`ijl/orjson#170`). Design proceeds against the observation
(orjson: no native option exists) rather than hoping a flag would appear.

UUID, for contrast, already works natively with no option needed:

```
>>> import uuid
>>> u = uuid.UUID("5284d425-7649-4ae6-baec-dfeaf0419cf7")
>>> orjson.dumps({"id": u})
b'{"id":"5284d425-7649-4ae6-baec-dfeaf0419cf7"}'
>>> import json
>>> json.dumps({"id": u})
TypeError: Object of type UUID is not JSON serializable
```

## Overhead measurement and BLOCKED decision (orjson-side NaN guard)

The task's binding rule: measure the overhead of a pre-serialization finiteness guard
on a representative ~10KB body; if overhead is genuinely prohibitive (**>10%**), stop
and report BLOCKED with measurements instead of shipping a divergence.

Representative body: a nested saved-object-shaped payload (id, type, attributes with a
title/description/150 float config values/panelsJSON string/timestamp, 60 UUID-bearing
references, 10 tags, a top-level score) — **9235 bytes** as orjson-encoded output.

Three mechanisms were built and measured, all using `timeit` with `N=20000` against the
same body object (Python 3.11.15, orjson 3.11.9, same machine as this evidence run):

| Mechanism | Cost alone | Cost + orjson.dumps | Overhead vs. `orjson.dumps` alone |
|---|---|---|---|
| `orjson.dumps` alone (baseline) | — | 6.32 us/call | — |
| Recursive Python walk (`isinstance`, recursion) | 19.98 us/call | 25.99 us/call | **+311.5%** |
| Iterative Python walk (`type() is float`, explicit stack, no recursion) | 13.90 us/call | 19.96 us/call | **+215.9%** |
| stdlib C-encoder used purely for validation (`json.dumps(..., allow_nan=False)`, output discarded) | 36.58 us/call | 43.83 us/call | **+594.0%** (worse — building the JSON string, even discarded, costs more than a lean type check) |

All three exceed the 10% budget by more than an order of magnitude — not a borderline
11-15% call. A useful comparison point: even with the *best* variant (the iterative
walk) wired in, `orjson.dumps` + guard (19.96 us/call for this body) would still be
**1.77x faster** than the stdlib fallback this project already ships automatically
when orjson isn't installed (36.65 us/call, measured the same way, `allow_nan=False`
included) — so the guard would never regress orjson-backed callers below the
already-shipped no-orjson baseline. In absolute terms the added cost (~14 us) is
negligible next to any real network round trip. Both of these mitigating facts are
recorded here for whoever revisits this decision; they do not change the outcome below,
because the task's stop condition is stated as an operational, pre-committed threshold
(">10%"), not a judgment call to reason past once a plausible-sounding justification
for shipping anyway is found — which is exactly the situation these numbers create.

**Decision: BLOCKED for the orjson-side NaN/Infinity guard.** No mechanism found stays
under the 10% budget; the fix was not wired into `OrjsonSerializer.dumps`. This is
called out in three places so it can't be missed by a future reader: this evidence
file, a docstring paragraph on `OrjsonSerializer.dumps` in `kibana/serializer.py`, and a
`strict=True` `xfail` in the unit test matrix (`tests/unit/test_serializer.py`) that
will itself start failing — forcing removal of the marker — the day a cheap-enough fix
is found or orjson adds a native option.

Everything else in #79 (UUID parity on both backends, stdlib's NaN/Infinity fix, the
shared exception type) has no such cost and is fixed below.

## TDD Iron Law: RED matrix first, both backends

"Forcing the stdlib path" for this matrix means instantiating `JSONSerializer`
directly — it's unconditionally defined regardless of whether orjson is installed (see
`kibana/serializer.py`), so no module-reload seam is needed the way the pre-existing
`test_fallback_to_json_serializer_when_orjson_unavailable` needs one (that test targets
*selection* logic — which class `DEFAULT_SERIALIZERS` picks — not *serialization
behavior*, which is what this matrix is about). `tests/unit/test_serializer.py` already
splits `TestJSONSerializer`/`TestOrjsonSerializer` this way; the new matrix reuses that
same seam.

Matrix: `{stdlib, orjson}` x `{NaN, +Inf, -Inf, nested-NaN, NaN-in-list}` for
non-finite floats, `{stdlib, orjson}` x `{UUID, UUID-in-list, nested-UUID,
cross-backend-value-equality}` for UUID parity, plus one direct cross-backend equality
test for a normal body.

### RED (fix stashed back to pre-fix `kibana/serializer.py`; test file at HEAD)

```
$ git stash push -m "wu8: serializer.py fix (stash to prove RED first)" -- kibana/serializer.py
$ .venv/bin/pytest tests/unit/test_serializer.py -q --no-cov
...
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_top_level_non_finite_float_raises_serialization_error[nan-stdlib]
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_top_level_non_finite_float_raises_serialization_error[inf-stdlib]
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_top_level_non_finite_float_raises_serialization_error[neg-inf-stdlib]
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_nested_non_finite_float_raises_serialization_error[stdlib]
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_non_finite_float_in_list_raises_serialization_error[stdlib]
FAILED tests/unit/test_serializer.py::TestNonFiniteFloatParity::test_stdlib_error_message_shape
FAILED tests/unit/test_serializer.py::TestUUIDSerializationParity::test_uuid_serializes_to_canonical_string[stdlib]
FAILED tests/unit/test_serializer.py::TestUUIDSerializationParity::test_uuid_in_list_serializes_to_canonical_strings[stdlib]
FAILED tests/unit/test_serializer.py::TestUUIDSerializationParity::test_nested_uuid_serializes_to_canonical_string[stdlib]
FAILED tests/unit/test_serializer.py::TestUUIDSerializationParity::test_cross_backend_uuid_output_is_value_identical
10 failed, 32 passed, 5 xfailed in 0.14s
```

Sample failure (UUID, stdlib, pre-fix — the exact bug):

```
TypeError: Object of type UUID is not JSON serializable
kibana/serializer.py:61: TypeError
```

The **5 xfailed** are the orjson non-finite-float cases — `xfail(strict=True)` by
design (see above), and their status is identical before and after the fix (orjson's
NaN handling is unchanged either way, so this is not part of the RED->GREEN delta; it
documents the tracked gap, not a bug this run introduces or fixes). The **32 passed**
are pre-existing tests plus the orjson-side UUID cases, which already worked pre-fix.

### GREEN (fix restored)

```
$ git stash pop
$ .venv/bin/pytest tests/unit/test_serializer.py -q --no-cov
42 passed, 5 xfailed in 0.09s
```

All 10 previously-failing stdlib cases now pass; the 5 orjson non-finite-float xfails
are unchanged (expected — that's the documented, tracked gap, not silently made green).

## Full unit suite + parity suite + lint + hooks (Makefile targets)

```
$ make test
...
kibana/serializer.py    66     10    85%   56, 58, 69, 113-115, 121, 167, 169, 175
----------------------------------------------------------------------------------
TOTAL                13306    760    94%
Required test coverage of 90% reached. Total coverage: 94.29%
3355 passed, 5 xfailed in 17.79s

$ .venv/bin/pytest tests/unit/test_sync_async_parity.py -q --no-cov
144 passed in 0.66s

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage). Passed
```

(`black` reformatted `tests/unit/test_serializer.py` on its first run; re-run was
clean, and `make test`/`make lint` were re-confirmed green after the reformat with no
logic change.)

No sync/async parity allowlist entry needed: `kibana/serializer.py` has no async twin
(it is imported, not duplicated, by both trees), so the whole-tree
name/signature/body guard has nothing new to compare.

## Battle-test (live, mandatory)

Both live probes below force a specific backend on a real, live client by swapping its
transport's registered `application/json` serializer in place
(`client._transport.serializers.serializers["application/json"] = <instance>`) —
the same override mechanism `elastic_transport.Transport(serializers=...)` itself
exposes, just applied post-construction so one client can be driven through both
backends without reconstructing it. All spaces created are deleted in a `finally`
block; deletion was confirmed to have run for every space actually created.

**Recorder note (a real environment-research catch during this run):** the existing
`tests/integration/test_space_validation_integration.py::record_requests` wraps
`Transport.perform_request` — correct for proving kibana's own pre-transport
validation (e.g. space-id format checks) never calls the transport at all, because
those checks run *before* kibana's code ever calls `self._transport.perform_request`.
It is the **wrong layer** to prove "zero bytes left the process" for a *serialization*
exception, because `Transport.perform_request` calls `self.serializers.dumps(...)`
**internally**, before ever reaching a node — wrapping it only proves
"`Transport.perform_request` was entered", not "a request left the process". This was
caught empirically, not by re-reading docs: an initial pass using that recorder showed
a `POST` as "sent" for the pre-fix stdlib UUID `TypeError` case, which is provably
false (the exception is raised while building `request_body`, several lines before
`node.perform_request(...)` is ever reached in `elastic_transport`'s
`Transport.perform_request` source). The battle test below instead wraps each real
node's `perform_request` (`Urllib3HttpNode.perform_request`, the actual HTTP-issuing
call) — the true "did a request leave the process" boundary — and every assertion
uses that recorder.

### Pre-fix baseline (fix stashed back to pre-fix `kibana/serializer.py`)

```
$ git stash push -m "wu8: stash fix for pre-fix baseline battle test" -- kibana/serializer.py
```

```
BACKEND = stdlib: NaN-bearing body
  RESULT: kibana.exceptions.BadRequestError raised
  message: [400] Invalid request payload JSON format
  Requests that actually reached a node: [('POST', '/api/spaces/space')]

BACKEND = orjson: NaN-bearing body
  RESULT: kibana.exceptions.BadRequestError raised
  message: [400] [request body.description]: expected value of type [string] but got [null]
  Requests that actually reached a node: [('POST', '/api/spaces/space')]

BACKEND = stdlib: UUID-bearing body
  RESULT: builtins.TypeError raised
  message: Object of type UUID is not JSON serializable
  Requests that actually reached a node: []

BACKEND = orjson: UUID-bearing body
  RESULT: no exception raised.
  HTTP status: 200
  fetched description == str(marker): True
  fetched description: '9d471d4e-a342-4ca4-bd42-c7f08ef56565'
  Requests that actually reached a node: [('POST', '/api/spaces/space'), ('GET', '/api/spaces/space/kbnpy-serializer79-uuid-orjson-142cfc42')]
```

Read carefully, this confirms the issue exactly, plus one nuance worth recording
honestly rather than smoothing over: pre-fix stdlib sends a real, malformed-JSON POST
that Kibana 400s on ("Invalid request payload JSON format") — matching the issue's
"stdlib emits the invalid-JSON token, Kibana rejects with 400". Pre-fix orjson *also*
sends a real POST (with `description` silently turned to `null`), and in this specific
case Kibana's own schema also rejects it with a 400 — but a **different, misleading**
one: `"expected value of type [string] but got [null]"` never mentions NaN, because by
the time Kibana sees the body, the NaN is already gone. A caller staring at that error
would have no way to know their actual input was `NaN` — the client already discarded
that fact silently before the request was ever built. That is the real harm target #1
of this issue describes: not merely "no error", but "the wrong error, blaming a value
the caller never provided, while the actual one is already lost". (A genuinely
schema-loose field would show a plain 200 with `null` silently stored instead; this
field's strict-string schema happens to catch the corruption downstream, but the
client-side silent data loss it's reacting to is the same either way.)

The stdlib UUID `TypeError` case (`Requests that actually reached a node: []`) is the
proof the node-level recorder was worth building: **zero** requests reached a node —
the pre-fix bug already failed closed for UUID (no bad request escaped), it just failed
with the wrong exception type instead of cleanly.

### Post-fix

```
$ git stash pop   # fix restored
```

```
BACKEND = stdlib: NaN-bearing body
  RESULT: kibana.exceptions.SerializationError raised
  message: Out of range float values are not JSON compliant
  Requests that actually reached a node: []

BACKEND = orjson: NaN-bearing body
  RESULT: kibana.exceptions.BadRequestError raised
  message: [400] [request body.description]: expected value of type [string] but got [null]
  Requests that actually reached a node: [('POST', '/api/spaces/space')]

BACKEND = stdlib: UUID-bearing body
  RESULT: no exception raised.
  HTTP status: 200
  fetched description == str(marker): True
  fetched description: '3ef29cb1-e94f-4afa-a3a7-fa1b9a26df32'
  Requests that actually reached a node: [('POST', '/api/spaces/space'), ('GET', '/api/spaces/space/kbnpy-serializer79-uuid-stdlib-a635c280')]

BACKEND = orjson: UUID-bearing body
  RESULT: no exception raised.
  HTTP status: 200
  fetched description == str(marker): True
  fetched description: 'a94f2550-dfa9-44f4-934b-8922cd811cd9'
  Requests that actually reached a node: [('POST', '/api/spaces/space'), ('GET', '/api/spaces/space/kbnpy-serializer79-uuid-orjson-82a021ba')]

CLEANUP
  deleted space kbnpy-serializer79-uuid-stdlib-a635c280
  deleted space kbnpy-serializer79-uuid-orjson-82a021ba
```

This is (a) and (b) from the mandatory battle-test requirements, both satisfied for the
parts of #79 that were fixed, and the orjson NaN gap shown live and unchanged (exactly
the documented BLOCKED behavior, not silently glossed over):

- **(a) UUID-bearing body accepted by real Kibana on both backends:** both `stdlib` and
  `orjson` now create a real space (HTTP 200) with a `uuid.UUID` object passed directly
  as the `description` field value, and a follow-up `GET` confirms the stored value is
  exactly `str(marker)` on both backends — real create, real fetch, real cleanup.
- **(b) NaN-bearing body raises client-side before any request, both backends:**
  **true for stdlib** — `SerializationError` raised, `Requests that actually reached a
  node: []` (zero, node-level recorder). **Not true for orjson** — this is the BLOCKED
  gap: the request still reaches Kibana with `description` silently turned to `null`,
  identical to the pre-fix baseline above. This divergence remains, by the measured,
  reported decision above, and is not claimed as fixed anywhere in this evidence file,
  the changelog, or the code comments.

Every space created during this evidence run (2 in the post-fix pass; the pre-fix
pass's single successful create was also deleted) was deleted in the script's `finally`
block; the script prints a `deleted space <id>` line per cleanup and no `WARNING:
failed to delete` line appeared in any run.

## Scope & caveats

- The orjson-side NaN/Infinity divergence is a known, intentionally-unfixed gap — not
  an oversight. See "Overhead measurement and BLOCKED decision" above for the
  full reasoning and the three code/test/doc locations that flag it.
- Point-in-time result: Kibana's space-description schema (strict, rejects `null` for
  a `string` field) is current as of 2026-08-01; the client-side guarantees this fix
  adds (stdlib raises before any request; UUID serializes identically on both backends)
  do not depend on that schema detail, but the specific downstream 400 message shown
  for the orjson NaN case could change if Kibana's schema for that field changes.
- Genuinely-unsupported-type handling (a plain custom class, a `set`) is unchanged on
  both backends and out of scope for #79.
