# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/pedro-angel/kibana-py/compare/v0.1.9...HEAD
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
