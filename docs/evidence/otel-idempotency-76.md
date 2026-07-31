# Evidence — `configure_opentelemetry()` idempotency (issue #76)

**Date:** 2026-07-31
**Change under test:** `kibana/observability/_config.py`, `_tracing.py`, `_imports.py`,
`__init__.py` on branch `fix/otel-idempotency-76`.
**Base commit (pre-fix, "main"):** `c139683`.

## Why

Issue #76 reports three independent idempotency defects in
`configure_opentelemetry()`:

1. **Handler stacking.** `_config.py` *read* `_created_log_handlers` through the
   `kibana.observability` package attribute (a snapshot of the empty list, taken at
   import time) but *wrote* the new handlers to `kibana.observability._logging`'s
   module global. Two separate bindings: the cleanup branch never saw anything to
   clean, so every repeat `configure_opentelemetry(..., logs_enabled=True)` attached
   another `OTelLogHandler` to the "kibana" logger — duplicated log export, handlers
   never closed.
2. **Silent no-op reconfigure.** OpenTelemetry installs the global tracer provider
   exactly once per process and refuses every later `set_tracer_provider()`, and
   `KibanaInstrumentor.enable()` early-returned when already enabled. A second
   `configure_opentelemetry()` with a new endpoint therefore built a provider and
   exporter that nothing ever reached — and still logged `OpenTelemetry configured`.
3. **Singleton race.** `KibanaInstrumentor.get_instance()` was an unsynchronized
   check-then-set; racing threads each build their own instance, and an `enable()`
   applied to a loser is lost.

Folded in from the WU1 review: `ConsoleLogExporter` was never bound in the logs
`except`-branch of `_imports.py` (same unbound-name class as #68/#70), plus a
disposition of the "guards catch only `ImportError`" question.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 26.5.2 |
| Role | local arm64 macOS dev workstation |
| Python (unit suite, mypy, hooks, battle test) | 3.11.15 (`.venv`) |
| OpenTelemetry | `opentelemetry-sdk` / `-api` / `-exporter-otlp-proto-http` / `-grpc` all 1.43.0 |
| APM server | `http://localhost:8200` (Elastic APM Server 9.4.3, pre-provisioned; `GET /` returned HTTP 200 with `"version": "9.4.3"` before any test ran) |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` returned 200) |
| Elasticsearch | queried only to count indexed documents (`logs-*`, `traces-apm*`) |
| Dead-port control | `http://localhost:8299` — verified refused (`nc -z localhost 8299` → non-zero) before use, used in (b) to make "which endpoint did the span actually leave by" answerable at the wire |

**CRITICAL environment rule honored:** no command in this evidence run targets
`localhost:4317` or `localhost:4318`. An unrelated collector owns those ports; every
live OTLP call here goes to `:8200` (or to the deliberately dead `:8299` control).

## Empirical probe before designing the fix (problem 2)

The brief's decided direction — "swap span processors on the EXISTING provider" —
was checked against the installed SDK before any code was written, rather than
assumed from documentation. Probe script: `probe.py` (scratchpad), run verbatim:

```
=== Q1: second set_tracer_provider ===
LOG WARNING opentelemetry.trace: Overriding of current TracerProvider is not allowed
  global is p1: True   global is p2: False

=== Q2: shutdown old BatchSpanProcessor, add new one ===
  after first span: A=['span-before-swap']
  -> proc_a.shutdown()
  [A] shutdown() called
  -> emitting span-after-swap (registered procs: 2)
LOG INFO opentelemetry.sdk._shared_internal: Shutdown called, ignoring Span.
  raised: None
  A=['span-before-swap']
  B=['span-after-swap']
  VERDICT Q2: dead processor silent=True, new processor exported=True, no exception=True
  VERDICT Q4: pre-swap tracer works=True

=== Q3: stable delegating wrapper, inner swapped ===
  A3=['s1']
  [A3] shutdown() called
  A3=['s1']
  B3=['s2']
  registered procs on provider: 1
  VERDICT Q3: swap works=True
```

**Which branch reality chose: processor swap is supported — the fix applies cleanly,
no "reconfigure refused" fallback was needed.**

Two viable shapes were confirmed, and the probe decided between them:

- **Q2** (shut down the old `BatchSpanProcessor`, `add_span_processor()` the new
  one) works — the dead processor exports nothing and raises nothing — but the SDK
  offers no way to *remove* a processor, so every reconfiguration leaves another
  dead processor registered forever, each logging `Shutdown called, ignoring Span.`
  for **every span** thereafter.
- **Q3** (register one stable delegating processor once, swap its delegates) is what
  shipped: the provider keeps exactly **1** processor no matter how many times
  configuration is re-applied, superseded exporters are shut down, and there is no
  per-span log noise. Q4 confirms tracers obtained *before* the swap keep working,
  which is what lets `KibanaInstrumentor`'s existing tracer stay valid.

## Fix summary

- `kibana/observability/_tracing.py`
  - `_SwappableSpanProcessor` — a duck-typed span processor (deliberately not a
    subclass: the SDK's `SpanProcessor` is `None` when the optional dependency is
    absent, which would make the `class` statement itself raise) whose delegates can
    be replaced in place, shutting the superseded ones down.
  - `_get_reconfigurable_tracer_provider()` / `_install_span_processors()` — the
    provider lifecycle: reuse-and-swap when kibana-py's provider is still the global
    one; otherwise release the previous configuration's exporters, attach a fresh
    swappable processor and offer the provider to OTel. The return value says whether
    the provider became the *global* one.
  - `KibanaInstrumentor.get_instance()` — double-checked locking on a class-level
    `threading.Lock`.
  - `KibanaInstrumentor.enable()` — "already enabled" is now a no-op only when the
    caller asks for the *same* provider; a different provider rebinds the tracer.
- `kibana/observability/_config.py` — reuses the installed provider instead of
  building an orphan; collects span processors into a list and installs them through
  `_install_span_processors()`; reads *and* writes `_created_log_handlers` through
  `kibana.observability._logging` only; warns (instead of implying success) when
  resource attributes cannot be changed or the global provider belongs to someone
  else; the success line now says `configured` vs `reconfigured` and is reached only
  when something changed.
- `kibana/observability/__init__.py` — stops re-exporting `_created_log_handlers`
  (mutable module state re-exported as a snapshot is precisely how the split binding
  arose); re-exports the two new lifecycle helpers.
- `kibana/observability/_imports.py` — binds `ConsoleLogExporter = None` in the logs
  `except`-branch, and broadens all six guards to `except (ImportError,
  AttributeError)` (see disposition below).

## RED first

Every fix below was written against a failing test (`pytest -p no:randomly`, pre-fix
`kibana/` tree — `git diff main -- kibana/` was empty when these ran):

```
FAILED tests/unit/test_observability.py::TestKibanaInstrumentor::test_get_instance_is_thread_safe
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_repeat_configure_does_not_stack_log_handlers
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_applies_new_endpoint_exporter
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_configure_warns_when_foreign_provider_blocks_install
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[issue70-logs-absent-must-not-clobber-trace-exporters]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[sdk-entirely-absent-api-only]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[otel-entirely-absent]
7 failed, 3 passed, 118 deselected in 1.18s
```

with the failures being the defects themselves, not incidental:

```
E       AssertionError: repeat configure stacked log handlers on the 'kibana' logger: [<OTelLogHandler (WARNING)>, <OTelLogHandler (WARNING)>]
E       assert 2 == 1
E        +  where 2 = len([<OTelLogHandler (WARNING)>, <OTelLogHandler (WARNING)>])

E       AssertionError: get_instance() handed out more than one instance under concurrency
E       assert 16 == 1
E        +  where 16 = len({4552626576, 4552626704, 4552628496, 4552628560, 4552628624, 4552631888, ...})

E       AssertionError: span did not reach the exporter built by the second configure
E       assert [] == ['after-reconfigure']

E         Differing items:
E         {'ConsoleLogExporter_present': 'False'} != {'ConsoleLogExporter_present': 'True'}
```

The corrupted-install cases (`AttributeError` during import) were also confirmed RED
against the pre-fix `_imports.py` (stashed for the check):

```
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_corrupted_install[corrupt-grpc-exporter]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_corrupted_install[corrupt-logs-sdk]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_corrupted_install[corrupt-otel]
3 failed, 128 deselected in 0.52s
```

The transcript above witnesses `test_configure_warns_when_foreign_provider_blocks_install`
— the test of the *abandoned* hard-refusal design (see "Design correction" below).
It is not evidence for the test that shipped in its place, so the shipped test was
re-run against the pre-fix tree (pre-fix `kibana/observability/` checked out from
`c139683`, current tests kept):

```
        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            _configure("http://localhost:8200")
        assert trace.get_tracer_provider() is foreign
>       assert "already installed the global OpenTelemetry tracer" in caplog.text
E       AssertionError: assert 'already installed the global OpenTelemetry tracer' in 'INFO     kibana.observability:_config.py:215 OTLP exporter configured: http://localhost:8200/v1/traces (protocol: htt...abled\nINFO     kibana.observability:_config.py:257 OpenTelemetry configured for service: kibana-py (logs: disabled)\n'
tests/unit/test_observability.py:498: AssertionError
------------------------------ Captured log call -------------------------------
INFO     kibana.observability:_config.py:215 OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
WARNING  opentelemetry.trace:__init__.py:556 Overriding of current TracerProvider is not allowed
INFO     kibana.observability:_tracing.py:141 Kibana OpenTelemetry instrumentation enabled
INFO     kibana.observability:_config.py:257 OpenTelemetry configured for service: kibana-py (logs: disabled)
=========================== short test summary info ============================
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_configure_warns_but_still_exports_under_foreign_provider
1 failed in 0.08s
```

The captured log is the defect in four lines: OTel refuses the override, and
kibana-py logs `OpenTelemetry configured for service` with no mention that the
global provider belongs to someone else.

## Fix round (spec-compliance review)

One MAJOR and six actionable minors, all addressed on the same branch.

**MAJOR — the resource-attribute warning was unexecuted by the whole suite.** No
test reached `_config.py`'s "resource attributes are pinned" branch, so nothing
pinned it. `test_reconfigure_warns_that_resource_attributes_stay_pinned` now
configures twice with different `service_name`s and asserts both halves — the
warning fires, *and* the installed provider keeps the first resource. Witnessed RED
against the pre-fix tree by the same checkout method:

```
        _configure("first-service")
        provider = trace.get_tracer_provider()
        assert provider.resource.attributes["service.name"] == "first-service"
        with caplog.at_level(logging.WARNING, logger="kibana.observability"):
            _configure("second-service")
>       assert "resource attributes" in caplog.text
E       AssertionError: assert 'resource attributes' in 'WARNING  opentelemetry.trace:__init__.py:556 Overriding of current TracerProvider is not allowed\n'
tests/unit/test_observability.py:450: AssertionError
------------------------------ Captured log call -------------------------------
WARNING  opentelemetry.trace:__init__.py:556 Overriding of current TracerProvider is not allowed
=========================== short test summary info ============================
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_warns_that_resource_attributes_stay_pinned
1 failed in 0.08s
```

Pre-fix the only warning in sight is OTel's own `Overriding of current
TracerProvider is not allowed` — logged by the SDK, invisible to a caller reading
kibana-py's output, and never explaining what did or did not apply.

**Minor 1 — the warning over-claimed.** It said resource attributes "keep the values
from the first configuration" full stop, but `_setup_log_forwarding` builds a fresh
`LoggerProvider` on every call, so *forwarded logs do pick up the new attributes*;
only spans are pinned. Warning text, changelog and user guide now say so, and the
test asserts the scoping (`"for spans"`) rather than just the presence of a warning.

**Minor 2 — "configured" vs "reconfigured" was derived from the wrong thing.** It
followed whether the provider was reusable, which is always false when another
component owns the global provider — so that path logged "OpenTelemetry configured"
on *every* call, contradicting the claim this fix makes elsewhere. It now follows
whether kibana-py itself had configured before (`_has_configured_tracer_provider()`,
read before installing anything, since installing is what changes the answer). The
foreign-provider test pins both calls' wording.

**Minor 4 — the corrupted-install cases asserted only that the import survived.**
They now assert the full availability-flag map per case, and those maps are the same
ones the `ImportError` matrix asserts for the same prefixes: degradation must not
depend on which exception a broken install happens to raise. Predicted from the
`ImportError` matrix before running; observed identical.

**Minors 5/6** are changelog and report bookkeeping: the two folded-in `_imports.py`
items now have their own `Fixed` bullet rather than riding along inside the #76
bullet, and the report records the test-count deviation.

Two review findings were resolved by ruling rather than change: the user-guide
section stays (sign-off granted), and the widening of the *outer* import guards to
`AttributeError` stays (intent confirmed; disclosed and tested).

## Battle test (live, mandatory) — pre-fix baseline vs post-fix

Same script (`battle.py`, scratchpad), same live stack, run once against the pre-fix
tree (`git diff main -- kibana/` empty) and again against the final committed tree.

### (a) Double `configure_opentelemetry(logs_enabled=True, protocol="http/protobuf", endpoint="http://localhost:8200", validate_endpoint=False)`

**Pre-fix (baseline):**

```
[a] marker=WU6-LOGMARKER-prefix service=kibana-py-wu6-prefix-logs
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OTLP log exporter configured: http://localhost:8200/v1/logs (protocol: http/protobuf)
[a] after configure #1: OTelLogHandler count on 'kibana' = 1
[a]   handler ids=[4472161616] enabled_flags=[True]
WARNING:opentelemetry.trace:Overriding of current TracerProvider is not allowed
WARNING:opentelemetry._logs._internal:Overriding of current LoggerProvider is not allowed
[a] after configure #2: OTelLogHandler count on 'kibana' = 2
[a]   handler ids=[4472161616, 4472172944] enabled_flags=[True, True]
WARNING:kibana:battle-test log record WU6-LOGMARKER-prefix
[a] flushed; waiting for indexing
[a] Elasticsearch logs-* documents containing WU6-LOGMARKER-prefix: 2
[a]   index=.ds-logs-apm.app.kibana_py_wu6_prefix_logs-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T11:08:40.328Z", "service": {"name": "kibana-py-wu6-prefix-logs"}, "message": "battle-test log record WU6-LOGMARKER-prefix"}
[a]   index=.ds-logs-apm.app.kibana_py_wu6_prefix_logs-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T11:08:40.328Z", "service": {"name": "kibana-py-wu6-prefix-logs"}, "message": "battle-test log record WU6-LOGMARKER-prefix"}
[a] done
```

Two handlers, the first still open (`enabled_flags=[True, True]`), and **two
identical documents** in Elasticsearch for a single `logger.warning(...)` — the
duplicated log export from the issue, observed end to end, not inferred.

**Post-fix:**

```
[a] marker=WU6-LOGMARKER-final service=kibana-py-wu6-final-logs
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OTLP log exporter configured: http://localhost:8200/v1/logs (protocol: http/protobuf)
[a] after configure #1: OTelLogHandler count on 'kibana' = 1
[a]   handler ids=[4554592272] enabled_flags=[True]
WARNING:opentelemetry._logs._internal:Overriding of current LoggerProvider is not allowed
[a] after configure #2: OTelLogHandler count on 'kibana' = 1
[a]   handler ids=[4554600656] enabled_flags=[True]
WARNING:kibana:battle-test log record WU6-LOGMARKER-final
[a] flushed; waiting for indexing
[a] Elasticsearch logs-* documents containing WU6-LOGMARKER-final: 1
[a]   index=.ds-logs-apm.app.kibana_py_wu6_final_logs-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T11:20:51.497Z", "service": {"name": "kibana-py-wu6-final-logs"}, "message": "battle-test log record WU6-LOGMARKER-final"}
[a] done
```

Handler count stays **1** across both calls (the id changes: the first handler was
closed and detached, the second attached), and the record is exported **exactly
once** — 1 document in `logs-apm*` for the unique marker. `Overriding of current
TracerProvider is not allowed` is also gone, because the second call now reuses the
installed provider instead of building an orphan.

### (b) Reconfigure with a changed endpoint

Configure #1 targets the dead control port, configure #2 targets the live APM server
with a distinguishing query parameter (WU5's `_get_signal_endpoint` preserves it), so
"which endpoint did the span actually leave by" is answerable at the wire and not
just by inspection.

**Pre-fix (baseline):**

```
[b] marker=wu6.reconfigure.prefix service=kibana-py-wu6-prefix-traces
INFO:kibana.observability:OTLP exporter configured: http://localhost:8299/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py-wu6-prefix-traces (logs: disabled)
[b] after configure #1 (dead http://localhost:8299): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8299/v1/traces')]
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces?wu6=prefix (protocol: http/protobuf)
WARNING:opentelemetry.trace:Overriding of current TracerProvider is not allowed
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py-wu6-prefix-traces (logs: disabled)
[b] after configure #2 (live http://localhost:8200?wu6=prefix): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8299/v1/traces')]
WARNING:opentelemetry.exporter.otlp.proto.http.trace_exporter:Transient error HTTPConnectionPool(host='localhost', port=8299): Max retries exceeded with url: /v1/traces (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8299): Failed to establish a new connection: [Errno 61] Connection refused")) encountered while exporting span batch, retrying in 0.87s.
WARNING:opentelemetry.exporter.otlp.proto.http.trace_exporter:Transient error HTTPConnectionPool(host='localhost', port=8299): Max retries exceeded with url: /v1/traces (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8299): Failed to establish a new connection: [Errno 61] Connection refused")) encountered while exporting span batch, retrying in 1.99s.
WARNING:opentelemetry.exporter.otlp.proto.http.trace_exporter:Transient error HTTPConnectionPool(host='localhost', port=8299): Max retries exceeded with url: /v1/traces (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8299): Failed to establish a new connection: [Errno 61] Connection refused")) encountered while exporting span batch, retrying in 3.48s.
ERROR:opentelemetry.exporter.otlp.proto.http.trace_exporter:Failed to export span batch due to timeout, max retries or shutdown.
[b] flushed; waiting for indexing
[b] Elasticsearch traces-apm* documents for kibana-py-wu6-prefix-traces: 0
[b] done
```

The reconfigured endpoint never took: the live exporter is still the `:8299` one, the
span is attempted against the dead port (wire-level proof), **0 documents** reach
Elasticsearch — and `OpenTelemetry configured for service: ...` was logged anyway.
That is exactly the false success claim in the issue.

**Post-fix:**

```
[b] marker=wu6.reconfigure.final service=kibana-py-wu6-final-traces
INFO:kibana.observability:OTLP exporter configured: http://localhost:8299/v1/traces (protocol: http/protobuf)
INFO:kibana.observability:Kibana OpenTelemetry instrumentation enabled
INFO:kibana.observability:OpenTelemetry configured for service: kibana-py-wu6-final-traces (logs: disabled)
[b] after configure #1 (dead http://localhost:8299): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8299/v1/traces')]
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces?wu6=final (protocol: http/protobuf)
INFO:kibana.observability:OpenTelemetry reconfigured for service: kibana-py-wu6-final-traces (logs: disabled)
[b] after configure #2 (live http://localhost:8200?wu6=final): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8200/v1/traces?wu6=final')]
[b] flushed; waiting for indexing
[b] Elasticsearch traces-apm* documents for kibana-py-wu6-final-traces: 1
[b]   index=.ds-traces-apm-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T11:20:59.744Z", "service": {"name": "kibana-py-wu6-final-traces"}, "processor": {"event": "transaction"}, "transaction": {"name": "wu6.reconfigure.final"}}
[b] done
```

The exporter reachable from the live provider is now the new one (query parameter
preserved), **not a single `:8299` connection attempt is made** — the superseded
exporter was shut down, not left running — and the span is indexed in
`traces-apm*`. The log line says `reconfigured`.

### (c) Concurrent `get_instance()`

**Pre-fix (baseline):**

```
[c] label=prefix
[c] natural race, 300 rounds x 8 threads: rounds handing out >1 instance = 0
[c] widened window (slow __init__), 16 threads: distinct instances = 16
```

**Post-fix:**

```
[c] label=final
[c] natural race, 300 rounds x 8 threads: rounds handing out >1 instance = 0
[c] widened window (slow __init__), 16 threads: distinct instances = 1
```

Stated honestly: **the natural race did not reproduce in 300 rounds × 8 threads on
either tree** — under CPython's GIL the check-then-set window is very narrow, so
"0 bad rounds" is not evidence the code was safe. The defect is demonstrated
deterministically by widening the window (a `__init__` that sleeps, so every thread
that passed `is None` is inside the constructor together): 16 of 16 threads got
distinct instances pre-fix, 1 shared instance post-fix. The unit test uses the same
widened window for the same reason — a test that only passes because the scheduler
was kind is not a test.

## Gates

```
$ make test
============================ 3299 passed in 14.29s =============================
Required test coverage of 90% reached. Total coverage: 94.33%

$ .venv/bin/python -m pytest tests/unit -q --no-cov      # full unit suite, random order
3302 passed in 8.46s

$ .venv/bin/python -m pytest tests/unit/test_sync_async_parity.py -q --no-cov
144 passed in 0.64s

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
black.................................................................................Passed
isort.................................................................................Passed
ruff check............................................................................Passed
no secret-looking file is tracked by git..............................................Passed
every Action is SHA-pinned, one pin per action repo-wide..............................Passed
no private identifier (hostname, internal name) enters the repo.......................Passed
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage).......................Passed
```

(3299 vs 3302 is the coverage run vs the final run: three tests — the
corrupted-install matrix cases — were added between the two.)

## Design correction found while implementing

The first implementation of problem 2 treated "another component owns the global
tracer provider" as a hard refusal: warn and return without configuring anything.
Re-reading the pre-fix behavior showed that would be a **regression**, not a fix:
pre-fix, `enable()` was handed kibana-py's own (non-global) provider, so kibana-py's
spans *were* exported in that scenario — only the *global* provider registration
failed. Refusing outright would have stopped exporting spans (and stopped setting up
log forwarding) for any application that configures its own OpenTelemetry before
calling `configure_opentelemetry()` — a common shape, not an exotic one.

The shipped behavior keeps the pre-fix capability and makes the caveat explicit: the
warning states that kibana-py is tracing through a provider of its own and that
`trace.get_tracer_provider()` still returns the other component's provider.
`test_configure_warns_but_still_exports_under_foreign_provider` pins both halves —
the warning *and* that spans still reach kibana-py's exporter, including after a
reconfiguration.

## Disposition — nested import guards caught only `ImportError`

**Fixed, not merely recorded.** A *missing* distribution raises `ImportError`, which
the guards handled; a *corrupted or version-mismatched* one executes its module body
and raises whatever that raises — classically `AttributeError` against a dependency
that no longer exports some symbol — which propagated straight out of `import
kibana` for every user of this client, whether or not they opted into observability.
All six guards in `_imports.py` now catch `(ImportError, AttributeError)`. The
blast radius of the broadening is bounded by construction: those `try` blocks
contain nothing but `import` statements, so the only thing a broadened `except` can
swallow is a broken third-party install — precisely the case the guards exist for.
Covered by `test_import_kibana_under_corrupted_install` (3 parametrized cases, RED
pre-fix as shown above).

## Round 2 (code-quality review) — two regressions into #76's own failure class

The code-quality review found two MAJORs, both introduced by the round-1 fix
itself, and both a re-entry into the defect this issue is about: *a call that
reports success and silently stops exporting*. Both were probe-verified by the
reviewer and are now pinned by tests that were witnessed failing against the
round-1 commit (`baf2461`) — pre-round-2 `kibana/observability/` restored,
round-2 tests kept:

```
        assert tracer is not None
>       assert working.exported == ["still-exporting"], (
E       AssertionError: the working exporter must survive a configuration that creates no exporter of its own
E       assert [] == ['still-exporting']

        assert tracer is not None
>       assert second.exported == ["after-repair"], (
E       AssertionError: the reconfigured exporter must actually receive spans, not be swapped into a processor registered on nothing
E       assert [] == ['after-repair']

            assert not failures, f"round {round_index}: {failures!r}"
            assert provider is not None and processor is not None
>           assert trace.get_tracer_provider() is provider, (
E           AssertionError: round 1: tracked provider is not the global one
E           assert <opentelemetry.sdk.trace.TracerProvider object at 0x10c257ad0> is <opentelemetry.sdk.trace.TracerProvider object at 0x10c172f90>
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_without_a_span_exporter_keeps_the_working_config
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_repairs_a_mismatched_tracked_pair
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_concurrent_first_configure_publishes_a_consistent_pair
3 failed in 0.12s
```

**MAJOR 1 — an empty exporter list was applied.** A reconfiguration that
produced no span processors (an unrecognized `exporter` value such as a
miscased `"OTLP"`, or a console exporter that failed to construct) called
`swap(())`: it shut the working exporter down, exported nothing, and logged
"reconfigured". Pre-#76 code kept exporting in that situation. Fixed: an empty
processor list is never installed over an existing configuration — it warns and
leaves the running exporters alone — and on a first configuration it warns that
no spans will be exported. `exporter` is also normalized and validated now
(minor 1), which removes the most likely way to reach the empty case by
accident.

**MAJOR 2 — the tracked provider/processor pair could be published
inconsistently.** They were two module globals assigned in sequence with no
lock across the read-check-install sequence, so two threads doing a first
configure could interleave into (thread A's provider, thread B's processor).
Every later reconfiguration then swapped exporters into a processor registered
on nothing while spans kept flowing out of the old exporter — success logged,
nothing changed. Fixed: one name holds the pair, published in a single
assignment under a module-level reentrant lock that spans the whole
read-check-install-publish sequence; a caller whose provider lost the race gets
the winner's provider back (and its own is shut down rather than left with a
live atexit hook); and a pair that is inconsistent anyway is *repaired* — the
orphan is released and a fresh processor attached to the provider that is
genuinely global — with a warning, instead of being swapped into. The threaded
test reproduced the race naturally on the round-1 commit (the transcript's
`round 1` is the loop's zero-based index — the *second* of 25 rounds), so
this one is not a scheduling-luck regression guard: it is a witnessed failure.

Ten minors were fixed in the same round: `exporter` normalization/validation;
`force_flush` sharing one deadline across delegates with no short-circuit;
`swap()` documenting its two accepted residuals (a span that captured the old
delegate tuple can be dropped by a just-shut-down delegate; releasing the
superseded delegate is synchronous and can stall up to the SDK's 30s join
against a dead endpoint — off-thread release is a recorded non-goal);
`shutdown()` clearing its delegates under the lock and un-publishing the pair;
the `TracerProvider` no longer being built before the early-return paths that
abandon it (it registers an atexit flush on construction); `_cleanup_log_handlers`
iterating a snapshot of `loggerDict` and reporting failures at WARNING (a
handler it fails to detach keeps exporting, which is the duplicate-export
defect); an in-code note for the deliberately-not-shut-down superseded
`LoggerProvider` (the first one installed is the process-global one that
unrelated code may hold loggers from — reclaiming one idle thread is not worth
breaking them); the user-guide claim softened from "exported exactly once" to
"no record is exported twice", naming the detach→attach window; the import
guards widened from `(ImportError, AttributeError)` to `Exception` (the
real-world corrupted-protobuf failure is `TypeError`, and guessing exception
types is how a guard stops guarding) with a WARNING that says the package *is*
installed rather than advising an install; and the unit fixture now saves and
restores the "kibana" logger level, which a real log-forwarding run otherwise
pins at WARNING for the whole session.

### Live re-run after round 2 (the reconfigure path changed)

```
[a] after configure #1: OTelLogHandler count on 'kibana' = 1
[a]   handler ids=[4544241104] enabled_flags=[True]
WARNING:opentelemetry._logs._internal:Overriding of current LoggerProvider is not allowed
[a] after configure #2: OTelLogHandler count on 'kibana' = 1
[a]   handler ids=[4544249168] enabled_flags=[True]
WARNING:kibana:battle-test log record WU6-LOGMARKER-round2
[a] Elasticsearch logs-* documents containing WU6-LOGMARKER-round2: 1
[a]   index=.ds-logs-apm.app.kibana_py_wu6_round2_logs-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T12:19:21.695Z", "service": {"name": "kibana-py-wu6-round2-logs"}, "message": "battle-test log record WU6-LOGMARKER-round2"}

[b] after configure #1 (dead http://localhost:8299): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8299/v1/traces')]
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces?wu6=round2 (protocol: http/protobuf)
INFO:kibana.observability:OpenTelemetry reconfigured for service: kibana-py-wu6-round2-traces (logs: disabled)
[b] after configure #2 (live http://localhost:8200?wu6=round2): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8200/v1/traces?wu6=round2')]
[b] Elasticsearch traces-apm* documents for kibana-py-wu6-round2-traces: 1
[b]   index=.ds-traces-apm-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T12:19:29.932Z", "service": {"name": "kibana-py-wu6-round2-traces"}, "processor": {"event": "transaction"}, "transaction": {"name": "wu6.reconfigure.round2"}}
```

Unchanged from the round-1 result: one handler and one indexed log document
after two configure calls; the live exporter swapped to the new endpoint with
its query parameter preserved; the span indexed in `traces-apm*`; and not one
connection attempt to the superseded `:8299` endpoint.

## Round 3 (code-quality re-review) — the same refusal, now under the lock

The re-review confirmed MAJOR 2 as addressed and found MAJOR 1 addressed only
*sequentially*: the empty-processor decision was read at the top of
`configure_opentelemetry` and acted on ~90 lines later, while installs happen
under `_provider_lock`. A configuration published in that window was still torn
down by a no-exporter call, and **both** calls logged success. Witnessed against
the round-2 commit (`d8c9b11`) with the interleaving forced rather than hoped
for — the no-exporter call is parked at the install boundary, after every
decision it makes, and only then does the working configuration land:

```
        assert not no_exporter_thread.is_alive()
        assert tracer is not None
>       assert working.exported == ["survived-the-race"], (
E       AssertionError: a concurrent no-exporter call tore down the working exporter
E       assert [] == ['survived-the-race']
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_concurrent_no_exporter_configure_cannot_tear_down_a_working_one
1 failed in 0.08s
```

**The fix moves the decision to where the truth is.** `_install_span_processors`
now owns it: it takes `_provider_lock`, reads the tracked state there, and
refuses an empty processor list under that lock. It also takes the provider as a
*factory* rather than a provider, so the branch that does not install never
constructs one (a `TracerProvider` registers an atexit flush on construction).
It returns an `_InstallOutcome` — provider in use, `is_global`, `applied`,
`reconfigured`, `global_slot_is_ours` — and every message the caller emits is
now phrased from those locked observations. The pre-lock `reconfiguring`
snapshot is gone, and with it `_has_configured_tracer_provider()` and
`_get_reconfigurable_tracer_provider()`, which existed only to serve it.

An empty configuration is now refused in *both* directions, not just over a live
one: installing an exporter-less provider on a first call would claim the
process-global slot that OpenTelemetry fills exactly once, locking out the next
call that does have exporters.

Eleven smaller items shipped with it: the superseded provider in the
foreign-global leg is shut down instead of merely drained (three configures used
to leave three atexit-hooked providers); a global slot still holding kibana-py's
own shut-down provider now says so instead of blaming "another component" the
reader would go hunting for; a non-string `exporter` warns and falls back rather
than raising `AttributeError` out of a telemetry call; the resource-attributes
warning is deferred until the call is known to be applied, so it cannot
contradict a "nothing is being applied" warning about the same call; the flush
deadline uses `time.monotonic_ns()` (a wall-clock step backwards would hand
later delegates more than the caller's budget); the stall note extends to the
shutdown/atexit path, which contends on the same lock; the user guide separates
kibana-py's own refusal policy from OpenTelemetry's two constraints and states
what a first empty-config call does; the corrupted-install report also goes
through `warnings.warn` (this package's `NullHandler` suppresses logging's
lastResort fallback, so the log line alone is invisible in a default
application); and the dual-layout fallbacks in two test helpers are gone, since
a `getattr` default could let a future "publishes nothing at all" regression
still satisfy every assertion built on them.

**Whole-call refusal, reported as such.** When a no-exporter call is refused, its
log-forwarding settings are not applied either. The alternative — apply the logs
half, skip the spans half — was rejected: it introduces a half-applied state
that no message can describe honestly, and the case is reachable only by passing
an `exporter` value that names nothing. The warning now says the whole call was
ignored, log forwarding included.

### Live re-run after round 3

```
[b] after configure #1 (dead http://localhost:8299): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8299/v1/traces')]
INFO:kibana.observability:OTLP exporter configured: http://localhost:8200/v1/traces?wu6=round3 (protocol: http/protobuf)
INFO:kibana.observability:OpenTelemetry reconfigured for service: kibana-py-wu6-round3-traces (logs: disabled)
[b] after configure #2 (live http://localhost:8200?wu6=round3): live exporters=[('BatchSpanProcessor', 'OTLPSpanExporter', 'http://localhost:8200/v1/traces?wu6=round3')]
[b] Elasticsearch traces-apm* documents for kibana-py-wu6-round3-traces: 1
[b]   index=.ds-traces-apm-default-2026.07.31-000001 source={"@timestamp": "2026-07-31T12:53:04.163Z", "service": {"name": "kibana-py-wu6-round3-traces"}, "processor": {"event": "transaction"}, "transaction": {"name": "wu6.reconfigure.round3"}}
```

Reconfiguration still applies at the wire after the restructure: the live
exporter is the new endpoint with its query parameter intact, the span is
indexed, and the superseded `:8299` endpoint is never contacted.

## Round 4 (re-review) — the visibility fix could not be allowed to raise

Round 3's `warnings.warn` for corrupted installs was a blocker in disguise:
`warnings.warn` **raises** under `-W error` (or a suite-wide
`filterwarnings("error")`), and it runs inside the import guards whose entire
purpose is to survive a broken install. Witnessed against the round-3 commit —
one optional exporter is corrupted, the interpreter runs with `-W error`:

```
E       AssertionError: `import kibana` died reporting a corrupted install under -W error:
E         stderr:
E         WARNING:kibana.observability:gRPC OTLP trace exporter is installed but failed to import (TypeError: blocked for test: opentelemetry.exporter.otlp.proto.grpc). …
E         WARNING:kibana.observability:OpenTelemetry tracing SDK is installed but failed to import (RuntimeWarning: gRPC OTLP trace exporter is installed but failed to import …
E         Traceback (most recent call last):
E           File "…/kibana/observability/_imports.py", line 106, in <module>
E             from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
E         TypeError: blocked for test: opentelemetry.exporter.otlp.proto.grpc
```

Read the second warning: the raised `RuntimeWarning` escaped the *inner* guard,
the *outer* guard caught it, and kibana-py concluded the whole tracing SDK had
failed — `OTEL_AVAILABLE` off over a fault in one optional exporter — before
that report's own warning killed `import kibana` (rc=1). A reporting channel had
become a second way to break.

The warning is now best effort: wrapped in its own `try/except`, with the log
line as what remains when warnings are fatal. `-W error` with a corrupted
exporter now exits 0 with `OTEL_AVAILABLE=True`, `GRPC_EXPORTER_AVAILABLE=False`
and the HTTP exporter untouched.

The same round fixed one contradiction left over from round 3: after a provider
shutdown, the next configure warned that the global slot holds kibana-py's own
shut-down provider and then called itself a first-time "configured". A previous
configuration leaves two possible traces — the tracked pair, and the record of
what kibana-py put in the global slot — and either one makes the next call a
reconfiguration, so `reconfigured` now reads both.

## Known residuals (not fixed here, deliberately)

- **The superseded `LoggerProvider` is not shut down on reconfigure.** Log *handlers*
  are now closed and detached (which is what stops duplicate export — proven in (a)),
  but `_setup_log_forwarding` builds a fresh `LoggerProvider` per call and the
  previous one keeps an idle `BatchLogRecordProcessor` thread until process exit. No
  records reach it once its handler is detached, so this is a resource residual, not
  a correctness one. Round 2 recorded the reason it stays that way, in code at the
  cleanup site: `set_logger_provider()` also refuses every call after the first, so
  the provider built by the *first* configuration is the process-global one that
  unrelated code may hold loggers from — shutting it down on reconfigure would break
  those callers to reclaim one idle thread.
- **A log record emitted during the reconfiguration window is not forwarded.** The
  old handler is detached before the new one is attached (well under a millisecond
  apart), and a record emitted in between reaches neither. This is the deliberate
  direction of the trade: never duplicate, occasionally drop. Documented in the user
  guide rather than claimed away as "exactly once".
- **A span can be dropped in a processor swap**, for the same reason: `on_end` reads
  the delegate tuple once, so a span holding the old tuple can reach a delegate that
  `swap()` has just shut down (the SDK drops it with an INFO line). Closing that
  window means a lock on every span's `on_end` — a hot-path mutex to protect an
  operation that happens a handful of times per process.
- **Releasing a superseded delegate is synchronous, and holds the lock.** A
  `BatchSpanProcessor` whose endpoint is unreachable can spend up to the SDK's 30s
  join inside the caller's `configure_opentelemetry()` call — while holding
  `_provider_lock`, so a concurrent configure waits it out, and so does any provider
  shutdown (including the SDK's atexit hook, since `_forget_installed_processor`
  takes the same lock). Off-thread release would hide the stall along with any
  failure, and is a recorded non-goal rather than an oversight.
- **A refused call is refused whole.** A configuration that creates no span
  exporter does not apply its log-forwarding settings either. Applying half a call
  would create a state no log line can describe honestly, and the case is only
  reachable by naming an `exporter` that does not exist; the warning says the whole
  call was ignored.
- **`set_logger_provider()` is refused on every call after the first**
  (`Overriding of current LoggerProvider is not allowed`, visible in the (a)
  transcripts on both trees). Log forwarding is unaffected because each
  `OTelLogHandler` holds a direct reference to the provider it was built with — the
  global logger provider is only what *other* code would resolve. Also a follow-up,
  not a regression.
- **Resource attributes cannot change on reconfigure** for spans (OpenTelemetry
  fixes a provider's resource at construction). Now warned about explicitly rather
  than silently ignored, and — after the fix round — the warning names the
  asymmetry itself: log forwarding builds a new provider per call, so forwarded
  logs *do* pick up the new attributes while spans keep the first configuration's.
