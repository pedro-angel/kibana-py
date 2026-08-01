# Evidence — `test_observability.py` order-dependent flakiness under pytest-randomly (issue #91)

**Date:** 2026-08-01
**Change under test:** `tests/unit/test_observability.py`
(`TestLogForwardingSetup.test_setup_log_forwarding_success`) on branch
`fix/import-guard-flake-91`. Test-only change — no file under `kibana/` touched.
**Base commit (pre-fix, `main`):** `6fed9e6b94fac192402e858f04a8d93b2588e46e`.

## Why (as filed)

Issue #91: `tests/unit/test_observability.py::TestImportGuardMatrix` was reported as
order-dependent under `pytest-randomly`, "reproduced identically on unmodified main"
per a campaign-internal report from the review round that filed this issue (not a
tracked repo artifact), with a related sighting of "6 failures in
`TestImportGuardMatrix`" on a Python 3.14 pyenv interpreter, described as "a
subprocess-isolated gRPC fork-safety stderr artifact" per a campaign-internal report
from the serializer-parity work (also not a tracked repo artifact). The issue also
ties this to PR #90's disclosed anomaly: one local run of `test_observability.py`
showed 20 failures that never recurred across ~95 subsequent runs, including 50 with
captured random seeds (no failing seed found at the time).

## Hunt log (Phase 1 — reproduce first)

### Round 1 — default interpreter (3.11.15, `.venv`), whole file, seeds 1–150

```
for s in $(seq 1 150); do
  pytest tests/unit/test_observability.py -q --no-cov -p randomly --randomly-seed=$s
done
```

Failing seeds found: **33, 66, 68, 105** (4/150). Every one of them produced the
*exact same* 20 failures (same test IDs, same order in the summary), e.g. seed 33:

```
FAILED tests/unit/test_observability.py::TestLogForwardingSetup::test_setup_log_forwarding_success
FAILED tests/unit/test_observability.py::TestLogForwardingSetup::test_setup_log_forwarding_logs_not_available
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_handle_telemetry_error_authentication
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_create_otlp_exporter_with_error_handling_import_error
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_handle_telemetry_error_network
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_create_otlp_exporter_with_error_handling_value_error
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_configure_opentelemetry_unsupported_protocol_warning_accurate_for_console_exporter
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_configure_opentelemetry_apm_connectivity_failure
FAILED tests/unit/test_observability.py::TestAPMServerIntegration::test_configure_opentelemetry_unsupported_protocol_warns_and_uses_grpc_default
FAILED tests/unit/test_observability.py::TestLogForwardingConfiguration::test_configure_invalid_log_level_uses_default
FAILED tests/unit/test_observability.py::TestLogForwardingConfiguration::test_configure_invalid_logs_loggers_type_uses_default
FAILED tests/unit/test_observability.py::TestSwappableSpanProcessor::test_configure_after_provider_shutdown_reports_a_reconfiguration
FAILED tests/unit/test_observability.py::TestObservabilityWithoutOpenTelemetry::test_configure_without_otel_logs_warning
FAILED tests/unit/test_observability.py::TestLogExporterCreation::test_create_otlp_log_exporter_with_error_handling_import_error
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_first_configure_without_a_span_exporter_warns
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_configure_warns_but_still_exports_under_foreign_provider
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_repairs_a_mismatched_tracked_pair
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_warns_that_resource_attributes_stay_pinned
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_reconfigure_without_a_span_exporter_keeps_the_working_config
FAILED tests/unit/test_observability.py::TestConfigureOpenTelemetryIdempotency::test_concurrent_no_exporter_configure_cannot_tear_down_a_working_one
20 failed, 130 passed in 9.19s
```

**Exactly 20 failures, identical set, every time it fails** — this is the same count
PR #90 disclosed. **No `TestImportGuardMatrix` test appears in any of the four failing
seeds.**

### Round 2 — Python 3.14 (pyenv/nox matrix, `.nox/test-3-14`), seeds 1–40

```
for s in $(seq 1 40); do
  .nox/test-3-14/bin/python -m pytest tests/unit/test_observability.py -q --no-cov \
    -p randomly --randomly-seed=$s
done
```

Failing seed: **33** (same seed number, since pytest-randomly's shuffle is a pure
function of seed + collection order, independent of interpreter version) —
**identical 20-failure list**, again none in `TestImportGuardMatrix`.

### Round 3 — adversarial ordering targeting `TestImportGuardMatrix` directly

Given the campaign-internal "gRPC fork-safety stderr artifact" hypothesis (a real, unclosed gRPC
channel from an earlier test leaving background C-core threads alive, then
`TestImportGuardMatrix`'s `subprocess.run(...)` forking the process and gRPC's
`fork_posix.cc` atfork handler printing a warning to the inherited stderr pipe), two
things were checked empirically rather than assumed:

1. **Does `subprocess.run(...)` (as called by `_run_with_blocked_imports`, no
   `close_fds` override) actually `fork()`, or does it use `posix_spawn` (no fork,
   handler can't fire)?** Read `subprocess.Popen._execute_child`: the `posix_spawn`
   fast path requires `not close_fds`; `close_fds` defaults to `True` and
   `_run_with_blocked_imports` never overrides it, so it **does** take the classic
   `fork()+exec()` path — the fork-handler hypothesis is at least mechanically
   possible here.
2. **Does a real gRPC channel with live background threads, then a fork, actually
   produce a stderr artifact on this platform?** Constructed a real
   `OTLPSpanExporter` (gRPC), forced a real (failing, `localhost:4317` unreachable)
   export to fully spin up gRPC's core (`ps -M <pid>` thread count: 1 → 20 OS-level
   threads, invisible to Python's `threading.enumerate()` since they're raw C-core
   threads), then forked 10 children via the exact same
   `subprocess.run([sys.executable, "-c", ...], capture_output=True, text=True,
   timeout=30)` call shape as `_run_with_blocked_imports`. **All 10 children: rc=0,
   stderr=''.** Also ran the real test pair back-to-back, forced via explicit
   command-line node-ID order (pytest preserves cmdline order for explicit node IDs —
   verified), 20 times: `test_create_otlp_exporter_grpc_protocol` immediately followed
   by every `TestImportGuardMatrix` case, **20/20 clean**.

Conclusion: the gRPC-fork-artifact mechanism could not be reproduced on this
environment (arm64 macOS, grpcio 1.82.1/1.83.0, Python 3.11.15/3.14.3) despite
deliberately constructing the exact preconditions (live gRPC core threads immediately
before a `fork()`-based `subprocess.run`). It may be a real, Linux-specific or
grpc-version-specific artifact (grpc's fork-unsafety warnings are documented as tied
to the `epoll1` polling engine, which macOS does not use), but it is not what
reproduced here, and after 190 seed/interpreter configurations plus 20 adversarial
back-to-back runs, `TestImportGuardMatrix` produced zero failures.

**Total hunt: 150 (3.11) + 40 (3.14) + 20 (adversarial ordering) = 210 configurations.**
4 genuine failures found, 0 of them in `TestImportGuardMatrix`, all 4 sharing one exact
mechanism (below) that is a real, deterministic order-dependence bug in this file and
an exact match for PR #90's disclosed anomaly.

## Root cause (Phase 1 continued — instrumentation)

Used `pytest --pdb -x --randomly-seed=33` to break at the first failure
(`test_setup_log_forwarding_success`, `assert mock_get_logger.call_count == 2` →
`46 == 2`) and inspected live state:

```
(Pdb) [c.args[0] for c in mock_get_logger.call_args_list]
['kibana', 'kibana.observability', 'opentelemetry.context', 'opentelemetry.attributes',
 ..., 'grpc._cython.cygrpc', 'grpc._observability', 'grpc', ...,
 'opentelemetry.exporter.otlp.proto.grpc.trace_exporter',
 'opentelemetry.exporter.otlp.proto.http.trace_exporter',
 'opentelemetry.exporter.otlp.proto.http._log_exporter',
 'kibana', 'kibana', 'kibana', 'kibana', 'kibana', 'test']
(Pdb) threading.enumerate()
[<_MainThread(MainThread, started ...)>]
```

Every one of those extra names is a module whose *own* top-level code calls
`logging.getLogger(__name__)` exactly once, the first time it is ever imported
(confirmed for `opentelemetry.sdk._logs._internal.export`, which even explains the
oddly specific `'...export.propagate.false'` entry —
`_propagate_false_logger = logging.getLogger(__name__ + ".propagate.false")` at that
module's line 61). Only `MainThread` is alive, so this is not a background-thread
artifact — it happens synchronously, inside this one test's call.

`test_setup_log_forwarding_success` collected **first in the entire 150-item run**
under seed 33 (confirmed via `--collect-only -p randomly --randomly-seed=33`):

```
<Module test_observability.py>
  <Class TestLogForwardingSetup>
    <Function test_setup_log_forwarding_success>      <- item #1 of 150
```

**Correction (mechanism-verification review round):** the first draft of this
document claimed the test's own `from kibana.observability import
_setup_log_forwarding` line was "the first time in the whole process" `kibana.
observability` gets imported. That claim was checked directly and is **wrong**. A
`sys.modules` probe inserted as the very first statement of the (pre-fix) function
body — *before* that import line runs — shows the module is already present:

```
[BODY-ENTRY PROBE] kibana.observability in sys.modules = True; kibana in sys.modules = True
```

i.e. by the time the test's own explicit import line executes, `kibana.observability`
is already a cache hit. Tracing the *actual* first `import kibana.observability` call
(a `builtins.__import__` wrapper recording the call stack the first time `name ==
"kibana.observability"`, run against the pre-fix file) shows where it really comes
from:

```
File ".../unittest/mock.py", line 1430, in __enter__
  self.target = self.getter()
File ".../pkgutil.py", line 700, in resolve_name
  mod = importlib.import_module(modname)
  ...
File "kibana/__init__.py", line 73, in <module>
  from kibana._async.client import AsyncKibana, AsyncSpaceScopedKibana
  ...
File "kibana/_sync/client/_base.py", line 25, in <module>
  from kibana.observability import KibanaInstrumentor, span_context
```

This is `unittest.mock.patch.__enter__` → `self.getter()` — i.e. **one of the six
`@patch("kibana.observability.*")` decorators'** own target resolution (`pkgutil.
resolve_name` → `importlib.import_module`) — cascading through `kibana/__init__.py`'s
own import chain into `kibana/_sync/client/_base.py`'s `from kibana.observability
import KibanaInstrumentor, span_context`, several frames removed from anything in the
test body. The test's own explicit import line never does the triggering; it just
observes an already-imported (and, pre-fix, already-poisoned) module. The corrected
"Full causal chain" below reflects this. The fix's correctness is unaffected either
way: under the fixed code, `logging.getLogger` is unmocked during all seven
`kibana.observability`-touching events (the six decorators' target resolution, plus
this function's own import line) — it no longer matters which one happens to go
first.

**The `MagicMock`-poisoning itself, confirmed directly (not inferred):**

```
(Pdb) import kibana.observability._imports as m
(Pdb) type(m.logger)
<class 'unittest.mock.MagicMock'>
(Pdb) import kibana.observability._validation as v
(Pdb) v.logger is m.logger
True
```

`kibana.observability._imports.logger` — the module-level `logger =
logging.getLogger("kibana.observability")` at that file's line 9, which every other
observability submodule imports and logs through — was **permanently** a `MagicMock`
instance for the rest of the process. `_validation.py`'s `_handle_telemetry_error`
(the function `test_handle_telemetry_error_authentication` exercises) calls
`logger.error(...)` on that same object; once it is a mock, the call is swallowed by a
`MagicMock` method instead of reaching any real handler, so `caplog.text` is `''` no
matter what the code does — explaining the other 18 failures, all `caplog`-based
assertions on `kibana.observability` logger output, scattered across five unrelated
test classes.

**Why the mock was active during that first import — decorator start order,
verified empirically (not assumed):**

```python
@patch("scratch_mod.A", 10)
@patch("scratch_mod.B", 20)     # closest to `def`
def test_func(*args): ...
# instrumented unittest.mock._patch.get_original to record order
# -> start order: ['B', 'A']
```

`unittest.mock` starts stacked decorators **bottom-up** — the one closest to `def`
activates first. `test_setup_log_forwarding_success`'s decorator stack (pre-fix) was:

```python
@patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)   # starts LAST
@patch("kibana.observability.LoggerProvider")
@patch("kibana.observability.set_logger_provider")
@patch("kibana.observability._create_otlp_log_exporter_with_error_handling")
@patch("kibana.observability.BatchLogRecordProcessor")
@patch("kibana.observability.OTelLogHandler")
@patch("logging.getLogger")                                # starts FIRST
def test_setup_log_forwarding_success(...):
```

`@patch("logging.getLogger")`, being closest to `def`, started first — mocking
`logging.getLogger` *before* any of the six `kibana.observability.*` patches ran their
own target resolution (each of which needs `importlib.import_module("kibana.observability")`
if not already imported). The traceback probe above nails down which one actually
does the importing: `unittest.mock`'s own `_patch.__enter__` → `self.getter()` →
`pkgutil.resolve_name` → `importlib.import_module`, one frame inside whichever of
the six is the first (in *their* bottom-up start order, i.e.
`@patch("kibana.observability.OTelLogHandler")`, closest to `def` among the six) to
run its target resolution — and that resolution ran while `logging.getLogger` was
already mocked, not the test body's own import line (see the correction above).

**Full causal chain:**

1. `pytest-randomly` seeds the shuffle. Only `test_setup_log_forwarding_success`
   itself can *trigger* the corruption — its sibling
   `test_setup_log_forwarding_logs_not_available` doesn't patch `logging.getLogger`,
   so it can only be a *victim* of an already-corrupted logger, never the cause. And
   only *this test's* landing in the literal first slot of the whole 150-item run
   matters: `tests/unit/conftest.py`'s autouse `_reset_otel_state` fixture runs a
   `from kibana.observability import KibanaInstrumentor` in its teardown (after
   *every* test, not just this one) with the real, unmocked `logging.getLogger` — so
   once any other test runs first, `kibana.observability`'s one-time import
   completes safely before `test_setup_log_forwarding_success` ever gets a turn,
   regardless of where in the remaining order it falls. That gives a naive
   probability of 1 test out of 150 landing in position 1 → **~1/150 ≈ 0.67%** per
   seed. The observed rate over the 150-seed hunt was **4/150 ≈ 2.7%** — higher than
   the naive estimate, but not statistically surprising from only 150 samples (a true
   rate of 1/150 yields 4-or-more hits in 150 trials with non-negligible probability
   under a Poisson approximation); no attempt was made to further tighten this beyond
   stating both numbers honestly. Read as "empirically ~1–3% per seed."
2. Its `@patch("logging.getLogger")` decorator starts before the function body runs,
   and before the other six `kibana.observability.*`-target decorators resolve their
   targets (bottom-up start order).
3. One of those six decorators' target resolution (confirmed via the traceback probe
   above — not the test's own `from kibana.observability import
   _setup_log_forwarding` line, which by then is a cache hit) triggers the
   first-ever `import kibana.observability`, running `_imports.py`'s module-level
   code — and transitively every OTel/grpc submodule's own `logger =
   logging.getLogger(__name__)` — while `logging.getLogger` is mocked.
4. Every one of those loggers binds permanently to the mock's `Mock()` return value.
   Python never re-executes a cached module's top-level code, so nothing later in the
   session can undo it.
5. Every subsequent test in the run that expects a *real* `kibana.observability`
   logger to reach `caplog` (or a real OTel-internal logger to behave normally) fails
   for the rest of the session — 19 more failures, plus the triggering test's own
   `mock_get_logger.call_count` assertion (expected `2`, got `46`, one per
   incidentally-first-imported module).

**`TestImportGuardMatrix` is structurally immune to this mechanism.** Its tests never
call `from kibana.observability import ...` in the parent process at all — they build
a command string and hand it to a brand-new `sys.executable -c ...` subprocess with
its own meta-path import blocker (`_run_with_blocked_imports`), then assert only on
that child's `stdout`/`stderr`/`returncode`. A poisoned logger object in the *parent*
process cannot reach a child interpreter that never inherits Python objects, only
`os.environ` and file descriptors. This is also why the round-3 hunt above targeted a
different candidate mechanism (gRPC fork-safety) rather than this one when looking
specifically for a `TestImportGuardMatrix` failure.

## Fix

`tests/unit/test_observability.py::TestLogForwardingSetup.test_setup_log_forwarding_success`:
moved the `from kibana.observability import _setup_log_forwarding` import to run
*before* `logging.getLogger` is mocked, and narrowed the mock from a
whole-function `@patch` decorator to a `with patch("logging.getLogger", ...)` block
scoped to just the `_setup_log_forwarding(...)` call under test. This mirrors the
pattern the same test class's other two `logging.getLogger`-patching tests already
use correctly (`test_cleanup_log_handlers` imports `_cleanup_log_handlers` before
entering its `with patch("logging.getLogger", ...)` block;
`test_cleanup_survives_a_logger_created_during_the_sweep`, same shape) — this was the
one outlier in the file (grep confirms `@patch("logging.getLogger"...)` as a bare
decorator appears exactly once in the whole test suite).

Net effect: the six `kibana.observability.*` decorators (unaffected by the reordering)
still resolve their targets first, using the real, unmocked `logging.getLogger` —
guaranteeing `kibana.observability`'s one-time import chain always completes safely,
regardless of whether this happens to be the first test in the session to touch it.
The mock now only ever affects the two `logging.getLogger(logger_name)` calls inside
`_setup_log_forwarding`'s own loop that the test intends to verify.

No production code (`kibana/`) changed — this was purely a test-isolation defect.

## Verification (Phase 4)

**RED confirmed pre-fix, GREEN post-fix — same 4 discovered seeds:**

```
$ pytest tests/unit/test_observability.py -q --no-cov -p randomly --randomly-seed=33
150 passed in 8.93s
$ pytest tests/unit/test_observability.py -q --no-cov -p randomly --randomly-seed=66
150 passed in 8.88s
$ pytest tests/unit/test_observability.py -q --no-cov -p randomly --randomly-seed=68
150 passed in 8.90s
$ pytest tests/unit/test_observability.py -q --no-cov -p randomly --randomly-seed=105
150 passed in 8.87s
```

**50-seed loop, default interpreter (3.11.15, `.venv`), seeds 1–50: all green.**

**50-seed loop, Python 3.14 (`.nox/test-3-14`), seeds 1–50: all green.**

**Extra spot-check (previously-failing seeds + a fresh block): seeds 33, 66, 68, 105,
51–60, 200–205 — all green.**

**`TestImportGuardMatrix` alone:**
```
$ pytest tests/unit/test_observability.py -k TestImportGuardMatrix --no-cov -q
13 passed, 137 deselected in 2.07s
```

**Full unit suite:**
```
$ pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3413 passed in 15.58s
Required test coverage of 90% reached. Total coverage: 94.41%
```

**Sync/async parity guard:**
```
$ pytest tests/unit/test_sync_async_parity.py --no-cov -q
144 passed in 0.66s
```

**mypy:**
```
$ mypy kibana/
Success: no issues found in 103 source files
```

**Hooks (file-scoped, since only the test file changed):**
```
$ pre-commit run --files tests/unit/test_observability.py
... all hooks Passed (black, isort, ruff check, secret/pin/identifier checks)
```

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 25.5.0 |
| Python (primary) | 3.11.15 (`.venv`, editable install) |
| Python (matrix cross-check) | 3.14.3 (`.nox/test-3-14`, nox-managed) |
| Role | local arm64 macOS dev workstation |
| grpcio | 1.82.1 (3.11 env) / 1.83.0 (3.14 nox env) |
| opentelemetry-exporter-otlp-proto-grpc | 1.43.0 (3.11 env) / 1.44.0 (3.14 nox env) |
| pytest-randomly | 4.1.0 |

## Note on PR #90's disclosed anomaly

PR #90 disclosed: *"One local run of `test_observability.py` showed 20 failures that
never recurred: ~95 subsequent runs green, including 50 with captured random seeds (no
failing seed found)."* This fix's root cause explains it exactly: 20 failures, same
count; only `test_setup_log_forwarding_success` can *trigger* the corruption (its
sibling `_logs_not_available` test is a victim, never a cause — see the "Full causal
chain" step 1 above), and only that one test's landing in the run's literal first
slot matters, thanks to `_reset_otel_state`'s autouse teardown import safing the
module after any other ordering. That gives a naive **~1/150 ≈ 0.67%** chance per
seed; the 150-seed hunt observed **4/150 ≈ 2.7%** (not a contradiction — a real rate
of 1/150 plausibly produces 4 hits in 150 Poisson-ish trials). Read either way as
"empirically ~1–3% per seed" — squarely consistent with "one run in dozens, no repeat
in 50 more seed-captured attempts." This is very likely the same event PR #90 hit, not
a separate, still-open anomaly.

## Note on `TestImportGuardMatrix` / residual (tracked as issue #100)

Issue #91 named `TestImportGuardMatrix` specifically, citing a campaign-internal
report from the review round that filed the issue ("reproduced identically on
unmodified main," not a tracked repo artifact) and a campaign-internal report from the
serializer-parity work (also not a tracked repo artifact) describing a 6-failure
Python 3.14 sighting as "a subprocess-isolated gRPC fork-safety stderr artifact." This
hunt (210 configurations across two interpreters plus 20 rounds of adversarial
ordering specifically targeting a gRPC-fork scenario) produced **zero**
`TestImportGuardMatrix` failures, and the confirmed mechanism above cannot touch that
class at all (its tests never share parent-process state with the corrupting test —
see "structurally immune" above). Two honest possibilities, not resolved further here:
(a) those reports actually observed this same 20-failure cascade and attributed it to
`TestImportGuardMatrix` by association (same file, same `pytest-randomly` session, or
a truncated/partial log that only showed the tail of a long failure list); or (b) the
gRPC-fork-safety mechanism reported is real but is specific to an environment not
reproduced here (Linux, a different grpc/polling-engine combination, or genuine
machine-load timing) — this platform's `subprocess.run` does take the real
`fork()`+`exec()` path (verified above, not assumed), so the mechanism is at least
possible here in principle; it simply didn't fire.

This residual — whether the gRPC-fork-safety hypothesis is real on the platform CI
actually runs (Linux, `ubuntu-latest`, exactly where the `epoll1` poller this
hypothesis depends on is used) — is carried forward as
[issue #100](https://github.com/pedro-angel/kibana-py/issues/100), filed as this
fix's successor rather than left implicit. #91 is not being auto-closed by this PR's
merge (this fix's commit trailer references it with `Refs`, not `Fixes`): #91's
originally-named symptom never reproduced here, so the repo maintainer will close #91
manually with this evidence attached once #100's Linux-platform gate resolves the
open question one way or the other. If a future run produces a captured failing seed
with a `TestImportGuardMatrix` failure and non-empty unexpected `stderr`, that is a
**distinct** bug from the one fixed here and should be root-caused under #100 — not
folded into this fix by inference.

## Fix round — mechanism-verification review response

An independent reviewer re-attacked this evidence before merge: reproduced all four
RED seeds pre-fix on both interpreters, confirmed the fix does not weaken coverage,
then found one MAJOR causal-narrative error and three lesser precision issues in the
write-up itself (the fix's code was not in question). Findings and responses:

1. **[MAJOR] "The test's own import line is the first-ever import" was checked and
   is wrong.** The original draft asserted this as established fact. The reviewer
   probed `sys.modules` at the first line of the (pre-fix) function body and found
   the module already present — i.e. the test's own explicit import line is always a
   cache hit, never the trigger. Verified independently in this fix round with two
   direct probes against the pre-fix code (temporarily restored via `git show
   HEAD~1:... > tests/unit/test_observability.py`, then reverted with `git checkout
   --`, leaving the committed fix untouched): (a) a `sys.modules`-at-body-entry print
   confirming `kibana.observability in sys.modules = True` before the test's import
   line runs; (b) a `builtins.__import__` wrapper capturing the full call stack of
   the actual first `import kibana.observability` in the process, showing it
   originates from `unittest.mock.patch.__enter__` → `self.getter()` →
   `pkgutil.resolve_name` → `importlib.import_module`, i.e. one of the six
   `@patch("kibana.observability.*")` decorators' own target resolution, cascading
   through `kibana/__init__.py` into `kibana/_sync/client/_base.py`'s `from
   kibana.observability import KibanaInstrumentor, span_context`. The causal
   narrative in the "Root cause" section above, the test's docstring, and the
   CHANGELOG entry are corrected accordingly; the "confirmed directly (not
   inferred)" framing is now scoped only to the `MagicMock`-poisoning finding (which
   was never in question) rather than the import-order claim. **The fix itself needed
   no change**: it removes `logging.getLogger` from the decorator stack entirely, so
   under the fixed code the mock is inactive during all seven `kibana.observability`
   -touching events regardless of which one goes first.
2. **[MAJOR] Commit trailer `Fixes #91` → `Refs #91`.** #91's named symptom
   (`TestImportGuardMatrix` failures) never reproduced in this hunt, and the
   platform-specific gRPC-fork-safety hypothesis is now tracked by successor issue
   #100 (filed by this review round) rather than silently dropped. Auto-closing #91
   on merge would read as "confirmed and fixed the reported symptom," which is not
   what happened; the maintainer will close #91 manually, referencing this evidence
   and #100, once #100's Linux-platform gate resolves the open question. See the
   "Note on `TestImportGuardMatrix` / residual" section above, which now names #100
   directly.
3. **[minor] Probability framing.** "~1-in-75" (an artifact of double-counting the
   victim test as also "vulnerable") is replaced throughout with the honest
   derivation: only `test_setup_log_forwarding_success` can trigger the corruption,
   and only its landing in the run's literal first slot matters (`conftest.py`'s
   autouse `_reset_otel_state` teardown safely imports `kibana.observability` after
   any other test's turn, using the real `logging.getLogger`) — naive **~1/150 ≈
   0.67%**, observed **4/150 ≈ 2.7%**, both stated together as "empirically ~1–3% per
   seed" rather than a single overprecise figure.
4. **[minor] "WU8" (and "WU7") are not checkable repo artifacts.** Both are now
   described as campaign-internal reports (WU8's, specifically, from the
   serializer-parity work) not tracked in this repository, so a future auditor
   searching for a "WU8" reference in this repo's history is not sent hunting a
   phantom.

Re-verification after these edits (docs/commit-message only — no code changed in this
round): `pre-commit run` on the touched files clean; full
`pytest tests/unit/test_observability.py` green; commit amended on the same branch,
trailers consolidated into one final block.
