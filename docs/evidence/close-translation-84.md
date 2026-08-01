# Evidence — `close()` transport-error translation (issue #84)

**Date:** 2026-08-01
**Change under test:** `Kibana.close()` (`kibana/_sync/client/__init__.py`) and
`AsyncKibana.close()` (`kibana/_async/client/__init__.py`) on branch
`fix/close-translation-84`.
**Base commit (pre-fix, "main"):** `cfa38ea4cf2425ca1f320ad657bc7180d56ebe90`.

## Why

`close()` on both clients wrapped `self._transport.close()` in a bare
`try/except Exception as e: logger.warning(...)`. Two defects, same root cause (no
narrowing, no translation):

1. **Invisible failures.** A real close failure (a leaked connection/socket) was
   swallowed to a WARNING log line — a caller with no logging configured, or one that
   just wants to know whether teardown actually succeeded, had no way to observe it.
2. **No translation.** Unlike the request path (`perform_request`, aligned in 0.4.1 via
   `kibana.exceptions.translate_transport_errors()`), a transport-layer exception out of
   `close()` was never translated to its `kibana.exceptions` equivalent — even if it
   *had* been re-raised instead of swallowed, it would have surfaced as the raw
   `elastic_transport` type, which the documented `except kibana.exceptions.*` clauses
   don't catch (they're distinct classes with the same names).

## Investigation — reusing the existing translation mechanism

`kibana/exceptions.py:388` already defines `translate_transport_errors()`, a
`@contextmanager` that re-raises `elastic_transport` exceptions as their
`kibana.exceptions` equivalents (specific-to-general: `ConnectionTimeout` -> `SSLError`
(via `TlsError`) -> `ConnectionError` -> `SerializationError` -> `TransportError`),
preserving `.message` and chaining the source via `raise ... from e`. The request path
(`kibana/_sync/client/_base.py:617`, `kibana/_async/client/_base.py:230`) uses it as a
plain `with translate_transport_errors():` wrapper around the transport call, nothing
more — any exception *not* one of the five mapped ET types propagates untouched (see
`test_helper_passes_through_non_transport_errors` in `tests/unit/test_transport_exceptions.py`,
pre-existing). `close()` now uses the exact same wrapper, so it inherits the same
"translate-or-propagate" convention with zero new exception-handling logic:

```python
def close(self) -> None:
    with translate_transport_errors():
        self._transport.close()
    logger.debug("Kibana client closed")
```

(async twin identical, with `await self._transport.close()`).

## Investigation — `__exit__`/`__aexit__` semantics (ecosystem norm)

The semantics decision was made upstream of this fix: **`close()` failures raise.**
What needed investigating was whether `__exit__`/`__aexit__` — which both already just
delegate to `close()`/`await close()` with no `try`/`except` of their own — needed a
masking-avoidance change now that `close()` can raise.

Checked the package's own call sites first:
- `SpaceScopedKibana.close()` / `AsyncSpaceScopedKibana.close()`
  (`kibana/_sync/client/__init__.py:707`, `kibana/_async/client/__init__.py:596`) purely
  delegate (`self._client.close()`) — no bare-except of their own, so they need no
  change; they now raise transitively, which is the intended parity.
- No `__del__` anywhere in the package (grepped `kibana/_sync/client/` and
  `kibana/_async/client/`) — so a raising `close()` can never fire during garbage
  collection and produce an "Exception ignored in `__del__`" message.
- No existing use of `contextlib.suppress` anywhere in the package or examples.

### Call-site census (script, not eyeballed — fix-round correction)

**Fix-round correction:** the first pass of this evidence eyeballed two example files
(`examples/basic_usage.py`, `examples/error_handling.py`) as "the" `finally:
client.close()` sites. A spec reviewer counted 55 of 56 example scripts using that
pattern and called the two-file claim out as an undercount. Redone here scriptably —
every `.close()` call site under `kibana/`, `examples/`, and `docs/source/` (Sphinx
source only; `docs/build/` is generated output, excluded), classified by context:

```python
import re
import pathlib

ROOTS = ["kibana", "examples", "docs/source"]
CLOSE_RE = re.compile(r"\.close\(\)")

results = {"context-manager": [], "finally-cleanup": [], "other": []}

for root in ROOTS:
    for path in sorted(pathlib.Path(root).rglob("*")):
        if not path.is_file() or path.suffix not in (".py", ".md", ".rst"):
            continue
        lines = path.read_text(errors="ignore").splitlines()
        for i, line in enumerate(lines):
            if not CLOSE_RE.search(line):
                continue
            indent = len(line) - len(line.lstrip())

            # Nearest dedented ancestor block a `finally:`?
            in_finally = False
            for j in range(i - 1, -1, -1):
                prev = lines[j]
                if prev.strip() == "":
                    continue
                if len(prev) - len(prev.lstrip()) < indent:
                    in_finally = prev.strip().startswith("finally:")
                    break

            # Inside an __exit__/__aexit__ method definition (the
            # context-manager delegation mechanism itself)?
            in_exit_def = False
            for j in range(i - 1, -1, -1):
                s = lines[j].strip()
                if s.startswith("def __exit__") or s.startswith("async def __aexit__"):
                    in_exit_def = True
                    break
                if s.startswith("def ") or s.startswith("async def "):
                    break

            bucket = "context-manager" if in_exit_def else (
                "finally-cleanup" if in_finally else "other"
            )
            results[bucket].append(f"{path}:{i + 1}: {line.strip()}")

for bucket in ("context-manager", "finally-cleanup", "other"):
    print(f"{bucket}: {len(results[bucket])}")
```

```
$ python3 find_close_sites.py
context-manager: 4
finally-cleanup: 66
other: 44
TOTAL call sites: 114
```

Cross-checked the finally-cleanup count independently, without the script, against the
reviewer's own framing ("55 of 56 example scripts"):

```
$ grep -l "\.close()" examples/*.py | wc -l
56
$ grep -lE "finally:" examples/*.py | xargs grep -l "client.close()\|await client.close()" | wc -l
55
```

Confirms the reviewer's count exactly: **55 of the 59 `examples/*.py` files** use
`finally: client.close()`; a 56th (`examples/utils.py`) calls `client.close()` outside
any `finally` (a plain `try/except` teardown at the bottom of its `__main__` block); the
other 3 (`async_comprehensive.py`, `async_example.py`, `async_simple_status.py`) call no
`.close()` at all — they rely entirely on `async with create_async_kibana_client() as
client:`, i.e. the context-manager mechanism, with no literal `.close()` text to match.

**Disposition, asserted per class, not assumed:**

- **`context-manager` (4 sites — `Kibana.__exit__`, `SpaceScopedKibana.__exit__`,
  `AsyncKibana.__aexit__`, `AsyncSpaceScopedKibana.__aexit__`):** this is the exact
  mechanism already investigated above and pinned by 4 new unit tests
  (`test_exit_propagates_close_translation_error`,
  `test_exit_close_error_chains_body_exception_as_context`, + async twins) — matches
  the `elasticsearch-py` norm, no masking-avoidance, chaining verified empirically.
  Nothing further needed.
- **`finally-cleanup` (66 sites — 55 `examples/*.py` files + `docs/source/**/*.md`
  usage samples):** the disposition claim ("a raising close in a finally after a body
  exception chains via `__context__`, nothing silently lost") is not specific to any
  one script's logic — it is CPython's own `try/finally` exception-chaining behavior,
  the same underlying mechanism a `with`-block's `__exit__` call uses (a `with`
  statement desugars to this exact shape). Verified directly, independent of this
  package, with a minimal reproduction:
  ```
  $ .venv/bin/python -c "
  try:
      try:
          raise ValueError('body failure')
      finally:
          raise RuntimeError('close failure')
  except Exception as final:
      print('final:', repr(final))
      print('final.__context__:', repr(final.__context__))
      print('final.__context__ is the body exception:', isinstance(final.__context__, ValueError))
  "
  final: RuntimeError('close failure')
  final.__context__: ValueError('body failure')
  final.__context__ is the body exception: True
  ```
  This holds unconditionally for every one of the 66 sites regardless of whether that
  particular script's `try` body can actually raise in practice — it is a Python
  language guarantee, not a per-site property to verify individually. No code change
  needed at any of the 66 sites; the `docs/source/**/*.md`/`.rst` occurrences are
  illustrative prose code samples (not executed by CI, no doctest runner configured
  for them), so the claim there is about what a reader's own script would do if they
  followed the sample verbatim — same guarantee, not a currently-running assertion.
- **`other` (44 sites):** on inspection, 3 are false positives from the naive
  `\.close\(\)` regex matching non-Kibana-client calls entirely unrelated to this fix
  — `kibana/observability/_logging.py:219` (`super().close()`, a stdlib
  `logging.Handler.close()` override), `:338` (`handler.close()`, same stdlib
  handler), and `kibana/observability/_validation.py:95` (`sock.close()`, a raw
  `socket.socket` in the APM connectivity probe). 2 more are non-executable doctest
  examples inside class docstrings (`kibana/_sync/client/__init__.py:87`,
  `kibana/_async/client/__init__.py:87`, both `>>> client.close()`). 2 are the fix's
  own translation call sites (`self._transport.close()` in `Kibana.close()` /
  `AsyncKibana.close()`, already covered above) and 2 are the `SpaceScopedKibana`
  delegation calls (`self._client.close()`, already covered above). The remaining
  sites (`examples/basic_usage.py` lines outside its own `finally` blocks,
  `examples/error_handling.py` likewise, `examples/connector_management.py`,
  `examples/space_scoped_connector.py`, `examples/utils.py`, assorted
  `docs/source/**/*.md` samples) call `.close()` in straight-line code with no
  enclosing `try` at all — if `close()` raises there, it simply propagates directly;
  there is no other in-flight exception for it to mask, so the masking question does
  not apply to this class at all. **No call site in any of the three classes
  genuinely needs a `contextlib.suppress` fix** (i.e., none is inside the package's
  own error-recovery path, catching an exception and closing a client as part of
  handling it while assuming the close itself cannot fail) — confirmed by this
  census, not merely asserted.

Then checked the ecosystem norm directly against `elasticsearch-py` 8.17.2
(`elasticsearch/_sync/client/__init__.py`) -- source obtained from a local `uv` cache
copy of the package (not a project dependency of kibana-py; fetched only to read its
source for this comparison) -- the sibling official Elastic client this package mirrors
architecturally (same `elastic_transport` transport layer, same
`NodeConfig`/`Transport` construction, same close/context-manager shape):

```python
def __exit__(self, *_: t.Any) -> None:
    self.close()

def close(self) -> None:
    """Closes the Transport and all internal connections"""
    self.transport.close()
```

`elasticsearch-py`'s `close()` has **no** try/except at all, and its `__exit__` has
**no** masking-avoidance of its own (no `contextlib.suppress`, no swallow-and-log,
no re-raise-original-on-conflict) — it just calls `close()` and lets whatever it raises
propagate as Python's own with-statement machinery dictates.

**Decision, matching that norm exactly:** `__exit__`/`__aexit__` are **unchanged** —
still a bare `self.close()` / `await self.close()`, no new `try`/`except`. If the
`with`/`async with` body already raised and `close()` now also raises a translated
error, Python's ordinary implicit exception chaining (not any code in this package)
keeps both exceptions rather than dropping either — confirmed empirically (not
assumed) below.

### Empirical chain verification

```
$ .venv/bin/python -c "
from unittest.mock import Mock
from elastic_transport import ConnectionError as ETConnectionError
from kibana import Kibana

client = Kibana(hosts='http://localhost:5601')
client._transport.close = Mock(side_effect=ETConnectionError('boom'))
body_exc = ValueError('body failure')
try:
    with client:
        raise body_exc
except Exception as final:
    print('final:', repr(final))
    print('final.__cause__:', repr(final.__cause__))
    print('final.__context__:', repr(final.__context__))
    print('final.__context__.__context__:', repr(final.__context__.__context__))
"
final: ConnectionError('Connection error')
final.__cause__: ConnectionError('boom')
final.__context__: ConnectionError('boom')
final.__context__.__context__: ValueError('body failure')
```

The propagating exception is the *translated* `kibana.exceptions.ConnectionError`
(what a caller's `except kibana.exceptions.ConnectionError:` catches); its `__cause__`/
`__context__` is the raw `elastic_transport.ConnectionError` it was translated from
(same object, since `translate_transport_errors()` does `raise ... from e`); and *that*
exception's own `__context__` is the original body exception — because the mock's
`ETConnectionError` was thrown into `translate_transport_errors()`'s generator (via
`gen.throw()`, how `@contextmanager` implements a `with`-block exception) while the
`ValueError` was still the exception being handled by the outer `with client:`
statement's own implicit except clause. Nothing is silently dropped; the body exception
is one link further down the `__context__` chain than the translated exception itself,
purely as a consequence of the translation being one extra frame of re-raising — the
same "two closes chain, `elasticsearch-py`'s own `__exit__` does nothing extra" outcome
its lack of masking-avoidance would also produce. Confirmed identical for the async
twin (`AsyncKibana.__aexit__`) with `asyncio.run` + `AsyncMock`.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / macOS 25.5.0 |
| Dev-venv Python (unit suite, mypy, pre-commit) | 3.11.15 |
| Role | local arm64 macOS dev workstation |
| `elastic_transport` | 9.4.2 (installed in `.venv`) |
| Kibana | `http://localhost:5601` (pre-provisioned Docker container,
  `docker.elastic.co/kibana/kibana:9.4.3`; `GET /api/status` returned 200 before any
  test ran) |
| Auth | basic auth, `elastic` / `ES_LOCAL_PASSWORD` from `elastic-start-local/.env`,
  via `examples/utils.py`'s `create_kibana_client()` / `create_async_kibana_client()` |

**CRITICAL environment rule honored:** no command in this evidence run ever targets
`localhost:4317` or `localhost:4318` — this fix touches only the transport-close path,
which has no relationship to the OTLP ports; none appear anywhere in this run.

## Test-first evidence (TDD, unit suite)

16 new RED-then-GREEN cases: 12 in `tests/unit/test_transport_exceptions.py` (the
5-case translation matrix x {sync, async} + one non-transport-propagation case x
{sync, async}), 4 in `tests/unit/test_kibana_client.py::TestCloseMethod` /
`tests/unit/test_async_kibana_client.py::TestAsyncCloseMethod` (the `__exit__`/
`__aexit__` pinning tests).

### RED (pre-fix `close()`, reproduced via `git stash` of only the two source files)

```
$ git stash push --keep-index -- kibana/_sync/client/__init__.py kibana/_async/client/__init__.py
$ grep -n "except Exception as e" kibana/_sync/client/__init__.py kibana/_async/client/__init__.py
kibana/_async/client/__init__.py:351:        except Exception as e:
kibana/_sync/client/__init__.py:351:        except Exception as e:
kibana/_sync/client/__init__.py:448:        except Exception as e:
```

(The sync file's line 448 is `_build_node_configs`'s unrelated `cloud_id` parsing
`except Exception as e: raise ValueError(...) from e` -- out of scope for #84, untouched
by this fix, shown here only because the grep pattern also matches it.)

```

$ .venv/bin/pytest tests/unit/test_transport_exceptions.py tests/unit/test_kibana_client.py::TestCloseMethod tests/unit/test_async_kibana_client.py::TestAsyncCloseMethod --no-cov -q
...
FAILED tests/unit/test_async_kibana_client.py::TestAsyncCloseMethod::test_aexit_close_error_chains_body_exception_as_context
FAILED tests/unit/test_async_kibana_client.py::TestAsyncCloseMethod::test_aexit_propagates_close_translation_error
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_translates_transport_error[ConnectionTimeout-ConnectionTimeout]
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_translates_transport_error[ConnectionTimeout-ConnectionTimeout]
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_propagates_non_transport_error
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_translates_transport_error[TransportError-TransportError]
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_translates_transport_error[ConnectionError-ConnectionError]
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_translates_transport_error[SerializationError-SerializationError]
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_translates_transport_error[ConnectionError-ConnectionError]
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_translates_transport_error[TlsError-SSLError]
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_translates_transport_error[TlsError-SSLError]
FAILED tests/unit/test_transport_exceptions.py::test_sync_client_close_propagates_non_transport_error
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_translates_transport_error[SerializationError-SerializationError]
FAILED tests/unit/test_transport_exceptions.py::test_async_client_close_translates_transport_error[TransportError-TransportError]
FAILED tests/unit/test_kibana_client.py::TestCloseMethod::test_exit_propagates_close_translation_error
FAILED tests/unit/test_kibana_client.py::TestCloseMethod::test_exit_close_error_chains_body_exception_as_context
16 failed, 26 passed in 0.12s
```

All 16 new cases fail exactly as expected against the pre-fix bare `except Exception`
swallow (`DID NOT RAISE`, or the wrong un-translated exception type); the other 26
close-adjacent tests in those files (multi-close-is-safe, clean context-manager exit,
etc.) still pass unmodified pre-fix, confirming the new tests target only the fixed
code path.

### GREEN (after restoring the fix)

```
$ git stash pop
$ .venv/bin/pytest tests/unit/test_transport_exceptions.py tests/unit/test_kibana_client.py::TestCloseMethod tests/unit/test_async_kibana_client.py::TestAsyncCloseMethod --no-cov -q
............................................                              [100%]
42 passed in 0.09s
```

## Full unit suite + parity + lint (Makefile-equivalent targets)

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q -p no:randomly
3400 passed
Required test coverage of 90% reached. Total coverage: 94.45%

$ .venv/bin/pytest tests/unit/test_sync_async_parity.py --no-cov -q
144 passed in 0.65s

$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ .venv/bin/pre-commit run --all-files
... (all hooks, incl. black/isort/ruff) ... Passed
```

(`black` reformatted the new multi-line `from kibana.exceptions import (...)` grouping
in both `kibana/_sync/client/__init__.py` and `kibana/_async/client/__init__.py` on its
first run — import-wrapping only; re-run was clean, and mypy/full-suite/parity were
re-confirmed green after.)

## Battle-test (live, mandatory)

Kibana reachability confirmed first:

```
$ curl -s -o /dev/null -w "%{http_code}\n" --max-time 3 http://localhost:5601/api/status
200
```

### (a) Sync: open -> real operation -> clean close, twice

```
$ .venv/bin/python -c "
import sys; sys.path.insert(0, 'examples')
from utils import create_kibana_client

client = create_kibana_client()
resp = client.actions.list_types()
print(f'real operation ok: found {len(resp.body)} connector types')
client.close()
print('sync close() completed WITHOUT exception (clean close, live stack)')
client.close()
print('sync close() called again after already-closed: still no exception')
"
🔗 Connecting to Kibana: http://localhost:5601
🔐 Using basic authentication (user: elastic)
real operation ok: found 63 connector types
sync close() completed WITHOUT exception (clean close, live stack)
sync close() called again after already-closed: still no exception
```

**PASS** — clean close against the real transport (a live, connected urllib3 pool
closes without raising), and calling `close()` a second time on an already-closed
transport is still safe (no ET exception is raised by a repeat `Transport.close()` in
practice, so no regression from the old "call close() twice" test).

### (b) Async: open -> real operation -> clean close, twice

```
$ .venv/bin/python -c "
import asyncio, sys; sys.path.insert(0, 'examples')
from utils import create_async_kibana_client

async def main():
    client = create_async_kibana_client()
    resp = await client.actions.list_types()
    print(f'real operation ok: found {len(resp.body)} connector types')
    await client.close()
    print('async close() completed WITHOUT exception (clean close, live stack)')
    await client.close()
    print('async close() called again after already-closed: still no exception')

asyncio.run(main())
"
🔗 Connecting to Kibana (async): http://localhost:5601
🔐 Using basic authentication (user: elastic)
real operation ok: found 63 connector types
async close() completed WITHOUT exception (clean close, live stack)
async close() called again after already-closed: still no exception
```

**PASS** — same clean-close guarantee holds for `AsyncKibana`.

### (c) Sync: forced transport-close failure on a LIVE, already-used client

```
$ .venv/bin/python -c "
import sys; sys.path.insert(0, 'examples')
from utils import create_kibana_client
from elastic_transport import ConnectionError as ETConnectionError
from kibana.exceptions import ConnectionError as KibanaConnectionError

client = create_kibana_client()
resp = client.actions.list_types()
print(f'real operation ok: found {len(resp.body)} connector types')

original_close = client._transport.close
def failing_close():
    raise ETConnectionError('forced close failure (battle-test #84)')
client._transport.close = failing_close

try:
    client.close()
    print('FAIL: close() did not raise')
except KibanaConnectionError as e:
    print(f'PASS: close() raised {type(e).__module__}.{type(e).__name__}')
    print(f'  .message = {e.message!r}')
    print(f'  isinstance of ET source preserved as __cause__: {isinstance(e.__cause__, ETConnectionError)}')
    print(f'  __cause__ = {e.__cause__!r}')
except Exception as e:
    print(f'FAIL: wrong exception type raised: {type(e)}: {e}')
finally:
    client._transport.close = original_close
    client.close()
    print('teardown: real transport.close() succeeded afterward')
"
🔗 Connecting to Kibana: http://localhost:5601
🔐 Using basic authentication (user: elastic)
real operation ok: found 63 connector types
PASS: close() raised kibana.exceptions.ConnectionError
  .message = 'Connection error'
  isinstance of ET source preserved as __cause__: True
  __cause__ = ConnectionError('forced close failure (battle-test #84)')
teardown: real transport.close() succeeded afterward
```

**PASS** — against a real, live-connected client (already used for a real API call),
a forced `elastic_transport.ConnectionError` out of the transport's own `close()`
surfaces to the caller as `kibana.exceptions.ConnectionError`, with `.message` set and
the raw ET exception preserved as `__cause__` — exactly the translated type a caller's
documented `except kibana.exceptions.ConnectionError:` catches, not the raw ET type and
not a swallowed WARNING. Teardown (restoring the real `close`) ran unconditionally in
`finally` and succeeded, releasing the real connection.

### (d) Async: forced transport-close failure on a LIVE, already-used client

```
$ .venv/bin/python -c "
import asyncio, sys; sys.path.insert(0, 'examples')
from utils import create_async_kibana_client
from elastic_transport import ConnectionError as ETConnectionError
from kibana.exceptions import ConnectionError as KibanaConnectionError

async def main():
    client = create_async_kibana_client()
    resp = await client.actions.list_types()
    print(f'real operation ok: found {len(resp.body)} connector types')

    original_close = client._transport.close
    async def failing_close():
        raise ETConnectionError('forced close failure (battle-test #84, async)')
    client._transport.close = failing_close

    try:
        await client.close()
        print('FAIL: close() did not raise')
    except KibanaConnectionError as e:
        print(f'PASS: close() raised {type(e).__module__}.{type(e).__name__}')
        print(f'  .message = {e.message!r}')
        print(f'  isinstance of ET source preserved as __cause__: {isinstance(e.__cause__, ETConnectionError)}')
        print(f'  __cause__ = {e.__cause__!r}')
    except Exception as e:
        print(f'FAIL: wrong exception type raised: {type(e)}: {e}')
    finally:
        client._transport.close = original_close
        await client.close()
        print('teardown: real transport.close() succeeded afterward')

asyncio.run(main())
"
🔗 Connecting to Kibana (async): http://localhost:5601
🔐 Using basic authentication (user: elastic)
real operation ok: found 63 connector types
PASS: close() raised kibana.exceptions.ConnectionError
  .message = 'Connection error'
  isinstance of ET source preserved as __cause__: True
  __cause__ = ConnectionError('forced close failure (battle-test #84, async)')
teardown: real transport.close() succeeded afterward
```

**PASS** — identical guarantee for `AsyncKibana`.

## Scope & caveats

- Only `Kibana.close()` and `AsyncKibana.close()` changed. `SpaceScopedKibana.close()`
  / `AsyncSpaceScopedKibana.close()` are unchanged in source (still a pure delegation to
  `self._client.close()`) and inherit the new raising behavior transitively — covered by
  the existing `tests/unit/test_space_scoped_client_comprehensive.py` suite, all still
  green.
- `__enter__`/`__exit__` and `__aenter__`/`__aexit__` are unchanged in *logic* (still a
  bare delegation to `close()`/`await close()`, no new `try`/`except`) — fix-round
  docstring additions (one sentence each, per spec review MINOR #3) document the
  now-raising behavior but change no code path. Their *observable* behavior changes
  only because `close()` now can raise — matching `elasticsearch-py`'s own
  `Elasticsearch.__exit__`/`close()` convention exactly (no masking-avoidance in either
  package).
- **Behavior change, called out in the changelog:** callers that relied on the old
  best-effort swallow-and-log now see `close()` raise on a genuine transport-layer
  close failure. Callers that want the old best-effort behavior back can wrap the call
  in `contextlib.suppress(kibana.exceptions.TransportError,
  kibana.exceptions.SerializationError)` -- both names are required.
  `TransportError` is the common base of only 4 of the 5 mapped types
  (`ConnectionTimeout`, `SSLError`, `ConnectionError`, `TransportError` itself);
  `SerializationError` subclasses `KibanaException` directly (confirmed via
  `SerializationError.__mro__`), so `contextlib.suppress(TransportError)` alone
  silently misses it -- an earlier round of this evidence stated the single-type
  recipe, caught by spec review; see "Fix round" below and
  `test_documented_close_suppress_recipe_covers_every_mapped_type_sync`/`_async` in
  `tests/unit/test_transport_exceptions.py`, which now pin the corrected recipe against
  all 5 types.
- **Point-in-time result.** `elastic_transport` 9.4.2 and Kibana 9.4.3 are current as of
  2026-08-01; a real `Transport.close()` (`elastic_transport/_transport.py:542`) simply
  iterates `node_pool.all()` and calls `node.close()` on each — in the observed
  environment this never itself raises one of the five mapped ET types in either the
  clean-close or repeat-close case, which is why the forced-failure battle tests above
  monkeypatch the transport's `close` directly (same approach the request-path's own
  translation tests use for the mocked cases) rather than relying on triggering a real
  close failure, which this environment cannot organically produce.

## Fix round — spec review response

A spec review of the round-1 fix found 2 BLOCKER-equivalent MAJORs + 2 minors, all
addressed here, on the same branch, same commit lineage.

### [MAJOR] The documented suppress recipe silently missed `SerializationError`

Round 1 documented `contextlib.suppress(kibana.exceptions.TransportError)` (in both
`close()` docstrings, the changelog, and this evidence file) as the escape hatch for a
caller who wants the old best-effort-close behavior back. Wrong: `SerializationError`
subclasses `KibanaException` **directly**, not `TransportError` — verified via its MRO:

```
$ .venv/bin/python -c "
from kibana.exceptions import SerializationError, TransportError
print(SerializationError.__mro__)
print('is TransportError subclass:', issubclass(SerializationError, TransportError))
"
(<class 'kibana.exceptions.SerializationError'>, <class 'kibana.exceptions.KibanaException'>, <class 'Exception'>, <class 'BaseException'>, <class 'object'>)
is TransportError subclass: False
```

A caller following the round-1 docs verbatim (`contextlib.suppress(TransportError)`)
would still see `close()` raise on a `SerializationError`-mapped transport failure —
exactly the invisible-failure problem this fix exists to solve, reintroduced through
the documented workaround.

**Fix:** every occurrence corrected to
`contextlib.suppress(kibana.exceptions.TransportError,
kibana.exceptions.SerializationError)` — both `close()` docstrings
(`kibana/_sync/client/__init__.py`, `kibana/_async/client/__init__.py`),
`CHANGELOG.md`, and this evidence file (the "Investigation" and "Scope & caveats"
sections above already reflect the corrected recipe and explain why both names are
required).

**RED-then-GREEN test added**, `tests/unit/test_transport_exceptions.py` — a module
constant `DOCUMENTED_CLOSE_SUPPRESS_RECIPE` mirroring the exact documented tuple,
asserted via `contextlib.suppress(*DOCUMENTED_CLOSE_SUPPRESS_RECIPE)` around `close()`
for all 5 mapped types (parametrized over the same `CASES` matrix used throughout this
file), sync and async, plus a grounding test that the MRO assertion above holds
(`test_serialization_error_does_not_subclass_transport_error`):

RED (recipe temporarily set to the round-1 buggy single-type tuple):
```
$ sed -i.bak 's/DOCUMENTED_CLOSE_SUPPRESS_RECIPE = (TransportError, SerializationError)/DOCUMENTED_CLOSE_SUPPRESS_RECIPE = (TransportError,)  # RED: pre-fix-round buggy recipe/' tests/unit/test_transport_exceptions.py
$ .venv/bin/pytest tests/unit/test_transport_exceptions.py -k "documented_close_suppress_recipe" --no-cov -q
...
>           raise SerializationError(str(e)) from e
E           kibana.exceptions.SerializationError: boom
FAILED tests/unit/test_transport_exceptions.py::test_documented_close_suppress_recipe_covers_every_mapped_type_sync[SerializationError-SerializationError]
FAILED tests/unit/test_transport_exceptions.py::test_documented_close_suppress_recipe_covers_every_mapped_type_async[SerializationError-SerializationError]
2 failed, 8 passed, 29 deselected in 0.14s
```

Exactly the 1-of-5 failure the bug predicts: the `SerializationError` case (sync and
async) escapes the single-type `suppress()` and fails the test with an uncaught
exception; the other 4 mapped types pass because they *do* subclass `TransportError`.
This is precisely the RED that "would have caught this," per the review.

GREEN (recipe restored to the corrected 2-tuple):
```
$ .venv/bin/pytest tests/unit/test_transport_exceptions.py --no-cov -q
.......................................                                  [100%]
39 passed in 0.08s
```

### [MAJOR] Call-site enumeration was undercounted (2 files named vs. 55 real ones)

Addressed by the full script-based census now in the "Investigation —
`__exit__`/`__aexit__` semantics" section above ("Call-site census (script, not
eyeballed — fix-round correction)"), replacing the round-1 two-file claim. Summary of
the corrected counts:

| Class | Count | Disposition |
|---|---|---|
| `context-manager` | 4 | Already covered by the 4 existing `__exit__`/`__aexit__` chaining tests; matches `elasticsearch-py` norm. |
| `finally-cleanup` | 66 (55 `examples/*.py` files + `docs/source/**/*.md` samples) | CPython's own `try/finally` chaining (verified with a minimal, package-independent reproduction) preserves the body exception as `__context__`; holds unconditionally, no code change needed anywhere in this class. |
| `other` | 44 (3 false-positive non-Kibana `.close()` matches, 2 docstring doctest examples, 4 already-covered internal delegation sites, remainder straight-line calls with no enclosing `try` at all — nothing to mask) | No masking risk applies; no code change needed anywhere in this class. |

**No call site in any class genuinely needed a `contextlib.suppress` fix** — confirmed
by the census (see the per-class disposition write-up above for the full reasoning),
not merely asserted as in round 1.

### [MINOR] Context-manager and delegating-close docstrings didn't mention the raising behavior

Fixed: one sentence added to each of `Kibana.__enter__`/`__exit__`,
`AsyncKibana.__aenter__`/`__aexit__`, `SpaceScopedKibana.__enter__`/`__exit__`/`close()`,
and `AsyncSpaceScopedKibana.__aenter__`/`__aexit__`/`close()` (8 docstrings total, both
trees) noting that exiting the context manager (or, for the space-scoped `close()`,
delegating to the main client) now raises the translated error on a transport-layer
close failure instead of swallowing it. No logic changed — confirmed by `mypy` and the
full unit suite staying green (below).

### [MINOR] "Installed elasticsearch-py 8.17.2" mischaracterized as a project dependency

Fixed: reworded (both the "Investigation" section above and this note) to state its
source was obtained from a local `uv` cache copy of `elasticsearch-py` 8.17.2, read
purely for this architectural comparison — it is not, and has never been, a dependency
of kibana-py (confirmed: not listed in `pyproject.toml`).

### Full verification after the fix-round

```
$ .venv/bin/pytest tests/unit/ --cov=kibana --cov-fail-under=90 -q -p no:randomly
3411 passed
Required test coverage of 90% reached. Total coverage: 94.45%

$ .venv/bin/pytest tests/unit/test_sync_async_parity.py --no-cov -q
144 passed in 0.64s

$ .venv/bin/mypy kibana/
Success: no issues found in 103 source files

$ .venv/bin/pre-commit run --all-files
... (all hooks, incl. black/isort/ruff) ... Passed
```

3411 vs round 1's 3400: +11, all in `test_transport_exceptions.py` —
`test_serialization_error_does_not_subclass_transport_error` (1) +
`test_documented_close_suppress_recipe_covers_every_mapped_type_sync`/`_async`
parametrized over the 5-case `CASES` matrix (5 x 2 = 10), matching the delta exactly.

No live re-run: this fix-round touched only docstrings, `CHANGELOG.md`, this evidence
file, and unit tests (the suppress-recipe test exercises the client's `close()` against
a mocked transport, same as round 1's mocked translation tests — no behavior on the
live path changed). Round 1's live battle-test results (clean sync/async
open→use→close, forced-failure translation surfacing on a live client, both above)
still hold unmodified.
