# Kibana Python Client

[![Documentation Status](https://readthedocs.org/projects/kibana-py/badge/?version=latest)](https://kibana-py.readthedocs.io/en/latest/?badge=latest)
[![Documentation Build](https://github.com/pedro-angel/kibana-py/workflows/Documentation/badge.svg)](https://github.com/pedro-angel/kibana-py/actions/workflows/docs.yml)
[![PyPI version](https://img.shields.io/pypi/v/kibana-py.svg)](https://pypi.org/project/kibana-py/)
[![PyPI downloads](https://img.shields.io/pypi/dm/kibana-py.svg)](https://pypi.org/project/kibana-py/)
[![Python Version](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> **Disclaimer:** This is an independent, community-driven project and is **not** officially affiliated with, endorsed by, or supported by Elastic N.V. or any of its subsidiaries. "Kibana" and "Elasticsearch" are trademarks of Elastic N.V. This project is provided "as is", without warranty of any kind. Use it at your own risk. See the [Disclaimer](#disclaimer) section and the [LICENSE](LICENSE) for full details.

A Python client library for the Kibana REST API with **complete Kibana 9.4.3 platform, Fleet, and Security Solution API coverage** — 39 namespaces, 610 endpoints, sync and async. Built following the design patterns of the [elasticsearch-py](https://github.com/elastic/elasticsearch-py) client, and verified live against Kibana 9.4.3.

Headline feature: first-class support for the **new Kibana Dashboards HTTP API** (`client.dashboards`, technical preview in 9.4) and its sibling **Visualizations HTTP API** (`client.visualizations`) — manage dashboards and Lens visualizations through a real, documented data model instead of opaque saved objects.

## 📚 Documentation

**[Read the full documentation on ReadTheDocs →](https://kibana-py.readthedocs.io/)**

- [Installation Guide](https://kibana-py.readthedocs.io/en/latest/installation.html)
- [Quick Start Guide](https://kibana-py.readthedocs.io/en/latest/quickstart.html)
- [User Guide](https://kibana-py.readthedocs.io/en/latest/user-guide/index.html)
- [API Reference](https://kibana-py.readthedocs.io/en/latest/api-reference/index.html)
- [Examples](https://kibana-py.readthedocs.io/en/latest/examples/index.html)

## Features

- **Complete API coverage**: 39 namespaces, 610 endpoints spanning the Kibana 9.4.3 platform, Fleet, and Security Solution REST APIs, every one live-tested against a real Kibana 9.4.3
- **Fleet & Security Solution**: full clients for Fleet (agents, policies, integrations/EPM, outputs, enrollment) and Security Solution (detection engine, exceptions, value lists, timelines, endpoint response actions, entity analytics, osquery, AI assistant, attack discovery)
- **New Dashboards & Visualizations APIs**: first-class clients for the tech-preview Dashboards and Lens Visualizations HTTP APIs introduced in Kibana 9.4
- **Dual API support**: synchronous (`Kibana`) and asynchronous (`AsyncKibana`) clients with full method parity
- **NDJSON & multipart**: saved-object export (`application/x-ndjson`) parsing and multipart/form-data uploads (saved-object import, APM source maps)
- **Type safety**: comprehensive type hints throughout, `py.typed` marker (PEP 561)
- **Reliable transport**: built on elastic-transport for connection pooling, retries, and node management; SSL/TLS options (`verify_certs`, `ca_certs`, client certs, custom contexts) fully honored
- **Flexible authentication**: API keys, basic auth, and bearer tokens
- **Space support**: multi-tenancy with Kibana Spaces — space-scoped clients and per-call `space_id`
- **Comprehensive error handling**: specific exception types per HTTP status, carrying Kibana's detailed error message
- **Observability**: built-in OpenTelemetry support for distributed tracing

## Installation

```bash
pip install kibana-py
```

**Requires Python 3.14+.**

**Optional dependencies:**
- `kibana-py[async]` - Async client support
- `kibana-py[orjson]` - High-performance JSON serialization
- `kibana-py[observability]` - OpenTelemetry tracing support

For detailed installation instructions, see the [Installation Guide](https://kibana-py.readthedocs.io/en/latest/installation.html).

## Quick Start

### Dashboards (new HTTP API, Kibana 9.4+)

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    basic_auth=("elastic", "password"),
)

# Create a dashboard with a markdown panel and a relative time range
dashboard = client.dashboards.create(
    title="Service health",
    description="Ops overview",
    time_range={"from": "now-24h", "to": "now"},
    panels=[
        {
            "type": "markdown",
            "grid": {"x": 0, "y": 0, "w": 48, "h": 6},
            "config": {"content": "## Runbook links"},
        }
    ],
)
dashboard_id = dashboard.body["id"]

# Search dashboards, then fetch the full panel layout of one
results = client.dashboards.get_all(query="service*", per_page=10)
print(f"Found {results.body['total']} dashboards")

full = client.dashboards.get(id=dashboard_id)
print(full.body["data"]["title"])

# Clean up
client.dashboards.delete(id=dashboard_id)
client.close()
```

### Connectors

```python
from kibana import Kibana

with Kibana("http://localhost:5601", basic_auth=("elastic", "password")) as client:
    connector = client.connectors.create(
        name="My Webhook",
        connector_type_id=".webhook",
        config={"url": "https://example.com/webhook"},
    )
    print(f"Created connector: {connector.body['id']}")
```

> **Deprecation note:** the connectors namespace was previously exposed as `client.actions`. `client.actions` still works as a deprecated alias of `client.connectors` and will be removed in a future release — new code should use `client.connectors`.

### Async Client

```python
import asyncio
from kibana import AsyncKibana

async def main():
    async with AsyncKibana(
        "http://localhost:5601",
        basic_auth=("elastic", "password")
    ) as client:
        status = await client.status.get_status()
        print(status.body["status"]["overall"]["level"])

asyncio.run(main())
```

For more examples and detailed usage, see:
- [Quick Start Guide](https://kibana-py.readthedocs.io/en/latest/quickstart.html)
- [User Guide](https://kibana-py.readthedocs.io/en/latest/user-guide/index.html)
- [Examples](https://kibana-py.readthedocs.io/en/latest/examples/index.html)

## API Coverage

Full coverage of the Kibana 9.4.3 platform, Fleet, and Security Solution REST APIs — 39 namespaces, 610 endpoints, identical sync and async surfaces.

### Platform (24 namespaces, 269 endpoints)

| Client namespace | Kibana API | Endpoints | Status |
|---|---|---|---|
| `client.dashboards` | Dashboards HTTP API | 5 | Tech preview |
| `client.visualizations` | Visualizations (Lens) HTTP API | 5 | Tech preview |
| `client.agent_builder` | Agent Builder (agents, tools, converse, MCP, A2A) | 37 | GA¹ |
| `client.alerting` | Alerting (`alerting.rule.*`, `alerting.backfill.*`, health, rule types) | 21 | GA |
| `client.apm` | APM (agent configuration, agent keys, annotations, source maps) | 14 | GA |
| `client.cases` | Cases (cases, comments, files, configuration, activity) | 22 | GA¹ |
| `client.connectors` | Connectors (formerly "actions"; `client.actions` is a deprecated alias) | 9 | GA |
| `client.data_views` | Data views (fields, runtime fields, default, swap references) | 15 | GA |
| `client.logstash` | Logstash centralized pipeline management | 4 | Tech preview |
| `client.maintenance_windows` | Maintenance windows | 7 | GA |
| `client.ml` | Machine learning saved objects (sync, space assignment) | 3 | GA |
| `client.observability_ai_assistant` | Observability AI Assistant chat completion | 1 | Tech preview |
| `client.saved_objects` | Saved objects (export/import + deprecated CRUD²) | 16 | GA² |
| `client.security` | Security (roles, sessions) | 7 | GA |
| `client.short_urls` | Short URLs | 4 | Tech preview |
| `client.slos` | SLOs (service level objectives) | 13 | GA |
| `client.spaces` | Spaces (CRUD, copy/share saved objects between spaces) | 10 | GA |
| `client.status` | Status, stats, and features | 3 | GA¹ |
| `client.streams` | Streams (wired streams, significant events, content packs) | 25 | Tech preview |
| `client.synthetics` | Synthetics (monitors, private locations, parameters, test-now) | 18 | GA |
| `client.task_manager` | Task Manager health | 1 | GA |
| `client.upgrade_assistant` | Upgrade Assistant readiness | 1 | Tech preview |
| `client.uptime` | Uptime settings | 2 | GA |
| `client.workflows` | Workflows (definitions, executions, logs) | 26 | GA |

### Fleet (6 namespaces, 140 endpoints)

| Client namespace | Kibana API | Endpoints | Status |
|---|---|---|---|
| `client.fleet` | Fleet setup, settings, space settings, health check, permissions | 7 | GA |
| `client.fleet_agents` | Elastic Agents (list, actions, bulk actions, status, uploads, tags) | 33 | GA |
| `client.fleet_policies` | Agent policies, package policies, agentless policies | 23 | GA |
| `client.fleet_epm` | Elastic Package Manager (integrations, installs, assets, custom integrations) | 37 | GA |
| `client.fleet_outputs` | Outputs, Fleet Server hosts, proxies, download sources, cloud connectors | 29 | GA |
| `client.fleet_enrollment` | Enrollment keys, service/logstash tokens, uninstall tokens, signing, kubernetes | 11 | GA |

### Security Solution (9 namespaces, 201 endpoints)

| Client namespace | Kibana API | Endpoints | Status |
|---|---|---|---|
| `client.detection_engine` | Detection rules, alerts (signals), prepackaged rules, migrations | 25 | GA |
| `client.exception_lists` | Exception lists & items, shared/rule exceptions, endpoint exceptions | 22 | GA |
| `client.lists` | Value lists & items (index, import/export) | 18 | GA |
| `client.timeline` | Timelines, notes, pinned events, drafts, import/export | 17 | GA |
| `client.endpoint` | Endpoint metadata, response actions, scripts library | 29 | GA |
| `client.entity_analytics` | Asset criticality, risk score, entity store, monitoring, watchlists³ | 42 | GA³ |
| `client.osquery` | Osquery packs, saved queries, live queries | 14 | GA |
| `client.security_ai_assistant` | AI Assistant conversations, prompts, knowledge base, chat complete | 21 | GA |
| `client.attack_discovery` | AI attack discoveries, generations, schedules | 13 | Tech preview |

¹ Some endpoints in this namespace are technical preview in Kibana 9.4 (e.g. Agent Builder consumption/skills/plugins, cases custom-field/template features, `status.get_features()`).

² Most single-object and bulk saved-object CRUD endpoints are deprecated by Kibana 9.4.3 in favor of the type-specific APIs (dashboards, data views, ...) and the export/import APIs; the client methods carry deprecation notes with replacements.

³ Entity analytics spans several maturity levels in Kibana 9.4: asset-criticality endpoints are deprecated (superseded by the entity store), watchlists and privileged-user monitoring are technical preview, and the risk-score engine and entity store are GA. Method docstrings note the per-endpoint state and any live-server behavior that differs from the OpenAPI spec.

For detailed API documentation, see the [API Reference](https://kibana-py.readthedocs.io/en/latest/api-reference/index.html).

## Health Checks & Readiness Probes

Use the **Status API** to build health check endpoints for Kubernetes liveness/readiness probes or load-balancer health checks:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="...")

# Simple health check
def is_kibana_ready() -> bool:
    """Return True if Kibana is green/ready."""
    try:
        status = client.status.get_status()
        return status.body["status"]["overall"]["level"] == "available"
    except Exception:
        return False

# Kubernetes-style probe endpoint (Flask example)
@app.route("/healthz")
def healthz():
    if is_kibana_ready():
        return {"status": "ok"}, 200
    return {"status": "unavailable"}, 503
```

## Authentication

The client supports multiple authentication methods:

```python
# API Key
client = Kibana("http://localhost:5601", api_key="your_api_key")

# Basic Auth
client = Kibana("http://localhost:5601", basic_auth=("username", "password"))

# Bearer Token
client = Kibana("http://localhost:5601", bearer_auth="your_token")
```

For more details, see the [Authentication Guide](https://kibana-py.readthedocs.io/en/latest/user-guide/authentication.html).

## Examples

The [examples/](examples/) directory contains a runnable `<namespace>_management.py` walkthrough for every namespace — dashboards, visualizations, alerting, cases, connectors, streams, workflows, agent builder, and the rest — plus quick-start, async, and error-handling examples. See [examples/README.md](examples/README.md) for the full catalog.

See the [Examples Documentation](https://kibana-py.readthedocs.io/en/latest/examples/index.html) for detailed explanations.

## Development

Contributions are welcome! See the [Contributing Guide](https://kibana-py.readthedocs.io/en/latest/development/contributing.html) for details on:

- Setting up your development environment
- Running tests
- Code style and quality standards
- Submitting pull requests

For more information, see the [Development Documentation](https://kibana-py.readthedocs.io/en/latest/development/index.html).

## Requirements

- Python 3.14+
- Kibana 9.4.x (developed and live-tested against 9.4.3)
- elastic-transport >= 9.1.0

## Resources

- **[Documentation](https://kibana-py.readthedocs.io/)** - Complete documentation on ReadTheDocs
- **[Examples](examples/)** - Working code examples
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines
- **[Maintainers](MAINTAINERS.md)** - Maintainer ownership and release responsibilities
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community participation standards
- **[Changelog](CHANGELOG.md)** - Release history
- **[Issue Tracker](https://github.com/pedro-angel/kibana-py/issues)** - Report bugs or request features
- **[Kibana API Docs](https://www.elastic.co/docs/api/doc/kibana/)** - Official Kibana API documentation

## Disclaimer

This project is an independent, community-driven open-source effort. It is **not** officially affiliated with, endorsed by, sponsored by, or supported by [Elastic N.V.](https://www.elastic.co/) or any of its subsidiaries. "Kibana", "Elasticsearch", and "Elastic" are trademarks or registered trademarks of Elastic N.V.

This software is provided **"as is"**, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors, contributors, or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

By using this library, you acknowledge that:

- The authors and contributors assume **no responsibility or liability** for any errors, issues, data loss, or damages resulting from the use of this software.
- You are solely responsible for evaluating the suitability of this software for your use case and for any consequences of its use.
- This project is not a substitute for Elastic's official tools, clients, or support channels.

For the complete license terms, see the [LICENSE](LICENSE) file.

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
