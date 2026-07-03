# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/pedro-angel/kibana-py/compare/v0.2.0...HEAD
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
