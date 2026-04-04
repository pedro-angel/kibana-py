# Connector Examples

Connectors (also called Actions) in Kibana allow you to integrate with external systems for alerting, automation, and data forwarding. This section demonstrates how to create, configure, and use connectors programmatically.

```{toctree}
:maxdepth: 2
:caption: Connector Examples

simple
debug
comprehensive
```

## Overview

The connector examples progress from simple to comprehensive, showing you:

- Basic connector creation and execution
- Debugging and troubleshooting techniques
- Production-ready patterns with error handling
- Space-scoped connector operations

## Example Progression

We provide three levels of connector examples, each building on the previous:

### 1. Simple Example (`simple_index_connector.py`)

**Purpose**: Minimal code to get started quickly

**What You'll Learn**:
- Create an index connector in ~50 lines of code
- Write a document to Elasticsearch via the connector
- Clean up resources interactively

**When to Use**: Perfect starting point for learning connectors or quick prototyping

[View Simple Example →](simple.md)

### 2. Debug Example (`debug_connector.py`)

**Purpose**: Understand API responses and troubleshoot issues

**What You'll Learn**:
- List available connector types
- Inspect API responses in detail
- Debug connector creation issues
- Understand connector configuration

**When to Use**: When you need to troubleshoot connector issues or understand the API better

[View Debug Example →](debug.md)

### 3. Advanced Example (`connector_management.py`)

**Purpose**: Production-ready patterns and advanced features

**What You'll Learn**:
- Class-based connector management
- Comprehensive error handling
- Update and delete operations
- Batch document writing
- Logging and observability integration

**When to Use**: Building production applications that manage connectors

[View Comprehensive Example →](comprehensive.md)

## What Are Connectors?

Connectors are Kibana's way of integrating with external systems. They can:

- **Write data** to Elasticsearch indices (index connector)
- **Send notifications** via email, Slack, webhooks
- **Trigger actions** in external systems
- **Forward logs** to monitoring systems

## Index Connector Basics

The index connector is one of the most commonly used connector types. It writes documents to Elasticsearch indices.

### Configuration

```python
config = {
    "index": "my-index-name",      # Target index
    "refresh": True,                # Refresh after write
    "executionTimeField": "@timestamp"  # Timestamp field
}
```

### Document Structure

Documents can contain any valid JSON data:

```python
document = {
    "@timestamp": "2024-01-01T12:00:00Z",
    "message": "Application started",
    "level": "INFO",
    "service": "web-server",
    "host": "server-01",
    # ... any other fields
}
```

## Common Use Cases

### 1. Application Logging

Write application logs to Elasticsearch for centralized logging:

```python
connector = client.actions.create(
    name="App Logs Connector",
    connector_type_id=".index",
    config={"index": "app-logs", "refresh": True}
)

# Write log entry
client.actions.execute(
    id=connector.body["id"],
    params={"documents": [{
        "@timestamp": datetime.now(UTC).isoformat(),
        "level": "ERROR",
        "message": "Database connection failed",
        "service": "api-server"
    }]}
)
```

### 2. Metrics Collection

Forward metrics to Elasticsearch:

```python
connector = client.actions.create(
    name="Metrics Connector",
    connector_type_id=".index",
    config={"index": "app-metrics", "refresh": False}
)

# Write metrics
client.actions.execute(
    id=connector.body["id"],
    params={"documents": [{
        "@timestamp": datetime.now(UTC).isoformat(),
        "metric_name": "response_time",
        "value": 150.5,
        "unit": "ms",
        "endpoint": "/api/users"
    }]}
)
```

### 3. Event Tracking

Track application events:

```python
connector = client.actions.create(
    name="Events Connector",
    connector_type_id=".index",
    config={"index": "app-events", "refresh": True}
)

# Track event
client.actions.execute(
    id=connector.body["id"],
    params={"documents": [{
        "@timestamp": datetime.now(UTC).isoformat(),
        "event_type": "user_signup",
        "user_id": "user123",
        "source": "web",
        "metadata": {"plan": "premium"}
    }]}
)
```

## Space-Scoped Connectors

Connectors can be created in specific Kibana spaces for multi-tenancy:

```python
# Create connector in a specific space
connector = client.actions.create(
    name="Marketing Team Connector",
    connector_type_id=".index",
    config={"index": "marketing-data"},
    space_id="marketing-team"
)

# Or use a space-scoped client
marketing_client = client.space("marketing-team")
connector = marketing_client.actions.create(
    name="Marketing Team Connector",
    connector_type_id=".index",
    config={"index": "marketing-data"}
)
```

See [Space-Scoped Connector Example](../spaces/management.md) for more details.

## Error Handling

All connector operations can raise exceptions:

```python
from kibana.exceptions import ConflictError, BadRequestError, NotFoundError

try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
except ConflictError:
    print("Connector with this name already exists")
except BadRequestError as e:
    print(f"Invalid configuration: {e}")
except NotFoundError:
    print("Connector type not found")
```

## Cleanup Best Practices

All examples include interactive cleanup to prevent connector accumulation:

```python
# At the end of your script
cleanup = input("Delete the connector? (y/N): ").lower().strip()
if cleanup == 'y':
    try:
        client.actions.delete(id=connector_id)
        print("✓ Connector deleted")
    except Exception as e:
        # Verify deletion
        try:
            client.actions.get(id=connector_id)
            print(f"❌ Failed to delete: {e}")
        except NotFoundError:
            print("✓ Connector deleted (confirmed)")
```

## Available Connector Types

Beyond index connectors, Kibana supports many connector types:

- `.index` - Write to Elasticsearch indices
- `.server-log` - Write to Kibana server logs
- `.webhook` - HTTP webhooks
- `.slack` - Slack notifications
- `.email` - Email notifications
- `.pagerduty` - PagerDuty integration
- `.servicenow` - ServiceNow integration
- And many more...

List available types:

```python
types = client.actions.list_types()
for connector_type in types.body:
    print(f"{connector_type['id']}: {connector_type['name']}")
```

## Next Steps

1. Start with the [Simple Example](simple.md) to understand the basics
2. Use the [Debug Example](debug.md) when troubleshooting
3. Study the [Comprehensive Example](comprehensive.md) for production patterns
4. Explore [Space-Scoped Operations](../spaces/index.md) for multi-tenancy
5. Review [Error Handling](../../user-guide/error-handling.md) for robust applications

## Related Documentation

- [Actions API Reference](../../api-reference/actions.rst)
- [Error Handling Guide](../../user-guide/error-handling.md)
- [Space Support](../../user-guide/spaces.md)
- [Observability Integration](../../user-guide/observability.md)
