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
(a full copy, never touching the caller's original body) and the existing container
type (list stays list, tuple stays tuple). The redacted-key set
(`_SENSITIVE_BODY_KEYS`) and the existing dict-recursion logic are unchanged.

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
element recurses into itself; anything else (a scalar) passes through unchanged. The
result is built as a new list, then cast to `type(values)(...)` so a tuple input
returns a tuple and a list input returns a list — no mutation of the input container or
any of its nested dicts/lists at any depth.

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
- Container-type preservation (list stays list, tuple stays tuple) is a deliberate,
  low-cost choice beyond the letter of the issue, to avoid a redacted log copy silently
  reporting a different Python type than what was actually sent — pinned by
  `test_tuple_elements_are_redacted`.
- Point-in-time result: Kibana's connector-creation schema (strict, rejects unknown
  top-level keys) is current as of 2026-08-01; a future Kibana release could change what
  the malformed reproduction body returns, though the DEBUG-log assertion itself does not
  depend on the exact rejection reason.
