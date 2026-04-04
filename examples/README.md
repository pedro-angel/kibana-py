# Kibana Python Client Examples

Examples demonstrating how to use the kibana-py client library. All examples auto-detect configuration from `elastic-start-local/.env` — just start the local stack and run them.

## Prerequisites

```bash
# Start the local Elastic Stack (Elasticsearch + Kibana + APM)
make stack-start

# Install the library with all optional dependencies
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

## Examples by API

### Status — Health monitoring

| Example | Description |
|---------|-------------|
| `simple_status.py` | Check Kibana health status |
| `debug_status.py` | Detailed status and system statistics |

### Actions — Connector management

| Example | Description |
|---------|-------------|
| `simple_index_connector.py` | Create a connector, write a document, clean up |
| `actions_management.py` | All connector operations: list types, create, get, update, execute, delete |
| `debug_connector.py` | Inspect connector responses and troubleshoot |
| `connector_management.py` | Advanced operations: list types, bulk writes, config updates |

### Spaces — Multi-tenancy

| Example | Description |
|---------|-------------|
| `simple_space.py` | Create, verify, and delete a space |
| `space_management.py` | Full CRUD with class-based pattern |
| `debug_spaces.py` | List all spaces with properties |
| `space_scoped_connector.py` | Create connectors scoped to a specific space |

### Saved Objects — Dashboards, visualizations, index patterns

| Example | Description |
|---------|-------------|
| `simple_saved_object.py` | Create, retrieve, and delete a saved object |
| `saved_objects_management.py` | Full CRUD with version control and space-scoped objects |
| `debug_saved_objects.py` | Inspect saved object structure and metadata |

### Alerting — Rule management

| Example | Description |
|---------|-------------|
| `simple_alerting_rules.py` | Create, get, find, update, and delete alerting rules |

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
3. `simple_index_connector.py` — first real API operation
4. `simple_space.py` — CRUD pattern
5. `error_handling.py` — exception handling
6. `async_example.py` — async/await usage

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
