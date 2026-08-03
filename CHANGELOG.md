# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
User-facing and dev-facing tooling changes get an entry; CI-only plumbing does not —
see [CONTRIBUTING.md § Changelog Policy](CONTRIBUTING.md#changelog-policy).

## [Unreleased]

### Fixed
- **Response bodies logged at DEBUG were never redacted, so secrets a Kibana
  endpoint echoed back appeared in logs in cleartext**
  ([#102](https://github.com/pedro-angel/kibana-py/issues/102)). `_process_response`
  rendered the body with a bare `str(response.body)` in both the sync and async
  clients. Request bodies had been redacted since #78 (dicts) and #92
  (lists/tuples), so a caller could reasonably read DEBUG logging as safe — while
  `saved_objects.bulk_create`, which returns the objects it just created with
  their attributes, handed the caller's own credential straight back into the log.
  Response bodies now go through the same machinery, with the same depth cap and
  fidelity policy: mappings and sequences are traversed and their sensitive keys
  replaced with `[REDACTED]`, while non-secret fields are preserved. Redaction
  runs on the object **before** rendering, so the 500-character truncation can
  never emit an unscrubbed prefix; the cap and its `... [truncated]` suffix are
  otherwise unchanged. **Behavior change:** a `bytes` response body now logs as
  `<N raw bytes>` instead of its content — there is no structure to redact in an
  opaque blob, and an export endpoint can return NDJSON carrying credentials.
  This matches what the request side already does for a raw body. A `str` body
  (from `TextApiResponse`) logs as before. The error branch (`status >= 400`)
  logged only the extracted message and is unchanged. Verified live against a
  real `bulk_create`: the same response that previously rendered
  `'password': 'hunter2-live-battletest'` now renders `'password': '[REDACTED]'`
  with the non-secret `title` intact — evidence in
  `docs/evidence/redact-response-bodies-102.md`.
- **The `vocabulary_conformant` gate and the `checks` CI job both pointed at a
  script that no longer exists.** Dev-facing only — no shipped code changed.
  De-vendoring the methodology pack removed `skills/`, which was correct for the
  23 skill documents an agent reads from a user-level tier, but that same folder
  also held `vocabulary-conformance.sh` and its manifest — a program executed by
  `make dod` and by `.github/workflows/checks.yml`, not a document. Both callers
  were left invoking a deleted path (`exit 127`), so the local gate NO-GO'd and
  the CI job would have failed on the first push. The checker is now consumed the
  same way every other executable control is: as a pinned `git-controls-starter`
  hook (`vocabulary-conformance`, added there in v1.4.0), with the manifest
  travelling alongside it rather than being vendored per repo. A new `make
  vocabulary` leaf gives the DoD gate its own criterion and fails loudly if the
  hook is ever dropped from `.pre-commit-config.yaml`; the dedicated CI step is
  gone because `pre-commit run --all-files` now covers it. The starter pin also
  moves `v1.2.0` → `v1.4.0`, picking up the pending v1.3.0 (layered security
  scanning; the four sibling control scripts gained one `shellcheck disable`
  comment each and are otherwise unchanged).
- **Removed `.github/workflows/methodology-sync.yml`.** Its weekly `rsync
  --delete` restored `skills/`, `AGENTS.md`, and `CLAUDE.md` from upstream — it
  would have re-vendored exactly what the de-vendoring removed. It had also been
  failing every scheduled run since 2026-07-13 (`GitHub Actions is not permitted
  to create or approve pull requests`), so no sync has landed since 2026-07-10.
  The same repository setting still blocks `pre-commit-autoupdate.yml`, which is
  why this change bumps the starter pin by hand.
- **`TestImportGuardMatrix`'s "must stay quiet" assertions could fail on a benign
  gRPC fork diagnostic, not a real kibana-py warning**
  ([#100](https://github.com/pedro-angel/kibana-py/issues/100)). Dev-facing only —
  no shipped code changed. `tests/unit/test_observability.py`'s
  `TestAPMServerIntegration.test_create_otlp_exporter_grpc_protocol` creates a
  real, unmocked `grpc.insecure_channel` (via `_create_otlp_exporter`); under
  `pytest-randomly`, that test can land shortly before `TestImportGuardMatrix`'s
  strict-empty-stderr cases in the same pytest process. Every later
  `subprocess.run()` call in that process — exactly what
  `_run_with_blocked_imports` performs, and which takes the classic POSIX
  `fork()`+`exec()` path since `close_fds` defaults to `True` — re-enters gRPC's
  process-wide `pthread_atfork` machinery in the forked child, which occasionally
  logs an informational diagnostic (`ev_poll_posix.cc:593] FD from fork parent
  still in poll list: ...`) straight to the inherited stderr fd before the child
  has even exec'd into the probe script, landing in that subprocess's captured
  output and failing `result.stderr == ""`. Reproduced deterministically locally
  (Python 3.12, `--randomly-seed=2442198158` against the full `tests/unit/`
  suite — a small isolated slice preserving the same relative order did not
  reproduce it, only the full-scale run did). This is gRPC's POSIX `poll()`
  backend (`ev_poll_posix.cc`, used because macOS has no epoll), **not** the
  Linux-specific `epoll1` backend issue #100 originally assumed for this
  sighting — correcting that specific attribution. Checked directly against
  the compiled `grpcio` extension: the matched text appears only alongside
  `ev_poll_posix.cc`, never `ev_epoll1_linux.cc`, so the fix is scoped to the
  backend actually observed and is not claimed to also cover an unverified,
  possibly differently-shaped Linux/`epoll1` diagnostic — #100's originally
  scoped Linux seed-loop gate stands unchanged. Fixed by having
  `_run_with_blocked_imports` strip only this one, narrowly-anchored benign
  pattern from captured subprocess stderr before returning — every other stderr
  assertion in the file (corrupted-install warnings, `-W error` survival, etc.)
  is unaffected and still sees everything else verbatim. `GRPC_VERBOSITY=ERROR`
  was probed as an alternative and confirmed to suppress gRPC's own C-core log
  lines, but only when set in the *parent* process before gRPC initializes —
  setting it in the subprocess's `env=` (as one might first reach for) cannot
  work, architecturally: the diagnostic is written by the forked child before
  `execve()` applies the new environment. Session-wide env is broader in scope
  than the anchored stderr filter for no added benefit, so it was not adopted.
  Evidence, the full investigation, and the seed-pinned RED/GREEN transcripts:
  `docs/evidence/grpc-fork-noise-100.md`.
- **A TOP-LEVEL LIST request body bypassed DEBUG-log redaction entirely**
  ([#92](https://github.com/pedro-angel/kibana-py/issues/92), sibling of
  [#78](https://github.com/pedro-angel/kibana-py/issues/78)). `perform_request`
  (both `kibana/_sync/client/_base.py` and `kibana/_async/client/_base.py`) only
  called `_redact_body_secrets` when `isinstance(body, dict)`; a body shaped as a
  bare list — `saved_objects.bulk_create`/`bulk_get`/`bulk_resolve`/`bulk_update`/
  `bulk_delete` and `synthetics.bulk_create_params` all send one — fell through to
  the `elif body is not None` branch and was logged as `<%d raw bytes>` (actually
  counting top-level elements, not bytes) instead of being redacted at all, so a
  `secrets`/`password`/`token`/`api_key`/`apikey` key inside any element skipped
  redaction outright rather than being caught by the existing dict/list-recursion
  logic #78 shipped. Fixed by adding an `elif isinstance(body, (list, tuple))`
  branch to both trees' `perform_request` that reuses the existing
  `_redact_body_secrets_sequence` machinery unchanged — same shared recursion
  depth cap, same plain-`list`/`tuple`-only fidelity policy, no new traversal
  logic. A live probe against a running Kibana (`saved_objects.bulk_create` with a
  `password`-keyed attribute on a `dynamic:false`-mapped `url`-type object, so the
  create genuinely succeeds instead of being rejected by strict-mapping
  validation) confirmed the pre-fix DEBUG log showed only `<1 raw bytes>` and the
  post-fix log shows the full list with `'password': '[REDACTED]'` alongside the
  untouched non-sensitive fields, on both the sync and async client.
- **`tests/unit/test_observability.py::TestLogForwardingSetup::test_setup_log_forwarding_success`
  no longer risks permanently corrupting every other test's logging under
  `pytest-randomly`** ([#91](https://github.com/pedro-angel/kibana-py/issues/91),
  tracked further by [#100](https://github.com/pedro-angel/kibana-py/issues/100)). Dev-facing
  only — no shipped code changed. The test patched `logging.getLogger` as a
  *decorator*, which `unittest.mock` starts before the test body runs and, for stacked
  decorators, starts bottom-up (confirmed empirically, not assumed) — so it activated
  before any of the test's six other `@patch("kibana.observability.*")` decorators
  resolved their own targets. If this test happened to land first in the whole pytest
  session (empirically ~1-3% of seeds — see the evidence doc for the derivation), one
  of those six decorators' target resolution — not the test's own `from
  kibana.observability import _setup_log_forwarding` line, confirmed by probing
  `sys.modules` at body-entry: already imported by then — triggered the real,
  one-time `import kibana.observability`, and with it every OTel/grpc submodule
  `kibana/observability/_imports.py` conditionally pulls in binding its own
  module-level `logger = logging.getLogger(__name__)`, while `logging.getLogger` was
  mocked. Every one of those loggers rebound permanently to a `Mock` (including
  kibana-py's own `kibana.observability` logger). Python never re-runs a cached
  module's top-level code, so every later test in the same run that asserted on real
  logging/caplog output from any of those loggers then failed — 20 unrelated-looking
  failures across five other test classes, deterministically reproducible with
  `--randomly-seed=33` (also `=66`/`=68`/`=105`) pre-fix, and the same mechanism behind
  PR #90's disclosed one-off "20 failures that never recurred" anomaly. Fixed by
  removing `logging.getLogger` from the decorator stack and scoping it to a `with`
  block around just the call under test — so it is never mocked during any of the
  seven import-triggering events, regardless of run order — matching the pattern
  already used by the neighboring `test_cleanup_log_handlers` /
  `test_cleanup_survives_a_logger_created_during_the_sweep` in the same file.
  `TestImportGuardMatrix` itself (the class issue #91 originally named) did not
  reproduce a failure in a 210-configuration hunt (seeds 1–150 on 3.11 + seeds 1–40 on
  3.14 + 20 rounds of adversarial ordering, all green both before and after this fix)
  — its subprocess-isolated design has no path back into this parent-process
  mechanism; the platform-specific gRPC-fork-safety hypothesis for that class's
  originally reported symptom is carried forward, untested on Linux, by #100. Evidence,
  full hunt log, and the seed-loop verification: `docs/evidence/import-guard-flake-91.md`.
- **`close()` on both clients now translates and re-raises transport-layer close
  failures instead of swallowing them** ([#84](https://github.com/pedro-angel/kibana-py/issues/84),
  found by the 2026-07-31 adversarial deep review, code-quality lens). **Behavior
  change:** `Kibana.close()` / `AsyncKibana.close()` (and the space-scoped clients,
  which delegate to them) used to catch bare `Exception` around
  `self._transport.close()` and only log a WARNING — a close failure (a leaked
  connection or socket) was invisible to the caller, and unlike the request path
  (aligned in 0.4.1), it was never translated to a `kibana.exceptions` type. `close()`
  now wraps the transport close call in the same
  `kibana.exceptions.translate_transport_errors()` the request path already uses, so
  a transport-layer close failure surfaces as the matching `kibana.exceptions` type
  (`ConnectionError`, `ConnectionTimeout`, `SSLError`, `SerializationError`,
  `TransportError`) with `.message` set and the original `elastic_transport`
  exception preserved as `__cause__` — and any other, non-transport exception is no
  longer caught at all, so it propagates as-is (same "translate-or-propagate"
  convention the request path already follows). Callers that relied on the old
  best-effort swallow and want that behavior back can wrap the call in
  `contextlib.suppress(kibana.exceptions.TransportError,
  kibana.exceptions.SerializationError)` — both are required: `SerializationError`
  subclasses `KibanaException` directly, not `TransportError`, so `TransportError`
  alone does not suppress it. `__enter__`/`__exit__`
  and `__aenter__`/`__aexit__` are unchanged — they still just delegate to
  `close()`/`await close()`, matching `elasticsearch-py`'s own `Elasticsearch.__exit__`,
  which has no masking-avoidance of its own either; if the `with`/`async with` body
  already raised and `close()` now also raises, Python's ordinary implicit exception
  chaining keeps both (the body exception as `__context__` of the `elastic_transport`
  source exception, itself the `__context__`/`__cause__` of the translated one) rather
  than silently dropping either.
- **APM connectivity probe (`validate_apm_server_availability` /
  `configure_opentelemetry(validate_endpoint=True)`) is now dual-stack and
  time-bounded, including DNS resolution** ([#83](https://github.com/pedro-angel/kibana-py/issues/83),
  found by the 2026-07-31 adversarial deep review, code-quality lens). The probe used a raw
  `socket.AF_INET` socket, so an IPv6-only APM host always failed validation —
  silently disabling telemetry against a server that was actually reachable — and its
  retries could block the synchronous `configure_opentelemetry` call for up to ~18s
  against an endpoint that hangs instead of refusing the connection. Now uses
  `socket.create_connection` (resolves via `getaddrinfo`, honors `/etc/hosts`, tries
  every address family the host resolves to) and hard-caps the total wall-clock time
  across all attempts and backoff sleeps at 5s (`_PROBE_TOTAL_BUDGET_SECONDS` in
  `kibana/observability/_validation.py`) regardless of the `timeout`/`max_retries`
  arguments, so the configure path never stalls process startup for tens of seconds on
  an unreachable or IPv6-only endpoint. The 5s cap is a true wall-clock deadline enforced
  from the caller's side (each attempt runs on a background daemon thread the caller
  waits on with the remaining budget as its own timeout), not merely whatever
  `create_connection`'s own `timeout` kwarg happens to bound — that kwarg cannot cover
  `getaddrinfo`, which has no timeout of its own and can hang independently of it, so an
  unresponsive DNS resolver is bounded by the cap too, not just a refusing/hanging TCP
  connect. Public function contract unchanged (`validate_apm_server_availability`'s
  signature, return semantics, and `protocol` param are untouched).
- **`release.yml` hardening: direct integration dependency, PyPI-before-GitHub-release
  ordering, immutable pin comment**
  ([#82](https://github.com/pedro-angel/kibana-py/issues/82), found by the 2026-07-31
  adversarial deep review, release-hygiene lens). Logged under the
  [changelog policy](CONTRIBUTING.md#changelog-policy)'s release-pipeline-behavior
  carve-out: this changes release-pipeline **behavior** — job ordering and gating
  semantics, specifically what a *failed* release leaves behind — not a routine
  workflow tweak or pin bump, which is the carve-out's own dividing line. Three changes:
  1. `publish-pypi` and `publish-github-release` both now list `integration` directly in
     `needs:`, not only transitively through each other — a future edit to either job
     can no longer silently drop the release gate.
  2. **Publish order flipped: PyPI now publishes before the GitHub Release.**
     `publish-pypi` needs `[build, integration]`; `publish-github-release` needs
     `[build, integration, publish-pypi]`. Under the old order, a `publish-pypi` failure
     left a public tag + GitHub Release with no installable package — not hypothetical:
     CI runs for tags `v0.1.3` through `v0.1.8` (April 2026) each show
     `publish-github-release` succeeding while `publish-pypi` failed in the same run;
     those five releases were later deleted once `v0.1.9` shipped clean. PyPI-first makes
     that failure mode structurally impossible (`publish-github-release` no longer runs
     at all if `publish-pypi` fails); the inverse failure — PyPI succeeds, the GitHub
     Release step then fails — is cheap to recover from by simply re-running
     `publish-github-release`, since PyPI refuses a second upload of the same version but
     the GitHub Release step is idempotent. Verified before reordering: neither job
     consumes the other's outputs (both independently download the same `build`-uploaded
     `dist` artifact), so no coupling blocked the swap.
  3. The `pypa/gh-action-pypi-publish` pin's trailing comment was `# release/v1` — a
     moving branch the repo's `check-pin-comments-match` control explicitly cannot verify
     strictly (branch comments are noted, not failed). Resolved the pinned SHA
     (`ba38be9e461d3875417946c167d0b5f3d385a247`) against the GitHub API directly (not
     trusted from Dependabot metadata): it peels to tag `v1.14.1` exactly, so the comment
     is now `# v1.14.1` and the hook verifies it strictly instead of skipping it.

  `docs/source/development/release-process.md` and `PUBLISHING_GUIDE.md` (both mermaid
  diagrams, both jobs tables, and the recovery-guidance prose) updated to the new graph in
  the same commit. Gate: `actionlint` clean, `check-pin-comments-match` passes strictly
  (no more skipped pin), full pre-commit suite clean, `needs:` edges verified by direct
  YAML parse. Honest residual: the reordered pipeline cannot be fully battle-tested
  without a real tag push — first live validation is the next release; the lint and
  job-graph checks bound the risk in the meantime. Evidence:
  `docs/evidence/release-hardening-82.md`.

- **Docs: six drift items found by the 2026-07-31 release review**
  ([#81](https://github.com/pedro-angel/kibana-py/issues/81)). `docs/source/changelog.md`
  was missing the 0.4.1 and 0.4.2 entries entirely (it topped out at 0.4.0) — added,
  mirroring this file, and `docs/source/development/release-process.md` now also tells
  a releaser to update it (it is not generated from this file and drifts silently
  otherwise). `release-process.md` documented only 4 release-workflow jobs and claimed
  "CI does not run \[the integration suite\] (needs a Docker Elastic Stack)"; `release.yml`
  has had a 5th `integration` job gating publish via `needs: [build, integration]` since
  before this issue was filed, and `PUBLISHING_GUIDE.md` already documented it correctly
  — `release-process.md`'s mermaid diagram, jobs table, and pre-release checklist now
  match. `docs/source/user-guide/observability.md` documented a nonexistent
  `validate_apm_connection`; the real public function is
  `validate_apm_server_availability` (with a `protocol` parameter) — both call sites
  fixed. `installation.md` and `observability.md` claimed the `observability` extra
  installs 3 packages; `pyproject.toml` installs 5 (`opentelemetry-exporter-otlp-proto-http`
  and `opentelemetry-instrumentation` were undocumented) — both pages now list all 5.
  The `flaky` pytest marker's docstring implied an active quarantine and cited closed
  [#53](https://github.com/pedro-angel/kibana-py/issues/53); reworded to state the
  quarantine is currently empty (confirmed: no test in the tree carries
  `@pytest.mark.flaky`). Finally, this file gained an explicit changelog policy
  (also spelled out in `CONTRIBUTING.md`): user-facing and dev-facing tooling changes
  get an entry, pure CI-only plumbing does not — codifying the practice already visible
  in recent entries (e.g. the `make audit` self-heal fix above is logged even though
  it ships no package code, while the CI-only pip+setuptools-upgrade-sharing commit it
  builds on was not). Evidence, disposition, and the verification script output for
  each item: `docs/evidence/docs-drift-81.md`.

- **`make audit` never refreshed base build tools on an existing venv**
  ([#80](https://github.com/pedro-angel/kibana-py/issues/80)), a residual of
  [#67](https://github.com/pedro-angel/kibana-py/pull/67): that fix upgraded pip+setuptools
  in `make setup` and CI's per-job install via one shared script
  (`scripts/upgrade-base-build-tools.sh`), but `make audit` / the DoD `audit_clean` criterion
  ran against whatever `.venv` already existed, so the next setuptools advisory would
  re-create the exact 0.4.2 incident (CI green, local DoD NO-GO) on any long-lived venv. The
  `audit` leaf now runs the same shared script (with the same `PYTHON=$(VENV_BIN)/python`
  threading `make setup` uses) before `pip-audit`, so a stale venv self-heals on every
  `make audit` / `make dod` run instead of only at `make setup` — no second hand-synced
  upgrade line, still one source. Dev-tooling only: not shipped in the package, no CI change
  needed (CI never calls `make audit`; see `docs/evidence/audit-self-heal-80.md`).

- **Request-body JSON semantics diverged between the stdlib and orjson serializer
  backends** ([#79](https://github.com/pedro-angel/kibana-py/issues/79)). `kibana/serializer.py`
  picks one of the two at import time depending on whether `orjson` is installed, and,
  pre-fix, they disagreed on two things: NaN/Infinity/-Infinity floats, and `uuid.UUID`
  values. **NaN/Infinity (both backends):** a non-finite float anywhere in a body now
  raises the identical `kibana.exceptions.SerializationError` (the package's existing
  serialization exception type), with the identical message, on both backends, instead
  of stdlib's invalid-JSON tokens `NaN`/`Infinity`/`-Infinity` (a live Kibana 400s on
  those) or orjson's silent `null` substitution (undetectable data loss). Stdlib:
  `JSONSerializer.dumps` now passes `allow_nan=False`. orjson has no native option for
  this (confirmed against orjson 3.11.9; open upstream request `ijl/orjson#170`), so a
  new `_reject_non_finite_floats` walk runs before `orjson.dumps` and raises the same
  exception — walking not just `dict`/`list` (including subclasses, which orjson
  serializes transparently) but also plain `tuple` (exact type only — a `tuple`
  *subclass* like `namedtuple` is deliberately left unwalked, since orjson rejects any
  tuple subclass outright as an unsupported type; walking into one would have produced
  a misleading "bad float" instead of that correct error), `dataclasses.dataclass`
  instances, and `enum.Enum` members, both of which orjson serializes natively with
  zero opt-in and would otherwise still silently null a non-finite value inside; stdlib
  has no such native support for dataclasses/Enum and keeps raising its own `TypeError`
  for them, which is unrelated, pre-existing, and out of scope. The walk uses a
  permanent, `id()`-keyed visited set for every container it starts expanding — a
  self-referential body used to hang the walk forever (orjson's own cycle detection
  never got the chance to fire, since this walk runs first and previously had no cycle
  protection of its own); the same visited set also makes a DAG (shared sub-object
  reachable via multiple paths) linear instead of exponential. Stdlib's own
  `except ValueError` used to mislabel any `ValueError` — including its own circular-
  reference detection and a `UnicodeEncodeError` from encoding a lone surrogate
  character — as the non-finite-float message; it now only does that for the actual
  out-of-range-float error (matched by **prefix**, not exact equality — CPython 3.12+
  appends the offending value's `repr` to this specific stdlib message, e.g.
  `"...compliant: nan"`, which an exact-equality check missed; confirmed across
  3.11/3.12/3.13/3.14 via `make test-python-matrix`) and wraps anything else honestly
  with its own message. The message this project raises is always the canonical
  constant regardless of which CPython version's wording triggered the match, so the
  cross-backend message-identity guarantee holds across supported Python versions too.
  Measured at ~262% CPU overhead / ~16.4µs absolute on a representative ~9KB body —
  accepted because the absolute cost is noise against real request latency, guarded
  orjson (~22.8µs) is ~1.7x faster than the stdlib fallback this project already ships
  when orjson isn't installed (~39.5µs), and silently losing a caller's NaN/Infinity
  value on the majority backend is exactly the defect this issue exists to remove (full
  measurements, two unplanned regressions found and fixed along the way — a
  dataclass/Enum performance regression and this round's cycle/error-honesty/tuple-
  subclass fixes — a numpy probe, and the decision record are all in
  `docs/evidence/serializer-parity-79.md`). **UUID (both backends):**
  `JSONSerializer._default` gained a `uuid.UUID` case (serializing to the canonical
  string form, `str(obj)`), matching orjson's pre-existing native handling — a UUID
  value anywhere in a body now serializes identically regardless of which backend is
  active, pinned by a cross-backend equality test and confirmed live (a real space
  create with a UUID-valued field, accepted by Kibana on both backends, fetched back
  byte-identical).
- **Credentials nested inside a list-valued request-body field reached DEBUG
  logs in cleartext** ([#78](https://github.com/pedro-angel/kibana-py/issues/78)).
  `_redact_body_secrets` (`kibana/_sync/client/_base.py`, shared by the async
  client) recursed into dict values but not into list/tuple values, so a
  shape like `{"connectors": [{"secrets": {...}}]}` — a secrets dict living
  one level inside a list — was logged with the secret intact instead of
  `[REDACTED]`; only secrets nested directly under dict keys were ever
  caught. A live probe against a running Kibana confirmed the leak (the exact
  reproduction from the issue, sent as a real request body) before the fix
  and the redaction after it. A new `_redact_body_secrets_sequence` helper
  now recurses into list/tuple elements — dicts and nested lists/tuples
  recurse, scalars pass through unchanged. The function still returns a full
  copy and never mutates the caller's body; the redacted-key set and
  dict-recursion logic are unchanged.
  A code-quality review of the initial fix found two further defects, both
  fixed in the same PR: (1) the first version rebuilt a redacted list/tuple by
  casting back to the caller's exact type (`type(values)(...)`), which raised
  `TypeError: ...__new__() missing N required positional arguments` for a
  multi-field namedtuple and silently corrupted a single-field one (the whole
  element list accepted as that one field's value, wrapping a scalar in a
  list) — both crashing or corrupting a real request just because DEBUG
  logging was on. The redacted copy exists only for safe logging, never to
  round-trip the caller's exact type, so list/tuple values (namedtuples
  included) now always normalize to a plain `list`/`tuple`, matching the dict
  branch's pre-existing plain-`dict` rebuild (which already ignored `dict`
  subclasses like `OrderedDict`). (2) **neither recursion axis had a depth
  bound** — a request body nested roughly 1000 levels deep raised
  `RecursionError` out of `perform_request` whenever DEBUG logging was
  enabled, a pre-existing gap on the dict axis that predates this issue,
  now closed for both axes together. Both branches share one
  `_MAX_REDACTION_DEPTH` (20) via a new `_redact_nested_body_value` helper;
  past the cap a container is replaced with a `"<redaction depth limit>"`
  placeholder instead of being recursed into further, so a pathologically
  deep or adversarial body fails closed (a placeholder in the log) rather
  than aborting the request.
- **`configure_opentelemetry()` is now idempotent: repeat calls no longer stack
  log handlers, and reconfiguring actually takes effect instead of silently
  doing nothing** ([#76](https://github.com/pedro-angel/kibana-py/issues/76)).
  Three independent defects, all confirmed live against a local APM server:
  (1) `_config.py` *read* `_created_log_handlers` through the
  `kibana.observability` package attribute — a snapshot of the empty list taken
  at import time — but *wrote* the new handlers to `_logging`'s module global,
  so the cleanup branch never fired and every repeat
  `configure_opentelemetry(..., logs_enabled=True)` attached another
  `OTelLogHandler` to the "kibana" logger: N calls meant N copies of every log
  record shipped to the APM server (two configure calls produced two identical
  documents in `logs-apm*`), and the superseded handlers were never closed. The
  list is now read and written through its defining module only, and repeat
  calls close and detach the previous handlers before attaching new ones —
  measured as one handler and one indexed document after two calls. Mutable
  module state is no longer re-exported from `kibana/observability/__init__.py`
  at all, which is what made the split binding possible.
  (2) OpenTelemetry installs the global tracer provider exactly once per
  process and refuses every later `set_tracer_provider()`, so a second
  `configure_opentelemetry()` with a new endpoint built a provider and exporter
  that nothing ever reached, while still logging "OpenTelemetry configured" —
  spans kept going to the *first* endpoint (verified at the wire: after
  reconfiguring from a dead port to the live APM server, spans still hit the
  dead port and never arrived). Reconfiguration now applies: kibana-py
  registers one swappable span processor on the provider and swaps the
  exporters behind it, shutting the superseded ones down, so the next span
  leaves via the new endpoint. `KibanaInstrumentor.enable()` likewise rebinds
  its tracer when handed a different provider instead of returning early.
  Two things OpenTelemetry genuinely cannot change in-process are now reported
  rather than implied to have worked: a changed `service_name`/`resource` warns
  that resource attributes keep the values from the first configuration **for
  spans; forwarded logs pick up the new attributes** (log forwarding builds a
  fresh logger provider per call, so the two signals genuinely differ here),
  and a global provider already owned by another component warns that kibana-py
  is tracing through a provider of its own (its spans are still exported — that
  behavior is unchanged). The success line now distinguishes "configured" from
  "reconfigured" — following whether kibana-py itself had configured before,
  including when it never owned the global provider — and is only reached when
  something actually changed.
  (3) `KibanaInstrumentor.get_instance()` was an unsynchronized check-then-set
  singleton: racing threads each built their own instrumentor and any
  `enable()` applied to a loser was silently discarded (16 of 16 threads got
  distinct instances with the constructor window widened). It now uses
  double-checked locking.
  Two further guarantees close the same failure mode from the other side. A
  configuration that creates **no** span exporter (an unrecognized `exporter`
  value — now type-checked, case-normalized and warned about — or a console
  exporter that failed to construct) is never applied: over a working
  configuration it would shut the running exporters down and report success,
  and over nothing at all it would still claim the process-global provider
  slot that OpenTelemetry fills exactly once, locking out the next call that
  does have exporters. Such a call now changes nothing at all — including its
  log-forwarding settings, which the warning says explicitly. And the
  provider/processor pair kibana-py tracks is published as a single value
  under a lock that also covers the decision to install, so concurrent
  `configure_opentelemetry()` calls can neither interleave into a mismatched
  pair (whose later reconfigurations would swap exporters into a processor
  registered on nothing) nor tear down a configuration published between one
  call's look and its leap. Concurrent first-time configuration converges on
  one installation, a provider that is shut down stops being tracked, and a
  superseded provider is shut down rather than left holding an atexit hook.
- **A missing or corrupted OpenTelemetry logs SDK no longer breaks log
  forwarding or `import kibana`.** `ConsoleLogExporter` was never bound in the
  logs `except`-branch of `kibana/observability/_imports.py`, so an install
  without the logs SDK did not degrade — it raised `ImportError` from inside
  `_setup_log_forwarding`, the same unbound-name defect as
  [#68](https://github.com/pedro-angel/kibana-py/issues/68)/[#70](https://github.com/pedro-angel/kibana-py/issues/70)
  deferred by one import; it is now bound to `None` like every other name in
  that branch. Separately, all six guards in that module now catch any
  exception, not just `ImportError`: a *missing* distribution raises
  `ImportError`, but a *corrupted or version-mismatched* one executes its
  module body and raises whatever that raises — `AttributeError` against a
  dependency that no longer exports a symbol, or `TypeError` out of generated
  protobuf code when protobuf and an exporter disagree — which previously
  propagated straight out of `import kibana` for every user of this client,
  whether or not they opted into observability. Those `try` blocks contain
  nothing but `import` statements, so the broad `except` can only absorb a
  broken third-party install. The two cases are no longer conflated in the
  logs either: a missing package stays a debug note that says how to install
  it, while a package that is present but fails to import now reports a
  **warning** saying exactly that, instead of advising an install that would
  not help — and reports it both through logging and, best effort, as a
  `RuntimeWarning`, since this package's own `NullHandler` suppresses
  logging's stderr fallback and an application that never configured logging
  would otherwise see nothing. Best effort because `warnings.warn` *raises*
  under `-W error`: a reporting channel must not be able to turn a degraded
  install into a failed `import kibana`, so when warnings are fatal the log
  line is what remains. All of it is pinned by the import-guard matrix
  ([#76](https://github.com/pedro-angel/kibana-py/issues/76) review follow-ups).
- **`configure_opentelemetry(protocol="http/protobuf")` now actually reaches the
  APM server instead of 404/405ing on every span.** Two compounding defects:
  (1) the OTLP/HTTP exporter got the raw configured (or default) endpoint
  verbatim — no `/v1/traces` resource path — so spans POSTed to the bare root
  and the APM server rejected them (`405 Method Not Allowed`), while log
  forwarding's `_get_log_endpoint` already appended `/v1/logs` correctly, so
  traces silently dropped while logs worked; (2) when no endpoint was
  configured, the default was always the gRPC port `:4317`, even for
  `http/protobuf`, which needs `:4318`
  ([#77](https://github.com/pedro-angel/kibana-py/issues/77)). A new
  `_get_trace_endpoint` helper (mirroring `_get_log_endpoint`) now appends
  `/v1/traces` for `http/protobuf` endpoints that don't already have a signal
  path, and the no-endpoint-configured default is now protocol-aware (`:4318`
  for `http/protobuf`, `:4317` for `grpc`) for both traces and log forwarding,
  which shares the same default-endpoint computation. The "does it already
  have the path" check is anchored to the end of the path (`_get_signal_endpoint`,
  a shared core now used by both `_get_trace_endpoint` and `_get_log_endpoint`),
  not a bare substring match, so an endpoint that merely contains `/v1/traces`
  or `/v1/logs` mid-path (e.g. behind a gateway route) still gets the real
  signal path appended instead of being wrongly treated as already-correct.
  `configure_opentelemetry`'s `protocol` argument is now case-normalized, and
  an unrecognized value logs a warning instead of silently picking a default.
  The check and append both operate on the URL's *path* component only (via
  `urllib.parse.urlsplit`/`urlunsplit`), so an endpoint with a query string or
  fragment (e.g. `http://h:8200?token=x`) still gets the signal path inserted
  into the path — not appended after the query — and query/fragment are
  preserved unchanged. gRPC endpoints and already-correct explicit endpoints
  (with or without a trailing slash, already ending in `/v1/traces`, or
  carrying a query string/fragment) are unaffected.
- **A malformed `space_id` now fails the same way in async as in sync: locally,
  with no request and nothing cached.** Sync checks the id's *format* before
  anything else, so `client.slos.get(slo_id="x", space_id="Bad Space!")` raised
  `InvalidSpaceIdError` immediately. Async checked the space's *existence*
  first: the same call issued a real `GET /api/spaces/space/Bad%20Space%21`,
  raised `SpaceNotFoundError` — the wrong exception for an id that could never
  name a space — and cached the malformed key as "missing" for the 300 s TTL
  ([#74](https://github.com/pedro-angel/kibana-py/issues/74)).
  `_maybe_validate_space` now validates the format first and unconditionally, so
  every async namespace raises `InvalidSpaceIdError` with zero requests and an
  untouched cache. Four namespaces (`connectors`, `data_views`, `ml`,
  `saved_objects` — 42 methods) built the space-scoped path before validating,
  the opposite order from the other 28; all 580 space-scoped async methods now
  validate first. `Kibana.space()` / `AsyncKibana.space()` also honor the
  `InvalidSpaceIdError` their docstrings always promised, raising before any
  request and regardless of `validate=` — so a bad id can no longer seed the
  space cache either. Valid space ids, and the exceptions raised for spaces that
  merely do not exist, are unchanged.
- **The sync/async parity guard can now see a mis-ordered or un-awaited space
  validation.** Its body normalizer deleted the `_maybe_validate_space`
  statement wherever it appeared, and unwrapped `await` before doing so, which
  made two real bugs structurally invisible to CI: the validate-after-build
  ordering above, and a dropped `await` — a bare
  `self._maybe_validate_space(...)` that never validates anything, exactly the
  regression PR #60 fixed — both of which passed the entire parity suite
  ([#75](https://github.com/pedro-angel/kibana-py/issues/75)). The fold now
  applies only to a genuinely awaited call standing immediately before the
  `_build_space_path` call for the same space; a dropped `await`, a swapped
  order, a detached check, or a check on a different space each fail as body
  drift. Verified by mutation: removing an `await` and restoring the old order
  each fail the suite, and the restored tree passes with no allowlist entry.
- **`spaces.create()` / `spaces.delete()` now invalidate the space-validation
  cache.** Space existence is cached for 5 minutes, but nothing ever cleared an
  entry: after `client.dashboards.get_all(space_id="team-a")` raised
  `SpaceNotFoundError` (caching the miss), a successful
  `client.spaces.create(id="team-a")` left the miss in place, so the same call
  kept raising `SpaceNotFoundError` for up to 300 s; symmetrically, a space
  deleted after a successful validation kept passing validation for the rest of
  the TTL ([#72](https://github.com/pedro-angel/kibana-py/issues/72)). Both
  `create` and `delete` now drop the affected space id from the cache after the
  request succeeds (sync and async), so the next space-scoped call re-validates
  against Kibana immediately. Space operations that cannot change whether a
  space exists — `update`, `copy_saved_objects`,
  `resolve_copy_saved_objects_errors`, `disable_legacy_url_aliases`,
  `get_shareable_references`, `update_objects_spaces` — deliberately leave the
  cache alone.
- **One space-validation cache per client instead of one per namespace, on a
  monotonic clock.** Each namespace client kept its own cache, so a single
  space was re-validated with a fresh `GET /api/spaces/space/{id}` once per
  namespace touched (up to ~40 duplicate lookups per client), and the TTL was
  measured with `time.time()`, letting an NTP step or DST change stretch or
  shrink a cached verdict ([#73](https://github.com/pedro-angel/kibana-py/issues/73)).
  The cache is now a single `SpaceValidationCache` created by the top-level
  `Kibana`/`AsyncKibana` client (`kibana/_space_cache.py`) that every namespace
  client — including sub-clients such as `alerting.rule`, every namespace of a
  `client.space(...)`-scoped client, and the clients `options()` returns —
  shares, measured with `time.monotonic()` (matching
  `kibana/_rate_limiter.py`). `client.space(...)` still checks the space against
  the server when it is constructed (a scoped client must fail on a space that
  has since disappeared) but now seeds the shared cache with the result instead
  of discarding it. One lookup per space per TTL window for the whole client,
  verified live: six namespaces → 1 lookup, and `client.space(X)` plus two
  namespace calls → 1 lookup (was 2). Default TTL (300 s) and all public
  behavior are unchanged; `_clear_space_cache()` still works and now clears the
  shared cache.
- **A scheme-less host string no longer silently routes traffic to
  `localhost`.** `_build_node_configs` (`kibana/_sync/client/__init__.py`,
  shared by `AsyncKibana` via import) parsed host strings with `urlparse`,
  which mis-parses a scheme-less string like `"myhost:5601"` into
  `scheme='myhost', host='localhost', port=5601` — so `Kibana("myhost:5601")`
  silently sent every request to `localhost` with a bogus scheme and path
  prefix instead of failing
  ([#71](https://github.com/pedro-angel/kibana-py/issues/71)). A string host
  whose parsed form has no scheme or no hostname (e.g. `"myhost:5601"`,
  `"myhost"`, `"http://"`, or `"://"`) now raises a `ValueError` naming the
  offending input and the expected form (`http://host:port` or
  `https://host:port`) before any transport is built. The check parses first
  and inspects the result — a plain substring check for `"://"` would still
  let `"http://"` (empty host) and `"host/path?q=a://b"` (`://` appearing
  outside the scheme separator) through. The fix rejects rather than guesses
  a default scheme, since silently assuming `http://` would surprise TLS
  deployments; valid `http://`/`https://` strings (including odd-but-parsable
  schemes), dict hosts, and `cloud_id` are unaffected.
- **`import kibana` no longer crashes on a partial OpenTelemetry install.**
  `kibana/observability/_imports.py` imported the gRPC OTLP trace exporter
  unconditionally, and its except-branch never bound `OTLPSpanExporter` /
  `HTTPOTLPSpanExporter`, so having the OTEL SDK installed without
  `opentelemetry-exporter-otlp-proto-grpc` — even for callers that only export
  over OTLP/HTTP — raised `ImportError: cannot import name 'HTTPOTLPSpanExporter'
  from 'kibana.observability._imports'` all the way up through `import kibana`
  ([#68](https://github.com/pedro-angel/kibana-py/issues/68)). The gRPC and HTTP
  trace exporters are now each imported in their own guarded block, so either
  one being absent degrades only that exporter. Separately, the logs
  except-branch was unconditionally rebinding those same two trace-exporter
  names to `None`, silently clobbering a trace exporter that had already
  imported successfully whenever the (private) OTEL logs modules failed to
  import ([#70](https://github.com/pedro-angel/kibana-py/issues/70)); it now
  degrades only the logs-specific names.
- **A missing gRPC OTLP exporter now fails loudly instead of silently.** With
  the above fix, "SDK present, gRPC exporter absent" became a newly-reachable
  state — previously `import kibana` itself crashed first, so this path never
  ran. `_create_otlp_exporter` gained an explicit `GRPC_EXPORTER_AVAILABLE`
  check on the gRPC path (mirroring the pre-existing HTTP check), so
  requesting `protocol="grpc"` in that state now raises a clear `ImportError`
  naming the missing package, instead of letting `OTLPSpanExporter` be `None`
  and raising an opaque `TypeError: 'NoneType' object is not callable` that
  the broad exception handler in `_create_otlp_exporter_with_error_handling`
  would mask as a generic "APM configuration error". This is what delivers
  #68's stated outcome — "OTEL simply runs without the gRPC exporter" — as an
  honest, diagnosable failure for the one signal that needs it, rather than a
  silent mismatch for callers who explicitly asked for gRPC.

## [0.4.2] - 2026-07-15

### Fixed
- **The async `TimelineClient` now validates space existence like the sync client.**
  Its 19 space-scoped operations built the space path but never called
  `_maybe_validate_space`, so an async caller targeting a nonexistent space
  silently proceeded instead of raising `SpaceNotFoundError` — even though the
  async docstrings advertised `validate_spaces` (default `True`). Each operation
  now `await`s the space-existence check before building the path, matching the
  sync twin and every other async namespace. Sync callers were unaffected
  ([#60](https://github.com/pedro-angel/kibana-py/pull/60)).

## [0.4.1] - 2026-07-12

### Fixed
- **Connection, timeout, TLS, and transport errors are now catchable through the
  public API.** The client documented `except ConnectionError / ConnectionTimeout
  / SSLError / TransportError`, but `elastic_transport` raised its own
  same-named-but-distinct classes that slipped past those handlers, so a dropped
  connection, request timeout, or TLS failure was uncatchable via
  `kibana.exceptions`. Transport-layer errors are now translated to the matching
  `kibana.exceptions` types (the original error is preserved as the exception
  cause), and `KibanaException` gained a uniform `.message` attribute across all
  exception types.
- **Space-existence checks no longer misfire or mis-cache.** `_validate_space_exists`
  and `_validate_space_on_creation` detected a missing space by string-matching
  error text under a broad `except Exception`, which (a) mislabeled unrelated
  400/403/500 errors as `SpaceNotFoundError` and broke on changed or localized
  Kibana messages, and (b) negatively cached the space as "missing" on any
  transient auth/network error for the whole cache TTL. They now catch the real
  `NotFoundError`; other errors propagate unchanged and are not cached.

## [0.4.0] - 2026-07-11

### Changed
- **Lowered the minimum supported Python from 3.14 to 3.11.** The previous
  `>=3.14` floor was a tooling/policy pin, not a runtime requirement: only two
  things actually needed 3.14 — unparenthesized `except A, B:` (PEP 758) and
  self/forward-reference annotations relying on 3.14's default-deferred
  evaluation (PEP 649). Both are now handled in-tree (the `except` clauses are
  parenthesized, and `from __future__ import annotations` is applied across the
  package), so the client runs unchanged on Python 3.11–3.14 — the full unit
  suite is verified identical across all four versions. `requires-python`, the
  classifiers, the mypy/black/ruff targets, and the CI test matrix were updated
  to match.

## [0.3.1] - 2026-07-07

### Fixed
- Examples: repaired a Python-2 `except` SyntaxError in `examples/utils.py` that broke
  `import utils` (and therefore every example) under Python 3.13 and earlier. (The
  unparenthesized form is actually valid on 3.14 via PEP 758; it is a `SyntaxError`
  only on 3.13 and older, which is what the project's tooling ran.)

### Changed
- Examples are now human-usable end-to-end: each run prints its results, then prompts to
  keep or delete the resources it created (`--cleanup` / `--no-cleanup` override; keep is the
  default, including non-interactively). Every resource is namespaced `kbnpy-<example>-<...>`
  so kept resources never collide across examples. Every resource-creating example uses an
  idempotent start — a stable caller-chosen id where the API allows one, otherwise a
  prefix-scoped cleanup of its own resources — so re-running a kept example **replaces** its
  own copy rather than accumulating duplicates, and never fails with a conflict. (The sole
  exception is `error_handling.py`, which creates a duplicate on purpose to demonstrate
  `ConflictError` handling.)

## [0.3.0] - 2026-07-07

Complete Kibana 9.4.3 Fleet and Security Solution REST API coverage on top of the platform surface: 15 new namespaces, 341 new endpoints (610 total across 39 namespaces), full sync/async parity, all verified live against Kibana 9.4.3 (Security AI namespaces exercised end-to-end through a local LM Studio OpenAI-compatible model).

### Added

#### Fleet namespaces (140 endpoints)
- `fleet` — Fleet setup, settings, per-space settings, health check, and permission check (7 endpoints).
- `fleet_agents` — Elastic Agents: list/get/update/delete, per-agent and bulk actions (reassign, unenroll, upgrade, migrate, privilege-level change, request diagnostics, rollback), action status/cancel, available versions, uploads, tags, and agent setup (33 endpoints).
- `fleet_policies` — agent policies (CRUD, copy, download, full policy, outputs, bulk get/delete), package policies (CRUD, bulk get/delete, upgrade + dry-run), and agentless policies (23 endpoints).
- `fleet_epm` — Elastic Package Manager: browse/install/update/uninstall packages (by name+version and by upload), bulk install/upgrade/uninstall/rollback with task-status polling, categories, stats, dependencies, package files, Kibana/rule/datastream assets, custom integrations, input templates, transform authorization, and data streams (37 endpoints).
- `fleet_outputs` — outputs (Elasticsearch/Kafka/remote-ES/logstash) with health, Fleet Server hosts, proxies, agent binary download sources, remote synced integrations status, and cloud connectors (29 endpoints).
- `fleet_enrollment` — enrollment API keys, service tokens, Logstash API keys, uninstall tokens, message-signing key rotation, and Kubernetes manifest/download (11 endpoints).

#### Security Solution namespaces (201 endpoints)
- `detection_engine` — detection rules (CRUD, find, bulk actions, preview, import/export), prepackaged rules status/install, alerts index management, signals search/status/tags/assignees, tags, privileges, and legacy signals migrations (25 endpoints).
- `exception_lists` — exception lists and items (CRUD, find, duplicate, import/export, summary), shared exceptions, rule exceptions, and endpoint exceptions (`endpoint_list`) (22 endpoints).
- `lists` — value lists and list items (CRUD, find, index management, import/export) and privileges (18 endpoints).
- `timeline` — timelines (CRUD, list, resolve, copy, drafts, favorite, import/export), notes, pinned events, and prepackaged timelines (17 endpoints).
- `endpoint` — endpoint metadata, response actions (isolate/release, kill/suspend process, running processes, get-file, execute, scan, memory dump, run script, upload, cancel), action status/details/file downloads, policy responses, protection-updates notes, and the scripts library (29 endpoints).
- `entity_analytics` — asset criticality, risk-score engine, entity store (install/status/start/stop/entities/resolution), privileged-user monitoring (engine, users, CSV), privileged-access detection (PAD), and watchlists (42 endpoints).
- `osquery` — osquery packs, saved queries, and live queries with results (14 endpoints).
- `security_ai_assistant` — AI Assistant conversations, prompts, anonymization fields, knowledge base (status/setup/entries), and chat completion (21 endpoints).
- `attack_discovery` — AI attack discoveries, generations (list/get/dismiss), schedules (CRUD, find, enable/disable), and on-demand generation (13 endpoints, technical preview).

#### Notes on live behavior
- All 15 namespaces ship live-verified integration tests. Endpoints whose happy path requires infrastructure the dev stack lacks (an enrolled Elastic Agent, an enrolled Elastic Defend endpoint, a cloud account, a reachable remote cluster) are still exercised live against their semantic error responses — asserting the server's actual message so a routing regression cannot pass silently — and fully unit-tested for request shape.
- Numerous spec/live discrepancies observed against Kibana 9.4.3 are documented in the method docstrings (for example: Fleet space-settings rejecting `-` in namespace prefixes; Logstash API-key creation requiring basic auth; Timeline `_copy`/`_import` using POST/multipart rather than the documented GET/JSON; the detection-engine `enabled` field not being editable via PATCH; the attack-discovery `schedules/_find` page off-by-one; the `.gen-ai` connector requiring the full `/chat/completions` URL).

### Changed
- The `Kibana`, `AsyncKibana`, `SpaceScopedKibana`, and `AsyncSpaceScopedKibana` clients now eagerly wire the 15 new Fleet and Security Solution namespaces alongside the existing platform namespaces.

## [0.2.0] - 2026-07-03

Complete Kibana 9.4.3 platform REST API coverage: 24 namespaces, 269 endpoints, full sync/async parity, all verified live against Kibana 9.4.3.

### Added

#### New Kibana Dashboards & Visualizations HTTP APIs (headline)
- **Dashboards API** (`client.dashboards`, technical preview in 9.4): search, create, get, upsert (`PUT` create-or-replace), and delete dashboards using Kibana's new flat dashboard data model — panels, sections, filters, queries, time ranges, tags, pinned panels, and access control.
- **Visualizations API** (`client.visualizations`, technical preview in 9.4): create, get, update/upsert, search, and delete Lens visualizations.

#### New namespaces
- `agent_builder` — agents, tools, conversations, converse (sync and streaming), MCP server, and A2A protocol (37 endpoints).
- `apm` — agent configurations, agent keys, deployment annotations, and RUM source map upload/list/delete.
- `cases` — cases, comments, file attachments, alerts, configuration, reporters, tags, and activity log (22 endpoints).
- `dashboards` — the new Dashboards HTTP API (see headline above).
- `data_views` — data views, field metadata, runtime fields, the default data view, and reference swapping (15 endpoints).
- `logstash` — centrally managed Logstash pipelines (technical preview).
- `maintenance_windows` — create, get, find, update, archive/unarchive, and delete maintenance windows.
- `ml` — ML saved-object sync and assigning jobs/trained models to spaces.
- `observability_ai_assistant` — chat completion (server-sent-event stream response).
- `security` — role CRUD, role query, bulk create/update roles, and session invalidation.
- `short_urls` — create, get, resolve, and delete Kibana short URLs (technical preview).
- `slos` — SLO CRUD, enable/disable, grouped find, definitions, and bulk delete/purge with task polling (13 endpoints).
- `streams` — wired streams: enable/disable/resync, forking, ingest/dashboard/query/rule links, significant events, and content pack export/import (technical preview, 25 endpoints).
- `synthetics` — monitors, private locations, global parameters, and on-demand test runs (18 endpoints).
- `task_manager` — Task Manager health report.
- `upgrade_assistant` — upgrade readiness status (technical preview).
- `uptime` — Uptime app settings get/update.
- `visualizations` — the new Visualizations HTTP API (see headline above).
- `workflows` — workflow CRUD, mget, import/export, clone, executions with logs, cancel/resume (26 endpoints).

#### Expanded existing namespaces
- `alerting` — restructured as `client.alerting.rule.*` (CRUD, find, enable/disable, mute/unmute per rule and per alert, snooze/unsnooze, update API key) and `client.alerting.backfill.*` (schedule, find, get, delete), plus framework health and rule types (21 endpoints).
- `connectors` — connector CRUD with caller-specified IDs, connector-type listing with `feature_id` filter, execute, and the 9.4.0 OAuth callback endpoints.
- `saved_objects` — export/import/resolve-import-errors, bulk operations, resolve, and encryption key rotation alongside the legacy CRUD (16 endpoints).
- `spaces` — copy and share saved objects between spaces, shareable references, legacy URL alias handling, `solution` and `imageUrl` fields, and `get_all` purpose filters (10 endpoints).
- `status` — `get_status()` now supports `v7format`/`v8format`; new `get_stats()` query options and new `get_features()` (`GET /api/features`, technical preview).

#### Core
- NDJSON support: `application/x-ndjson` responses (e.g. saved-object export) are parsed instead of failing with a serialization error.
- multipart/form-data request support, used by saved-object import/resolve-import-errors and APM source map upload.
- SSL/TLS options (`verify_certs`, `ca_certs`, client certificates, `ssl_context`, `ssl_assert_hostname`, `ssl_assert_fingerprint`, `ssl_version`, `ssl_show_warn`) are now passed through to the transport instead of being ignored.
- Pass-through serializers for non-JSON response content types returned by Kibana (`text/html`, `application/javascript`, `application/zip`, SSE/binary streams).

### Changed

- **BREAKING**: Python >= 3.14 is now required (previously 3.10+).
- **BREAKING**: `AsyncKibana.space()` is now a coroutine — call `await client.space("my-space")` — and it now actually validates that the space exists instead of silently skipping validation.
- The `actions` namespace is renamed to `connectors` (`client.connectors`, `ConnectorsClient`) to match Kibana's terminology. `client.actions` remains as a deprecated alias and will be removed in a future release.
- `client.alerting.rule.find()` no longer sends a default `sort_order` on its own: only explicitly passed query parameters are sent (live Kibana 9.4.3 rejects `sort_order` without `sort_field` with HTTP 406).
- `connectors.update()` now requires `name`, matching the API contract: `PUT /api/actions/connector/{id}` is a full replacement, and omitted `config`/`secrets` are reset to `{}` on the server (documented in the method docstring).
- Namespace clients are wired eagerly at client construction instead of lazily on attribute access.
- API errors now surface Kibana's detailed boom message (`statusCode`/`error`/`message` from the response body) instead of only the generic HTTP reason phrase.
- Most `/api/saved_objects` CRUD endpoints are deprecated by Kibana 9.4.3; the corresponding client methods carry deprecation notes pointing at the type-specific APIs (dashboards, data views, ...) and the export/import APIs.

### Fixed

- List-valued query parameters are now encoded as repeated keys (`doseq`-style) instead of a Python `repr` string; previously e.g. `saved_objects.find(type=[...])` silently returned zero results and `fields=[...]` silently dropped requested fields.
- Boolean and dict query parameters are encoded correctly (booleans as `true`/`false`, dict parameters such as `has_reference` JSON-encoded); dict parameters previously always failed with HTTP 400.
- `application/x-ndjson` response bodies (saved-object export) no longer raise `SerializationError`.
- Responses are wrapped as `ObjectApiResponse`/`ListApiResponse`/`TextApiResponse`/`BinaryApiResponse` (subscriptable, `.body`/`.meta`), matching the annotated return types, instead of leaking raw `TransportApiResponse` named tuples.
- `cloud_id` values with embedded ports are parsed correctly.
- The client-side rate limiter no longer misbehaves under concurrent use.
- `spaces.update()` now requires `name`: live Kibana requires `id` + `name` in the `PUT` body, so name-less partial updates previously always failed with HTTP 400.
- `saved_objects.find()` parameter handling: `type`/`fields`/`search_fields` lists are sent as repeated keys (no more comma-joining into one bogus field name) and `has_reference` is JSON-encoded.

### Requirements

- Python 3.14+
- Kibana 9.4.x (developed and live-tested against 9.4.3)

## [0.1.9] - 2026-04-05

### Changed

- Updated `.github/workflows/release.yml` release automation to improve publishing robustness:
  - switched GitHub Actions `uses:` references to major-version tags (for example `@v4`, `@v5`, `@v2`),
  - added cleanup of non-package artifacts (`dist/*.json`) before the PyPI publish step,
  - published from `packages-dir: dist/` with `pypa/gh-action-pypi-publish@release/v1`.

## [0.1.8] - 2026-04-04

### Fixed

- Updated `.github/workflows/release.yml` to run `twine check` with explicit distribution globs (`dist/*.whl dist/*.tar.gz`) instead of brace expansion, avoiding shell-dependent behavior during release validation.

## [0.1.7] - 2026-04-04

### Fixed

- Removed the build provenance attestation step from `.github/workflows/release.yml` to avoid release failures when GitHub cannot persist attestations for this repository integration setup.

## [0.1.6] - 2026-04-04

### Fixed

- Fixed release workflow `twine check` command to only validate Python distributions (`.whl` and `.tar.gz`), excluding the SBOM file. This prevents "Unknown distribution format" errors during the build step.

## [0.1.5] - 2026-04-04

### Changed

- Enabled `id-token: write` in `.github/workflows/release.yml` so PyPI trusted publishing (OIDC) can authenticate correctly during release.

## [0.1.4] - 2026-04-04

### Changed

- Release metadata update for v0.1.4.

## [0.1.3] - 2026-04-04

### Changed

- Release metadata update for v0.1.3.

## [0.1.2] - 2026-04-04

### Changed

- Added workflow support for Python 3.13 across CI, documentation, and release pipelines.
- Updated GitHub Actions runners to Ubuntu 26.04 for test, docs, and release workflows.

### Documentation

- Added Read the Docs build configuration in `.readthedocs.yaml` with Python 3.13 and Ubuntu 26.04.

## [0.1.1] - 2026-04-04

### Changed

- Hardened release workflow validation in `.github/workflows/release.yml`:
	- Tagged commit must be reachable from `origin/main`.
	- Build now verifies wheel content sanity (`kibana/py.typed` is present).
	- Build now fails if `tests/`, `docs/`, or `examples/` paths are present in the wheel.

### Documentation

- Updated `PUBLISHING_GUIDE.md` to reflect enforced release workflow checks and added troubleshooting guidance for tags created from non-main commits.

## [0.1.0] - 2026-03-17

Initial release of kibana-py, a Python client library for the Kibana REST API.

### Added

#### Client Architecture
- **Synchronous client** (`Kibana`): thread-safe client for blocking I/O.
- **Asynchronous client** (`AsyncKibana`): async/await support for non-blocking I/O.
- **Options pattern**: per-request configuration via `client.options(...)`.
- **Context managers**: `with` / `async with` support for automatic cleanup.
- **Space-scoped clients**: `client.space("marketing")` returns a client pinned to a Kibana Space.

#### API Coverage
- **Actions API** (connectors): `create`, `get`, `get_all`, `list_types`, `update`, `delete`, `execute`.
- **Spaces API**: `create`, `get`, `get_all`, `update`, `delete`.
- **Saved Objects API**: `create`, `get`, `find`, `update`, `delete` with space-scoped operations.
- **Status API**: `get_status`, `get_stats`.
- **Alerting API** (rules): `create`, `get`, `update`, `delete`, `find`.

#### Authentication & Security
- API key, basic auth, and bearer token authentication.
- TLS/SSL support with certificate verification.
- Automatic credential redaction in logs.

#### Error Handling
- Exception hierarchy: `KibanaException` → `ApiError` (with `BadRequestError`, `AuthenticationException`, `AuthorizationException`, `NotFoundError`, `ConflictError`), `TransportError` → `ConnectionError` → `ConnectionTimeout` / `SSLError`, `SerializationError`, `SpaceError` → `SpaceNotFoundError` / `InvalidSpaceIdError`.
- All exceptions carry HTTP status code, response metadata, and body.

#### Space Support
- Space validation with caching (5-minute TTL).
- Negative caching for non-existent spaces.
- `validate_space` parameter to bypass validation per-request.

#### Type Safety
- Full type annotations throughout, `py.typed` marker (PEP 561).
- Compatible with mypy and pyright.

#### Serialization
- `JSONSerializer` (stdlib) and `OrjsonSerializer` (optional, high-performance).
- Automatic datetime → ISO 8601 conversion.

#### Observability (optional)
- OpenTelemetry integration via `configure_opentelemetry()`.
- OTLP (gRPC and HTTP) and console exporters.
- Log forwarding with `OTelLogHandler`.
- Graceful degradation when OTel is not installed.

#### Transport
- Built on `elastic-transport` for connection pooling, retries, node selection, and dead-node handling.

#### Developer Tooling
- Makefile with targets: `setup`, `test`, `test-integration`, `benchmark`, `lint`, `format`, `build`, `docs`, `clean`, `stack-start`, `stack-stop`.
- Nox sessions for cross-Python-version testing.
- Pre-commit hooks (black, isort, ruff).
- CI workflows for testing (Python 3.10–3.13), release (PyPI trusted publishing), and documentation.

#### Documentation
- README with quickstart, authentication, and API examples.
- Sphinx documentation source under `docs/`.
- 20+ example scripts in `examples/`.
- PUBLISHING_GUIDE for release procedures.

### Dependencies
- `elastic-transport >=9.1.0, <10`
- `python-dateutil`
- `typing-extensions`
- Optional: `aiohttp >=3, <4` (async), `orjson >=3`, `opentelemetry-*` (observability)

### Requirements
- Python 3.10+
- Kibana 9.x

---

[Unreleased]: https://github.com/pedro-angel/kibana-py/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.4.2
[0.4.1]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.4.1
[0.4.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.4.0
[0.3.1]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.3.1
[0.3.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.3.0
[0.2.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.2.0
[0.1.9]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.9
[0.1.8]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.8
[0.1.7]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.7
[0.1.6]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.6
[0.1.5]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.5
[0.1.4]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.4
[0.1.3]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.3
[0.1.2]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.2
[0.1.1]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.1
[0.1.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.0
