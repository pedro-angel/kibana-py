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
- `examples/*.py` call `client.close()` either at the tail of a happy path (closing a
  connection that just succeeded — realistically won't raise) or inside
  `finally: client.close()` after a `try` that may have already failed
  (`examples/basic_usage.py`, `examples/error_handling.py`). In the latter case, a
  concurrent close failure now surfaces via Python's *own* implicit exception chaining
  (see below) instead of being silently swallowed as before — strictly an improvement,
  not a new masking risk. No example needed a code change.
- No existing use of `contextlib.suppress` anywhere in the package or examples.

Then checked the ecosystem norm directly against installed `elasticsearch-py` 8.17.2
(`elasticsearch/_sync/client/__init__.py`) -- the sibling official Elastic client this
package mirrors architecturally (same `elastic_transport` transport layer, same
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
- `__enter__`/`__exit__` and `__aenter__`/`__aexit__` are unchanged in source. Their
  *observable* behavior changes only because `close()` now can raise — matching
  `elasticsearch-py`'s own `Elasticsearch.__exit__`/`close()` convention exactly (no
  masking-avoidance in either package).
- **Behavior change, called out in the changelog:** callers that relied on the old
  best-effort swallow-and-log now see `close()` raise on a genuine transport-layer
  close failure. Callers that want the old best-effort behavior back can wrap the call
  in `contextlib.suppress(kibana.exceptions.TransportError)` (`TransportError` is the
  common base of all five mapped types).
- **Point-in-time result.** `elastic_transport` 9.4.2 and Kibana 9.4.3 are current as of
  2026-08-01; a real `Transport.close()` (`elastic_transport/_transport.py:542`) simply
  iterates `node_pool.all()` and calls `node.close()` on each — in the observed
  environment this never itself raises one of the five mapped ET types in either the
  clean-close or repeat-close case, which is why the forced-failure battle tests above
  monkeypatch the transport's `close` directly (same approach the request-path's own
  translation tests use for the mocked cases) rather than relying on triggering a real
  close failure, which this environment cannot organically produce.
