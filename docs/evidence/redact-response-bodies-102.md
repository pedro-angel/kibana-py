# Evidence — response bodies redacted in DEBUG logs (issue #102)

**Date:** 2026-08-03
**Change under test:** `_format_response_body_for_log` in `kibana/_sync/client/_base.py`,
consumed by `_process_response` in both `kibana/_sync/client/_base.py` and
`kibana/_async/client/_base.py`, on branch `fix/redact-response-bodies-102`.
**Base commit (pre-fix):** `adb6d43` (`fix/vocabulary-gate-after-devendor`).
**Runner:** the author, on the local Elastic stack (`kibana-py-es-local`,
`-kibana-local`, `-apm-local`), Kibana at `http://localhost:5601`.

## Why

`_process_response` logged the response body as a bare `str(response.body)`:

```python
# Log response body for debugging (truncate if too large)
body_str = str(response.body)
if len(body_str) > 500:
    body_str = body_str[:500] + "... [truncated]"
logger.debug("Response body: %s", body_str)
```

Nothing on that path passed through the redaction machinery. The request side had been
redacted since #78 (dicts) and #92 (lists/tuples), so a caller could reasonably believe
DEBUG logging was safe — while every secret a Kibana endpoint echoed back was still
written in cleartext. `saved_objects.bulk_create` is the sharp case: it returns the
objects it just created, attributes included, so the exact credential the caller sent
came straight back out.

Both trees were affected, and the two blocks were byte-identical apart from the word
"Async".

## Fix summary

A shared `_format_response_body_for_log` helper, single-sourced in the sync tree and
imported by async (the same arrangement as `_redact_body_secrets` and friends):

- **dict** → `_redact_body_secrets`
- **list / tuple** → `_redact_body_secrets_sequence`
- **bytes / bytearray** → `<N raw bytes>`, never the content — there is no structure to
  redact, and an export endpoint can return NDJSON carrying credentials. This mirrors
  what the request side already does for a raw body. *Behavior change:* previously such
  a body was rendered with `str()`, which showed the bytes.
- **anything else** (notably `str`, from `TextApiResponse`) → `str()` as before; there
  are no fields to redact and the length cap still applies.

**Redaction runs on the object, before rendering.** Truncating first and scrubbing the
string afterwards cannot work — the machinery walks structure, not text — and would emit
the first 500 characters verbatim, secrets included. The 500-character cap and the
`... [truncated]` suffix are unchanged.

Depth cap (`_MAX_REDACTION_DEPTH = 20`) and the fidelity policy come along unchanged,
since the traversal is the same code.

## Unit tests — RED witnessed before the fix

Six new tests, four sync (`tests/unit/test_logging.py`) and two async
(`tests/unit/test_async_base_client.py`). All six failed against the pre-fix tree:

```
FAILED tests/unit/test_logging.py::TestRequestResponseLogging::test_debug_logging_redacts_response_body_secrets
FAILED tests/unit/test_logging.py::TestRequestResponseLogging::test_debug_logging_redacts_list_shaped_response_body
FAILED tests/unit/test_logging.py::TestRequestResponseLogging::test_debug_logging_redacts_response_before_truncating
FAILED tests/unit/test_logging.py::TestRequestResponseLogging::test_debug_logging_binary_response_body_logs_size_not_content
FAILED tests/unit/test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_response_body_secrets
FAILED tests/unit/test_async_base_client.py::TestAsyncLogging::test_debug_logging_redacts_list_shaped_response_body
6 failed, 67 deselected in 4.23s
```

The failures were the defect itself, not setup errors — the secret was present in the
captured log:

```
>       assert "hunter2" not in log_messages
E       assert 'hunter2' not in "Making POST...hunter2'}}]}"
E         'hunter2' is contained here:
E           ssword': 'hunter2'}}]}
```

After the fix: `6 passed`. Full unit suite: **3434 passed** (3428 before, plus these
six), including `tests/unit/test_sync_async_parity.py`. `mypy`: `Success: no issues
found in 103 source files`.

## Live battle-test

A real `saved_objects.bulk_create` against the running stack, creating an
`index-pattern` whose attributes carry `password: "hunter2-live-battletest"`, with the
`kibana` logger captured at DEBUG. The pre-fix baseline is computed from the **same live
response object**, so before and after are one request, not two.

Pre-fix rendering (`str(body)`, then truncate):

```
Response body: {'saved_objects': [{'type': 'index-pattern', 'id': 'kibana-py-102-f7d03bfe-...',
'namespaces': ['default'], 'attributes': {'title': 'battletest-kibana-py-102-f7d03bfe-...',
'password': 'hunter2-live-battletest'}, 'references': [], 'managed': False, ... [truncated]

  secret present in pre-fix rendering: True
```

What this build actually logged, captured from the live call:

```
Response body: {'saved_objects': [{'type': 'index-pattern', 'id': 'kibana-py-102-f7d03bfe-...',
'namespaces': ['default'], 'attributes': {'title': 'battletest-kibana-py-102-f7d03bfe-...',
'password': '[REDACTED]'}, 'references': [], 'managed': False, ... [truncated]

  secret present in captured log:      False
  [REDACTED] present in captured log:  True
  title preserved (non-secret field):  True

VERDICT: PASS
```

The non-secret `title` survives intact, so this is redaction rather than blanket
suppression, and truncation still fires on the same body.

**Teardown:** the script deletes the one `index-pattern` it created and nothing else. No
pre-existing object was touched; the unrelated `macobs-*` containers were not involved.

## Scope note

The error branch (`status >= 400`) logs only the extracted error message, not the body,
so it is unchanged. The raised exception still carries `body=response.body` — that is an
exception payload rather than a log, and out of scope for #102.
