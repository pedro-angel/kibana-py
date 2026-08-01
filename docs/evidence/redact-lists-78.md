# Evidence — `_redact_body_secrets` list/tuple recursion fix (issue #78)

**Date:** 2026-08-01
**Change under test:** `kibana/_sync/client/_base.py` (`_redact_body_secrets`, new
`_redact_body_secrets_sequence` helper) on branch `fix/redact-lists-78`. The async
client (`kibana/_async/client/_base.py`) imports both functions from the sync module
rather than redefining them — there is only **one** implementation, so the fix applies
to both trees without a separate async edit (see "One implementation, not two" below).
**Base commit (pre-fix, `main`):** `928140c`.

## Why

`_redact_body_secrets` recursed into `dict` values but not into `list`/`tuple` values.
A request body shaped like `{"connectors": [{"secrets": {"p": "<fake-secret [redacted
in evidence]>"}}]}` — the exact reproduction shape in the issue — was logged at DEBUG
level with the secret intact, because the loop's `elif isinstance(value, dict)` branch
never fired for the list sitting between the outer dict and the inner one.

## Scope

Only the traversal: recurse into list/tuple elements (dicts and nested lists/tuples
recurse further; scalars pass through unchanged), preserving non-mutating semantics
(a full copy, never touching the caller's original body). **Superseded by the fix
round below:** the redacted copy normalizes list/tuple-shaped values to a **plain**
`list`/`tuple` — not the caller's exact subclass — and both recursion axes (dict and
list/tuple) are capped at a shared max depth. See "Fix round — code-quality review
response" for why and the RED/GREEN evidence. The redacted-key set
(`_SENSITIVE_BODY_KEYS`) and the existing dict-recursion logic (which key) are
unchanged throughout.

## One implementation, not two

The brief named "the async twin" as a second edit site. Checked first
(`kibana/_async/client/_base.py:20-29`): `_redact_body_secrets` and
`_redact_sensitive_headers` are **imported** from `kibana._sync.client._base`, not
hand-duplicated — the async client has no separate copy of this function to drift.
`test_sync_async_parity.py` (whole-tree body-diff guard) only discovers classes named
`*Client`; a bare module-level helper like this one is outside what it walks, and
correctly so here — importing the same object means there is nothing to keep in sync.
Fixing the one definition fixes both `BaseClient.perform_request` and
`AsyncBaseClient.perform_request`, which both call `_redact_body_secrets(body)` at the
same call-site shape. No async-specific code change was needed or made; the "both
trees" requirement is met by testing the fix through both `BaseClient.perform_request`
and `AsyncBaseClient.perform_request` (see the two new integration tests below), not by
editing two copies of a function that doesn't have two copies.

## Fix summary

```python
elif isinstance(value, (list, tuple)):
    # Nesting through a list/tuple (e.g. {"connectors": [{"secrets": {...}}]})
    redacted[key] = _redact_body_secrets_sequence(value)
```

`_redact_body_secrets_sequence(values)` recurses into each element: a `dict` element
goes through `_redact_body_secrets` (dict-recursion, unchanged); a `list`/`tuple`
element recurses into itself; anything else (a scalar) passes through unchanged — no
mutation of the input container or any of its nested dicts/lists at any depth.

**Original round-1 result cast the container back with `type(values)(...)`** so a tuple
input returned a tuple and a list input returned a list; a code-quality review caught
that this crashes (multi-field namedtuple) or silently corrupts (single-field
namedtuple) any tuple *subclass* — see "Fix round" below for the corrected, permanent
policy (plain `list`/`tuple` only, never the caller's exact subclass).

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 25.5.0 |
| Python (unit suite, mypy, hooks, battle-test) | 3.11.15 (`.venv`, editable install) |
| Role | local arm64 macOS dev workstation |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` reachable throughout) |
| Auth | basic auth via `tests/integration/utils.py::create_test_kibana_client` (same config the integration suite uses) |

**CRITICAL environment rule honored:** no command in this evidence run touches ports
`4317`/`4318` (OTel collector ports); every live call targets only
`http://localhost:5601`.

## Test-first evidence (TDD Iron Law)

11 new cases across two files:

- `tests/unit/test_logging.py::TestBodySecretRedaction` (9 cases) — pure-function
  coverage of `_redact_body_secrets`: dict-in-list, non-secret siblings in a list,
  list-in-dict-in-list, tuple elements, deeply-nested mixed list/tuple/dict, a list of
  plain scalars (untouched), empty list and empty tuple (untouched), input-not-mutated,
  and result-is-a-new-object (top level and nested).
- `tests/unit/test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_nested_in_list`
  (sync tree) and
  `tests/unit/test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_nested_in_list`
  (async tree) — integration-level: a real `perform_request`/`await perform_request`
  call with a `{"connectors": [{"name": ..., "secrets": {...}}]}` body, asserting the
  captured DEBUG log contains `[REDACTED]` and the non-secret sibling `name`, and does
  **not** contain the secret value.

### RED (isolated: `_base.py` stashed back to pre-fix; test files stay at HEAD)

```
$ git stash push -m "wu7: isolate _base.py fix for RED capture" -- kibana/_sync/client/_base.py
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction \
    tests/unit/test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_nested_in_list \
    tests/unit/test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_nested_in_list \
    -v --no-cov
...
FAILED test_logging.py::TestBodySecretRedaction::test_tuple_elements_are_redacted
FAILED test_logging.py::TestBodySecretRedaction::test_non_secret_siblings_in_list_untouched
FAILED test_logging.py::TestBodySecretRedaction::test_deeply_nested_mixed_containers
FAILED test_logging.py::TestBodySecretRedaction::test_dict_in_list_is_redacted
FAILED test_logging.py::TestBodySecretRedaction::test_list_in_dict_in_list_is_redacted
FAILED test_logging.py::TestBodySecretRedaction::test_returns_a_copy_not_the_same_object
FAILED test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_nested_in_list
FAILED test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_nested_in_list
8 failed, 3 passed in 0.10s
```

Sample failure (async integration test, showing the cleartext leak the fix removes):

```
AssertionError: assert '<fake-secret [redacted in evidence]>' not in "Making async POST
request ... Request body: {'connectors': [{'name': 'my-webhook', 'secrets':
{'password': '<fake-secret [redacted in evidence]>'}}]} ..."
 +  where '<fake-secret [redacted in evidence]>' is contained here:
   Making async POST request to /api/actions/connector with headers: {...} Request
   body: {'connectors': [{'name': 'my-webhook', 'secrets': {'password': '<fake-secret
   [redacted in evidence]>'}}]}
   Async request completed successfully with status 200 Response body: {'result':
   'success'}
```

The 3 that already passed pre-fix (`test_list_of_scalars_untouched`,
`test_empty_list_and_tuple_untouched`, `test_input_is_not_mutated`) are the
coincidental-identity cases: the pre-fix code never touches list/tuple values at all,
so "leave a list of scalars/empty containers alone" and "never mutate the input"
already held by omission — confirming the RED set isolates exactly the
recursion-into-containers defect, not everything indiscriminately.

### GREEN (fix restored: `git stash pop`)

```
$ git stash pop
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction \
    tests/unit/test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_nested_in_list \
    tests/unit/test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_nested_in_list \
    -v --no-cov
...
11 passed in 0.07s
```

## Parity

```
$ .venv/bin/pytest tests/unit/test_sync_async_parity.py -q --no-cov
144 passed in 0.68s
```

No allowlist entry needed: the fix touches a shared, imported helper function, not a
per-tree `Client` method body, so the whole-tree name/signature/body guard has nothing
new to compare.

## Full unit suite + lint + hooks (Makefile targets)

```
$ make test
3330 passed
Required test coverage of 90% reached. Total coverage: 94.28%

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage). Passed
```

(`black` reformatted the four touched files — `_base.py` and the three test files — on
its first run; re-run was clean, and `make test`/`make lint` were re-confirmed green
after the reformat with no logic change.)

## Battle-test (live, mandatory)

Kibana reachability confirmed first:

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5601/api/status
200
```

Research first (per environment-research): does any real, currently-reachable Kibana
endpoint accept a body where a `secrets`/`password`/`token`/`api_key` key is a list
element's **own** top-level key (not one level deeper)? Checked live:

- `POST /api/actions/connector` (connector create) — `secrets` is a flat top-level key,
  never inside a list.
- `POST /api/saved_objects/_bulk_create` — the wire body (`objects`) is a **bare
  top-level list**, not a dict; `perform_request` only calls `_redact_body_secrets` when
  `isinstance(body, dict)`, so a top-level list body never reaches this function at all
  (it hits the `<%d raw bytes>` fallback instead — a separate, narrower quirk, out of
  this fix's scope, noted here for the record). Empirically confirmed live: a
  `bulk_create` `tag` object with an extra `password` attribute key was rejected by
  Elasticsearch's strict mapping (`strict_dynamic_mapping_exception`), confirming `tag`
  (and similarly-mapped types) reject unknown attribute keys outright.
- `POST /api/actions/connector` with an extra unknown top-level field alongside a valid
  connector body (e.g. `batch_items: [{"secrets": {...}}]`) — confirmed live, rejected:
  `[request body.batch_items]: Additional properties are not allowed`.

**Conclusion, chosen call:** no real, currently-reachable endpoint accepts the exact
list-nested-secrets shape as a genuine 2xx. Per the brief's own fallback ("construct the
closest real call... and say what you chose"), the battle test sends the issue's own
literal reproduction body — `{"connectors": [{"secrets": {"p": "<value>"}}]}` — as a
real `POST /api/actions/connector` request via the client's public
`perform_request()`. Kibana's schema validation rejects it with a real, deterministic
400 (`[request body.name]: expected value of type [string] but got [undefined]`) — this
does not affect what's under test, because the DEBUG log line is emitted by the client
*before* the request goes over the wire (`_base.py`'s debug-logging block runs, then
`self._transport.perform_request(...)` is called), so the log content is fixed
regardless of the server's response. This exercises: (a) real auth headers, (b) a real
socket connection to the live Kibana, (c) the real, unmodified `_redact_body_secrets`
code path, and (d) an exact real semantic rejection rather than a fabricated one — the
same "assert the server's exact rejection" allowance used when a happy path isn't
reachable. The secret value used throughout was an obviously-fake marker string, shown
in this file only as `<fake-secret [redacted in evidence]>` — never the literal
string — per the requirement that evidence files never carry a secret-looking value in
the clear, even a fake one.

### (a) Pre-fix baseline: the secret leaks in cleartext

Reproduced by stashing only `kibana/_sync/client/_base.py` back to `main`'s pre-fix
content (editable install, same interpreter — confirmed the loaded module was the
stashed pre-fix version by grepping it for the recursion branch before running):

```
$ git stash push -m "wip: redact-lists-78 fix, stashed for pre-fix baseline capture" -u
$ grep -n "isinstance(value" kibana/_sync/client/_base.py
        elif isinstance(value, dict):    # <- confirms pre-fix: no list/tuple branch
$ .venv/bin/python -c "
import logging, sys
sys.path.insert(0, 'tests/integration')
from utils import create_test_kibana_client
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('kibana').setLevel(logging.DEBUG)
client = create_test_kibana_client()
body = {'connectors': [{'secrets': {'p': '<fake-secret [redacted in evidence]>'}}]}
try:
    client.perform_request('POST', '/api/actions/connector', body=body)
except Exception as e:
    print('response:', type(e).__name__, e)
"
```

Captured DEBUG log (the fake secret value is replaced below with `<fake-secret
[redacted in evidence]>` in place of the literal string the live run actually used —
this evidence file never carries the secret-looking value in the clear, even though it
was never a real credential):

```
DEBUG:kibana:Making POST request to /api/actions/connector with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: {'connectors': [{'secrets': {'p': '<fake-secret [redacted in evidence]>'}}]}
DEBUG:kibana:Request failed with status 400: [request body.name]: expected value of type [string] but got [undefined]
```

Assertions recorded: `secret_in_log: true` — **the fake secret marker appeared in
cleartext in the DEBUG log** (shown above with the placeholder substituted in), which
is exactly the leak this fix closes, confirmed live against the real client before the
fix.

### (b) Post-fix: the secret is redacted

```
$ git stash pop   # fix restored
$ .venv/bin/python -c "
import logging, sys
sys.path.insert(0, 'tests/integration')
from utils import create_test_kibana_client
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('kibana').setLevel(logging.DEBUG)
client = create_test_kibana_client()
body = {'connectors': [{'secrets': {'p': '<fake-secret [redacted in evidence]>'}}]}
try:
    client.perform_request('POST', '/api/actions/connector', body=body)
except Exception as e:
    print('response:', type(e).__name__, e)
"
```

```
DEBUG:kibana:Making POST request to /api/actions/connector with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: {'connectors': [{'secrets': '[REDACTED]'}]}
DEBUG:kibana:Request failed with status 400: [request body.name]: expected value of type [string] but got [undefined]
```

Assertions recorded: `secret_in_log: false`, `redaction_marker_in_log: true` —
**the same real request, same real 400 rejection, now shows `'secrets': '[REDACTED]'`
instead of the value.** Same server behavior in both runs (the 400 is unrelated to the
fix and unchanged by it), isolating the DEBUG-log content as the only difference.

### (c) Real connector create/delete lifecycle — non-regression on the pre-existing flat-secrets path

Required by the brief ("a connector create uses `secrets`... clean up any created
objects"). A genuinely successful, flat-body connector create (the shape that was
*already* redacted correctly before this fix) followed by delete, run against the
post-fix code, to confirm the list/tuple recursion fix didn't regress the existing
dict-redaction path:

```
$ .venv/bin/python -c "
import logging, sys
sys.path.insert(0, 'tests/integration')
from utils import create_test_kibana_client
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('kibana').setLevel(logging.DEBUG)
client = create_test_kibana_client()
created = client.connectors.create(
    name='kbnpy-redact78-probe-ea99e8ac',
    connector_type_id='.gen-ai',
    config={'apiProvider': 'OpenAI',
            'apiUrl': 'https://example.invalid/v1/chat/completions',
            'defaultModel': 'placeholder-model'},
    secrets={'apiKey': '<fake-secret [redacted in evidence]>'},
)
connector_id = created.body['id']
client.connectors.delete(id=connector_id)
"
```

```
DEBUG:kibana:Making POST request to /api/actions/connector with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: {'name': 'kbnpy-redact78-probe-ea99e8ac', 'connector_type_id': '.gen-ai', 'config': {'apiProvider': 'OpenAI', 'apiUrl': 'https://example.invalid/v1/chat/completions', 'defaultModel': 'placeholder-model'}, 'secrets': '[REDACTED]'}
DEBUG:kibana:Request completed successfully with status 200
DEBUG:kibana:Response body: {'id': '3d402de0-4ff7-4b4b-950b-b1a9be794c89', 'name': 'kbnpy-redact78-probe-ea99e8ac', ...}
```

`create_secret_in_log: false`, `create_redaction_marker_in_log: true`,
`create_status: success` (HTTP 200, connector id
`3d402de0-4ff7-4b4b-950b-b1a9be794c89` created for real), `delete_status: success`
(HTTP 204). Cleanup verified independently — `client.connectors.get(id=...)` after
delete raised `NotFoundError` (404), confirming zero residue left on the stack.

## Scope & caveats

- The top-level-list-body logging quirk noted above (`saved_objects.bulk_create`'s body
  is a bare list, so `perform_request` logs `<%d raw bytes>` — misleadingly counting
  objects, not bytes — instead of calling `_redact_body_secrets` at all) is a related but
  distinct defect from #78 and is out of scope for this surgical fix; noted here for a
  future issue rather than folded into this diff.
- List-vs-tuple distinction (a tuple input redacts to a plain `tuple`, a list input to a
  plain `list`) is kept — pinned by `test_tuple_elements_are_redacted` — but **exact
  subclass preservation is deliberately not attempted** as of the fix round below: see
  that section for why (`type(values)(...)` crashes on multi-field namedtuples and
  silently corrupts single-field ones).
- Point-in-time result: Kibana's connector-creation schema (strict, rejects unknown
  top-level keys) is current as of 2026-08-01; a future Kibana release could change what
  the malformed reproduction body returns, though the DEBUG-log assertion itself does not
  depend on the exact rejection reason.

## Fix round — code-quality review response

A code-quality review of the round-1 fix (commit `98ae2f8`) found 1 BLOCKER + 1 MAJOR +
4 minors, all addressed in the fix-round commit that follows this one on the same
branch (see `git log`).

### [BLOCKER] `type(values)(redacted_elements)` crashes multi-field namedtuples, silently corrupts single-field ones

`_redact_body_secrets_sequence` rebuilt the redacted copy by casting back to the
input's exact type: `type(values)(redacted_elements)`. For a plain `list`/`tuple` this
works (`list(...)`/`tuple(...)` both accept a single iterable argument), but a
namedtuple's `__new__` takes one positional argument **per field**, not one iterable —
so:

- A **multi-field** namedtuple element (e.g. `Point(x=..., y=...)`) raised
  `TypeError: Point.__new__() missing 1 required positional argument: 'y'` — the whole
  list of redacted elements was passed as if it were the first field only, and every
  other field's argument was missing. This propagated all the way out of
  `perform_request`, aborting a real request for no reason other than DEBUG logging
  being enabled.
- A **single-field** namedtuple element (e.g. `Single(value=...)`) did not raise, but
  silently corrupted the value: the entire one-element list was accepted as that one
  field's value, so `Single(value="keep-me")` became `Single(value=["keep-me"])` — a
  scalar silently wrapped in a list, with no exception to signal it.

**Decided fidelity policy (binding, not reopened):** the redacted copy exists only for
safe logging, never to round-trip the caller's exact type back to them. Both
recursion branches now always rebuild a **plain** container:

- The dict branch already did this — `redacted: dict[str, Any] = {}` builds a fresh
  plain `dict` regardless of whether the input was a `dict`, an `OrderedDict`, or any
  other mapping subclass. Unchanged; pinned as a regression test below.
- The list/tuple branch now matches: `type(values)(...)` is gone. A tuple-ish input
  (including any tuple subclass, namedtuples included) normalizes to a plain `tuple`;
  a list input normalizes to a plain `list`.

```python
redacted_elements = [_redact_nested_body_value(v, _depth) for v in values]
return tuple(redacted_elements) if isinstance(values, tuple) else redacted_elements
```

A short comment stating this one fidelity policy now lives in both `_redact_body_secrets`'s
and `_redact_body_secrets_sequence`'s docstrings (cross-referencing each other), so a
future reader touching either branch sees the shared rule and the crash/corruption
history that motivated it.

RED (new namedtuple tests, run against the round-1 code as committed at `98ae2f8`, with
only the fix-round tests added):

```
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction -k "namedtuple" -v --no-cov
...
FAILED test_multi_field_namedtuple_is_redacted_without_raising
  TypeError: Point.__new__() missing 1 required positional argument: 'y'
FAILED test_single_field_namedtuple_does_not_wrap_scalar_in_list
  AssertionError: assert Single(value=['keep-me']) == ('keep-me',)
    At index 0 diff: ['keep-me'] != 'keep-me'
2 failed, 12 deselected in 0.08s
```

GREEN (after the fix):

```
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction -k "namedtuple or ordereddict" -v --no-cov
...
3 passed, 11 deselected in 0.06s
```

(`test_ordereddict_value_normalizes_to_plain_dict`, the regression pin for the
already-correct dict-branch policy, passed both before and after — it isn't new
behavior, it documents the existing one the sequence branch now matches.)

### [MAJOR] No recursion-depth bound on either axis — `RecursionError` out of `perform_request`

Neither `_redact_body_secrets` (dict values) nor `_redact_body_secrets_sequence`
(list/tuple elements) had a depth bound. A ~1000-level-deep request body — plausible
from a deeply nested config blob, not necessarily adversarial — raised
`RecursionError: maximum recursion depth exceeded` out of `perform_request` the moment
DEBUG logging was enabled, aborting the request. This is the same class of defect as
the BLOCKER above (a caller's DEBUG flag causing a real request to fail) but on the
*depth* axis instead of the *type* axis, and it predates this issue entirely — both the
pre-existing dict-only recursion and the new list/tuple recursion added in round 1
shared the same missing bound.

**Fix:** one shared constant, `_MAX_REDACTION_DEPTH = 20`, and a new
`_redact_nested_body_value(value, depth)` helper used by both `_redact_body_secrets`'s
loop and `_redact_body_secrets_sequence`'s comprehension — the single place that
decides, per nested value, whether to recurse (dict → `_redact_body_secrets`,
list/tuple → `_redact_body_secrets_sequence`, either capped) or pass a scalar through
unchanged. Past the cap, a container value is replaced with
`_REDACTION_DEPTH_LIMIT_PLACEHOLDER = "<redaction depth limit>"` instead of being
recursed into further — failing closed (a placeholder in the log) rather than raising.
Extracting one shared helper also means the depth check exists in exactly one place
for both axes, rather than being duplicated (and potentially drifting) across two
loops.

RED (new depth-cap tests, run against the round-1 code):

```
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction -k "deeper_than_cap" -v --no-cov
...
FAILED test_list_deeper_than_cap_uses_placeholder_instead_of_raising
  RecursionError: maximum recursion depth exceeded while calling a Python object
FAILED test_dict_deeper_than_cap_uses_placeholder_instead_of_raising
  RecursionError: maximum recursion depth exceeded while calling a Python object
2 failed, 12 deselected in 0.11s

$ .venv/bin/pytest tests/unit/test_base_client.py::TestLogging -k "pathologically_deep" -v --no-cov
...
FAILED test_debug_logging_pathologically_deep_list_body_does_not_raise
  RecursionError: maximum recursion depth exceeded while calling a Python object
FAILED test_debug_logging_pathologically_deep_dict_body_does_not_raise
  RecursionError: maximum recursion depth exceeded while calling a Python object
    (raised from inside perform_request's own DEBUG-logging block --
    kibana/_sync/client/_base.py:538, logger.debug("Request body: %s", _redact_body_secrets(body)) --
    confirming the crash happens on the real request path, not just the pure helper)
2 failed, 3 deselected in 0.12s
```

GREEN (after the fix):

```
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction -k "deeper_than_cap" -v --no-cov
2 passed, 12 deselected in 0.06s

$ .venv/bin/pytest tests/unit/test_base_client.py::TestLogging -k "pathologically_deep" -v --no-cov
2 passed, 3 deselected in 0.06s
```

The `perform_request`-level tests use a mock transport (per the review's own allowance
— "unit-level with a mock transport is fine") and additionally assert
`mock_transport.perform_request.assert_called_once()`: proof that the request actually
reached the transport instead of aborting during the DEBUG-logging block, which is the
concrete symptom this fixes.

### Minors (same round)

1. **Evidence doc's type-preservation claim requalified.** The "Scope", "Fix summary",
   and "Scope & caveats" sections above were updated in place (not left stale) to state
   the plain-container policy and point here, instead of the round-1 "list stays list,
   tuple stays tuple" phrasing that implied full subclass fidelity.
2. **Mixed-nesting test now asserts the mid-structure tuple stays a tuple.**
   `test_deeply_nested_mixed_containers` gained
   `assert isinstance(redacted["outer"][0], tuple)` — previously it only asserted the
   redacted value was reachable at the right path, not that the container type at that
   level was preserved.
3. **Test-gap minor closed by the BLOCKER's own regression tests** — the namedtuple and
   `OrderedDict` cases above are exactly the missing coverage.
4. **Asymmetry minor closed by the fidelity-policy comment** — both
   `_redact_body_secrets` and `_redact_body_secrets_sequence` now carry a docstring
   paragraph naming the one shared policy (plain containers only) and cross-referencing
   each other, instead of the policy being implicit in one branch's code shape only.

### Full verification after the fix round

```
$ .venv/bin/pytest tests/unit/test_logging.py::TestBodySecretRedaction tests/unit/test_base_client.py::TestLogging -v --no-cov
19 passed in 0.07s

$ make test
3337 passed
Required test coverage of 90% reached. Total coverage: 94.29%

$ .venv/bin/pytest tests/unit/test_sync_async_parity.py -q --no-cov
144 passed in 0.67s

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage). Passed
```

No allowlist entry needed in the parity suite (same reasoning as round 1: this is a
shared, imported helper function, not a per-tree `Client` method body).

### Live re-check: namedtuple-bearing body no longer crashes at the wire

Per the review's required addition. Kibana reachability re-confirmed
(`curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5601/api/status` → `200`)
before running.

**Pre-fix** (`_base.py` stashed back to the round-1 commit `98ae2f8`, same isolation
technique as round 1's baseline capture):

```
$ .venv/bin/python -c "
import logging, sys
from collections import namedtuple
sys.path.insert(0, 'tests/integration')
from utils import create_test_kibana_client
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('kibana').setLevel(logging.DEBUG)
client = create_test_kibana_client()
Point = namedtuple('Point', ['x', 'y'])
body = {'connectors': Point(x={'secrets': {'p': '<fake-secret [redacted in evidence]>'}}, y='keep-me')}
try:
    client.perform_request('POST', '/api/actions/connector', body=body)
except Exception as e:
    print('response:', type(e).__name__, e)
"
```

```
INFO:kibana:Kibana client initialized with 1 node(s)
DEBUG:kibana:Making POST request to /api/actions/connector with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
response: TypeError Point.__new__() missing 1 required positional argument: 'y'
```

Confirms the BLOCKER live: the `"Making POST request..."` header line printed, but the
`"Request body:"` line never did — the `TypeError` was raised *while evaluating the
logging call's own argument* (`_redact_body_secrets(body)`, inside
`logger.debug("Request body: %s", ...)`), aborting `perform_request` before any request
was attempted.

**Post-fix** (fix restored):

```
INFO:kibana:Kibana client initialized with 1 node(s)
DEBUG:kibana:Making POST request to /api/actions/connector with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: {'connectors': ({'secrets': '[REDACTED]'}, 'keep-me')}
response: TypeError Type is not JSON serializable: Point
```

The `"Request body:"` line now prints cleanly — `{'connectors': ({'secrets':
'[REDACTED]'}, 'keep-me')}` — proving the DEBUG-logging path no longer crashes on a
namedtuple-bearing body: the secret is redacted, the plain-tuple normalization is
visible (`(...)`, not `Point(...)`), and the sibling scalar `'keep-me'` is untouched.

The **second** `TypeError` (`Type is not JSON serializable: Point`) is a distinct,
pre-existing, and out-of-scope limitation: `elastic_transport`'s request serializer
does not accept a raw namedtuple as a body value (independent of this fix — a plain
`tuple` in the same position serializes to a JSON array without issue, as every other
live capture in this file demonstrates). It fires *after* the DEBUG log line has
already completed successfully, from a completely different code path
(`_transport.perform_request`'s own body serialization, not `_redact_body_secrets`), so
it does not undermine what this probe set out to prove. Noted here for the record, not
folded into this fix: nobody is expected to pass a raw namedtuple as an actual request
body (the fix only needs to stop the *logging* path from crashing on one, which it
now does).
