# Examples

This section provides comprehensive examples demonstrating how to use the Kibana Python client. Examples progress from simple to advanced, covering all major features.

```{toctree}
:maxdepth: 2
:caption: Examples

basic-usage
connectors/index
spaces/index
saved-objects/index
async/index
observability
```

## Getting Started

New to kibana-py? Start here:

1. **[Basic Usage](basic-usage.md)** - Client initialization, authentication, and fundamental patterns
2. **[Connectors](connectors/index.md)** - Create and manage Kibana connectors (actions)
3. **[Spaces](spaces/index.md)** - Organize resources with Kibana Spaces
4. **[Saved Objects](saved-objects/index.md)** - Manage dashboards, visualizations, and more

## Example Categories

### Basic Usage

Learn the fundamentals of using the Kibana client:

- **[Basic Usage](basic-usage.md)** - Client initialization, authentication, response handling, and configuration

**Start here if you're new to kibana-py.**

### Connectors (Actions)

Create and manage connectors for alerting and automation:

- **[Connector Overview](connectors/index.md)** - Introduction to connectors
- **[Simple Example](connectors/simple.md)** - Minimal connector creation (~50 lines)
- **[Debug Example](connectors/debug.md)** - Troubleshooting and API inspection
- **[Comprehensive Example](connectors/comprehensive.md)** - Production-ready patterns

**Perfect for integrating with external systems.**

### Spaces

Organize Kibana resources with spaces for multi-tenancy:

- **[Space Overview](spaces/index.md)** - Introduction to Kibana Spaces
- **[Simple Example](spaces/simple.md)** - Basic space creation
- **[Management Example](spaces/management.md)** - Full CRUD operations

**Essential for multi-tenant applications.**

### Saved Objects

Manage Kibana saved objects programmatically:

- **[Saved Objects Overview](saved-objects/index.md)** - Introduction to saved objects
- **[Management Example](saved-objects/management.md)** - CRUD operations and version control

**For managing dashboards and visualizations.**

### Async Operations

Use the async client for concurrent operations:

- **[Async Overview](async/index.md)** - Introduction to AsyncKibana
- **[Async Patterns](async/patterns.md)** - Concurrent operations and best practices

**For high-performance applications.**

### Observability

Monitor your application with OpenTelemetry:

- **[Observability](observability.md)** - Tracing and log forwarding

**For production monitoring and debugging.**

## Example Progression

### Level 1: Simple Examples

Minimal code to get started quickly:

- [Simple Connector](connectors/simple.md) - ~50 lines
- [Simple Space](spaces/simple.md) - ~40 lines
- [Basic Usage](basic-usage.md) - Fundamental patterns

**Best for**: Learning, prototyping, quick scripts

### Level 2: Debug Examples

Understand API responses and troubleshoot issues:

- [Debug Connector](connectors/debug.md) - Verbose output and API inspection

**Best for**: Troubleshooting, understanding the API

### Level 3: Comprehensive Examples

Production-ready patterns with error handling:

- [Comprehensive Connector](connectors/comprehensive.md) - Class-based, full lifecycle
- [Space Management](spaces/management.md) - Complete CRUD operations
- [Saved Objects Management](saved-objects/management.md) - Version control and bulk operations

**Best for**: Production applications, robust implementations

## Running Examples

### Prerequisites

1. **Running Kibana instance** (default: http://localhost:5601)
2. **Elasticsearch cluster** with write permissions
3. **Authentication** (optional but recommended):
   - API key, or
   - Basic authentication (username/password), or
   - Bearer token

### Quick Start with elastic-start-local

The easiest way to run examples:

```bash
# Start local Elastic Stack
./local-stack.sh -o start

# Run any example
python examples/simple_index_connector.py
```

### Manual Configuration

Set environment variables:

```bash
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="changeme"

python examples/simple_index_connector.py
```

## Automatic Configuration

All examples support automatic configuration from multiple sources:

1. **Environment variables**: `KIBANA_URL`, `KIBANA_API_KEY`, etc.
2. **Local development setup**: Reads from `elastic-start-local/.env`
3. **Defaults**: Falls back to `http://localhost:5601`

## Common Patterns

### Pattern 1: Context Manager

```python
from kibana import Kibana

with Kibana("http://localhost:5601") as client:
    # Use client
    response = client.status.get_status()
# Automatic cleanup
```

### Pattern 2: Response Handling

```python
# Always access .body attribute
response = client.actions.list_types()
types = response.body  # This is the actual data

# Access metadata
print(f"Status: {response.meta.status}")
```

### Pattern 3: Error Handling

```python
from kibana.exceptions import ConflictError, NotFoundError

try:
    connector = client.actions.create(...)
except ConflictError:
    print("Already exists")
except NotFoundError:
    print("Not found")
```

### Pattern 4: Space-Scoped Operations

```python
# Method 1: space_id parameter
connector = client.actions.create(
    name="Test",
    connector_type_id=".index",
    config={},
    space_id="marketing"
)

# Method 2: Space-scoped client
marketing_client = client.space("marketing")
connector = marketing_client.actions.create(
    name="Test",
    connector_type_id=".index",
    config={}
)
```

## Example Features

All examples include:

- ✅ **Automatic configuration** from environment or local setup
- ✅ **Interactive cleanup** to prevent resource accumulation
- ✅ **Proper error handling** with specific exceptions
- ✅ **Response handling** using `.body` attribute
- ✅ **OpenTelemetry support** for tracing and logging
- ✅ **Clear output** with status messages

## Best Practices

1. **Start simple** - Begin with simple examples, progress to comprehensive
2. **Use context managers** - Automatic resource cleanup
3. **Handle errors** - Catch specific exceptions
4. **Clean up resources** - Delete test connectors and spaces
5. **Enable observability** - Use tracing for production applications

## Troubleshooting

### Connection Issues

**Problem**: `ConnectionError: Connection refused`

**Solution**: Ensure Kibana is running at the specified URL

### Authentication Issues

**Problem**: `AuthenticationException: Authentication failed`

**Solution**: Verify credentials are correct

### Permission Issues

**Problem**: `AuthorizationException: Insufficient permissions`

**Solution**: Ensure user has required permissions for the operation

## Next Steps

1. **Start with [Basic Usage](basic-usage.md)** to understand fundamentals
2. **Explore [Connectors](connectors/index.md)** for integration patterns
3. **Learn [Spaces](spaces/index.md)** for multi-tenancy
4. **Review [User Guide](../user-guide/index.md)** for detailed documentation
5. **Check [API Reference](../api-reference/index.rst)** for complete API documentation

## Related Documentation

- [Installation Guide](../installation.md)
- [Quick Start](../quickstart.md)
- [User Guide](../user-guide/index.md)
- [API Reference](../api-reference/index.rst)
- [Error Handling](../user-guide/error-handling.md)
- [Observability](../user-guide/observability.md)
