# Evidence — scheme-less host string fails fast instead of routing to localhost (issue #71)

**Date:** 2026-07-31
**Change under test:** `_build_node_configs` in `kibana/_sync/client/__init__.py`
(shared by `AsyncKibana` via `from kibana._sync.client import _build_node_configs`
in `kibana/_async/client/__init__.py`), on branch `fix/scheme-less-host-71`.
**Base commit (pre-fix, "main"):** `8a93b74`.

## Why

`_build_node_configs` parsed every string host with `urllib.parse.urlparse`. A
scheme-less string like `"myhost:5601"` mis-parses under `urlparse` — `urlparse`
reads `myhost` as the *scheme* (because of the trailing `:`), leaving `netloc`
empty, so the code's `parsed_url.hostname or "localhost"` fallback silently
produced `NodeConfig(scheme='myhost', host='localhost', port=5601,
path_prefix='/5601')`. `Kibana("myhost:5601")` (and `AsyncKibana(...)`, which
shares the same function) silently sent all traffic to `localhost` with a
bogus scheme instead of failing. Decided design (not reopened here): reject
scheme-less strings rather than assume a default scheme — silently defaulting
to `http://` would surprise TLS deployments expecting `https://`.

## Fix summary

`kibana/_sync/client/__init__.py`, inside the per-host string branch of
`_build_node_configs`: call `urlparse(host)` first, then raise `ValueError`
when the parsed result has no real scheme or hostname —
`not parsed_url.scheme or parsed_url.hostname is None` — naming the
offending input (via plain `{host}` interpolation, matching the sibling
raises already in this function) and the expected form
(`'http://host:port' or 'https://host:port'`), before any
`NodeConfig`/transport construction ever runs. Both `Kibana` and `AsyncKibana`
get the fix from one edit, since the async client imports
`_build_node_configs` directly from `kibana._sync.client` rather than
maintaining its own copy (confirmed by
`grep -n "_build_node_configs" kibana/_async/client/__init__.py` →
`from kibana._sync.client import _build_node_configs, _build_node_options`).
Dict hosts, `cloud_id`, and non-string/non-dict rejection are untouched — the
check only fires on `isinstance(host, str)` entries whose parsed form is
missing a scheme or a hostname.

**Note on iteration:** an earlier version of this fix used a `"://" not in
host` substring guard. A code-quality review found that guard bypassable —
`"://"`, `"http://"`, and `"host/path?q=a://b"` all contain the `"://"`
substring (or contain it in the wrong place) yet still parse to no real
scheme/hostname, so they slipped past a substring check while still silently
building a localhost `NodeConfig`. The structural `urlparse`-first check
above replaces that substring guard and closes all three; it does not
restrict which schemes are accepted (any real `scheme://host` — including
odd-but-parsable non-http(s) schemes — is unaffected), only whether a scheme
and hostname parsed at all. The RED/GREEN detail for those three inputs is
tracked in `tests/unit/test_build_node_configs.py`
(`test_forms_containing_but_not_using_scheme_separator_raise`), not repeated
here since it landed after this evidence file was first captured; the
live-battle-test outputs below were re-verified against the final structural
guard (see the note under section (b)).

## TDD — RED then GREEN

New test module `tests/unit/test_build_node_configs.py` calls
`_build_node_configs` directly; `tests/unit/test_kibana_client.py` and
`tests/unit/test_async_kibana_client.py` each gained a parametrized
constructor-level test (`test_init_with_scheme_less_host_raises_value_error`)
covering both public entry points.

**RED (against pre-fix code, watched fail for the right reason):**

```
$ .venv/bin/pytest tests/unit/test_build_node_configs.py -v --no-cov
...
tests/unit/test_build_node_configs.py::TestBuildNodeConfigsSchemeLessHosts::test_scheme_less_string_raises_value_error[myhost:5601] FAILED
tests/unit/test_build_node_configs.py::TestBuildNodeConfigsSchemeLessHosts::test_scheme_less_string_raises_value_error[localhost:5601] FAILED
tests/unit/test_build_node_configs.py::TestBuildNodeConfigsSchemeLessHosts::test_scheme_less_string_raises_value_error[myhost] FAILED
tests/unit/test_build_node_configs.py::TestBuildNodeConfigsSchemeLessHosts::test_scheme_less_string_does_not_default_to_localhost FAILED
tests/unit/test_build_node_configs.py::TestBuildNodeConfigsSchemeLessHosts::test_scheme_less_host_in_list_raises_value_error FAILED
5 failed, 9 passed in 3.71s
```

Each failure is `pytest.raises(ValueError)` finding no exception raised —
i.e. `_build_node_configs("myhost:5601", None)` returned a (bogus) NodeConfig
list instead of raising, reproducing the issue exactly. The 9 passes at RED
time are the pre-existing valid-URL, dict-host, and non-string-non-dict cases
— confirming those code paths already worked and this fix must not disturb
them.

**GREEN (after the minimal fix):**

```
$ .venv/bin/pytest tests/unit/test_build_node_configs.py -v --no-cov
...
============================== 14 passed in 0.06s ==============================

$ .venv/bin/pytest tests/unit/test_kibana_client.py tests/unit/test_async_kibana_client.py \
    tests/unit/test_build_node_configs.py -v --no-cov
============================== 95 passed in 0.45s ==============================
```

## Full unit suite + linters (Makefile canonical targets)

```
$ make test
============================ 3194 passed in 13.73s =============================
Required test coverage of 90% reached. Total coverage: 94.21%

$ make lint
.venv/bin/mypy kibana/
Success: no issues found in 102 source files

$ make audit
.venv/bin/pip-audit
No known vulnerabilities found

$ make sast
.venv/bin/bandit -r kibana/ -ll -q
(no output = no findings, exit 0)

$ make hooks
.venv/bin/pre-commit run --all-files
... (all hooks) .......................................................Passed
.venv/bin/pre-commit run check-pin-comments-match --hook-stage manual --all-files
every pin's # comment still dereferences to its SHA (network; run at CI/manual stage) Passed

$ make docs
... build succeeded.
.venv/bin/pre-commit run check-diagrams-rendered --hook-stage manual --all-files
every mermaid fence rendered in the built docs (post-docs-build; run at CI/manual stage) Passed
```

## Sync/async parity test (explicit run)

```
$ .venv/bin/pytest tests/unit/test_sync_async_parity.py -v --no-cov
...
tests/unit/test_sync_async_parity.py::test_public_method_bodies_match[Kibana] PASSED
tests/unit/test_sync_async_parity.py::test_discovered_the_client_pairs PASSED
============================= 139 passed in 0.65s ==============================
```

## Battle-test — live stack

**Run (properties, not runner):**

| Property | Value |
|---|---|
| Arch / OS | arm64 / Darwin |
| Python (venv) | 3.11.15 |
| Role | local arm64 macOS dev workstation |
| Kibana | `http://localhost:5601` (elastic-start-local stack, already up; confirmed reachable, `curl -o /dev/null -w '%{http_code}'` → `200`, before any test ran) |
| Credentials | resolved via `tests/integration/utils.get_integration_test_config()`, which reads `elastic-start-local/.env` (`ES_LOCAL_API_KEY` / `KIBANA_USERNAME` / `KIBANA_PASSWORD` etc.) — no secret values printed here |

**CRITICAL environment rule honored:** ports `4317`/`4318` (unrelated OTLP
collector) were never touched by this evidence run; every call below targets
only `http://localhost:5601`.

### (a) `Kibana("http://localhost:5601", ...)` still connects live

```
$ .venv/bin/python3 - <<'PYEOF'
from tests.integration.utils import create_test_kibana_client
client = create_test_kibana_client()
resp = client.status.get_status()
body = resp.body
print("status.get_status() response type:", type(resp).__name__)
print("top-level keys:", sorted(body.keys()))
print("overall status level:", body["status"]["overall"]["level"])
client.close()
print('RESULT: Kibana("http://localhost:5601", ...) connected successfully via .status.get_status()')
PYEOF
status.get_status() response type: ObjectApiResponse
top-level keys: ['metrics', 'name', 'status', 'uuid', 'version']
overall status level: available
RESULT: Kibana("http://localhost:5601", ...) connected successfully via .status.get_status()
```

→ **PASS.** The valid `http://` form is completely unaffected by the fix and
round-trips against the real, running Kibana.

### (b) `Kibana("localhost:5601", ...)` now raises before any network I/O

To prove the rejection happens *before* any connection attempt (not just
"eventually raises"), `socket.create_connection` was monkeypatched to raise an
`AssertionError` if the constructor ever tried to open a socket:

```
$ .venv/bin/python3 - <<'PYEOF'
import socket
from kibana import Kibana

def _guard(*a, **kw):
    raise AssertionError("Network I/O was attempted during Kibana() construction")

socket.create_connection = _guard
try:
    Kibana("localhost:5601")
    print("FAIL: no exception was raised")
except ValueError as e:
    print('RESULT: Kibana("localhost:5601") raised ValueError as expected, before any network I/O')
    print("Exception message:", e)
PYEOF
RESULT: Kibana("localhost:5601") raised ValueError as expected, before any network I/O
Exception message: Host localhost:5601 is missing a scheme. Expected the form 'http://host:port' or 'https://host:port'.
```

→ **PASS.** The `ValueError` fires during argument parsing inside
`_build_node_configs`, before `NodeConfig`/`Transport` construction — the
guarded `socket.create_connection` never fired, confirming no network I/O was
attempted.

**Re-verification note:** the exception message above was re-run live
against the running Kibana stack (`curl -o /dev/null -w '%{http_code}'
http://localhost:5601/api/status` → `200`, confirmed immediately before
re-running) after the guard changed from the substring check to the final
structural check and the message interpolation changed from `{host!r}` to
plain `{host}`. The only difference from the originally captured output is
quoting — `Host 'localhost:5601' is missing a scheme...` (repr, single-quoted)
became `Host localhost:5601 is missing a scheme...` (plain) — the raise site,
timing (before any network I/O), and wording are otherwise identical. The
output pasted above is the current, re-verified one.

### Bonus — `AsyncKibana` (same shared function), both directions

```
$ .venv/bin/python3 - <<'PYEOF'
import asyncio
from tests.integration.utils import create_test_async_kibana_client
from kibana import AsyncKibana

async def main():
    client = create_test_async_kibana_client()
    resp = await client.status.get_status()
    print("AsyncKibana status.get_status() overall level:", resp.body["status"]["overall"]["level"])
    await client.close()
    try:
        AsyncKibana("localhost:5601")
        print("FAIL: no exception was raised")
    except ValueError as e:
        print('AsyncKibana("localhost:5601") raised ValueError as expected:', e)

asyncio.run(main())
PYEOF
AsyncKibana status.get_status() overall level: available
AsyncKibana("localhost:5601") raised ValueError as expected: Host localhost:5601 is missing a scheme. Expected the form 'http://host:port' or 'https://host:port'.
```

(Re-run live alongside the section (b) re-verification above, against the
same reachable stack; quoting differs from the original capture the same
way — no other change.)

→ Confirms both public constructors — not just the sync one named in the
issue's battle-test gate — inherit the fix and the pre-existing valid-URL
behavior, exactly as expected from the shared-function architecture.

## Scope & caveats

- This fix only changes behavior for **string** hosts whose parsed form is
  missing a scheme or a hostname (`not urlparse(host).scheme or
  urlparse(host).hostname is None`) — not merely strings "lacking `://`";
  that weaker substring characterization was superseded once a code-quality
  review showed it was bypassable (see the note under "Fix summary"). Dict
  hosts (`{"host": ..., "port": ..., "scheme": ...}`), `cloud_id`, and
  already-invalid non-string/non-dict entries are unchanged — verified by
  `TestBuildNodeConfigsNonStringHostsUnchanged` in
  `tests/unit/test_build_node_configs.py`, which passed both at RED and GREEN.
- No default scheme is guessed; this is the explicitly decided design (see
  issue #71's "Fix" section), not left open for reconsideration.
- Point-in-time result: Kibana version and elastic-start-local stack state are
  current as of 2026-07-31.
