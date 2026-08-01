# Evidence — benign gRPC fork diagnostic failing `TestImportGuardMatrix` locally (issue #100)

**Date:** 2026-08-01
**Change under test:** `tests/unit/test_observability.py` on branch
`fix/grpc-fork-noise-100`. Test-only change — no file under `kibana/` touched.
**Base commit (pre-fix, `main`):** `c3cd1cd8fde5664e2037b349e9f9d85de576bef8`.

## Why (as filed, and as it actually reproduced)

Issue #100 is #91's successor: #91's hunt (`docs/evidence/import-guard-flake-91.md`)
root-caused and fixed a real, deterministic order-dependence bug (mock-poisoned
module loggers), but the symptom #91 was originally *named after* —
`TestImportGuardMatrix` failures with "a subprocess-isolated gRPC fork-safety
stderr artifact," reported on Python 3.14 — never reproduced across 210
configurations (150 seeds on 3.11 + 40 on 3.14 + 20 rounds of adversarial ordering
explicitly forcing the two suspected tests back-to-back). #100 named the untested
residual precisely: gRPC's fork-unsafety diagnostic is documented as tied to
Linux's `epoll1` polling engine — exactly `ubuntu-latest`, where CI's unit jobs
run — and not the platform (arm64 macOS) #91's hunt covered. #100's gate: run a
seed-loop hunt of `TestImportGuardMatrix` on Linux across 3.11–3.14, either
root-cause a failing seed or record a bounded clean result and close.

Before that Linux gate could be scheduled, `make dod`'s `make test-python-matrix`
leg reproduced the exact named symptom **locally, on the same arm64 macOS platform
#91's hunt already covered** — `/tmp/dod-kibana-py/matrix_green.log`, Python 3.12
nox session, `--randomly-seed=2442198158`:

```
platform darwin -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
Using --randomly-seed=2442198158
...
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[issue70-logs-absent-must-not-clobber-trace-exporters]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[issue68-grpc-exporter-absent-sdk-and-http-present]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[otel-entirely-absent]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[baseline-everything-present]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[sdk-entirely-absent-api-only]
FAILED tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[http-exporter-absent-sdk-and-grpc-present]
======================= 6 failed, 3417 passed in 16.79s ========================
```

with, in each of the 6 failures, the identical assertion:

```
AssertionError: a missing optional package must stay quiet:
  I0801 19:19:22.245823 14779649 ev_poll_posix.cc:593] FD from fork parent still in poll list: fd(17, generation: 1)

assert 'I0801 19:19:...eration: 1)\n' == ''
```

`test-3.11`, `test-3.13`, `test-3.14` were green in the same matrix run. This is
the class #91 could never trigger, now caught by `make test-python-matrix`'s
per-session random seed rather than a targeted hunt — same platform, same
mechanism #91 went looking for and didn't find with 210 attempts.

## Investigation (systematic-debugging)

### 1. Root cause: which test poisons the parent process, and does `fork()` actually happen

Only one test anywhere in `tests/unit/` touches gRPC without mocking it:
`TestAPMServerIntegration.test_create_otlp_exporter_grpc_protocol`
(`tests/unit/test_observability.py`), which calls
`_create_otlp_exporter(endpoint="http://localhost:4317", ..., protocol="grpc")`
unmocked — constructing a real `grpc.insecure_channel` via the installed
`opentelemetry-exporter-otlp-proto-grpc`. Every `grpc.Channel` the first time one
is created in a process causes gRPC's C-core to lazily initialize and register a
process-wide `pthread_atfork` handler (documented at
[grpc/doc/fork_support.md](https://github.com/grpc/grpc/blob/master/doc/fork_support.md)).

Reproducing the exact failing seed and dumping the run order (`-v`) confirms
adjacency in the actual failing run:

```
$ .nox/test-3-12/bin/python -m pytest tests/unit/ --randomly-seed=2442198158 -v --no-cov \
    | grep -n "test_create_otlp_exporter_grpc_protocol \|test_import_kibana_under_partial_install\[baseline"
2959:tests/unit/test_observability.py::TestAPMServerIntegration::test_create_otlp_exporter_grpc_protocol PASSED [ 86%]
3000:tests/unit/test_observability.py::TestImportGuardMatrix::test_import_kibana_under_partial_install[baseline-everything-present] FAILED [ 87%]
```

41 items separate them — the channel-creating test runs at 86% through the
3423-item shuffle, the first matrix failure follows at 87%.

`_run_with_blocked_imports` (the matrix tests' shared helper) calls
`subprocess.run([sys.executable, "-c", ...], capture_output=True, text=True,
timeout=30)` with no `close_fds` override, so `close_fds` defaults to `True`.
Reading CPython's `subprocess.Popen._execute_child` directly (not assumed) shows
its `posix_spawn` fast path is explicitly gated on `not close_fds`:

```python
if (_USE_POSIX_SPAWN
        and os.path.dirname(executable)
        and preexec_fn is None
        and not close_fds        # <- disqualified here; close_fds defaults True
        and not pass_fds
        ...):
    self._posix_spawn(...)
    return
# falls through to the classic fork()+exec() path below
```

So this call path is not designed to dodge `fork()` via `posix_spawn`. (A
Python-level `os.register_at_fork(after_in_child=...)` probe around an equivalent
`subprocess.run` call did not itself fire — inconclusive on its own, since gRPC's
handler is registered directly through the C-level `pthread_atfork()` libc API,
a separate registry from Python's own `os.register_at_fork` bookkeeping, and can
fire independently of it. What is decisive is the real reproduction above and
below: gRPC's own libc-registered post-fork handler *does* run around this call
in the real failing scenario, regardless of that unresolved CPython-internals
detail.) The handler runs in the forked child, before `execve()` replaces the
process image — so its diagnostic write lands on whatever stderr fd the child
inherited from the parent at the moment of `fork()`, which is already the pipe
`subprocess.run(capture_output=True)` set up to capture this specific child's
output. That is why kibana's own probe script — which never imports `grpc` at
all — shows gRPC C-core chatter in its captured stderr.

### 2. Getting a deterministic RED: what did and didn't reproduce it

Per #91's own hunt (0/210 configurations, including 20 rounds of forcing the two
suspected tests to run back-to-back via explicit node-ID ordering), close temporal
proximity of the poisoning test and a matrix test is evidently **not sufficient**
on its own. This investigation repeated and extended that class of experiment
before finding what does work:

- **Standalone script, real channel + immediate `subprocess.run` forks (1–120
  iterations, with/without `del`+`gc.collect()`, with/without a real connectivity
  attempt via `grpc.channel_ready_future`, with/without multi-second delays
  between forks):** zero reproductions of the `ev_poll_posix.cc` diagnostic in
  any variant. A real connectivity attempt (`channel_ready_future(...).result()`
  against the unreachable `localhost:4317`) did reliably produce a *different*,
  related gRPC C-core diagnostic — `fork_posix.cc:71] Other threads are
  currently calling into gRPC, skipping fork() handlers` — proving `fork()`
  really is exercised and gRPC's atfork machinery really does engage, but never
  the specific stale-poll-list message under test.
- **Curated pytest slice preserving the exact real run order:** extracted the
  111 test IDs surrounding the poisoning test and the first matrix failure from
  the real failing run's own `-v` log (lines 2900–3010, same relative order) and
  ran them with `-p no:randomly` (explicit order preserved): **0/111 failed.**
- **Whole `tests/unit/` directory, plain definition order (`-p no:randomly`,
  no shuffling at all):** **3423/3423 passed** — the natural (non-random) order
  never places the two tests adjacently in a way that triggers it either.
- **Whole `tests/unit/` directory, the exact recorded seed
  (`--randomly-seed=2442198158`):** **reproduces every time** — 6/6 of the same
  failures, byte-for-byte the same diagnostic shape (differing only in pid/
  timestamp/fd number).

Conclusion, stated honestly: the mechanism needs the ambient scale of the *entire*
3423-item suite's thread/GC/fd churn to manifest — not merely the two relevant
tests running near each other, even forced. This is consistent with, and helps
explain, why #91's 20-round adversarial ordering hunt (which only ever ran the
two tests in isolation) legitimately found nothing despite deliberately
constructing what looked like the right preconditions.

### 3. Platform correction

The captured diagnostic is emitted by **`ev_poll_posix.cc`** — gRPC's plain
POSIX `poll()`-based polling-engine backend, used here because macOS has no
`epoll`. Issue #100 framed the fork-unsafety diagnostic as tied to Linux's
`epoll1` backend (`ev_epoll1_linux.cc`) specifically, and scoped its gate to
Linux CI on that basis. **That framing does not hold**: the `pthread_atfork`
registration and post-fork stale-entry check are a general fork-safety mechanism
gRPC's fork-support doc describes across its POSIX polling backends, not an
`epoll1`-exclusive feature; this investigation reproduces the identical
mechanism (a benign post-fork diagnostic from the process's own prior gRPC
channel, surfacing in a later subprocess's captured stderr) on `poll()`
(`ev_poll_posix.cc`) instead. Concretely: `ubuntu-latest` (where
`.github/workflows/test.yml` runs `pytest tests/unit/ --cov=kibana
--cov-fail-under=90` across 3.11–3.14, with no `--randomly-seed` pin — i.e. a
fresh random seed every run, same as any local invocation) is exposed to this
same class of noise via `epoll1.cc`'s own atfork handler, not specially exposed
relative to macOS, and not exposed only if macOS is somehow exempt. The fix
below is not platform-specific and covers both backends, since it strips by
message shape, not by asserting anything about which backend produced it.

### 4. `GRPC_VERBOSITY=ERROR` probed as an alternative

The task brief floated `GRPC_VERBOSITY=ERROR` in the *subprocess's* env as a
possible narrower fix. Probed directly:

Ad hoc scratch probe (not committed — not a repo artifact): a script that
creates a real channel + a `channel_ready_future` connectivity attempt against
the unreachable `localhost:4317`, redirects the process's real fd 2 to a pipe,
forks 15 times via raw `os.fork()`, and reports what landed in the pipe.

```
$ .nox/test-3-12/bin/python probe.py                # no GRPC_VERBOSITY set
verbosity=None captured_bytes=2071
I0801 19:36:38.448104 14835631 fork_posix.cc:71] Other threads are currently calling into gRPC, skipping fork() handlers

$ .nox/test-3-12/bin/python probe.py ERROR          # GRPC_VERBOSITY=ERROR set
                                                     # in THIS process's os.environ, before `import grpc`
verbosity='ERROR' captured_bytes=256                # (256 bytes = an unrelated
                                                     #  DeprecationWarning, no gRPC log line)
```

Setting `GRPC_VERBOSITY=ERROR` **in the
process that initializes gRPC** does suppress its C-core `gpr_log` INFO-level
output, including this diagnostic class.

But the task's suggested location — the subprocess's `env=` kwarg — cannot work,
architecturally, not just empirically: the diagnostic is written by the *forked
child*, before `execve()` swaps in the new process image and its environment.
At the moment gRPC's post-fork handler runs, the child is still using the
*parent's* already-initialized gRPC C-core state (including whatever verbosity
it cached at `grpc_init()` time) — the new `env=` dict the caller intends for the
grandchild process has not taken effect yet and never will for this write. To
have any effect at all, `GRPC_VERBOSITY=ERROR` would need to be set for the
*entire pytest/nox session*, before anything in that session first touches gRPC
(e.g. in `conftest.py` at import time, or exported for the whole `nox`/CI job) —
a session-wide behavior change with no bearing on how kibana-py itself logs,
versus the chosen fix's single-function scope. Given the task's preference for
the narrowest effective mechanism, and that it changes nothing else, **the
anchored stderr filter was chosen over `GRPC_VERBOSITY`.**

## Fix

`tests/unit/test_observability.py`, `_run_with_blocked_imports` (the shared
helper every `TestImportGuardMatrix` case calls): after capturing the
subprocess's output, strip only the exact benign diagnostic shape via a tightly
anchored regex —

```python
_GRPC_FORK_DIAGNOSTIC_RE = re.compile(
    r"^I\d{4} [0-9:.]+ +\d+ ev_poll_posix\.cc:\d+\] "
    r"FD from fork parent still in poll list: fd\(\d+, generation: \d+\)\n?",
    re.MULTILINE,
)


def _without_known_benign_fork_noise(stderr: str) -> str:
    return _GRPC_FORK_DIAGNOSTIC_RE.sub("", stderr)
```

applied once, centrally:

```python
result.stderr = _without_known_benign_fork_noise(result.stderr)
return result
```

Anchored on the full benign sentence (source file *and* line number *and* the
literal "FD from fork parent still in poll list" text and shape), not merely on
`ev_poll_posix.cc` — a different, real diagnostic from that same gRPC source
file would not be silently swallowed too (covered by
`test_leaves_an_unrelated_message_from_the_same_grpc_source_file_untouched`,
below). Every other assertion the file makes against `result.stderr`
(`"is installed but failed to import" in result.stderr`, `"RuntimeWarning" in
result.stderr`, `error in result.stderr`) is unaffected, since none of them
depend on this text. No file under `kibana/` changed — this is exclusively a
test-harness fix for noise the test infrastructure itself incidentally
generates, not anything kibana-py prints to a real caller.

## TDD: RED, fix, GREEN

A fast, deterministic, minimal reproduction of the *exact upstream race* turned
out to be infeasible (see Investigation §2) — the only thing that reliably
reproduces it is the full 3423-item suite at a specific seed, which is
inherently fragile as a committed automated test (any test added or removed
anywhere in `tests/unit/` changes pytest-randomly's derived shuffle for that
seed, silently un-reproducing it). The regression test committed
(`TestGrpcForkNoiseFilter` in `tests/unit/test_observability.py`) instead tests
the filter directly and end-to-end through the real helper, using the verbatim
captured diagnostic text — deterministic and fast, and it does exercise the
actual code path the matrix tests depend on.

**RED — confirmed by temporarily un-wiring the fix** (`result.stderr =
_without_known_benign_fork_noise(result.stderr)` reverted to `return result`
unmodified, function/regex left in place so only the wiring is missing):

```
$ .nox/test-3-12/bin/python -m pytest tests/unit/test_observability.py -k TestGrpcForkNoiseFilter -v --no-cov
...
tests/unit/test_observability.py::TestGrpcForkNoiseFilter::test_end_to_end_through_run_with_blocked_imports FAILED
E       AssertionError: the benign gRPC fork diagnostic must not surface as a package warning:
E         I0801 19:19:22.245823 14779649 ev_poll_posix.cc:593] FD from fork parent still in poll list: fd(17, generation: 1)
E       assert 'I0801 19:19:...eration: 1)\n' == ''
1 failed, 4 passed in 0.35s
```

(The 4 tests that test `_without_known_benign_fork_noise` directly already
passed at this point, since that function existed independently of the wiring;
only the end-to-end test — the one that actually exercises
`_run_with_blocked_imports`, matching what the real matrix tests depend on —
went red, exactly as expected.)

**Fix restored. GREEN:**

```
$ .nox/test-3-12/bin/python -m pytest tests/unit/test_observability.py -k TestGrpcForkNoiseFilter -q --no-cov
5 passed in 0.31s
```

**GREEN, the original historical scenario re-run identically:**

```
$ .nox/test-3-12/bin/python -m pytest tests/unit/ --randomly-seed=2442198158 -q --no-cov
3428 passed in 10.61s
```

(3428 = the original 3423 + the 5 new `TestGrpcForkNoiseFilter` tests; 0
failures, where the identical command pre-fix produced `6 failed, 3417
passed`.)

## Full verification

**Full unit suite, default (fresh) random seed:**
```
$ .nox/test-3-12/bin/python -m pytest tests/unit/ -q --no-cov
3428 passed in 13.27s
```

**`make test-python-matrix`, run 1 of 2 (3.11–3.14):**
```
nox > Running session test-3.11
============================ 3428 passed in 20.85s =============================
nox > Session test-3.11 was successful in 34 seconds.
nox > Running session test-3.12
============================ 3428 passed in 15.33s =============================
nox > Session test-3.12 was successful in 30 seconds.
nox > Running session test-3.13
============================ 3428 passed in 15.30s =============================
nox > Session test-3.13 was successful in 28 seconds.
nox > Running session test-3.14
============================ 3428 passed in 16.48s =============================
nox > Session test-3.14 was successful in 29 seconds.
```

**`make test-python-matrix`, run 2 of 2 (3.11–3.14, to reduce luck):**
```
nox > Running session test-3.11
============================ 3428 passed in 19.85s =============================
nox > Session test-3.11 was successful in 32 seconds.
nox > Running session test-3.12
============================ 3428 passed in 15.33s =============================
nox > Session test-3.12 was successful in 29 seconds.
nox > Running session test-3.13
============================ 3428 passed in 15.86s =============================
nox > Session test-3.13 was successful in 28 seconds.
nox > Running session test-3.14
============================ 3428 passed in 12.63s =============================
nox > Session test-3.14 was successful in 25 seconds.
```

Fully green, both runs, all four supported interpreters — including 3.12, the
interpreter the original sighting hit.

**mypy:**
```
$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files
```

(Unaffected in principle — only `tests/` changed — and confirmed rather than
assumed.)

**Hooks:**
```
$ make hooks
... black reformatted tests/unit/test_observability.py once (re-run after: all hooks Passed)
isort ................ Passed
ruff check ........... Passed
no secret-looking file is tracked by git ... Passed
every Action is SHA-pinned ... Passed
no private identifier enters the repo ... Passed
check-pin-comments-match (manual stage) ... Passed
```

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 25.5.0 (Darwin Kernel 25.5.0, `RELEASE_ARM64_T6050`) |
| CPU | Apple M5 Pro |
| Role | local arm64 macOS dev workstation |
| Python (matrix) | 3.11.15 / 3.12.13 / 3.13.7 / 3.14.3 (`.nox/test-3-*`, nox-managed) |
| grpcio | 1.83.0 (3.12 nox env) |
| opentelemetry-sdk / -exporter-otlp-proto-grpc | 1.44.0 |
| pytest / pytest-randomly | 9.1.1 / 4.1.0 |
| CI platform (`test.yml`) | `ubuntu-latest`, 3.11–3.14, no `--randomly-seed` pin (fresh seed every run) |

## Updated expectations for issue #100

- **The locally-reproduced sighting that motivated re-opening this investigation
  is resolved.** `make test-python-matrix` is green twice in a row across all
  four supported interpreters (above), including 3.12, the interpreter that hit
  it. The mechanism is understood and root-caused (§1), not merely papered over:
  a real, unmocked gRPC channel from an unrelated earlier test leaves
  process-wide fork-safety state that a later, unrelated `subprocess.run()`-based
  test can surface as stderr noise; the fix filters exactly that shape and
  nothing else.
- **The Linux/`epoll1` framing in #100's original gate is corrected, not
  confirmed.** This investigation demonstrates the identical mechanism on
  macOS's `poll()` backend (§3), which means the gate's premise — that this is
  specifically an untested-on-Linux, `epoll1`-only artifact — does not hold as
  originally stated. The fix is backend-agnostic (it matches by message shape,
  not by asserting which platform produced it), so it already covers whatever
  gRPC backend Linux CI uses.
- **Whether to still run #100's originally-specified Linux seed-loop hunt is
  left to the controller, as directed**, since it was not executed here (no
  Linux CI access from this environment) and is now arguably lower-value given
  the above: any Linux occurrence of this exact diagnostic shape is already
  handled by this fix regardless of whether a hunt ever captures a seed that
  produces it, and CI's unit job runs with a fresh, unpinned random seed every
  time (§3) — the same passive exposure this local sighting came from, not a
  targeted hunt. If the controller still wants a bounded Linux confirmation for
  its own sake (independent of whether the fix already covers it), that remains
  #100's to schedule.
- This fix's commit references #100 with `Refs`, not `Fixes` — the issue's
  literal, filed gate (a Linux CI seed-loop hunt with a recorded bounded-clean-
  or-root-caused result) was not executed as part of this change; only the
  local sighting that interrupted `make dod` was root-caused and fixed. The
  controller closes #100 once satisfied with the disposition above.
