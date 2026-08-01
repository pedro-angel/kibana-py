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
Reading CPython's `subprocess.Popen._execute_child` directly (not assumed, and
checked across all four supported interpreters via `.nox/test-3-*`) shows its
`posix_spawn` fast path is gated on `close_fds` — but the exact gate is **not**
the same across the supported version range:

```python
# Python 3.11 / 3.12 (checked directly in .nox/test-3-11, .nox/test-3-12):
if (_USE_POSIX_SPAWN
        and os.path.dirname(executable)
        and preexec_fn is None
        and not close_fds        # <- disqualified here; close_fds defaults True
        and not pass_fds
        ...):
    self._posix_spawn(...)
    return

# Python 3.13 / 3.14 (checked directly in .nox/test-3-13, .nox/test-3-14):
if (_USE_POSIX_SPAWN
        and os.path.dirname(executable)
        and preexec_fn is None
        and (not close_fds or _HAVE_POSIX_SPAWN_CLOSEFROM)   # <- widened
        and not pass_fds
        ...):
    self._posix_spawn(...)
    return
```

`_HAVE_POSIX_SPAWN_CLOSEFROM = hasattr(os, 'POSIX_SPAWN_CLOSEFROM')` — checked
directly on this box, `False` for both `.nox/test-3-13` and `.nox/test-3-14`
(macOS's `os` module has no `POSIX_SPAWN_CLOSEFROM`), so on **this** platform
`close_fds=True` still disqualifies `posix_spawn` and forces the classic
`fork()+exec()` path on all four interpreters — which is what actually
reproduced the bug here. `POSIX_SPAWN_CLOSEFROM` is a real POSIX flag exposed
by CPython's `os` module only where the platform's libc provides it (glibc ≥
2.34 on Linux); on a Linux box where it *is* available, 3.13+'s widened
condition could let `posix_spawn` fire even with `close_fds=True` — and
`posix_spawn`, unlike `fork()`, does not invoke `pthread_atfork` handlers at
all, so gRPC's handler would never run and this diagnostic could not appear
that way on such a system. This is one part of why the "Linux is exposed the
same way" framing in an earlier draft of this document was too strong — see
§3 below for the fuller correction.

So this call path is not designed to dodge `fork()` via `posix_spawn` **on this
platform and interpreter set**, which is what matters for the reproduction
actually being explained here. (A
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

### 3. Platform correction — and what is, and is not, established about Linux

The captured diagnostic is emitted by **`ev_poll_posix.cc`** — gRPC's plain
POSIX `poll()`-based polling-engine backend, used here because macOS has no
`epoll`. Issue #100 framed the fork-unsafety diagnostic as tied to Linux's
`epoll1` backend (`ev_epoll1_linux.cc`) specifically, and scoped its gate to
Linux CI on that basis. **That specific attribution — that this exact sighting
is an `epoll1` artifact — does not hold**, since what actually reproduced here
is the `poll()` backend, not `epoll1`, on a platform that never runs `epoll1`
at all (macOS has no epoll). That much is a real correction to #100's framing.

**What this investigation does *not* establish, corrected from an earlier
draft of this document:** that the fix, or the underlying mechanism, transfers
to Linux/`epoll1`. Checked directly against the installed `grpcio` 1.83.0's
compiled extension (`strings` against `grpc/_cython/cygrpc.cpython-312-darwin.so`):
the literal text `"FD from fork parent still in poll list"` appears only
alongside `ev_poll_posix.cc` (both the legacy `iomgr` and newer `posix_engine`
copies of that file) — **not** alongside `ev_epoll1_linux.cc` anywhere in the
binary. `epoll1` is a different implementation; if it emits an analogous
fork-safety diagnostic on a stale post-fork entry at all, its wording is not
confirmed to match this pattern, and the regex below is deliberately not
written to guess at a Linux shape it has never observed. Separately (§1), on a
Linux box where `os.POSIX_SPAWN_CLOSEFROM` is available (glibc ≥ 2.34), Python
3.13+'s widened `posix_spawn` fast-path condition could route
`_run_with_blocked_imports`'s call through `posix_spawn` instead of `fork()`
even with `close_fds=True` — and `posix_spawn` does not invoke
`pthread_atfork` handlers at all, so this diagnostic could not arise that way
on such a system regardless of backend.

Net: **issue #100's original Linux/`epoll1` seed-loop gate remains exactly as
originally scoped** — this investigation neither confirms nor rules out an
analogous Linux sighting, and the fix below is verified only against the
`ev_poll_posix.cc` shape actually observed on this platform. It is not claimed
to be backend-agnostic, and CI's Linux jobs are not established to be "exposed
the same way" as this local sighting.

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
- **The Linux/`epoll1` framing in #100's original gate is corrected only in
  its specific attribution, not confirmed or refuted more broadly.** This
  investigation demonstrates the mechanism reproduces on macOS's `poll()`
  backend, not on `epoll1` (§3) — so #100's premise that *this exact sighting*
  is an `epoll1`-specific artifact does not hold, since `epoll1` never runs on
  the platform where it reproduced. That is the extent of the correction.
  **The fix is verified only against the `ev_poll_posix.cc` message shape
  actually observed here** — `strings` against the compiled `grpcio` 1.83.0
  extension found the matched text only alongside `ev_poll_posix.cc`, never
  `ev_epoll1_linux.cc` (§3) — and is not claimed to be backend-agnostic or to
  already cover whatever Linux's `epoll1` backend does or does not emit.
- **#100's originally-specified Linux seed-loop gate remains as originally
  scoped and is left to the controller to schedule, as directed** — it was not
  executed here (no Linux CI access from this environment), and nothing in
  this investigation reduces its value: whether `epoll1` produces an analogous
  diagnostic, in what shape, and whether this fix's regex would need a second,
  Linux-specific pattern to also cover it, is exactly what that gate would
  determine and remains unanswered. §1 adds a further, separate reason a
  Linux-specific check still matters: on a Linux box where
  `os.POSIX_SPAWN_CLOSEFROM` is available (glibc ≥ 2.34), Python 3.13+ could
  route this same call through `posix_spawn` instead of `fork()`, which would
  change whether this class of diagnostic can appear at all on such a system —
  another platform-specific variable this hunt would need to account for.
- This fix's commit references #100 with `Refs`, not `Fixes` — the issue's
  literal, filed gate (a Linux CI seed-loop hunt with a recorded bounded-clean-
  or-root-caused result) was not executed as part of this change; only the
  local sighting that interrupted `make dod` was root-caused and fixed. The
  controller closes #100 once satisfied with the disposition above.

## Micro-round — filter review response

A reviewer re-attacked this evidence before merge. The regex anchor itself was
verified tight (real warnings unmatched, an adjacent-but-different
`ev_poll_posix.cc` line unmatched, and the regression test proven
non-tautological by a revert-and-rerun showing genuine RED). One MAJOR and two
minor findings on the surrounding *claims*, all addressed:

1. **[MAJOR] "Backend-agnostic" / "already covers whatever backend Linux CI
   uses" was refuted, not merely softened.** The reviewer searched the
   compiled `grpcio` 1.83.0 extension directly and found the literal string
   `"FD from fork parent still in poll list"` only alongside `ev_poll_posix.cc`
   — never `ev_epoll1_linux.cc`, whose file-name-anchored appearance in the
   binary's strings is unrelated (a poller-name enum, not this log line).
   Independently re-verified in this round with the same technique (`strings`
   against `grpc/_cython/cygrpc.cpython-312-darwin.so`): confirmed, two hits,
   both immediately adjacent to the two `ev_poll_posix.cc` paths (legacy
   `iomgr` and newer `posix_engine`), zero hits adjacent to
   `ev_epoll1_linux.cc`. Every "backend-agnostic" / "Linux is exposed the same
   way" / "already covers Linux" claim (the code comment above
   `_GRPC_FORK_DIAGNOSTIC_RE`, the CHANGELOG entry, and §3 plus "Updated
   expectations" in this document) is struck and replaced: the fix is scoped
   to the `ev_poll_posix.cc` shape actually observed; an analogous
   `epoll1`-emitted diagnostic, if one exists at all, is unverified and not
   assumed to share this wording; #100's originally-scoped Linux seed-loop
   gate stands, unchanged in scope by this fix.
2. **[minor] The `Popen._execute_child` excerpt presented the pre-3.13
   condition as the whole story.** Checked directly across all four
   interpreters (`.nox/test-3-11` through `.nox/test-3-14`): 3.11/3.12 gate
   `posix_spawn` on bare `not close_fds`; 3.13/3.14 widen it to
   `not close_fds or _HAVE_POSIX_SPAWN_CLOSEFROM`, where
   `_HAVE_POSIX_SPAWN_CLOSEFROM = hasattr(os, 'POSIX_SPAWN_CLOSEFROM')` — a
   flag CPython's `os` module only exposes where the platform's libc provides
   it (glibc ≥ 2.34 on Linux). Confirmed `False` on this macOS box for both
   3.13 and 3.14 nox envs, so the behavioral conclusion for *this*
   reproduction is unaffected — but on a Linux 3.13+/glibc≥2.34 combination
   where it is `True`, `posix_spawn` could fire even with `close_fds=True`,
   and `posix_spawn` never invokes `pthread_atfork` handlers at all. §1 and §3
   now state the version split and flag this as a second, independent reason
   "Linux is exposed the same way" cannot be asserted.
3. **[minor] `test_leaves_a_real_kibana_warning_untouched` used a hand-typed
   stand-in for the message `_report_guarded_import_failure` actually
   emits.** Replaced with a live capture: the test now runs the exact same
   `_run_with_blocked_imports(("opentelemetry.exporter.otlp.proto.grpc",),
   TestImportGuardMatrix.PROBE, error="TypeError")` call
   `test_import_kibana_under_corrupted_install` exercises, asserts the real
   captured stderr actually contains `"is installed but failed to import"`
   and `"RuntimeWarning"` (guarding against an accidentally-empty or
   unrelated capture), and then asserts the filter is a no-op against that
   verbatim, runtime-produced text — rather than a guess at its shape.

Re-verification after these changes: `pytest tests/unit/test_observability.py`
(155 passed — the corrected test still passes, and still fails if the fix is
un-wired, confirmed by re-running the same revert-and-rerun check used
originally); `pre-commit run --all-files` clean. No behavioral change to the
shipped filter (`_GRPC_FORK_DIAGNOSTIC_RE` and
`_without_known_benign_fork_noise` are byte-for-byte the same regex and
function as before this round) — only the surrounding claims and one test's
fixture were corrected.
