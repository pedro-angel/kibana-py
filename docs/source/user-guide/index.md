# User Guide

Welcome to the kibana-py user guide. This guide provides comprehensive documentation for using the Kibana Python client library.

## Getting Started

If you're new to kibana-py, start with these topics:

- [Authentication](authentication.md) - Learn how to authenticate with Kibana
- [Connectors](connectors.md) - Create and manage connectors for alerting and automation

## Core Features

### Resource Management

- [Connectors](connectors.md) - Manage Kibana connectors (actions) for alerting and automation
- [Spaces](spaces.md) - Organize resources with Kibana Spaces for multi-tenancy
- [Saved Objects](saved-objects.md) - Manage dashboards, visualizations, and other saved objects
- [Status Monitoring](status-monitoring.md) - Monitor Kibana health and operational statistics

### Advanced Topics

- [Error Handling](error-handling.md) - Handle exceptions and errors gracefully
- [Observability](observability.md) - Integrate OpenTelemetry for distributed tracing and log forwarding
- [Advanced Usage](advanced-usage.md) - Per-request configuration, async patterns, and performance optimization

## Quick Reference

### Basic Client Usage

```python
from kibana import Kibana

# Initialize client
client = Kibana(
    "http://localhost:5601",
    api_key="your_api_key"
)

# Use the client
status = client.status.get_status()
print(f"Kibana status: {status.body['status']['overall']['level']}")

# Close the client
client.close()
```

### Context Manager

```python
with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    status = client.status.get_status()
    print(status.body)
```

### Async Client

```python
import asyncio
from kibana import AsyncKibana

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        status = await client.status.get_status()
        print(status.body)

asyncio.run(main())
```

## Next Steps

- Explore the [API Reference](../api-reference/index.rst) for detailed method documentation
- Check out the [Examples](../examples/index.md) for practical code samples
- Learn about [Development](../development/index.md) if you want to contribute
