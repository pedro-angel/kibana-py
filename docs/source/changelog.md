# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

(unreleased)=
## Unreleased

(v0.4.0)=
## [0.4.0] - 2026-07-11

### Changed

- **Lowered the minimum supported Python from 3.14 to 3.11.** The previous `>=3.14` floor was a tooling/policy pin, not a runtime requirement: only unparenthesized `except A, B:` (PEP 758) and self/forward-reference annotations relying on 3.14's default-deferred evaluation (PEP 649) needed it. Both are now handled in-tree (parenthesized `except` clauses; `from __future__ import annotations` across the package), so the client runs unchanged on Python 3.11–3.14, with the unit suite verified identical across all four. `requires-python`, classifiers, tooling targets, and the CI test matrix were updated to match.

(v0.3.1)=
## [0.3.1] - 2026-07-07

Examples and developer tooling only — no shipped API changes (`kibana/` is unchanged apart from the version bump, so this is a patch).

### Fixed

- Repaired a Python-2 `except` SyntaxError in `examples/utils.py` that broke `import utils` (and therefore every example) under Python 3.13 and earlier. (The unparenthesized form is valid on 3.14 via PEP 758; it is a `SyntaxError` only on 3.13 and older, which is what the project's tooling ran.)

### Changed

- Examples are now human-usable end-to-end: each run prints its results, then prompts to keep or delete the resources it created (`--cleanup` / `--no-cleanup` override; keep is the default, including non-interactively). Resources are namespaced `kbnpy-<example>-<...>` so kept resources never collide across examples, and every resource-creating example uses an idempotent start so re-running a kept example **replaces** its own copy rather than accumulating duplicates (the sole exception is `error_handling.py`, which demonstrates `ConflictError`).

See the [root CHANGELOG](https://github.com/pedro-angel/kibana-py/blob/main/CHANGELOG.md) for full detail.

(v0.3.0)=
## [0.3.0] - 2026-07-07

Complete Kibana 9.4.3 Fleet and Security Solution REST API coverage on top of the platform surface: **15 new namespaces, 341 new endpoints (610 total across 39 namespaces)**, full sync/async parity, all verified live against Kibana 9.4.3. The Security AI namespaces (`security_ai_assistant`, `attack_discovery`) were exercised end-to-end through a local OpenAI-compatible model.

### Added

- **Fleet (140 endpoints):** `fleet` (setup, settings, health), `fleet_agents` (agents, actions, bulk actions, status), `fleet_policies` (agent/package/agentless policies), `fleet_epm` (Elastic Package Manager: integrations, installs, assets, custom integrations), `fleet_outputs` (outputs, Fleet Server hosts, proxies, download sources, cloud connectors), and `fleet_enrollment` (enrollment keys, tokens, signing, Kubernetes).
- **Security Solution (201 endpoints):** `detection_engine` (rules, alerts, prepackaged rules, migrations), `exception_lists` (exceptions, shared/rule/endpoint exceptions), `lists` (value lists and items), `timeline` (timelines, notes, pinned events), `endpoint` (metadata, response actions, scripts library), `entity_analytics` (asset criticality, risk score, entity store, monitoring, watchlists), `osquery` (packs, saved queries, live queries), `security_ai_assistant` (conversations, prompts, knowledge base, chat), and `attack_discovery` (discoveries, generations, schedules — technical preview).

### Changed

- The `Kibana`, `AsyncKibana`, `SpaceScopedKibana`, and `AsyncSpaceScopedKibana` clients eagerly wire the 15 new Fleet and Security Solution namespaces.

See the [root CHANGELOG](https://github.com/pedro-angel/kibana-py/blob/main/CHANGELOG.md) for the full per-endpoint detail and the documented spec/live discrepancies.

(v0.2.0)=
## [0.2.0] - 2026-07-03

Complete Kibana 9.4.3 **platform** REST API coverage: 24 namespaces, 269 endpoints, full sync/async parity, all verified live against Kibana 9.4.3. Headlined by first-class clients for the new tech-preview **Dashboards** and **Visualizations** HTTP APIs. Breaking: requires Python 3.14+; async `space()` is now a coroutine; `actions` renamed to `connectors` (deprecated alias kept). See the [root CHANGELOG](https://github.com/pedro-angel/kibana-py/blob/main/CHANGELOG.md) for full detail.

(v0.1.0)=
## [0.1.0] - 2026-03-17

Initial release of kibana-py, a Python client library for Kibana following the design patterns and quality standards of elasticsearch-py.

### Core Features

#### Client Architecture

- **Synchronous Client** (`Kibana`): Thread-safe synchronous client for blocking I/O
- **Asynchronous Client** (`AsyncKibana`): Async/await support for non-blocking I/O
- **BaseClient**: Shared foundation with common functionality
- **Options Pattern**: Per-request configuration without creating new client instances
- **Context Managers**: Support for `with` and `async with` statements

#### API Coverage

##### Actions API (Connectors) ✅

Complete CRUD operations for Kibana connectors:

- `create()` - Create new connectors with configuration and secrets
- `get()` - Retrieve connector by ID
- `get_all()` - List all connectors
- `list_types()` - Get available connector types
- `update()` - Update connector configuration
- `delete()` - Remove connectors
- `execute()` - Execute connector actions

Supported connector types:

- `.index` - Elasticsearch index
- `.webhook` - HTTP webhooks
- `.slack` - Slack notifications
- `.email` - Email notifications
- `.server-log` - Server logging
- `.pagerduty` - PagerDuty incidents
- `.servicenow` - ServiceNow tickets
- And more...

##### Spaces API ✅

Multi-tenancy support with Kibana Spaces:

- `create()` - Create new spaces with customization
- `get()` - Retrieve space by ID
- `get_all()` - List all spaces
- `update()` - Update space properties
- `delete()` - Remove spaces
- Space-scoped operations for saved objects

##### Saved Objects API ✅

Manage dashboards, visualizations, and other saved objects:

- `create()` - Create saved objects with optional ID
- `get()` - Retrieve saved object by type and ID
- `update()` - Update saved object attributes
- `delete()` - Remove saved objects
- `find()` - Search saved objects with filters and pagination
- `bulk_create()` - Batch create operations
- `bulk_get()` - Batch retrieve operations
- `bulk_update()` - Batch update operations
- `export()` - Export saved objects with dependencies
- `import_objects()` - Import saved objects with conflict resolution
- Space-scoped operations support

##### Status API ✅

Health monitoring and system information:

- `get()` - Get Kibana status and version
- `get_stats()` - Get detailed system statistics

#### Authentication & Security

- **API Key Authentication**: String or tuple format
- **Basic Authentication**: Username/password
- **Bearer Token**: Token-based authentication
- **TLS/SSL Support**: Certificate verification and client certificates
- **Secure Defaults**: Automatic credential redaction in logs

#### Error Handling

Comprehensive exception hierarchy:

- `KibanaException` - Base exception class
- `ApiError` - API error responses with metadata
- `TransportError` - Transport-level errors
- `ConnectionError` - Connection failures
- `ConnectionTimeout` - Timeout errors
- `SSLError` - TLS/SSL errors
- `AuthenticationException` - 401 errors
- `AuthorizationException` - 403 errors
- `NotFoundError` - 404 errors
- `ConflictError` - 409 errors
- `BadRequestError` - 400 errors
- `SerializationError` - Data serialization failures

All exceptions include:

- Descriptive error messages
- HTTP status codes
- Response metadata
- Original response body for debugging

#### Type Safety

- **Full Type Hints**: Complete type annotations throughout
- **py.typed Marker**: PEP 561 compliance for type checkers
- **Mypy Strict Mode**: Passes strict type checking
- **Pyright Support**: Compatible with Pyright type checker
- **IDE Support**: Enhanced autocomplete and inline documentation

#### Serialization

- **JSONSerializer**: Standard library JSON implementation
- **OrjsonSerializer**: Optional high-performance serialization
- **Datetime Handling**: Automatic ISO 8601 conversion
- **Custom Serializers**: Extensible serializer interface

#### Observability

Built-in OpenTelemetry support:

- **Automatic Instrumentation**: All API calls traced automatically
- **Configurable Exporters**: OTLP, Console, and custom exporters
- **Span Attributes**: Rich metadata for each operation
- **Error Tracking**: Exception details in spans
- **Environment Variables**: Standard OTEL configuration
- **Optional Dependency**: Only loaded when needed

Configuration:

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:4317"
)
```

See {doc}`user-guide/observability` for details.

#### Transport Layer

Built on elastic-transport for reliability:

- **Connection Pooling**: Efficient connection reuse
- **Automatic Retries**: Configurable retry logic
- **Node Selection**: Load balancing across nodes
- **Dead Node Handling**: Automatic node penalization
- **Timeout Management**: Request and connection timeouts
- **Thread Safety**: Safe for concurrent use

### Testing

#### Unit Tests

- 100+ unit tests covering all components
- Mock-based isolation for fast execution
- Comprehensive edge case coverage
- Pytest fixtures for common scenarios

#### Integration Tests

- 190 integration tests against real Kibana
- Automatic configuration from environment
- Resource cleanup after each test
- Support for elastic-start-local setup
- Tests for all API operations
- Error scenario validation

#### Test Coverage

- Overall: 74% code coverage
- Core clients: 100% coverage
- Exception handling: 100% coverage
- Serialization: 74% coverage
- Target: ≥90% for production release

#### Test Infrastructure

- **pytest**: Main testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **pytest-cov**: Coverage reporting
- **Automatic cleanup**: No test artifacts left behind

### Documentation

#### README

- Quick start guide
- Installation instructions
- Authentication examples
- API usage examples
- Configuration options
- Error handling patterns
- Async client usage

#### Examples

20+ example scripts organized by category:

- **Actions**: Connector management examples
- **Spaces**: Space CRUD operations
- **Saved Objects**: Dashboard and visualization management
- **Status**: Health monitoring
- **Async**: Asynchronous operation patterns
- **Error Handling**: Exception handling best practices

Example categories:

- `simple_*.py` - Minimal examples for quick start
- `debug_*.py` - Detailed debugging and exploration
- `*_management.py` - Comprehensive CRUD operations
- `async_*.py` - Asynchronous patterns

#### API Documentation

- Comprehensive docstrings for all public methods
- Parameter descriptions with types
- Return value documentation
- Usage examples in docstrings
- Exception documentation

#### Contributing Guide

- Development setup instructions
- Testing guidelines
- Code quality standards
- Pull request process
- Example development strategy

### Development Tools

#### Build System

- **hatchling**: Modern build backend
- **pyproject.toml**: Centralized configuration
- **pip**: Package management
- **Python 3.10+**: Modern Python features

#### Code Quality

- **black**: Code formatting (line length: 88)
- **isort**: Import sorting (black profile)
- **ruff**: Fast linting (E, F, W, I, N, UP rules)
- **mypy**: Static type checking (strict mode)
- **pyright**: Additional type checking

#### Task Automation

- **nox**: Task runner for common operations
- Sessions: test, format, lint, docs
- Virtual environment management
- Cross-version testing support

#### CI/CD Ready

- Automated testing
- Code coverage reporting
- Linting and type checking
- Example validation

### Dependencies

- elastic-transport >= 9.1.0, < 10
- python-dateutil
- typing-extensions

### Optional Dependencies

- aiohttp >= 3, < 4 (for async support)
- orjson >= 3 (for high-performance JSON)
- opentelemetry-api >= 1.20.0 (for observability)
- opentelemetry-sdk >= 1.20.0 (for observability)
- opentelemetry-exporter-otlp-proto-grpc >= 1.20.0 (for observability)

### Requirements

- Python 3.10 or higher
- Kibana 9.x

---

## Release Notes Format

Each release should include:

### Added

- New features and capabilities

### Changed

- Changes to existing functionality

### Deprecated

- Features that will be removed in future versions

### Removed

- Features that have been removed

### Fixed

- Bug fixes

### Security

- Security-related changes

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backward-compatible manner
- **PATCH** version for backward-compatible bug fixes

## Upgrade Guide

### From 0.x to 1.0 (Future)

When version 1.0 is released, this section will contain upgrade instructions.

## Support

- **Current stable**: 0.1.x (when released)
- **Python support**: 3.11+
- **Kibana support**: 9.x

## Links

- [GitHub Repository](https://github.com/pedro-angel/kibana-py)
- [Issue Tracker](https://github.com/pedro-angel/kibana-py/issues)
- [PyPI Package](https://pypi.org/project/kibana-py/)
- [Documentation](https://kibana-py.readthedocs.io/)

[Unreleased]: https://github.com/pedro-angel/kibana-py/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.4.0
[0.3.1]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.3.1
[0.3.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.3.0
[0.2.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.2.0
[0.1.0]: https://github.com/pedro-angel/kibana-py/releases/tag/v0.1.0
