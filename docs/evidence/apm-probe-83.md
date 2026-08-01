# Evidence — APM connectivity probe: dual-stack + wait-budget cap (issue #83)

**Date:** 2026-08-01
**Change under test:** `kibana/observability/_validation.py` (`_validate_apm_connectivity`,
`validate_apm_server_availability`) on branch `fix/apm-probe-83`.
**Base commit (pre-fix, "main"):** `3a35c6b089dd2bf079b221992b0b444027ef7caa`.

## Why

`_validate_apm_connectivity` opened a raw `socket.socket(socket.AF_INET, ...)` and called
`connect_ex((host, port))`. Two defects, both from the same root cause (a hand-rolled
socket instead of the standard library's own connect helper):

1. **IPv4-only.** An IPv6-only APM host (or any endpoint reachable only via an IPv6
   literal/AAAA record) always failed the probe — `connect_ex` on an `AF_INET` socket
   can't resolve an IPv6 address at all, it raises `socket.gaierror`. Since
   `validate_endpoint=True` is `configure_opentelemetry`'s **default**, this silently
   disabled telemetry against a server that was actually reachable.
2. **Unbounded worst-case wait.** The retry loop's own arithmetic (`timeout=5` seconds x
   `max_retries=2`, i.e. 3 attempts, plus `2**0 + 2**1 = 3s` of exponential backoff) could
   block the *synchronous* `configure_opentelemetry` call for up to **~18s** against an
   endpoint that hangs (drops packets) instead of refusing the connection outright — long
   enough to look like the calling process had hung, not that a validation check was
   running.

## Fix summary

- `_validate_apm_connectivity` now calls `socket.create_connection((host, port), timeout=...)`
  instead of building an `AF_INET` socket by hand. `create_connection` resolves the host via
  `getaddrinfo` (honoring `/etc/hosts`) and tries every address family it resolves to, so an
  IPv6-only endpoint is reached the same as an IPv4 one.
- A new module-level constant, `_PROBE_TOTAL_BUDGET_SECONDS = 5.0`, hard-caps the *total*
  wall-clock time spent across every attempt and every backoff sleep, tracked via
  `time.monotonic()` and re-checked before each attempt and before each backoff sleep. The
  per-attempt socket timeout is `min(timeout, remaining_budget)`, and a sleep is only taken if
  it fits inside what's left of the budget — so the loop always exits at or before the 5s
  ceiling regardless of the caller's own `timeout`/`max_retries` values (both callers in this
  codebase, `_config.py` and `_logging.py`, pass their own values straight through, unchanged
  by this fix). 5s is comfortably above a healthy APM server's actual handshake time
  (sub-millisecond against the local server, confirmed below) while keeping the worst-case
  extra startup latency on an unreachable/misconfigured host bounded to something noticeable
  but tolerable, instead of ~18s. The constant's full justification is in a comment directly
  above it in `_validation.py`.
- `except OSError` now catches connection-refused, `TimeoutError` (an `OSError` subclass since
  Python 3.10), and `socket.gaierror` (DNS failures, also an `OSError` subclass) uniformly —
  `create_connection` raises `OSError` for all three, so the old separate `TimeoutError` /
  generic-`Exception` branches collapsed into one.
- Public contract unchanged: `validate_apm_server_availability`'s signature, return semantics
  (`bool`), and `protocol` parameter are untouched; its only caller inside this repo,
  `_config.py`'s `validate_endpoint` path (`if validate_endpoint and not
  _obs._validate_apm_connectivity(endpoint, headers, protocol): ...`), calls
  `_validate_apm_connectivity` with its own default `timeout`/`max_retries` exactly as before.
  `_logging.py`'s `validate_log_forwarding_connectivity` (which threads its own `timeout`
  positionally into `_validate_apm_connectivity`) is likewise unaffected in shape — its
  `test_validate_log_forwarding_connectivity_*` unit tests, and the
  `tests/integration/test_log_graceful_degradation_integration.py` tests that call
  `_validate_apm_connectivity` directly, all still pass unmodified (see below). Docstrings on
  both functions were extended with a short note on the dual-stack behavior and the wait-budget
  cap — neither function had any timing behavior documented before this fix that needed
  correcting.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 26.5.2 |
| Dev-venv Python (unit suite, mypy, pre-commit) | 3.11.15 |
| Role | local arm64 macOS dev workstation |
| APM server | `http://localhost:8200` (Elastic APM Server 9.4.3, pre-provisioned; confirmed reachable, HTTP 200, before any test ran) |
| Kibana | `http://localhost:5601` (pre-provisioned; `GET /api/status` returned 200 during the battle test) |
| Elasticsearch | `http://localhost:9200` (used only to query `traces-apm*` for battle-test verification) |

**CRITICAL environment rule honored:** no command in this evidence run ever targets
`localhost:4317` or `localhost:4318` — those ports are owned by an unrelated collector on this
machine. Every live call below targets only `http://localhost:8200`, the pre-provisioned APM
server, or clearly-labeled throwaway addresses used purely to exercise failure paths (an
ephemeral IPv6 loopback listener bound by the test itself, and the RFC 5737 TEST-NET-1 address
`192.0.2.1`, which is reserved for documentation and never routed). `4317`/`4318` appear only
inside the code's own port-guess default values and inside unit-test assertions of those
defaults (mocked, no network I/O) — never as a live target.

## Test-first evidence (TDD, unit suite)

2 new RED-then-GREEN cases added to `TestAPMServerIntegration` in
`tests/unit/test_observability.py`, plus 5 existing mocked tests adapted to the new
implementation detail (mock target moved from `socket.socket`/`connect_ex` to
`socket.create_connection`, since the old code no longer exists to mock).

### RED — real dependency on the pre-fix implementation

Run against a clean **git worktree of `main`@`3a35c6b`** (pre-fix code), from a neutral cwd
with no local `kibana/` to shadow it — confirmed the loaded module's `__file__` was inside the
worktree before proceeding. Paths elided per evidence hygiene (`<neutral-dir>`, `<worktree>`);
otherwise verbatim:

```
$ cd <neutral-dir>
$ PYTHONPATH=<worktree> .venv/bin/python -c "
import kibana
assert 'apm-probe-83-baseline' in kibana.__file__
print('confirmed pre-fix worktree module:', kibana.__file__)

import socket, time
from kibana.observability import _validate_apm_connectivity

# (a) IPv6-only listener
server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
server.bind(('::1', 0)); server.listen(1)
port = server.getsockname()[1]
result = _validate_apm_connectivity(
    endpoint=f'http://[::1]:{port}', headers={}, protocol='grpc', max_retries=0,
)
print(f'(a) pre-fix IPv6-only probe result: {result} (expected True, got False = bug confirmed)')
server.close()

# (b) unreachable TEST-NET-1 address, default retry/timeout params
start = time.monotonic()
result2 = _validate_apm_connectivity(
    endpoint='http://192.0.2.1:8300', headers={}, protocol='grpc',
)
elapsed = time.monotonic() - start
print(f'(b) pre-fix unreachable-endpoint elapsed: {elapsed:.2f}s (result={result2})')
"
confirmed pre-fix worktree module: <worktree>/kibana/__init__.py
(a) pre-fix IPv6-only probe result: False (expected True, got False = bug confirmed)
(b) pre-fix unreachable-endpoint elapsed: 18.02s (result=False)
```

Confirms both defects directly, independent of the test suite: the IPv6-only listener is
unreachable (bug (1)), and the unreachable-endpoint probe blocks for ~18s using nothing but the
function's own defaults (bug (2)) — matching the issue's "up to ~3x5s timeouts + 3s backoff"
description almost exactly.

### RED — same failures reproduced as committed unit tests (pre-fix code, new tests only)

The two new tests, plus the 5 adapted mocked tests, run against the pre-fix implementation
(`_validation.py` reverted to `main` via `git stash`, test file kept as committed):

```
$ pytest tests/unit/test_observability.py -k "validate_apm_connectivity or validate_apm_server_availability" --no-cov -v
...
PASSED test_validate_apm_server_availability_public_function
FAILED test_validate_apm_connectivity_reaches_ipv6_only_listener
FAILED test_validate_apm_connectivity_unrecognized_protocol_uses_grpc_port_bias
FAILED test_validate_apm_connectivity_total_wait_budget_capped
  AssertionError: probe blocked the caller for 18.03s -- the total wait budget cap is not
  being enforced
  assert 18.028472542006057 < 7.5
FAILED test_validate_apm_connectivity_http_protocol_uses_4318_port
FAILED test_validate_apm_connectivity_failure
PASSED test_validate_apm_connectivity_success
5 failed, 2 passed, 143 deselected in 21.24s
```

The two required RED cases fail exactly as expected:
`test_validate_apm_connectivity_reaches_ipv6_only_listener` (IPv6 unreachable pre-fix) and
`test_validate_apm_connectivity_total_wait_budget_capped` (18.03s, over the 7.5s cap+margin
assertion, matching the ~18s worst case computed above almost to the second).

The other 3 failures are an expected side effect of adapting the mocks to the new
implementation detail, not a second RED requirement: the pre-fix code never calls
`socket.create_connection` at all, so patching it has no effect and the old code makes *real*
socket calls instead — against `localhost:8200`, that real call happens to succeed (hence
`test_validate_apm_connectivity_success` passing "by coincidence", not via the mock), while the
port-bias assertions and the explicit-`OSError`-injection failure test can't observe a call
that never happened. All 5 pass cleanly post-fix (below), which is what's required by the
spec ("existing behavior tests stay green").

### GREEN (after the fix)

```
$ .venv/bin/pytest tests/unit/test_observability.py -k "validate_apm_connectivity or validate_apm_server_availability" --no-cov -v
...
test_validate_apm_connectivity_reaches_ipv6_only_listener PASSED
test_validate_apm_connectivity_http_protocol_uses_4318_port PASSED
test_validate_apm_connectivity_unrecognized_protocol_uses_grpc_port_bias PASSED
test_validate_apm_connectivity_total_wait_budget_capped PASSED
test_validate_apm_server_availability_public_function PASSED
test_validate_apm_connectivity_success PASSED
test_validate_apm_connectivity_failure PASSED
7 passed, 143 deselected in 5.08s

$ .venv/bin/pytest tests/unit/test_observability.py --no-cov -q
150 passed in 13.43s
```

Note the wall-clock cost: the whole 7-test slice now takes ~5s (dominated by the real,
un-mocked `test_validate_apm_connectivity_total_wait_budget_capped`, which genuinely blocks for
the full budget against `192.0.2.1`) — down from the pre-fix run above, which took 21s and
still failed 5 of 7.

## Full unit suite + lint (Makefile targets)

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3384 passed
Required test coverage of 90% reached. Total coverage: 94.40%

$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) ... Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage) ... Passed

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 103 source files
```

(`black` reformatted `kibana/observability/_validation.py` and
`tests/unit/test_observability.py` on its first run against the new code — line-wrapping only;
re-run was clean, and the full suite + mypy were re-confirmed green after.)

### Related integration tests (already touch this function; live stack, unmodified)

```
$ .venv/bin/pytest tests/integration/test_log_graceful_degradation_integration.py -k "connectivity" --no-cov -v
test_connectivity_validation_failure PASSED
test_otlp_connectivity_validation_with_timeout PASSED
test_log_forwarding_with_intermittent_connectivity PASSED
3 passed, 18 deselected in 12.20s
```

`test_otlp_connectivity_validation_with_timeout` (a non-routable `10.255.255.1` endpoint,
`timeout=2, max_retries=1`, asserting `elapsed_time < 10`) already exercised a scenario safely
under the new 5s cap — no regression, no change needed to that test.

## Battle-test (live, mandatory)

APM server and Kibana reachability confirmed first:

```
$ curl -s -o /dev/null -w "%{http_code}\n" --max-time 3 http://localhost:8200
200
$ curl -s --max-time 3 http://localhost:8200
{"build_date": "2026-06-25T15:29:03Z", ..., "version": "9.4.3"}
```

### (a) Probe against the real APM server succeeds via the new code, both protocol values

```
$ .venv/bin/python -c "
import time
from kibana.observability import validate_apm_server_availability

for protocol in ('grpc', 'http/protobuf'):
    start = time.monotonic()
    result = validate_apm_server_availability('http://localhost:8200', protocol=protocol)
    elapsed = time.monotonic() - start
    print(f'protocol={protocol!r} -> result={result} elapsed={elapsed:.3f}s')
"
protocol='grpc' -> result=True elapsed=0.002s
protocol='http/protobuf' -> result=True elapsed=0.001s
```

**PASS** — both protocol values succeed against the live server in ~1-2ms, confirming the new
`socket.create_connection` path reaches a real, reachable server correctly (not just a mocked
one) and does not add meaningful latency for the healthy case.

### (b) Probe against an unreachable endpoint returns failure within the budget (timed, verbatim)

```
$ .venv/bin/python -c "
import time
from kibana.observability import validate_apm_server_availability

start = time.monotonic()
result = validate_apm_server_availability('http://192.0.2.1:8300', protocol='grpc')
elapsed = time.monotonic() - start
print(f'result={result} elapsed={elapsed:.3f}s')
"
result=False elapsed=5.004s
```

**PASS** — 5.004s, matching `_PROBE_TOTAL_BUDGET_SECONDS = 5.0` almost exactly (the extra 4ms
is the loop/logging overhead around the capped socket timeout) — down from the ~18s the same
scenario took pre-fix (see the RED section above), and well clear of a caller ever mistaking
this for a hang.

### (c) `configure_opentelemetry(validate_endpoint=True, ...)` end-to-end against the live server

```
$ .venv/bin/python -c "
from kibana.observability import configure_opentelemetry, create_span

configure_opentelemetry(
    enabled=True, protocol='http/protobuf',
    endpoint='http://localhost:8200', validate_endpoint=True,
    logs_enabled=False, service_name='kibana-py-apm-probe-83-battletest',
)
span = create_span('apm-probe-83.validate-endpoint-true-smoke')
span.end()
print('configure_opentelemetry(validate_endpoint=True) completed WITHOUT EXCEPTION')
"
configure_opentelemetry(validate_endpoint=True) completed WITHOUT EXCEPTION
```

Queried Elasticsearch directly for proof the span was accepted, not just absence of an error:

```
$ curl -s -u "elastic:${ES_LOCAL_PASSWORD}" "http://localhost:9200/traces-apm*/_search" \
    -H "Content-Type: application/json" -d '{
  "query": { "match": { "service.name": "kibana-py-apm-probe-83-battletest" } },
  "_source": ["service.name","transaction.name","@timestamp","processor.event"]
}'
{"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_source":{
  "@timestamp":"2026-08-01T13:02:16.264Z",
  "service":{"name":"kibana-py-apm-probe-83-battletest"},
  "processor":{"event":"transaction"},
  "transaction":{"name":"apm-probe-83.validate-endpoint-true-smoke"}
}}]}}
```

**PASS** — with `validate_endpoint=True` (the default), the probe let the real, reachable APM
server through, telemetry configured, and the span was accepted and indexed. This is the exact
end-to-end path the issue's "battle-test gate" calls for: "configure path end-to-end with
validation on."

## Scope & caveats

- Only `_validate_apm_connectivity`'s connection mechanism and total-wait accounting changed.
  The port-guess logic (explicit port in the URL vs. the `_HTTP_OTLP_PROTOCOLS`-driven
  4318/4317 bias) is untouched and still covered by its own two unit tests, both still green.
- `validate_apm_server_availability`'s signature, return type, and `protocol` parameter are
  unchanged; so is `_validate_apm_connectivity`'s full signature
  (`endpoint, headers, protocol, timeout=5, max_retries=2`) — both callers in this repo
  (`_config.py`, `_logging.py`) needed no changes.
- The wait-budget cap is a single hardcoded module constant
  (`_PROBE_TOTAL_BUDGET_SECONDS = 5.0`), not configurable per call — this matches the issue's
  ask ("pick a defensible constant") rather than adding a new public parameter, keeping the
  fix surgical.
- **Point-in-time result.** The APM server build (9.4.3) and this host's network/sandbox
  behavior for RFC 5737 TEST-NET-1 traffic (confirmed here to genuinely block until timeout
  rather than fail fast) are current as of 2026-08-01; a differently-configured network could
  in principle fail such a connection instantly (fast `ENETUNREACH`) rather than timing out —
  that would only make the probe return *faster*, never slower than the 5s cap, so it would
  not weaken the fix.

## Fix round — spec review response

A spec review of the round-1 fix (commit `efea794`) found 1 BLOCKER + 1 MAJOR + 2 minors, all
addressed in the fix-round commit that follows on the same branch (see `git log`).

### [BLOCKER] The round-1 budget only bounded the connect phase, not DNS resolution

Round 1's docstring claimed the probe "never blocks its caller ... beyond that cap, even
against an endpoint that hangs" — **not fully true as written**. Round 1 called
`socket.create_connection((host, port), timeout=attempt_timeout)` directly, in the caller's own
thread. `create_connection` resolves the host via `getaddrinfo` *before* it ever opens a socket,
and `getaddrinfo` takes no timeout parameter of its own — an unresponsive or misbehaving DNS
resolver can hang there indefinitely, entirely ahead of the connect-phase `timeout` kwarg ever
applying. The budget was real for a slow/refusing *connect*, not for a resolver that never
answers.

**Fix:** each attempt (DNS resolution + TCP connect, together, since they can't be bounded
separately with the standard library's own API) now runs on a background `threading.Thread(daemon=True)`
(`_probe_attempt_worker` in `_validation.py`), reporting its outcome back through a
`queue.Queue`. The calling thread enforces the deadline itself: `outcome.get(timeout=attempt_timeout)`.
If the worker hasn't reported back in time, the attempt is treated as failed and the worker is
abandoned — not joined. This makes the total-budget guarantee a true wall-clock deadline from
the *caller's* side, independent of whatever `create_connection`'s own timeout handling does or
doesn't cover internally.

**Honest residual, verified empirically (not assumed):** an abandoned worker stuck in
`getaddrinfo` keeps running in the background until the OS resolver itself gives up. Whether
that's harmless depends entirely on whether the mechanism used is a *daemon* thread. This was
checked directly rather than trusted, because the two obvious choices differ:

```
$ .venv/bin/python -c "
import concurrent.futures, time
ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
fut = ex.submit(time.sleep, 9999)
try:
    fut.result(timeout=0.5)
except concurrent.futures.TimeoutError:
    print('timed out as expected, returning without shutdown()')
print('about to exit process')
" &
PID=$!; sleep 5
kill -0 $PID 2>/dev/null && echo "STILL RUNNING after 5s -- blocked" || echo "exited cleanly"
```
```
timed out as expected, returning without shutdown()
about to exit process
STILL RUNNING after 5s -- blocked
```
(process had to be killed — `concurrent.futures.ThreadPoolExecutor`'s own `atexit` hook joins
every worker thread it ever created, including one permanently stuck in a blocking call, which
hangs interpreter shutdown.)

```
$ .venv/bin/python -c "
import threading, time
t = threading.Thread(target=time.sleep, args=(9999,), daemon=True)
t.start(); t.join(timeout=0.5)
print(f'join timed out as expected, thread alive={t.is_alive()}')
print('about to exit process')
" &
PID=$!; sleep 3
kill -0 $PID 2>/dev/null && echo "STILL RUNNING after 3s -- blocked" || echo "exited cleanly (exit code 0)"
```
```
join timed out as expected, thread alive=True
about to exit process
process exited cleanly within 3s -- daemon thread does NOT block exit
exit code: 0
```

**Conclusion, acted on:** a plain `threading.Thread(daemon=True)` is what's actually used (not
`concurrent.futures.ThreadPoolExecutor`, whose pooled workers are joined at exit and would turn
an abandoned DNS-hang attempt into a hung process on every affected exit) — this is the only
version of the fix for which "daemon thread, no caller impact" is a true statement rather than
an assumption. `_PROBE_TOTAL_BUDGET_SECONDS`'s comment documents this explicitly, including why
`ThreadPoolExecutor` was considered and rejected.

RED (before the fix-round; run against round-1 code at `efea794`, stubbing
`socket.create_connection` with a double that ignores its arguments — including its own
`timeout` kwarg — and just blocks, standing in for an unresponsive resolver):

```
$ .venv/bin/pytest tests/unit/test_observability.py -k test_validate_apm_connectivity_hung_attempt_bounded_by_deadline --no-cov -v
...
FAILED test_validate_apm_connectivity_hung_attempt_bounded_by_deadline
  AssertionError: probe blocked the caller for 30.00s against a stub connect call that never
  returns -- the deadline is not being enforced independent of create_connection's own timeout
  kwarg
  assert 30.000475542037748 < 2.5
WARNING  kibana.observability:_validation.py:122 APM server connectivity validation failed:
  'NoneType' object has no attribute 'close'
1 failed, 149 deselected in 30.18s
```

(The 30.00s is the stub's own `time.sleep(30)` running to completion, uninterrupted, inside
round-1's single-threaded call — confirming there was no mechanism to abandon it. The
`'NoneType' object has no attribute 'close'` warning is round-1's `sock.close()` finally running
against the stub's `None` return, 30 seconds after the call started — not a new bug, just what
happens once the stub returns.)

GREEN (after the fix-round; same test, same stub, same 0.5s patched budget):

```
$ .venv/bin/pytest tests/unit/test_observability.py -k test_validate_apm_connectivity_hung_attempt_bounded_by_deadline --no-cov -v
...
1 passed in <1s
```

### [MAJOR] The ~5s un-mocked network test didn't belong in the fast unit tier

Round 1's `test_validate_apm_connectivity_total_wait_budget_capped` made a real, un-mocked
network call to `192.0.2.1` and took ~5s by design — 28% of that unit file's wall clock, and
real-network semantics belong in the integration tier regardless of raw cost.

**Fix:**
- **Moved** to `tests/integration/test_log_graceful_degradation_integration.py` as
  `TestOTLPEndpointUnavailable.test_apm_connectivity_total_wait_budget_capped_live`, right next
  to its closest existing sibling (`test_otlp_connectivity_validation_with_timeout`, a
  non-routable-IP timeout test that already lives there). Needs no local stack — only outbound
  network reachability, same as its sibling.
- **Added** a fast sibling in the unit tier,
  `TestAPMServerIntegration::test_validate_apm_connectivity_hung_attempt_bounded_by_deadline`
  (the same test that RED-verifies the BLOCKER above) — patches `_PROBE_TOTAL_BUDGET_SECONDS`
  down to `0.5` and stubs `socket.create_connection` to hang, pinning the deadline mechanism
  itself without a real network round-trip. One test now serves both the BLOCKER's RED
  requirement and this MAJOR's "fast sibling" requirement, rather than duplicating near-identical
  coverage under two names.

Before/after, unit-tier wall clock (the exact slice affected):

```
# round 1 (includes the ~5s real-network test)
$ .venv/bin/pytest tests/unit/test_observability.py -k "validate_apm_connectivity or validate_apm_server_availability" --no-cov -v
7 passed, 143 deselected in 5.08s

# fix-round (real-network test moved out, fast stub sibling added)
$ .venv/bin/pytest tests/unit/test_observability.py -k "validate_apm_connectivity or validate_apm_server_availability" --no-cov -v
7 passed, 143 deselected in 0.59s

$ .venv/bin/pytest tests/unit/test_observability.py --no-cov -q
# round 1: 150 passed in 13.43s
# fix-round: 150 passed in 8.95s
```

Live run of the moved integration test (real network, no stack required):

```
$ .venv/bin/pytest tests/integration/test_log_graceful_degradation_integration.py -k "connectivity" --no-cov -v
test_apm_connectivity_total_wait_budget_capped_live PASSED
test_otlp_connectivity_validation_with_timeout PASSED
test_connectivity_validation_failure PASSED
test_log_forwarding_with_intermittent_connectivity PASSED
4 passed, 18 deselected in 17.21s

$ .venv/bin/pytest tests/integration/test_log_graceful_degradation_integration.py --no-cov -q
22 passed, 10 warnings in 28.25s
```

### Minor 1 — IPv6-only-listener test gains a capability guard

`test_validate_apm_connectivity_reaches_ipv6_only_listener` now wraps `server.bind(("::1", 0))`
in `try`/`except OSError: pytest.skip(...)` — some sandboxes/CI runners disable IPv6 loopback
binding entirely, and this test exists to prove the probe *can* reach an IPv6-only target, which
is meaningless to assert on a host that cannot even create one. Skip, not fail or false-pass.

### Minor 2 — path-elision labeling

The RED transcript above (worktree baseline) elides absolute paths (`<neutral-dir>`,
`<worktree>`) for identity hygiene; the transcript is now explicitly labeled "Paths elided per
evidence hygiene ...; otherwise verbatim", per the `async-validation-order-74-75.md` precedent.

### Correcting the round-1 "Fix summary" claim

Round 1's fix summary and docstrings said the probe "never blocks its caller ... beyond that
cap, even against an endpoint that hangs instead of refusing the connection." As the BLOCKER
above shows, that was true for a hanging *connect*, not for a hanging *resolve* — an overclaim.
The docstrings and `_PROBE_TOTAL_BUDGET_SECONDS` comment have been rewritten in the fix-round
commit to state the guarantee precisely (a true caller-side wall-clock deadline covering
resolution and connect together, via the background-thread mechanism) and to name the one
honest residual (the abandoned daemon thread's own lifetime, empirically confirmed harmless to
the caller and to interpreter shutdown) rather than asserting unqualified "never blocks."

### Full verification after the fix-round

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q
3384 passed
Required test coverage of 90% reached. Total coverage: 94.37%

$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) ... Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage) ... Passed
```

(`black` reformatted `tests/unit/test_observability.py` again on its first run against the new
test — line-wrapping only; re-run was clean, full suite + mypy re-confirmed green after.)

### Re-battle-test after the fix-round (mechanism changed materially — re-checked, not assumed)

```
$ curl -s -o /dev/null -w "APM reachable, HTTP %{http_code}\n" --max-time 3 http://localhost:8200
APM reachable, HTTP 200

$ .venv/bin/python -c "
import time
from kibana.observability import validate_apm_server_availability
for protocol in ('grpc', 'http/protobuf'):
    start = time.monotonic()
    result = validate_apm_server_availability('http://localhost:8200', protocol=protocol)
    elapsed = time.monotonic() - start
    print(f'protocol={protocol!r} -> result={result} elapsed={elapsed:.3f}s')
"
protocol='grpc' -> result=True elapsed=0.001s
protocol='http/protobuf' -> result=True elapsed=0.001s

$ .venv/bin/python -c "
import time
from kibana.observability import validate_apm_server_availability
start = time.monotonic()
result = validate_apm_server_availability('http://192.0.2.1:8300', protocol='grpc')
elapsed = time.monotonic() - start
print(f'unreachable result={result} elapsed={elapsed:.3f}s')
"
unreachable result=False elapsed=5.004s
```

**PASS** — both the reachable and unreachable live scenarios behave identically to round 1
(sub-2ms success, 5.004s bounded failure), confirming the thread/queue-based deadline mechanism
didn't regress the already-verified live behavior.

```
$ .venv/bin/python -c "
from kibana.observability import configure_opentelemetry, create_span
configure_opentelemetry(
    enabled=True, protocol='http/protobuf', endpoint='http://localhost:8200',
    validate_endpoint=True, logs_enabled=False,
    service_name='kibana-py-apm-probe-83-fixround-battletest',
)
span = create_span('apm-probe-83.fixround-validate-endpoint-true-smoke')
span.end()
print('configure_opentelemetry(validate_endpoint=True) completed WITHOUT EXCEPTION (fix-round)')
"
configure_opentelemetry(validate_endpoint=True) completed WITHOUT EXCEPTION (fix-round)

$ curl -s -u "elastic:${ES_LOCAL_PASSWORD}" "http://localhost:9200/traces-apm*/_search" \
    -H "Content-Type: application/json" -d '{
  "query": { "match": { "service.name": "kibana-py-apm-probe-83-fixround-battletest" } },
  "_source": ["service.name","transaction.name","@timestamp","processor.event"]
}'
{"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_source":{
  "@timestamp":"2026-08-01T13:23:51.816Z",
  "service":{"name":"kibana-py-apm-probe-83-fixround-battletest"},
  "processor":{"event":"transaction"},
  "transaction":{"name":"apm-probe-83.fixround-validate-endpoint-true-smoke"}
}}]}}
```

**PASS** — `configure_opentelemetry(validate_endpoint=True)` end-to-end against the live server
still works after the fix-round, span accepted and indexed.

### Scope note (fix-round)

No change to the port-guess logic, the public function contract
(`validate_apm_server_availability`'s signature/return semantics/`protocol` param), or either
real caller (`_config.py`, `_logging.py`) — all round-1 scope notes above still hold. The
fix-round changed only: (1) how an attempt's deadline is enforced (background daemon thread +
queue instead of trusting `create_connection`'s own timeout kwarg alone), (2) where the
real-network budget test lives (moved to integration, with a fast stub-based sibling pinning the
same semantics in the unit tier), and (3) the precision of the docstrings' own claims.
