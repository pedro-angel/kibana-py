# Evidence — http/protobuf trace endpoint fix (issue #77)

**Date:** 2026-07-31
**Change under test:** `kibana/observability/_exporters.py` (new `_get_trace_endpoint`),
`kibana/observability/_config.py` (protocol-aware default endpoint + trace-path wiring),
`kibana/observability/__init__.py` (re-export) on branch `fix/http-trace-endpoint-77`.
**Base commit (pre-fix, "main"):** `ed0bf66`.

## Why

`kibana/observability/_config.py`'s default OTLP endpoint was always the gRPC port
(`http://localhost:4317`) regardless of `protocol`, and the endpoint was passed to
`HTTPOTLPSpanExporter` verbatim — no `/v1/traces` resource path ever got appended —
while `_get_log_endpoint` (`kibana/observability/_exporters.py`) already appended
`/v1/logs` for log forwarding. Net effect: `configure_opentelemetry(protocol="http/protobuf",
endpoint="http://host:4318")` POSTed spans to the bare root, the APM server rejected them
(`405 Method Not Allowed`), and **all traces silently dropped while logs worked** — the
exact scenario in the issue.

## Scope

Only endpoint derivation and protocol-aware defaults, per brief. `_created_log_handlers`,
`enable()` early-return, and the instrumentor singleton (issue #76) are untouched.

## Fix summary

- New `_get_trace_endpoint(base_endpoint, protocol)` in `_exporters.py`, mirroring
  `_get_log_endpoint`: for `http/protobuf` (and its `http` alias), appends `/v1/traces` to
  an endpoint that doesn't already end in it (handling a trailing slash without a double
  slash); gRPC endpoints pass through untouched (gRPC has no HTTP resource path).
  Re-exported from `kibana/observability/__init__.py`.
- `_config.py`'s exporter-creation call now runs the endpoint through
  `_get_trace_endpoint` before calling `_create_otlp_exporter_with_error_handling`. The
  original `endpoint` variable is left unmodified so log forwarding (which appends its own
  `/v1/logs` via `_get_log_endpoint`, later in the same function) still sees the same base.
- The no-endpoint-configured default in `_config.py` is now protocol-aware: `4318` for
  `http`/`http/protobuf`, `4317` for `grpc` — replacing the previous always-`4317` fallback.
  **This same default computation is shared by traces and log forwarding** (`endpoint` is
  threaded into `_setup_log_forwarding(endpoint=endpoint, ...)` later in
  `configure_opentelemetry`), so this one change fixes the identical wrong-default-port
  defect for **both** signals — logs previously also defaulted to `:4317` under
  `http/protobuf` before falling through `_get_log_endpoint`'s `/v1/logs` append, producing
  `http://localhost:4317/v1/logs` instead of `http://localhost:4318/v1/logs`. Confirmed via
  a new unit test (`test_configure_default_endpoint_http_protocol_logs_use_4318`, RED before
  the fix, GREEN after) — no separate logs-specific code change was needed since both
  signals share the same `endpoint` default computed once in `configure_opentelemetry`.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 26.5.2 |
| Dev-venv Python (unit suite, mypy, pre-commit) | 3.11.15 |
| Battle-test Python | 3.13.7 (`.venv` interpreter, same venv as dev — OTLP HTTP + gRPC exporters both installed) |
| Role | local arm64 macOS dev workstation |
| APM server | `http://localhost:8200` (Elastic APM Server 9.4.3, pre-provisioned; confirmed reachable, HTTP 200, before any test ran) |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` returned 200 during the battle test) |
| Elasticsearch | `http://localhost:9200` (used only to query `traces-apm*` for battle-test verification) |

**CRITICAL environment rule honored:** no command in this evidence run ever targets
`localhost:4317` or `localhost:4318` — those ports are owned by an unrelated collector on
this machine. Every live OTLP call below targets only `http://localhost:8200`, the
pre-provisioned APM server. `4317`/`4318` appear only inside the code's *default values*
and inside unit-test assertions of those defaults (mocked, no network I/O) — never as a
live target.

## Test-first evidence (TDD, unit suite)

11 new cases in `tests/unit/test_observability.py` (`TestAPMServerIntegration`), covering
the RED matrix: protocol (http/protobuf × grpc) × default/explicit endpoint ×
trailing-slash × already-has-path, for both traces and the shared logs default.

### RED (against pre-fix code, same working tree before the implementation edit)

```
$ .venv/bin/pytest tests/unit/test_observability.py -k "test_get_trace_endpoint or test_configure_opentelemetry_http_protocol or test_configure_opentelemetry_grpc_protocol_endpoint_untouched or test_configure_opentelemetry_default_endpoint or test_configure_default_endpoint" --no-cov -v
...
FAILED ...test_get_trace_endpoint_grpc_protocol
  ImportError: cannot import name '_get_trace_endpoint' from 'kibana.observability'
FAILED ...test_configure_opentelemetry_http_protocol_appends_v1_traces
  AssertionError: expected call not found.
  Expected: _create_otlp_exporter_with_error_handling('http://localhost:8200/v1/traces', {}, 'http/protobuf')
    Actual: _create_otlp_exporter_with_error_handling('http://localhost:8200', {}, 'http/protobuf')
FAILED ...test_get_trace_endpoint_with_existing_path
  ImportError: cannot import name '_get_trace_endpoint' from 'kibana.observability'
FAILED ...test_configure_default_endpoint_http_protocol_logs_use_4318
  AssertionError: assert 'http://localhost:4317' == 'http://localhost:4318'
FAILED ...test_configure_opentelemetry_http_protocol_trailing_slash
  AssertionError: expected call not found (endpoint missing /v1/traces)
FAILED ...test_configure_opentelemetry_default_endpoint_http_protocol_uses_4318
  AssertionError: expected call not found.
  Expected: _create_otlp_exporter_with_error_handling('http://localhost:4318/v1/traces', {}, 'http/protobuf')
    Actual: _create_otlp_exporter_with_error_handling('http://localhost:4317', {}, 'http/protobuf')
FAILED ...test_get_trace_endpoint_http_protocol
  ImportError: cannot import name '_get_trace_endpoint' from 'kibana.observability'
7 failed, 4 passed, 91 deselected
```

The 4 that already passed pre-fix are the coincidental-identity cases where the *absence*
of any transform happens to look correct: gRPC endpoints (untouched either way) and an
explicit endpoint already ending in `/v1/traces` (nothing to append either way) —
confirming the RED matrix isolates exactly the defective combinations (http/protobuf ×
missing-path, and the wrong http/protobuf default port for both signals) rather than
failing indiscriminately.

### GREEN (after the fix)

```
$ .venv/bin/pytest tests/unit/test_observability.py -k "test_get_trace_endpoint or test_configure_opentelemetry_http_protocol or test_configure_opentelemetry_grpc_protocol_endpoint_untouched or test_configure_opentelemetry_default_endpoint or test_configure_default_endpoint" --no-cov -v
...
11 passed, 91 deselected

$ .venv/bin/pytest tests/unit/test_observability.py --no-cov -q
102 passed
```

## Full unit suite + lint (Makefile targets)

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3273 passed
Required test coverage of 90% reached. Total coverage: 94.30%

$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ .venv/bin/pre-commit run --files kibana/observability/_config.py kibana/observability/_exporters.py \
    kibana/observability/__init__.py tests/unit/test_observability.py
black.................................................................................Passed
isort.................................................................................Passed
ruff check............................................................................Passed
(all other hooks: Passed)
```

## Battle-test (live, mandatory)

APM server and Kibana reachability confirmed first:

```
$ curl -s -o /dev/null -w "%{http_code}\n" --max-time 3 http://localhost:8200
200
$ curl -s --max-time 3 http://localhost:8200
{"build_date": "2026-06-25T15:29:03Z", ..., "version": "9.4.3"}
```

### (a) Pre-fix baseline: reproduce the 405 on the bare root

Reproduced from a **clean `git worktree` of `main`@`ed0bf66`** (pre-fix code, run via
`PYTHONPATH` pointed at the worktree from a neutral cwd with no local `kibana/` to shadow
it — confirmed the loaded module's `__file__` was inside the worktree before proceeding):

```
$ PYTHONPATH=<worktree> .venv/bin/python -c "
import kibana
assert 'wu5-baseline' in kibana.__file__  # confirmed: worktree module, not the branch
from kibana.observability import configure_opentelemetry, create_span
configure_opentelemetry(
    enabled=True, protocol='http/protobuf',
    endpoint='http://localhost:8200', validate_endpoint=False, logs_enabled=False,
)
span = create_span('wu5.baseline-pre-fix'); span.end()
"
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200 (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
ERROR:opentelemetry.exporter.otlp.proto.http.trace_exporter:Failed to export span batch code: 405, reason: Method Not Allowed
configure_opentelemetry(...) completed WITHOUT EXCEPTION (pre-fix baseline)
```

**Confirmed: pre-fix code POSTs to the bare `http://localhost:8200` root and the APM
server rejects it with `405 Method Not Allowed`.** `configure_opentelemetry` itself doesn't
raise — the failure is silent from the caller's perspective, exactly as the issue
describes.

### (b) Post-fix: http/protobuf spans reach `/v1/traces` and get accepted

Same script, run against the actual `fix/http-trace-endpoint-77` working tree:

```
$ .venv/bin/python -c "
from kibana.observability import configure_opentelemetry, create_span
configure_opentelemetry(
    enabled=True, protocol='http/protobuf',
    endpoint='http://localhost:8200', validate_endpoint=False, logs_enabled=False,
    service_name='kibana-py-wu5-battletest',
)
span = create_span('wu5.postfix-http-protobuf-smoke'); span.end()
"
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py-wu5-battletest (logs: disabled)
configure_opentelemetry(...) completed WITHOUT EXCEPTION (post-fix)
```

No `Failed to export span batch` error this time (contrast with (a)). Queried
Elasticsearch directly for proof of acceptance, not just absence of an error log:

```
$ curl -s -u "elastic:${ES_LOCAL_PASSWORD}" "http://localhost:9200/traces-apm*/_search" \
    -H "Content-Type: application/json" -d '{
  "query": { "match": { "service.name": "kibana-py-wu5-battletest" } },
  "_source": ["service.name","transaction.name","@timestamp","processor.event"]
}'
{
  "hits": { "total": { "value": 1, "relation": "eq" }, "hits": [ {
    "_source": {
      "@timestamp": "2026-07-31T10:13:10.993Z",
      "service": { "name": "kibana-py-wu5-battletest" },
      "processor": { "event": "transaction" },
      "transaction": { "name": "wu5.postfix-http-protobuf-smoke" }
    }
  } ] }
}
```

**1 document found** — the span was accepted by the APM server and indexed into
`traces-apm-default` under the exact transaction name we created. **PASS.**

### (c) Traced client op against Kibana (required combination: http/protobuf export + real Kibana call)

```python
from kibana import Kibana
from kibana.observability import configure_opentelemetry

configure_opentelemetry(
    enabled=True, protocol="http/protobuf", endpoint="http://localhost:8200",
    validate_endpoint=False, logs_enabled=False,
    service_name="kibana-py-wu5-client-op",
)
client = Kibana(
    hosts=[KIBANA_LOCAL_URL], basic_auth=(KIBANA_USERNAME, KIBANA_PASSWORD),
    verify_certs=False,
)
status = client.status.get_status()
client.close()
```

```
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
INFO:kibana:Kibana client initialized with 1 node(s)
INFO:elastic_transport.transport:GET http://localhost:5601/api/status [status:200 duration:0.013s]
Kibana status.get_status() -> ObjectApiResponse
done - traced client op finished
```

ES confirms the auto-instrumented span for this real Kibana call was accepted and indexed,
including the real HTTP status the client observed:

```
$ curl -s -u "elastic:${ES_LOCAL_PASSWORD}" "http://localhost:9200/traces-apm*/_search" \
    -H "Content-Type: application/json" -d '{
  "query": { "match": { "service.name": "kibana-py-wu5-client-op" } },
  "_source": ["service.name","transaction.name","transaction.type","http.response.status_code"]
}'
{
  "hits": { "hits": [ { "_source": {
    "service": { "name": "kibana-py-wu5-client-op" },
    "http": { "response": { "status_code": 200 } },
    "transaction": { "name": "kibana.get", "type": "request" }
  } } ] }
}
```

**PASS** — the traced `client.status.get_status()` call's span (`kibana.get`,
`http.response.status_code: 200`) was exported over `http/protobuf`, accepted by the APM
server, and is queryable from the stack.

### (d) Direct route confirmation: bare root vs. `/v1/traces`

```
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:8200 \
    -H "Content-Type: application/x-protobuf" --data-binary ""
HTTP 405
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:8200/v1/traces \
    -H "Content-Type: application/x-protobuf" --data-binary ""
HTTP 200
```

Confirms the endpoint-shape difference directly at the HTTP layer, independent of the
Python client: the bare root 405s (matches the pre-fix repro in (a)); `/v1/traces` accepts
the POST.

### (e) gRPC path — unit-level config-shape, plus a live bonus (both installed)

Unit level: `test_configure_opentelemetry_grpc_protocol_endpoint_untouched` and
`test_configure_opentelemetry_default_endpoint_grpc_protocol_uses_4317` (both in the GREEN
run above) assert the gRPC endpoint is passed to
`_create_otlp_exporter_with_error_handling` byte-for-byte unchanged, both for an explicit
endpoint and for the no-endpoint default (`http://localhost:4317`).

`opentelemetry-exporter-otlp-proto-grpc` is installed in this dev venv, and the APM server
supports OTLP/gRPC on the same port, so a live export was also run (not required, done as a
bonus per the brief):

```
$ .venv/bin/python -c "
from kibana.observability import configure_opentelemetry, create_span
configure_opentelemetry(
    enabled=True, protocol='grpc', endpoint='http://localhost:8200',
    validate_endpoint=False, logs_enabled=False, service_name='kibana-py-wu5-grpc-smoke',
)
span = create_span('wu5.postfix-grpc-smoke'); span.end()
"
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200 (protocol: grpc)
```

Note the logged endpoint is unchanged (`http://localhost:8200`, no path) — confirming
pass-through. ES confirms this trace was also accepted:

```
$ curl ... -d '{"query": {"match": {"service.name": "kibana-py-wu5-grpc-smoke"}}, ...}'
{ "hits": { "hits": [ { "_source": {
  "service": { "name": "kibana-py-wu5-grpc-smoke" },
  "transaction": { "name": "wu5.postfix-grpc-smoke" }
} } ] } }
```

**PASS** — gRPC export to `:8200` also succeeds end-to-end, unaffected by the fix (as
required: "gRPC path must stay working").

## Scope & caveats

- **`_get_trace_endpoint` is called only from `configure_opentelemetry`**, not from
  `_create_otlp_exporter` itself — mirroring where `_get_log_endpoint` is called (from
  `_setup_log_forwarding`, not from `_create_otlp_log_exporter`). This keeps the endpoint
  helpers as pure, protocol-aware string transforms and the exporter-creation functions
  endpoint-agnostic, consistent with the existing logs architecture.
- **Reconfigure/idempotency semantics untouched, by design** (`_created_log_handlers`,
  `enable()` early-return, the instrumentor singleton) — that is issue #76, owned
  separately.
- **The `validate_endpoint` connectivity check** (`_validate_apm_connectivity`) still
  receives the un-suffixed base `endpoint`. This is intentional and unchanged: it's a raw
  TCP `host:port` reachability probe (see `_validation.py`), not an HTTP-path-aware check,
  so appending a signal path first would have no effect on it either way.
- **Point-in-time result.** OTEL SDK versions and the APM server build (9.4.3) are current
  as of 2026-07-31; a future APM server release could change what the bare root or
  `/v1/traces` return.
