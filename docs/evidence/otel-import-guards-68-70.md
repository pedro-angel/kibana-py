# Evidence — OTEL conditional-import guards (issues #68, #70)

**Date:** 2026-07-31
**Change under test:** `kibana/observability/_imports.py` (+ `kibana/observability/_exporters.py`,
`kibana/observability/__init__.py`) on branch `fix/otel-import-guards`.
**Base commit (pre-fix, "main"):** `8a93b74`.

## Why

- **#68:** `import kibana` raised `ImportError: cannot import name 'HTTPOTLPSpanExporter'
  from 'kibana.observability._imports'` whenever the OTEL SDK was installed but the gRPC
  OTLP exporter package (`opentelemetry-exporter-otlp-proto-grpc`) was not — even for callers
  that only export over OTLP/HTTP. Root cause: the grpc trace exporter was imported
  unconditionally inside the main OTEL try-block, and the block's `except ImportError` never
  bound `OTLPSpanExporter` / `HTTPOTLPSpanExporter`, so a grpc-only failure left both names
  fully unbound at module scope.
- **#70 (sibling, opposite direction):** the *logs* except-branch unconditionally rebound
  `OTLPSpanExporter = None` / `HTTPOTLPSpanExporter = None`, clobbering trace exporters that
  had already imported successfully — so a future private-API rename in the OTEL logs modules
  (`opentelemetry._logs`, `opentelemetry.sdk._logs`) would silently disable trace export too,
  with `OTEL_AVAILABLE` still reporting `True`.

## Fix summary

- The gRPC trace exporter import is now its own nested `try/except` (mirroring the pattern
  already used for the HTTP trace exporter and both log exporters), with a new
  `GRPC_EXPORTER_AVAILABLE` flag. Either exporter being absent degrades only that exporter —
  the rest of the SDK (`TracerProvider`, `Resource`, the other exporter) stays usable.
- The outer trace `except ImportError` branch now binds `OTLPSpanExporter = None` and
  `HTTPOTLPSpanExporter = None` so neither name is ever left unbound (#68).
- The logs `except ImportError` branch no longer touches `OTLPSpanExporter` /
  `HTTPOTLPSpanExporter` at all — it degrades only the logs-specific names (#70).
- `_exporters.py`'s `_create_otlp_exporter` now checks `GRPC_EXPORTER_AVAILABLE` before calling
  `OTLPSpanExporter(...)` (mirroring the pre-existing `HTTP_EXPORTER_AVAILABLE` check on the
  HTTP branch), raising a clear `ImportError` instead of letting `None(**kwargs)` raise an
  opaque `TypeError: 'NoneType' object is not callable` that the broad
  `except Exception` in `_create_otlp_exporter_with_error_handling` would otherwise mask as a
  generic "APM configuration error".

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / Darwin |
| Dev-venv Python (unit suite, mypy, bandit) | 3.11.15 |
| Battle-test venvs (scratchpad matrix) | 3.13.7 |
| Role | local arm64 macOS dev workstation |
| APM server | `http://localhost:8200` (Elastic APM Server 9.4.3, pre-provisioned; confirmed reachable, HTTP 200, before any test ran) |

**CRITICAL environment rule honored:** no test in this evidence run ever targets
`localhost:4317` or `localhost:4318` — those ports are owned by an unrelated collector on this
machine (confirmed: something is listening on `4318`). Every OTLP call below targets only
`http://localhost:8200`, the pre-provisioned APM server.

## Test-first evidence (TDD, unit suite)

Full RED → GREEN detail is in `tests/unit/test_observability.py` (`TestImportGuardMatrix`,
6 subprocess-isolated cases parametrizing the SDK/grpc/http/logs partial-install matrix, plus
`test_create_otlp_exporter_grpc_protocol_raises_clear_error_when_absent`). Summary:

**RED (against pre-fix `_imports.py`/`_exporters.py`)** — 7 failing tests, each for the
expected reason:

```
$ .venv/bin/pytest tests/unit/test_observability.py -k TestImportGuardMatrix --no-cov -q
FAILED ...[baseline-everything-present]              # GRPC_EXPORTER_AVAILABLE didn't exist yet
FAILED ...[issue68-grpc-exporter-absent-sdk-and-http-present]
  AssertionError: `import kibana` failed with blocked=('opentelemetry.exporter.otlp.proto.grpc',):
  ...
  ImportError: cannot import name 'HTTPOTLPSpanExporter' from 'kibana.observability._imports'
FAILED ...[http-exporter-absent-sdk-and-grpc-present]
FAILED ...[issue70-logs-absent-must-not-clobber-trace-exporters]
  assert {'HTTPOTLPSpanExporter_bound': 'False', ...} == {'HTTPOTLPSpanExporter_bound': 'True', ...}
FAILED ...[sdk-entirely-absent-api-only]
FAILED ...[otel-entirely-absent]
6 failed, 84 deselected

$ .venv/bin/pytest tests/unit/test_observability.py -k test_create_otlp_exporter_grpc_protocol_raises_clear_error_when_absent --no-cov -q
FAILED ... AttributeError: <module 'kibana.observability._exporters' ...> does not have the
attribute 'GRPC_EXPORTER_AVAILABLE'
1 failed
```

The `issue68` failure reproduces the exact `ImportError` text from the issue report. The
`issue70` failure shows `HTTPOTLPSpanExporter_bound` flipping from the expected `True` to
`False` — the logs except-branch clobbering a successfully-imported trace exporter.

**GREEN (after the fix):**

```
$ .venv/bin/pytest tests/unit/test_observability.py -k TestImportGuardMatrix --no-cov -v
...6 passed...

$ .venv/bin/pytest tests/unit/test_observability.py --no-cov -q
91 passed
```

## Full unit suite + linters (what CI runs for units)

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3174 passed
Required test coverage of 90% reached. Total coverage: 94.18%

$ .venv/bin/mypy kibana/
Success: no issues found in 102 source files

$ .venv/bin/bandit -r kibana/ -ll -q ; echo exit=$?
exit=0

$ .venv/bin/pip-audit
No known vulnerabilities found

$ .venv/bin/pre-commit run --files kibana/observability/_imports.py kibana/observability/_exporters.py \
    kibana/observability/__init__.py tests/unit/test_observability.py
black.................................................................................Passed
isort.................................................................................Passed
ruff check............................................................................Passed
(all other hooks: Passed)
```

## Battle-test — throwaway venv matrix (scratchpad)

Built under `.../scratchpad/wu1-venvs/`:

- `main-checkout/` — a local `git clone --branch main` of this repo at `8a93b74` (pre-fix).
- `venv-main-repro68/` — Python 3.13.7 venv: `opentelemetry-api` + `opentelemetry-sdk` +
  `opentelemetry-exporter-otlp-proto-http` installed, **grpc exporter absent**, `kibana-py`
  installed editable from `main-checkout/` (i.e. pre-fix code).
- `venv-fix-repro68/` — identical OTEL package set (grpc absent), `kibana-py` installed
  editable from the actual working tree on `fix/otel-import-guards` (post-fix code).

Both venvs' `pip freeze` confirm the target config:

```
opentelemetry-api==1.44.0
opentelemetry-exporter-otlp-proto-common==1.44.0
opentelemetry-exporter-otlp-proto-http==1.44.0
opentelemetry-proto==1.44.0
opentelemetry-sdk==1.44.0
opentelemetry-semantic-conventions==0.65b0
# opentelemetry-exporter-otlp-proto-grpc: WARNING: Package(s) not found (absent, as required)
```

> Note on method: the first run of this comparison accidentally imported the *host* repo's
> `kibana` package instead of each venv's installed one, because Python's `-c` inserts the
> current working directory at `sys.path[0]` and the shell's cwd was the host repo (which
> happens to also contain a top-level `kibana/` directory). Re-run from a neutral directory
> with no `kibana/` subdirectory once this was caught; all results below are from that
> corrected setup, verified via each process's own `kibana.observability._imports.__file__`.

### (a) `import kibana` — main (pre-fix) fails, branch (post-fix) succeeds

```
$ cd wu1-venvs/run   # neutral cwd, no local kibana/ to shadow sys.path
$ venv-main-repro68/bin/python -c "from kibana.observability import _imports as m"
Traceback (most recent call last):
  ...
  File ".../main-checkout/kibana/observability/_exporters.py", line 7, in <module>
    from kibana.observability._imports import (
    ...
ImportError: cannot import name 'HTTPOTLPSpanExporter' from 'kibana.observability._imports'
(.../main-checkout/kibana/observability/_imports.py)

$ venv-fix-repro68/bin/python -c "
import kibana
print('import kibana: SUCCESS')
from kibana.observability import _imports as m
print('OTEL_AVAILABLE=', m.OTEL_AVAILABLE)
print('GRPC_EXPORTER_AVAILABLE=', m.GRPC_EXPORTER_AVAILABLE)
print('HTTP_EXPORTER_AVAILABLE=', m.HTTP_EXPORTER_AVAILABLE)
print('OTLPSpanExporter=', m.OTLPSpanExporter)
print('HTTPOTLPSpanExporter=', m.HTTPOTLPSpanExporter)
"
import kibana: SUCCESS
OTEL_AVAILABLE= True
GRPC_EXPORTER_AVAILABLE= False
HTTP_EXPORTER_AVAILABLE= True
OTLPSpanExporter= None
HTTPOTLPSpanExporter= <class 'opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter'>
```

→ `import kibana` fails on `main` with the exact error from the issue report, and succeeds on
the fix branch with `OTLPSpanExporter` cleanly degraded to `None` while `HTTPOTLPSpanExporter`
stays the real, usable class. **PASS.**

### (b) `configure_opentelemetry(...)` completes without exception, live against the APM server

APM server reachability confirmed before running (single `curl`, non-000 code — no polling
loop needed, it answered immediately):

```
$ curl -s -o /dev/null -w "%{http_code}\n" --max-time 3 http://localhost:8200
200
$ curl -s --max-time 3 http://localhost:8200
{"build_date": "2026-06-25T15:29:03Z", ..., "version": "9.4.3"}
```

Smoke test, run from `venv-fix-repro68` (grpc absent, http present — the #68 repro config),
targeting only `http://localhost:8200`:

```
$ venv-fix-repro68/bin/python -c "
import logging; logging.basicConfig(level=logging.INFO)
from kibana.observability import configure_opentelemetry, create_span
configure_opentelemetry(
    enabled=True, protocol='http/protobuf',
    endpoint='http://localhost:8200', logs_enabled=False,
)
print('configure_opentelemetry(...) completed WITHOUT EXCEPTION')
span = create_span('wu1.otel-import-guard-smoke')
print('create_span ->', span)
span.end()
"
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200 (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py (logs: disabled)
ERROR:opentelemetry.exporter.otlp.proto.http.trace_exporter:Failed to export span batch code: 405, reason: Method Not Allowed
configure_opentelemetry(...) completed WITHOUT EXCEPTION
create_span -> _Span(name="wu1.otel-import-guard-smoke", ...)
```

`configure_opentelemetry(...)` returned normally as required — **PASS** on the stated
acceptance criterion. One honest caveat: the background `BatchSpanProcessor` worker later
logged (not raised) a `405 Method Not Allowed` when it actually POSTed, because the bare
`http://localhost:8200` root isn't the OTLP traces ingest path. This is an **endpoint-shape**
question (whether `configure_opentelemetry` should default/append a signal-specific path),
explicitly owned by #76/#77, not this fix. Confirmed the underlying export pipeline itself is
sound by re-running with the correct path:

```
$ venv-fix-repro68/bin/python -c "
from kibana.observability import configure_opentelemetry, create_span
import time
configure_opentelemetry(
    enabled=True, protocol='http/protobuf',
    endpoint='http://localhost:8200/v1/traces', logs_enabled=False,
)
span = create_span('wu1.otel-import-guard-smoke-explicit-path')
span.end()
time.sleep(2)
print('done')
"
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py (logs: disabled)
done
```

No export error logged this time — end-to-end export to the real APM server succeeds when
given the signal-specific path, confirming the 405 above was purely an endpoint-shape artifact
and not a defect introduced by this fix.

## Scope & caveats

- **Not exhaustive of the full 2×2×2×2 install matrix.** The unit-test parametrization and this
  venv matrix cover the two issues' exact repro configs plus representative boundary cases
  (both exporters present/absent individually, SDK entirely absent, OTEL entirely absent); they
  do not enumerate all 16 combinations. The boundary cases chosen are the ones where the fix
  changes behavior; the omitted combinations are strict subsets of these (e.g. "grpc absent AND
  http absent" is exercised implicitly by the "SDK entirely absent" and "OTEL entirely absent"
  outer-except paths, which are strictly more restrictive).
- **A real package-internal coupling was discovered, not assumed:** the installed
  `opentelemetry-exporter-otlp-proto-grpc` build's trace-exporter module imports
  `opentelemetry.sdk._logs.ReadableLogRecord` internally (shared trace/log encoding code). So
  blocking `opentelemetry.sdk._logs` also breaks the **grpc** trace exporter as a genuine side
  effect — the `issue70` unit test asserts against that real, empirically-observed outcome
  (`GRPC_EXPORTER_AVAILABLE: False`) rather than a naive "nothing else changes" assumption, and
  still proves the point of #70: `HTTPOTLPSpanExporter` (unaffected by that coupling) must
  survive the logs except-branch, and does.
- **Endpoint-shape/path-default behavior is intentionally untouched** — see the 405 note above.
  This fix only changes what gets *imported and bound*, not what URL `configure_opentelemetry`
  builds or validates.
- **Point-in-time result.** OTEL package versions (`opentelemetry-*==1.44.0`) and the APM
  server build are current as of 2026-07-31; a future release could change the internal
  `sdk._logs` coupling noted above.
