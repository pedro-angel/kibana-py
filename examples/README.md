# Kibana Python Client Examples

Examples demonstrating how to use the kibana-py client library. All examples auto-detect configuration from `elastic-start-local/.env` — just start the local stack and run them. Every API namespace has a runnable `<namespace>_management.py` walkthrough, live-tested against Kibana 9.4.3.

## Prerequisites

```bash
# Start the local Elastic Stack (Elasticsearch + Kibana + APM)
make stack-start

# Install the library with all optional dependencies (Python 3.14+)
make setup

# Activate the Python virtual environment
source .venv/bin/activate

# Run any example
python examples/simple_status.py
```

If not using the local stack, set environment variables:
```bash
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="changeme"
```

Shared helpers live in `utils.py` (stack detection, client construction, optional OpenTelemetry setup) — the examples import it, you don't run it directly.

## Running examples: keep or clean

Each example that creates resources in your Kibana instance prints what it did, then decides
whether to delete them:

```
Delete created resources? (y/N):
```

- **Interactively**, you're prompted as shown above; anything but `y` keeps the resources.
- **`--cleanup`** deletes the created resources without prompting.
- **`--no-cleanup`** keeps the created resources without prompting.
- **Non-interactively** (no TTY — e.g. piped input, cron, CI) and neither flag is given, the
  example keeps the resources by default and prints a notice instead of prompting. Keep is
  always the default when in doubt.

Every resource an example creates is namespaced `kbnpy-<example>-<resource>` (for example,
`lists_management.py` creates a value list called `kbnpy-lists-bad-ips`), so resources kept from
one example never collide with another. Each example also clears only its own prior resources
before creating new ones, so re-running a kept example is safe and won't fail with a conflict.

## Examples by API

### Dashboards & Visualizations — the new HTTP APIs (tech preview, Kibana 9.4+)

| Example | Description |
|---------|-------------|
| `dashboards_management.py` | Create a dashboard with panels/tags/time range, get it, upsert with a custom ID, search with filters and pagination |
| `visualizations_management.py` | Create a Lens metric visualization, get, rename, search by title, delete |

### Status — Health monitoring

| Example | Description |
|---------|-------------|
| `simple_status.py` | Check Kibana health status |
| `status_management.py` | Overall health, legacy v7 format, operational stats, and registered features |
| `debug_status.py` | Detailed status and system statistics |
| `task_manager_management.py` | Read the Task Manager health report: status, monitored stats, workload |

### Connectors — Connector management

| Example | Description |
|---------|-------------|
| `simple_index_connector.py` | Create a connector, write a document, clean up |
| `connectors_management.py` | All connector operations: list types (with feature filter), create (incl. custom ID), get, update (full-replace PUT), execute, OAuth callback script, delete |
| `actions_management.py` | Same operations through the deprecated `client.actions` alias |
| `connector_management.py` | Advanced operations: list types, bulk writes, config updates |
| `debug_connector.py` | Inspect connector responses and troubleshoot |

### Alerting & Maintenance Windows

| Example | Description |
|---------|-------------|
| `simple_alerting_rules.py` | Create, get, find, update, and delete alerting rules |
| `alerting_management.py` | Framework health, rule types, rule CRUD with custom IDs, enable/mute/snooze lifecycle, backfills |
| `maintenance_windows_management.py` | Create, find, archive/unarchive, update, and delete maintenance windows |

### Cases

| Example | Description |
|---------|-------------|
| `cases_management.py` | Create a case, manage comments, update status, search and aggregate tags, inspect the activity log |

### Spaces — Multi-tenancy

| Example | Description |
|---------|-------------|
| `simple_space.py` | Create, verify, and delete a space |
| `spaces_management.py` | Solution-view spaces, listing with authorized purposes, updates, copying and sharing saved objects between spaces |
| `space_management.py` | Full CRUD with class-based pattern |
| `debug_spaces.py` | List all spaces with properties |
| `space_scoped_connector.py` | Create connectors scoped to a specific space |

### Saved Objects & Data Views

| Example | Description |
|---------|-------------|
| `simple_saved_object.py` | Create, retrieve, and delete a saved object |
| `saved_objects_management.py` | Single and bulk CRUD, find with filters, NDJSON export, import round trip, conflict resolution |
| `data_views_management.py` | Data view CRUD, field metadata, runtime fields, default data view, reference swap preview |
| `debug_saved_objects.py` | Inspect saved object structure and metadata |

### Security

| Example | Description |
|---------|-------------|
| `security_management.py` | Role CRUD, role query with paging/sorting, bulk create/update, session invalidation |

### Observability — APM, SLOs, Synthetics, Uptime, Streams, AI Assistant

| Example | Description |
|---------|-------------|
| `apm_management.py` | Agent configurations, deployment annotations, RUM source map upload/list/delete |
| `slos_management.py` | Create an SLO with a custom KQL indicator, find/update/enable/disable, bulk delete with task polling |
| `synthetics_management.py` | Global parameter, private location, HTTP monitor, on-demand test run |
| `uptime_management.py` | Read Uptime settings, apply a partial update, restore |
| `streams_management.py` | Enable wired streams, fork a child stream, significant events, content pack export (tech preview) |
| `observability_ai_assistant_management.py` | Chat completion via an LLM connector (SSE stream response, tech preview) |

### Automation & Platform — Workflows, Agent Builder, ML, Logstash, Upgrade Assistant, Short URLs

| Example | Description |
|---------|-------------|
| `workflows_management.py` | Create a workflow from YAML, run it, poll the execution, read logs |
| `agent_builder_management.py` | ES\|QL tool, custom agent, A2A card, MCP handshake, converse |
| `ml_management.py` | ML saved-object sync and assigning jobs/trained models to spaces |
| `logstash_management.py` | Centrally managed Logstash pipelines: create, read, upsert, list, delete (tech preview) |
| `upgrade_assistant_management.py` | Check upgrade readiness and remaining deprecation issues (tech preview) |
| `short_urls_management.py` | Create a short URL with a custom slug, get, resolve, delete (tech preview) |

### Async — Non-blocking I/O

| Example | Description |
|---------|-------------|
| `async_simple_status.py` | Basic async client usage |
| `async_example.py` | All namespace clients with concurrent operations |
| `async_comprehensive.py` | Concurrent API calls with `asyncio.gather()` |
| `async_index_connector.py` | Async connector with concurrent document writes |

### Patterns

| Example | Description |
|---------|-------------|
| `basic_usage.py` | Client initialization, authentication methods, context managers |
| `error_handling.py` | Exception hierarchy, catch patterns, retry logic |

## Recommended order for new users

1. `simple_status.py` — verify your setup works
2. `basic_usage.py` — learn client initialization and auth
3. `dashboards_management.py` — the new Dashboards HTTP API
4. `simple_index_connector.py` — first real API operation
5. `simple_space.py` — CRUD pattern
6. `error_handling.py` — exception handling
7. `async_example.py` — async/await usage

## Authentication

The examples support three authentication methods:

```python
from kibana import Kibana

# API key (preferred)
client = Kibana("http://localhost:5601", api_key="your_api_key")

# Basic auth
client = Kibana("http://localhost:5601", basic_auth=("elastic", "password"))

# Bearer token
client = Kibana("http://localhost:5601", bearer_auth="your_token")
```

When using `elastic-start-local`, authentication is configured automatically.

## Observability

All examples include optional OpenTelemetry integration. When the local stack is running (includes an APM server), traces and logs are collected automatically. View them at `http://localhost:5601/app/apm`.

To disable telemetry: `export KIBANA_OTEL_ENABLED=false`

See the [observability user guide](https://kibana-py.readthedocs.io/en/latest/user-guide/observability.html) for details.
