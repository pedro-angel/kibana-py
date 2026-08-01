# Evidence — stdlib/orjson request-body JSON serialization parity (issue #79)

**Date:** 2026-08-01
**Change under test:** `kibana/serializer.py` (`JSONSerializer.dumps`, `JSONSerializer._default`,
`OrjsonSerializer.dumps`, `_reject_non_finite_floats`) on branch `fix/serializer-parity-79`.
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
  pinned here with cross-backend equality tests. **NaN/Infinity is now fixed too** —
  `_reject_non_finite_floats` walks the body before handing it to `orjson.dumps` and
  raises the identical `SerializationError`/message stdlib raises. This was initially
  measured as BLOCKED against a >10%-overhead budget; see "Overhead measurement and
  decision record" below for the full reasoning, the coordinator's adjudication that
  reversed that call, and the final, post-wiring numbers.
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
serialize-as-string option (`ijl/orjson#170`, cited here and not filed separately —
this evidence file's reference to it is the tracking record). Design proceeds against
the observation (orjson: no native option exists) rather than hoping a flag would
appear — the fix below is a client-side guard, not a wait for upstream.

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

## Overhead measurement and decision record (orjson-side NaN guard)

### Original measurement and initial BLOCKED call

The task's binding rule as originally stated: measure the overhead of a
pre-serialization finiteness guard on a representative ~10KB body; if overhead is
genuinely prohibitive (**>10%**), stop and report BLOCKED with measurements instead of
shipping a divergence.

Representative body: a nested saved-object-shaped payload (id, type, attributes with a
title/description/150 float config values/panelsJSON string/timestamp, 60 UUID-bearing
references, 10 tags, a top-level score) — **9235 bytes** as orjson-encoded output.

Three mechanisms were built and measured, all using `timeit` with `N=20000` against the
same body object (Python 3.11.15, orjson 3.11.9, same machine as this evidence run):

| Mechanism | Cost alone | Cost + orjson.dumps | Overhead vs. `orjson.dumps` alone |
|---|---|---|---|
| `orjson.dumps` alone (baseline) | — | 6.32 us/call | — |
| Recursive Python walk (`isinstance`, recursion) | 19.98 us/call | 25.99 us/call | **+311.5%** |
| Iterative Python walk (`type() is float`/`type() is dict`, explicit stack, no recursion) | 13.90 us/call | 19.96 us/call | **+215.9%** |
| stdlib C-encoder used purely for validation (`json.dumps(..., allow_nan=False)`, output discarded) | 36.58 us/call | 43.83 us/call | **+594.0%** (worse — building the JSON string, even discarded, costs more than a lean type check) |

All three exceeded the stated 10% budget by more than an order of magnitude — not a
borderline 11-15% call. This was reported BLOCKED with these measurements, plus two
mitigating facts recorded for whoever adjudicated the call: even the *iterative* variant
would leave orjson+guard 1.77x faster than the stdlib fallback this project already
ships automatically when orjson isn't installed, and the absolute added cost (~14 us) is
negligible next to any real network round trip.

### Adjudication (coordinator decision, recorded verbatim)

> BLOCKED adjudicated — decision: SHIP the orjson-side guard (iterative-walk variant).
> Rationale: the 10% budget was set against the wrong denominator (serializer-relative
> cost); the decision metrics are (a) absolute added cost ~14µs per ~9.2KB body — noise
> against millisecond-scale request RTTs, (b) guarded orjson remains 1.77x faster than
> the stdlib fallback the package already ships as an accepted path, and (c) silent
> NaN→null data loss on the majority backend is exactly the defect #79 exists to
> remove — correctness outranks a microbenchmark percentage here.

This reverses the original stop condition: the 10% figure was a ratio against
`orjson.dumps`'s own raw cost, which is a Rust-accelerated call a few microseconds
long — any correctness-preserving Python-level check will look enormous as a
*percentage* of that baseline no matter how it's written, because that percentage
gap is orjson's entire reason to exist. Judged instead against what actually matters
operationally (absolute added latency, and the alternative real-world serializer the
package already ships), the guard is worth it. The original measurements above are
kept, not deleted, because they are the evidence the decision was informed by, not a
mistake being erased.

### A correctness gap found while wiring the guard in, and why the shipped mechanism differs slightly from the originally-measured "iterative" variant

Before wiring the "iterative" variant in verbatim, its container check
(`type(x) is dict`, `type(x) is list or type(x) is tuple`) was checked against what
orjson actually accepts — because shipping a guard with a coverage hole would defeat
the entire point of shipping it for correctness. Confirmed live:

```
>>> from collections import OrderedDict, namedtuple
>>> class MyDict(dict): pass
>>> class MyList(list): pass
>>> orjson.dumps(OrderedDict({"a": 1, "b": float("nan")}))
b'{"a":1,"b":null}'
>>> orjson.dumps(MyDict({"a": 1, "b": float("nan")}))
b'{"a":1,"b":null}'
>>> orjson.dumps({"l": MyList([1, float("nan")])})
b'{"l":[1,null]}'
>>> Point = namedtuple("Point", ["x", "y"])
>>> orjson.dumps({"p": Point(1, float("nan"))})
TypeError: Type is not JSON serializable: Point
>>> class MyFloat(float): pass
>>> orjson.dumps({"v": MyFloat("nan")})
TypeError: Type is not JSON serializable: MyFloat
```

orjson serializes `dict`/`list` **subclasses** (`OrderedDict`, a custom subclass)
exactly like the plain type — silently nulling a non-finite float inside one, same as
it does for a plain `dict`/`list`. A guard using `type(x) is dict` would silently skip
recursing into any of those, reintroducing the exact silent-data-loss bug this guard
exists to close, just scoped to container subclasses — a real, non-hypothetical gap
(e.g. any caller who builds a request body with `collections.OrderedDict` for
deterministic key order). orjson *rejects* real `float`/`tuple`-subclass instances
(`namedtuple`, a custom `float` subclass) outright as unsupported types, so there is no
equivalent silent-null risk on that side — skipping one in the guard just means that
already-obscure case raises orjson's own `TypeError` instead of the guard's
`SerializationError`, never a silent success.

**Shipped mechanism:** the explicit-stack (non-recursive) traversal structure of the
"iterative" variant is kept for its performance win over plain recursion, but the
container checks use `isinstance(value, dict)` / `isinstance(value, (list, tuple))`
instead of `type(value) is ...` — matching orjson's actual acceptance surface. The
float leaf check stays `type(value) is float` (safe, per the reasoning above). This is
`_reject_non_finite_floats` in `kibana/serializer.py`, pinned by a regression test
(`test_non_finite_float_inside_dict_subclass_still_raises`, parametrized over both
backends) in `tests/unit/test_serializer.py`.

### Final overhead measurement (shipped mechanism, post-wiring)

Measured directly against the shipped `OrjsonSerializer.dumps` / `_reject_non_finite_floats`
(not a standalone prototype), same representative ~9.2KB body, `timeit` N=20000, 3
trials for stability:

```
trial 0: raw=6.09us guarded=24.55us stdlib=39.65us overhead=303.4% guarded_vs_stdlib=1.61x
trial 1: raw=6.26us guarded=24.67us stdlib=39.86us overhead=294.3% guarded_vs_stdlib=1.62x
trial 2: raw=6.26us guarded=24.68us stdlib=39.89us overhead=294.3% guarded_vs_stdlib=1.62x
```

**FINAL overhead: ~300% relative to raw `orjson.dumps`** (absolute added cost ~18.4us
on the ~9.2KB representative body: 24.6us guarded vs. 6.2us raw). This is higher than
the originally-measured "iterative" prototype's 215.9%, because the `isinstance`-based
container checks (necessary for correctness — see above) cost a bit more than the
`type() is` checks the original prototype used; the isinstance overhead is the accepted
price of not leaving a subclass-shaped hole in the guard. Guarded orjson remains
**~1.6x faster** than the stdlib fallback this project already ships automatically
when orjson isn't installed (24.6us vs. ~39.7us) — slightly lower than the originally-cited
1.77x for the same reason, but the qualitative conclusion in the adjudication ("guarded
orjson still beats the already-shipped no-orjson path") holds at the corrected number
too.

## TDD Iron Law: RED matrix first, both backends; then RED→GREEN again for the guard

"Forcing the stdlib path" for this matrix means instantiating `JSONSerializer`
directly — it's unconditionally defined regardless of whether orjson is installed (see
`kibana/serializer.py`), so no module-reload seam is needed the way the pre-existing
`test_fallback_to_json_serializer_when_orjson_unavailable` needs one (that test targets
*selection* logic — which class `DEFAULT_SERIALIZERS` picks — not *serialization
behavior*, which is what this matrix is about). `tests/unit/test_serializer.py` already
splits `TestJSONSerializer`/`TestOrjsonSerializer` this way; the new matrix reuses that
same seam.

Matrix: `{stdlib, orjson}` x `{NaN, +Inf, -Inf, nested-NaN, NaN-in-list, NaN-inside-dict-subclass}`
for non-finite floats, `{stdlib, orjson}` x `{UUID, UUID-in-list, nested-UUID,
cross-backend-value-equality}` for UUID parity, one direct cross-backend
exception-type-and-message-identity test, plus one cross-backend equality test for a
normal body.

### RED, round 1 (fix stashed back to pre-fix `kibana/serializer.py`; test file at HEAD)

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

At this point in the history the **5 xfailed** were the orjson non-finite-float cases —
`xfail(strict=True)`, documenting the then-BLOCKED gap. That marker (and this whole
section) has since been superseded by the adjudication above; kept here as the
historical RED record.

### GREEN, round 1 (stdlib + UUID fix restored)

```
$ git stash pop
$ .venv/bin/pytest tests/unit/test_serializer.py -q --no-cov
42 passed, 5 xfailed in 0.09s
```

### RED, round 2 — the guard flips the xfails to XPASS(strict), which pytest reports as a failure

After wiring `_reject_non_finite_floats` into `OrjsonSerializer.dumps` (guard shipped,
xfail markers still in the test file, unmodified from round 1), the 5 previously-`xfail`
cases now pass — and `xfail(strict=True)` turns an *unexpected* pass into a reported
failure, exactly as designed (a stale marker can't silently stay green once its
reason no longer holds):

```
$ .venv/bin/pytest tests/unit/test_serializer.py -q --no-cov
........................................F..FFFF                          [100%]
[XPASS(strict)] Tracked gap (#79): orjson has no native option to reject non-finite
floats; a Python-level guard measured 215-310% overhead on a representative ~9KB
body, over the accepted 10% budget. See docs/evidence/serializer-parity-79.md.
(x5, one per case)
5 failed, 42 passed in 0.07s
```

This is the flip confirmation: **5 xfail→XPASS(strict), i.e. 5 cases that now
genuinely pass** the guard added. The `xfail(strict=True)` markers (and the
`NON_FINITE_BACKENDS`/`_backend_param(..., non_finite=...)` machinery that special-cased
orjson) were then removed from `tests/unit/test_serializer.py`; `NON_FINITE_BACKENDS`
now lists both backends unconditionally, matching `PARITY_BACKENDS`. Two more cases
were added: a `type(x) is dict`-vs-`isinstance` regression pin
(`test_non_finite_float_inside_dict_subclass_still_raises`, both backends) and a direct
cross-backend exception-type-and-message-identity test
(`test_error_type_and_message_identical_across_backends`) for requirement 3.

### GREEN, round 2 (markers removed, matrix now unconditional on both backends)

```
$ .venv/bin/pytest tests/unit/test_serializer.py -q --no-cov
....................................................                     [100%]
52 passed in 0.08s
```

**52 passed, 0 xfailed, 0 skipped** (orjson installed in this environment) — every
non-finite-float case now genuinely passes on both backends, no marker hiding anything.

## Full unit suite + parity suite + lint + hooks (Makefile targets)

Post-guard, final state:

```
$ make test
...
kibana/serializer.py    79     10    87%   94, 96, 107, 151-153, 159, 212, 214, 221
----------------------------------------------------------------------------------
TOTAL                13319    760    94%
Required test coverage of 90% reached. Total coverage: 94.29%
3365 passed in 18.02s

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

(`black` reformatted the touched files on the first hooks run of round 1; re-run was
clean both rounds, and `make test`/`make lint` were re-confirmed green after each
reformat with no logic change.)

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
block; deletion was confirmed to have run for every space actually created, in every
pass (pre-fix, round-1 post-fix, round-2 post-guard).

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

### Pass 1 — pre-fix baseline (fix stashed back to pre-fix `kibana/serializer.py`)

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

### Pass 2 — post-fix, pre-guard (stdlib + UUID fixed, orjson NaN guard not yet wired)

```
$ git stash pop   # round-1 fix restored (stdlib allow_nan=False + UUID; orjson unguarded)
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

At this point (the initial BLOCKED state): stdlib's NaN case now raises client-side
with zero node requests, but orjson's NaN case is unchanged from pre-fix — still a real
POST with `description` silently nulled.

### Pass 3 — post-guard (both backends fixed, current shipped state)

```
$ .venv/bin/python .../battle_test.py   # OrjsonSerializer.dumps now guarded
```

```
BACKEND = stdlib: NaN-bearing body
  RESULT: kibana.exceptions.SerializationError raised
  message: Out of range float values are not JSON compliant
  Requests that actually reached a node: []

BACKEND = orjson: NaN-bearing body
  RESULT: kibana.exceptions.SerializationError raised
  message: Out of range float values are not JSON compliant
  Requests that actually reached a node: []

BACKEND = stdlib: UUID-bearing body
  RESULT: no exception raised.
  HTTP status: 200
  fetched description == str(marker): True
  fetched description: '722155af-92d5-4090-8504-c030b20e2f22'
  Requests that actually reached a node: [('POST', '/api/spaces/space'), ('GET', '/api/spaces/space/kbnpy-serializer79-uuid-stdlib-1f30faaa')]

BACKEND = orjson: UUID-bearing body
  RESULT: no exception raised.
  HTTP status: 200
  fetched description == str(marker): True
  fetched description: 'f5b0dbd2-892a-4c98-abce-b05801b87d96'
  Requests that actually reached a node: [('POST', '/api/spaces/space'), ('GET', '/api/spaces/space/kbnpy-serializer79-uuid-orjson-56d36d5f')]

CLEANUP
  deleted space kbnpy-serializer79-uuid-stdlib-1f30faaa
  deleted space kbnpy-serializer79-uuid-orjson-56d36d5f
```

**This is (a) and (b) from the mandatory battle-test requirements, now both fully
satisfied on both backends:**

- **(a) UUID-bearing body accepted by real Kibana on both backends:** both `stdlib` and
  `orjson` create a real space (HTTP 200) with a `uuid.UUID` object passed directly as
  the `description` field value, and a follow-up `GET` confirms the stored value is
  exactly `str(marker)` on both backends — real create, real fetch, real cleanup.
- **(b) NaN-bearing body raises client-side before any request, both backends:**
  **`SerializationError` raised, `Requests that actually reached a node: []`
  (zero, node-level recorder) — on stdlib *and* orjson**, with the identical message
  `"Out of range float values are not JSON compliant"` on both. This is the change from
  Pass 2: orjson's NaN case no longer reaches Kibana at all, and no longer differs from
  stdlib in exception type or message.

Every space created across all three passes was deleted in the script's `finally`
block; the script prints a `deleted space <id>` line per cleanup and no `WARNING:
failed to delete` line appeared in any run.

## Scope & caveats

- The orjson-side NaN/Infinity divergence is now closed. No known observable
  serialization-semantics divergence remains between the two backends for #79's scope
  (NaN/Infinity/-Infinity, UUID).
- Point-in-time result: Kibana's space-description schema (strict, rejects `null` for
  a `string` field) is current as of 2026-08-01, but no longer load-bearing for this
  fix's guarantees — both backends now reject a non-finite float before any request is
  built, so the specific Kibana-side rejection message is no longer part of what's being
  proven (it only mattered while orjson's path still reached the server, in Pass 1/2
  above).
- Genuinely-unsupported-type handling (a plain custom class, a `set`) is unchanged on
  both backends and out of scope for #79.
- `_reject_non_finite_floats`'s guard is scoped to what the client actually constructs
  request bodies from (`dict`/`list`/`tuple`, including subclasses of the first two;
  `float`; and whatever `JSONSerializer._default`/orjson's native types handle) — it is
  not a general-purpose arbitrary-object walker, matching the scope of #79 itself.
