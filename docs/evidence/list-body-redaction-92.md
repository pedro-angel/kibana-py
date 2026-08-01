# Evidence — top-level-list request body redaction fix (issue #92)

**Date:** 2026-08-01
**Change under test:** `kibana/_sync/client/_base.py` and `kibana/_async/client/_base.py`
(`perform_request`'s DEBUG-log block), branch `fix/list-body-redaction-92`.
**Base commit (pre-fix, `main`):** `43654e67bfbca747123ee7a41a235435d88657dd`.

## Why

Issue #92 is the sibling of #78: #78 fixed `_redact_body_secrets` to recurse *into*
lists/tuples nested **inside** a dict-shaped body. This issue is the case #78 didn't
cover — a body that is **itself** a bare list/tuple at the top level, with no wrapping
dict at all. `perform_request`'s DEBUG-log block only called `_redact_body_secrets` when
`isinstance(body, dict)`:

```python
if isinstance(body, dict):
    logger.debug("Request body: %s", _redact_body_secrets(body))
elif body is not None:
    logger.debug("Request body: <%d raw bytes>", len(body))
```

A top-level list body fell straight into the `elif` branch. Redaction never ran, and the
body's actual content was replaced with a `<%d raw bytes>` placeholder that (for a list)
is `len(body)` — the element **count**, not a byte count; a genuinely misleading label,
confirmed empirically below rather than assumed. Net effect: any sensitive key
(`secrets`/`secret`/`password`/`token`/`api_key`/`apikey`) inside an element of a
top-level-list body skipped the redaction path outright, exactly as #78 fixed for the
dict-wrapped case.

## One shared implementation, unlike #78 — both trees needed a real edit

#78's fix lived entirely in one function (`_redact_body_secrets` in the sync module,
imported unmodified by the async client) — so fixing it once fixed both trees with no
second edit. **This issue is different: `perform_request` itself is not shared.**
`kibana/_sync/client/_base.py::BaseClient.perform_request` and
`kibana/_async/client/_base.py::AsyncBaseClient.perform_request` are two independent,
hand-maintained methods (per the project's sync/async parity architecture — no unasync),
each with its own copy of the `isinstance(body, dict)` DEBUG-log block. Both copies had
the identical gap and both needed the identical one-line fix. Confirmed by direct
inspection before editing:

```
kibana/_sync/client/_base.py:585:            if isinstance(body, dict):
kibana/_async/client/_base.py:196:            if isinstance(body, dict):
```

## Fix summary

Both `perform_request` methods gained one `elif` branch, reusing the existing
`_redact_body_secrets_sequence` helper unchanged (no new traversal logic, same shared
`_MAX_REDACTION_DEPTH` cap, same plain-`list`/`tuple`-only fidelity policy #78 already
established):

```python
if isinstance(body, dict):
    logger.debug("Request body: %s", _redact_body_secrets(body))
elif isinstance(body, (list, tuple)):
    logger.debug("Request body: %s", _redact_body_secrets_sequence(body))
elif body is not None:
    logger.debug("Request body: <%d raw bytes>", len(body))
```

`kibana/_async/client/_base.py` additionally imports `_redact_body_secrets_sequence`
from `kibana._sync.client._base` alongside the already-imported `_redact_body_secrets`
(same "imported, not duplicated" pattern the async client already uses for every helper
in this module).

## Enumeration — every non-dict-body call site (requirement #2)

Grepped every `perform_request(...)` call across `kibana/_sync/client/*.py` for the
`# type: ignore[arg-type]` marker mypy forces onto a call whose `body=` argument does not
statically match `NamespaceClient.perform_request`'s declared
`body: dict[str, Any] | None` (the resource-specific wrapper each endpoint module calls
through — narrower than `BaseClient.perform_request`'s own `body: Any | None`). Confirmed
this marker is a reliable, mypy-verified signal (not just a grep heuristic) by
temporarily removing one such comment on a scratch copy of `saved_objects.py` and
re-running `mypy`:

```
kibana/_sync/client/saved_objects.py:697: error: Argument "body" to "perform_request" of
"NamespaceClient" has incompatible type "list[dict[str, Any]]"; expected "dict[str, Any]
| None"  [arg-type]
... (4 more, one per bulk_* method)
Found 5 errors in 1 file (checked 1 source file)
```

21 marked call sites total (sync tree; async tree has the identical 21, same line
shapes). Inspecting each call site's source variable against its function signature
(read directly, not inferred) splits them into exactly two categories:

**LIST bodies — the ones this issue is about (6):**

| Endpoint | File:line (sync) | File:line (async) |
|---|---|---|
| `saved_objects.bulk_create` | `saved_objects.py:697` | `saved_objects.py:634` |
| `saved_objects.bulk_get` | `saved_objects.py:745` | `saved_objects.py:680` |
| `saved_objects.bulk_resolve` | `saved_objects.py:794` | `saved_objects.py:727` |
| `saved_objects.bulk_update` | `saved_objects.py:850` | `saved_objects.py:781` |
| `saved_objects.bulk_delete` | `saved_objects.py:903` | `saved_objects.py:832` |
| `synthetics.bulk_create_params` | `synthetics.py:826` | `synthetics.py:823` |

All six pass a `list[dict[str, Any]]` parameter (`objects=`/`parameters=`) straight
through as `body=`. All six are fixed by the one shared `elif isinstance(body, (list,
tuple))` branch in `perform_request` — no per-endpoint change needed, confirmed by the
live test below exercising `bulk_create`/`bulk_delete` and the unit tests exercising the
shape generically (any top-level list/tuple, not tied to one endpoint's schema).

**BYTES bodies — out of scope, already handled correctly (15):** every other
`# type: ignore[arg-type]` site passes `bytes` (a multipart form body or a raw file
upload), never a list/tuple. Confirmed by reading each function's own signature/body
construction, not inferred from the ignore comment alone:

`apm.upload_sourcemap`, `cases.add_file`, `exception_lists.import_lists`,
`detection_engine.import_rules`, `entity_analytics.upload_monitored_users_csv`,
`entity_analytics.upload_watchlist_csv`, `lists.import_items`,
`saved_objects.import_objects`, `saved_objects.resolve_import_errors`,
`fleet_epm.install_package_by_upload`, `streams.import_content`,
`timeline.import_timelines`, `endpoint.upload`, `endpoint.create_script`,
`endpoint.update_script`.

These already take the (correct, pre-existing) `elif body is not None: <%d raw bytes>`
branch — `len(bytes)` genuinely is a byte count there, unlike the list case — and carry
no sensitive-key redaction concern in scope for this issue (raw file/multipart payloads,
not structured JSON with `secrets`/`password`/etc. keys). Untouched by this fix; not
regressed (`test_perform_request_with_body`-style pre-existing tests for these still
pass, and no bytes-body test in the new/changed set was added or needed).

No other non-dict-body call sites exist outside this marked set: every other `body=`
call site in the sync/async client trees (~270 occurrences) passes a `dict` literal or a
`dict`-typed local variable, unmarked because it type-checks cleanly against
`NamespaceClient.perform_request`'s `dict[str, Any] | None`.

## Test-first evidence (TDD Iron Law)

10 new cases across two files, 5 scenarios × 2 trees (requirement #3: sensitive key
inside a list element, tuple variant, empty list, list of scalars, non-mutation):

- `tests/unit/test_base_client.py::TestLogging` (sync, 5 new methods):
  `test_debug_logging_redacts_secrets_in_top_level_list_body`,
  `test_debug_logging_redacts_secrets_in_top_level_tuple_body`,
  `test_debug_logging_top_level_empty_list_body_does_not_raise`,
  `test_debug_logging_top_level_list_of_scalars_untouched`,
  `test_debug_logging_top_level_list_body_is_not_mutated`.
- `tests/unit/test_async_base_client.py::TestAsyncLogging` — the same 5 as async twins,
  same names, `await`-ing `perform_request`.

### RED (isolated: both `_base.py` files stashed back to pre-fix; test files stay at HEAD)

```
$ git stash push -m "wu13c: isolate _base.py fix for RED/baseline capture (#92)" -- \
    kibana/_sync/client/_base.py kibana/_async/client/_base.py
$ .venv/bin/pytest tests/unit/test_base_client.py::TestLogging \
    tests/unit/test_async_base_client.py::TestAsyncLogging -k "top_level" -v --no-cov
...
FAILED test_async_base_client.py::TestAsyncLogging::test_debug_logging_top_level_empty_list_body_does_not_raise
FAILED test_async_base_client.py::TestAsyncLogging::test_debug_logging_top_level_list_of_scalars_untouched
FAILED test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_in_top_level_tuple_body
FAILED test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_secrets_in_top_level_list_body
FAILED test_base_client.py::TestLogging::test_debug_logging_top_level_list_of_scalars_untouched
FAILED test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_in_top_level_tuple_body
FAILED test_base_client.py::TestLogging::test_debug_logging_top_level_empty_list_body_does_not_raise
FAILED test_base_client.py::TestLogging::test_debug_logging_redacts_secrets_in_top_level_list_body
8 failed, 2 passed, 11 deselected in 0.11s
```

Sample failure, showing the exact pre-fix defect (redaction skipped, content masked
under a mislabeled counter instead of shown redacted):

```
AssertionError: assert '[REDACTED]' in "Making POST request to
/api/saved_objects/_bulk_create with headers: {...} Request body: <2 raw bytes> Request
completed successfully with status 200 Response body: {'saved_objects': []}"
```

Captured DEBUG log for that failure:

```
DEBUG    kibana:_base.py:579 Making POST request to /api/saved_objects/_bulk_create with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true'}
DEBUG    kibana:_base.py:588 Request body: <2 raw bytes>
DEBUG    kibana:_base.py:667 Request completed successfully with status 200
DEBUG    kibana:_base.py:675 Response body: {'saved_objects': []}
```

The 2 that already passed pre-fix (one per tree:
`test_debug_logging_top_level_list_body_is_not_mutated`) are the same coincidental-
identity case #78's evidence noted: the pre-fix code never touches list/tuple values at
all, so "never mutate the input" held by omission — confirming the RED set isolates
exactly the redaction-is-skipped defect, not a broader regression.

### GREEN (fix restored: `git stash pop`)

```
$ git stash pop
$ .venv/bin/pytest tests/unit/test_base_client.py::TestLogging \
    tests/unit/test_async_base_client.py::TestAsyncLogging -k "top_level" -v --no-cov
...
10 passed, 11 deselected in 0.07s
```

## Parity

```
$ .venv/bin/pytest tests/unit/test_sync_async_parity.py -q --no-cov
144 passed in 0.64s
```

**This green run does not, by itself, prove the two new `elif` branches mirror each
other.** `("Kibana", "perform_request")` and `("BaseClient", "perform_request")` are
pre-existing entries in `_BODY_DRIFT_ALLOWLIST` (`tests/unit/test_sync_async_parity.py:402-403`)
— `perform_request` is documented there as *the* sync/async I/O boundary (sync
transport call vs. `await`ed, plus two intentional string-literal differences), so
`test_public_method_bodies_match` skips comparing this method's body in both trees
entirely, before and after this change. The 144-passed run confirms names/signatures
still match and every *other* method pair's body still matches; it says nothing about
whether the new `elif isinstance(body, (list, tuple))` branch is identical in both
trees.

That mirror was instead verified by direct diff/inspection: both branches, read
side by side, are byte-identical modulo surrounding line numbers —
`kibana/_sync/client/_base.py:585-590` and `kibana/_async/client/_base.py:197-202`:

```python
            if isinstance(body, dict):
                logger.debug("Request body: %s", _redact_body_secrets(body))
            elif isinstance(body, (list, tuple)):
                logger.debug("Request body: %s", _redact_body_secrets_sequence(body))
            elif body is not None:
                logger.debug("Request body: <%d raw bytes>", len(body))
```

No allowlist change was made or needed: the exemption already covered this method
before this fix, and remains scoped to the same, pre-existing reason (the sync/await
boundary), not to this new branch specifically.

## Full unit suite + lint + hooks (Makefile targets)

```
$ make test
3423 passed
Required test coverage of 90% reached. Total coverage: 94.41%

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage). Passed
```

(`black` reformatted the two `_base.py` files and one test file on its first run —
collapsing a two-line `logger.debug(...)` call onto one line; re-run was clean, and
`make test`/`make lint` were re-confirmed green after the reformat with no logic change.)

## Battle-test (live, mandatory)

### Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 26.5.2 (kernel report: Darwin 25.5.0) |
| Python (unit suite, mypy, hooks, battle-test) | 3.11.15 (`.venv`, editable install) |
| Role | local arm64 macOS dev workstation |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` reachable throughout) |
| Auth | basic auth via `tests/integration/utils.py::create_test_kibana_client` /
`create_test_async_kibana_client` (same config the integration suite uses) |

**CRITICAL environment rule honored:** no command in this evidence run touches ports
`4317`/`4318` (OTel collector ports, occupied by an unrelated stack component); every
live call targets only `http://localhost:5601`.

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5601/api/status
200
```

### Choosing a saved-object type that actually accepts the probe (environment research first)

The exact endpoint named in the issue, `saved_objects.bulk_create`, was used directly —
no substitution needed, unlike #78 (whose exact reproduction shape hit no reachable
endpoint). But the *first* type tried, `tag`, rejects the probe: its Elasticsearch
mapping is strict (confirmed live, not assumed):

```
$ curl -s -u "elastic:***" http://localhost:9200/.kibana_9.4.3_001/_mapping \
    | python3 -c "... print(props['tag']) ..."
tag -> {"properties": {"color": ..., "description": ..., "name": ...}}
```

No `"dynamic": "false"` on `tag` — an extra `password` attribute key is rejected
(`strict_dynamic_mapping_exception`), matching what #78's evidence already found for
this same type. Checking other registered types' live mappings found several marked
`"dynamic": "false"` (unmapped fields stored, not rejected):

```
url -> {"dynamic": "false", "properties": {"accessDate": ..., "createDate": ..., "slug": ...}}
config -> {"dynamic": "false", ...}
space -> {"dynamic": "false", ...}
```

Chose `url` (Kibana's short-URL saved-object type). Confirmed live with a throwaway
probe (created and immediately deleted, id and value never reused in the timed evidence
runs below) that a `password`-keyed attribute is genuinely accepted end-to-end — a real
2xx create, not a schema-rejected one — which is what the requirement's "clean up
created objects" implies (a real object to clean up, not a 400 that never creates
anything).

### Probe script

`/private/tmp/.../scratchpad/live_bulk_create_probe.py` (temporary, not committed): for a
given phase (`sync`/`async`) and unique id suffix, enables DEBUG logging on the `kibana`
logger, calls `saved_objects.bulk_create` with one `url`-type object carrying a
`password` attribute set to an obviously-fake marker value, prints the create result,
then calls `saved_objects.bulk_delete` on the same id and prints the delete result.

### (a) Pre-fix baseline: redaction skipped, content masked under a mislabeled counter

Isolated by stashing only the two `_base.py` files back to pre-fix content (same
technique as the RED capture above), confirmed by grep before running:

```
$ git stash push -m "wu13c: isolate _base.py fix for RED/baseline capture (#92)" -- \
    kibana/_sync/client/_base.py kibana/_async/client/_base.py
$ grep -n "isinstance(body" kibana/_sync/client/_base.py kibana/_async/client/_base.py
kibana/_sync/client/_base.py:585:            if isinstance(body, dict):    # <- no list/tuple branch
kibana/_async/client/_base.py:196:            if isinstance(body, dict):   # <- no list/tuple branch
$ .venv/bin/python live_bulk_create_probe.py sync baseline-sync-run
$ .venv/bin/python live_bulk_create_probe.py async baseline-async-run
```

Captured DEBUG log, sync tree (async tree's is line-for-line identical modulo the
`async` wording and log line numbers):

```
DEBUG:kibana:Making POST request to /api/saved_objects/_bulk_create with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: <1 raw bytes>
DEBUG:elastic_transport.transport:POST http://localhost:5601/api/saved_objects/_bulk_create [status:200 duration:0.142s]
DEBUG:kibana:Request completed successfully with status 200
DEBUG:kibana:Response body: {'saved_objects': [{'type': 'url', 'id': 'kbnpy-redact92-sync-baseline-sync-run', 'attributes': {'slug': 'kbnpy-redact92-baseline-sync-run', 'url': '/app/kibana', 'password': '<fake-secret [redacted in evidence]>'}, ...}]}
DEBUG:kibana:Making POST request to /api/saved_objects/_bulk_delete with headers: {...}
DEBUG:kibana:Request body: <1 raw bytes>
DEBUG:kibana:Request completed successfully with status 200
DEBUG:kibana:Response body: {'statuses': [{'success': True, 'id': 'kbnpy-redact92-sync-baseline-sync-run', 'type': 'url'}]}
```

Assertions recorded: `redaction_ran: false` — the **request-body** DEBUG log line shows
only `<1 raw bytes>` (the real defect: redaction never runs for a list body, and the
label itself is wrong — `1` is the element count, not a byte count, confirmed since the
real serialized JSON body is far more than 1 byte). This is the exact defect #92
describes: a sensitive key inside a list-body element is never routed through
`_redact_body_secrets`/`_redact_body_secrets_sequence` at all.

**Scope note, recorded honestly:** the `password` value *does* appear in cleartext in
the `Response body:` log line above — but that is Kibana's own bulk_create response
echoing back the object's attributes it just stored, logged by a completely separate,
pre-existing code path (`_process_response`'s `body_str = str(response.body)`, which has
never applied `_redact_body_secrets` to responses, before or after #78, and is not part
of what issue #92 or this fix addresses). This fix's scope is the **request**-body DEBUG
log line only, matching the issue's own fix description ("apply redaction to list-shaped
bodies **at the call boundary**"); response-body redaction is a distinct, out-of-scope
gap, noted here for the record rather than folded into this diff.

### (b) Post-fix: the request body is redacted, non-sensitive fields stay visible

```
$ git stash pop   # fix restored
$ .venv/bin/python live_bulk_create_probe.py sync postfix-sync-run
$ .venv/bin/python live_bulk_create_probe.py async postfix-async-run
```

Sync tree:

```
DEBUG:kibana:Making POST request to /api/saved_objects/_bulk_create with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: [{'type': 'url', 'id': 'kbnpy-redact92-sync-postfix-sync-run', 'attributes': {'slug': 'kbnpy-redact92-postfix-sync-run', 'url': '/app/kibana', 'password': '[REDACTED]'}}]
DEBUG:elastic_transport.transport:POST http://localhost:5601/api/saved_objects/_bulk_create [status:200 duration:0.940s]
DEBUG:kibana:Request completed successfully with status 200
DEBUG:kibana:Response body: {'saved_objects': [{'type': 'url', 'id': 'kbnpy-redact92-sync-postfix-sync-run', 'attributes': {..., 'password': '<fake-secret [redacted in evidence]>'}, ...}]}
DEBUG:kibana:Making POST request to /api/saved_objects/_bulk_delete with headers: {...}
DEBUG:kibana:Request body: [{'type': 'url', 'id': 'kbnpy-redact92-sync-postfix-sync-run'}]
DEBUG:kibana:Request completed successfully with status 200
DEBUG:kibana:Response body: {'statuses': [{'success': True, 'id': 'kbnpy-redact92-sync-postfix-sync-run', 'type': 'url'}]}
```

Async tree (independent `perform_request` copy, same fix applied there too):

```
DEBUG:kibana:Making async POST request to /api/saved_objects/_bulk_create with headers: {'content-type': 'application/json', 'kbn-xsrf': 'true', 'authorization': 'Basic [REDACTED]'}
DEBUG:kibana:Request body: [{'type': 'url', 'id': 'kbnpy-redact92-async-postfix-async-run', 'attributes': {'slug': 'kbnpy-redact92-postfix-async-run', 'url': '/app/kibana', 'password': '[REDACTED]'}}]
DEBUG:elastic_transport.transport:POST http://localhost:5601/api/saved_objects/_bulk_create [status:200 duration:0.796s]
DEBUG:kibana:Async request completed successfully with status 200
DEBUG:kibana:Response body: {'saved_objects': [{'type': 'url', 'id': 'kbnpy-redact92-async-postfix-async-run', 'attributes': {..., 'password': '<fake-secret [redacted in evidence]>'}, ...}]}
DEBUG:kibana:Making async POST request to /api/saved_objects/_bulk_delete with headers: {...}
DEBUG:kibana:Request body: [{'type': 'url', 'id': 'kbnpy-redact92-async-postfix-async-run'}]
DEBUG:kibana:Async request completed successfully with status 200
DEBUG:kibana:Response body: {'statuses': [{'success': True, 'id': 'kbnpy-redact92-async-postfix-async-run', 'type': 'url'}]}
```

Assertions recorded (both trees): `redaction_ran: true`, `secret_in_request_log: false`,
`non_sensitive_fields_visible: true` (`slug`/`url` stay in cleartext), `create_status:
success` (HTTP 200, real objects created), `delete_status: success` (HTTP 200/`success:
true`). Same server behavior in both phases (the create/delete both genuinely succeed
either way) — the DEBUG-log **request**-body content is the only difference, isolating
exactly what this fix changes.

### Cleanup verification

Every phase (baseline sync, baseline async, post-fix sync, post-fix async — 4
create/delete cycles total, one object each) deleted its own object immediately after
creating it, and each delete response showed `'success': True`. Independently
re-verified zero residue left on the stack after all four runs:

```
$ .venv/bin/python -c "
client.saved_objects.find(type='url', search='kbnpy-redact92*', search_fields=['slug'])
"
remaining objects matching probe prefix: 0
```

## Scope & caveats

- **Response-body logging is not redacted at all, before or after this fix** — a
  pre-existing, distinct gap (see the scope note in "(a)" above). Out of scope for #92
  (which is specifically about the request-body DEBUG-log call boundary, matching the
  issue's own "Fix" line), noted here for a future issue rather than folded into this
  surgical diff.
- The 15 bytes-bodied endpoints enumerated above were read and classified but not
  live-tested in this evidence run — they were already correct before this fix (the
  `<%d raw bytes>` branch is accurate for real bytes) and are unchanged by it; the live
  test focuses on the 6 list-bodied endpoints this issue is actually about, exercising
  the named one (`bulk_create`) plus its `bulk_delete` cleanup call on both trees.
- Point-in-time result: Kibana's `url` saved-object type is `dynamic: false`-mapped as of
  9.4.3; a future Kibana release tightening that mapping could require choosing a
  different type for a live reproduction, though the DEBUG-log assertions here don't
  depend on which type was used, only that the create genuinely succeeds.
