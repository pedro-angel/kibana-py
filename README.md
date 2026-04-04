# Kibana Python Client

[![Documentation Status](https://readthedocs.org/projects/kibana-py/badge/?version=latest)](https://kibana-py.readthedocs.io/en/latest/?badge=latest)
[![Documentation Build](https://github.com/pedro-angel/kibana-py/workflows/Documentation/badge.svg)](https://github.com/pedro-angel/kibana-py/actions/workflows/docs.yml)
[![PyPI version](https://img.shields.io/pypi/v/kibana-py.svg)](https://pypi.org/project/kibana-py/)
[![PyPI downloads](https://img.shields.io/pypi/dm/kibana-py.svg)](https://pypi.org/project/kibana-py/)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> **Disclaimer:** This is an independent, community-driven project and is **not** officially affiliated with, endorsed by, or supported by Elastic N.V. or any of its subsidiaries. "Kibana" and "Elasticsearch" are trademarks of Elastic N.V. This project is provided "as is", without warranty of any kind. Use it at your own risk. See the [Disclaimer](#disclaimer) section and the [LICENSE](LICENSE) for full details.

A Python client library for interacting with Kibana's REST API. Built following the design patterns of the [elasticsearch-py](https://github.com/elastic/elasticsearch-py) client.

## 📚 Documentation

**[Read the full documentation on ReadTheDocs →](https://kibana-py.readthedocs.io/)**

- [Installation Guide](https://kibana-py.readthedocs.io/en/latest/installation.html)
- [Quick Start Guide](https://kibana-py.readthedocs.io/en/latest/quickstart.html)
- [User Guide](https://kibana-py.readthedocs.io/en/latest/user-guide/index.html)
- [API Reference](https://kibana-py.readthedocs.io/en/latest/api-reference/index.html)
- [Examples](https://kibana-py.readthedocs.io/en/latest/examples/index.html)

## Features

- **Dual API Support**: Both synchronous (`Kibana`) and asynchronous (`AsyncKibana`) clients
- **Type Safety**: Comprehensive type hints throughout for better IDE support and type checking
- **Reliable Transport**: Built on elastic-transport for connection pooling, retries, and node management
- **Flexible Authentication**: Support for API keys, basic auth, and bearer tokens
- **Space Support**: Multi-tenancy with Kibana Spaces
- **Comprehensive Error Handling**: Specific exception types for different HTTP status codes
- **Pythonic API**: Clean, idiomatic Python interface to Kibana's REST APIs
- **Observability**: Built-in OpenTelemetry support for distributed tracing

## Installation

```bash
pip install kibana-py
```

**Optional dependencies:**
- `kibana-py[async]` - Async client support
- `kibana-py[orjson]` - High-performance JSON serialization
- `kibana-py[observability]` - OpenTelemetry tracing support

For detailed installation instructions, see the [Installation Guide](https://kibana-py.readthedocs.io/en/latest/installation.html).

## Quick Start

### Basic Usage

```python
from kibana import Kibana

# Initialize client with authentication
client = Kibana(
    "http://localhost:5601",
    basic_auth=("elastic", "password")
)

# Get Kibana status
status = client.status.get_status()
print(f"Kibana status: {status.body['status']['overall']['level']}")

# Create a connector
connector = client.actions.create(
    name="My Webhook",
    connector_type_id=".webhook",
    config={"url": "https://example.com/webhook"}
)

print(f"Created connector: {connector.body['id']}")

# Close the client
client.close()
```

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
        print(status.body)

asyncio.run(main())
```

For more examples and detailed usage, see:
- [Quick Start Guide](https://kibana-py.readthedocs.io/en/latest/quickstart.html)
- [User Guide](https://kibana-py.readthedocs.io/en/latest/user-guide/index.html)
- [Examples](https://kibana-py.readthedocs.io/en/latest/examples/index.html)

## API Coverage

The client currently supports the following Kibana APIs:

- ✅ **Actions API** - Manage connectors for alerting and automation
- ✅ **Spaces API** - Multi-tenancy with Kibana Spaces
- ✅ **Saved Objects API** - Manage dashboards, visualizations, and other saved objects
- ✅ **Status API** - Check Kibana health and operational status
- ✅ **Alerting API** - Create, manage, and monitor alerting rules

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
        status = client.status()
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

The [examples/](examples/) directory contains working examples for all major features:

- **Connectors** - Create and manage Kibana connectors
- **Spaces** - Multi-tenancy with Kibana Spaces
- **Saved Objects** - Manage dashboards and visualizations
- **Async Operations** - Asynchronous client usage
- **Error Handling** - Exception handling patterns

See the [Examples Documentation](https://kibana-py.readthedocs.io/en/latest/examples/index.html) for detailed explanations.

## Development

Contributions are welcome! See the [Contributing Guide](https://kibana-py.readthedocs.io/en/latest/development/contributing.html) for details on:

- Setting up your development environment
- Running tests
- Code style and quality standards
- Submitting pull requests

For more information, see the [Development Documentation](https://kibana-py.readthedocs.io/en/latest/development/index.html).

## Requirements

- Python 3.10+
- Kibana 9.x
- elastic-transport >= 9.1.0

## Resources

- **[Documentation](https://kibana-py.readthedocs.io/)** - Complete documentation on ReadTheDocs
- **[Examples](examples/)** - Working code examples
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines
- **[Maintainers](MAINTAINERS.md)** - Maintainer ownership and release responsibilities
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community participation standards
- **[Changelog](CHANGELOG.md)** - Release history
- **[Issue Tracker](https://github.com/pedro-angel/kibana-py/issues)** - Report bugs or request features
- **[Kibana API Docs](https://www.elastic.co/guide/en/kibana/current/api.html)** - Official Kibana API documentation

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
