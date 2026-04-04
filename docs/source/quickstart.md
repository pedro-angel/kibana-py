# Quick Start

This guide will help you get started with kibana-py quickly. We'll cover basic client initialization, authentication, and a simple example of working with connectors.

## Prerequisites

Before you begin, make sure you have:

- Installed kibana-py (see {doc}`installation`)
- A running Kibana instance (version 9.x)
- Valid credentials for authentication

## Basic Usage

Here's the simplest way to use kibana-py:

```python
from kibana import Kibana

# Initialize the client
client = Kibana("http://localhost:5601")

# Get Kibana status
status = client.status.get_status()
print(f"Kibana status: {status.body['status']['overall']['level']}")

# Close the client when done
client.close()
```

:::{tip}
Always close the client when you're done to release resources. Better yet, use a context manager (see below).
:::

## Authentication

kibana-py supports three authentication methods. Choose the one that matches your Kibana configuration.

### API Key Authentication

API keys are the recommended authentication method for production applications:

```python
from kibana import Kibana

# Using a base64-encoded API key string
client = Kibana(
    "http://localhost:5601",
    api_key="your_base64_encoded_api_key"
)

# Or using an API key tuple (id, secret)
client = Kibana(
    "http://localhost:5601",
    api_key=("key_id", "key_secret")
)
```

To create an API key in Kibana:
1. Go to Stack Management → API Keys
2. Click "Create API key"
3. Set appropriate privileges
4. Copy the generated key

### Basic Authentication

Use username and password authentication:

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    basic_auth=("username", "password")
)
```

:::{warning}
Basic authentication sends credentials with every request. Use HTTPS in production to protect credentials.
:::

### Bearer Token

Use a bearer token for authentication:

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    bearer_auth="your_bearer_token"
)
```

## Using Context Managers

The recommended way to use kibana-py is with context managers, which automatically handle cleanup:

```python
from kibana import Kibana

with Kibana("http://localhost:5601", basic_auth=("elastic", "password")) as client:
    status = client.status.get_status()
    print(f"Kibana is {status.body['status']['overall']['level']}")
    # Client is automatically closed when exiting the context
```

## Complete Example: Working with Connectors

Here's a complete example that demonstrates creating, using, and cleaning up a connector:

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError, ApiError

# Initialize client with authentication
client = Kibana(
    "http://localhost:5601",
    basic_auth=("elastic", "password")
)

try:
    # Create a webhook connector
    print("Creating webhook connector...")
    connector = client.actions.create(
        name="My Webhook",
        connector_type_id=".webhook",
        config={
            "url": "https://example.com/webhook",
            "method": "post",
            "headers": {"Content-Type": "application/json"}
        }
    )

    connector_id = connector.body["id"]
    print(f"✓ Created connector: {connector_id}")

    # List all connectors
    print("\nListing all connectors...")
    connectors = client.actions.get_all()
    for conn in connectors.body:
        print(f"  - {conn['name']} ({conn['connector_type_id']})")

    # Get the specific connector
    print(f"\nRetrieving connector {connector_id}...")
    retrieved = client.actions.get(id=connector_id)
    print(f"✓ Connector name: {retrieved.body['name']}")

    # Execute the connector
    print("\nExecuting connector...")
    result = client.actions.execute(
        id=connector_id,
        params={"body": '{"message": "Hello from Kibana!"}'}
    )
    print(f"✓ Execution status: {result.body['status']}")

    # Clean up: delete the connector
    print(f"\nDeleting connector {connector_id}...")
    client.actions.delete(id=connector_id)
    print("✓ Connector deleted")

except NotFoundError as e:
    print(f"✗ Resource not found: {e.message}")
except ApiError as e:
    print(f"✗ API error: {e.message}")
    print(f"  Status code: {e.status_code}")
    print(f"  Response: {e.body}")
finally:
    # Always close the client
    client.close()
```

## Error Handling

Always handle exceptions when working with the API:

```python
from kibana import Kibana
from kibana.exceptions import (
    NotFoundError,
    AuthenticationException,
    ConflictError,
    ApiError
)

client = Kibana("http://localhost:5601", basic_auth=("elastic", "password"))

try:
    # Try to get a non-existent connector
    connector = client.actions.get(id="non-existent-id")
except NotFoundError as e:
    print(f"Connector not found: {e.message}")
except AuthenticationException as e:
    print(f"Authentication failed: {e.message}")
except ConflictError as e:
    print(f"Conflict: {e.message}")
except ApiError as e:
    # Catch-all for other API errors
    print(f"API error: {e.message}")
    print(f"Status code: {e.status_code}")
finally:
    client.close()
```

See {doc}`user-guide/error-handling` for comprehensive error handling patterns.

## Async Client

For asynchronous applications, use `AsyncKibana`:

```python
import asyncio
from kibana import AsyncKibana

async def main():
    # Use async context manager
    async with AsyncKibana(
        "http://localhost:5601",
        basic_auth=("elastic", "password")
    ) as client:
        # Get Kibana status
        status = await client.status.get_status()
        print(f"Kibana status: {status.body['status']['overall']['level']}")

        # Create a connector
        connector = await client.actions.create(
            name="Async Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"}
        )

        print(f"Created connector: {connector.body['id']}")

# Run the async function
asyncio.run(main())
```

:::{note}
Async support requires the `aiohttp` package. Install with: `pip install kibana-py[async]`
:::

See {doc}`user-guide/advanced-usage` for more async patterns.

## Per-Request Configuration

You can override settings for individual requests using the `options()` method:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", basic_auth=("elastic", "password"))

# Set a longer timeout for a specific request
result = client.options(request_timeout=60).actions.get_all()

# Use different authentication for a specific request
result = client.options(api_key="different_key").actions.get_all()

# Add custom headers
result = client.options(
    headers={"X-Custom-Header": "value"}
).actions.get_all()

client.close()
```

## Working with Spaces

Kibana Spaces provide multi-tenancy. You can scope operations to specific spaces:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", basic_auth=("elastic", "password"))

# Create a connector in a specific space
connector = client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://example.com/webhook"},
    space_id="marketing"  # Create in the "marketing" space
)

# Or use a space-scoped client for multiple operations
marketing_client = client.space("marketing")
connector = marketing_client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://example.com/webhook"}
)

client.close()
```

See {doc}`user-guide/spaces` for comprehensive space management.

## Next Steps

Now that you've learned the basics, explore these topics:

- **{doc}`user-guide/authentication`** - Detailed authentication configuration
- **{doc}`user-guide/connectors`** - Complete guide to working with connectors
- **{doc}`user-guide/spaces`** - Multi-tenancy with Kibana Spaces
- **{doc}`user-guide/saved-objects`** - Managing dashboards and visualizations
- **{doc}`user-guide/error-handling`** - Comprehensive error handling
- **{doc}`user-guide/observability`** - OpenTelemetry integration
- **{doc}`examples/index`** - More code examples

## Common Patterns

### Check Kibana Health

```python
from kibana import Kibana

with Kibana("http://localhost:5601") as client:
    status = client.status.get_status()
    overall = status.body['status']['overall']

    if overall['level'] == 'available':
        print("✓ Kibana is healthy")
    else:
        print(f"⚠ Kibana status: {overall['level']}")
        print(f"  Summary: {overall['summary']}")
```

### List Available Connector Types

```python
from kibana import Kibana

with Kibana("http://localhost:5601", basic_auth=("elastic", "password")) as client:
    types = client.actions.list_types()

    print("Available connector types:")
    for connector_type in types.body:
        print(f"  - {connector_type['id']}: {connector_type['name']}")
```

### Create and Manage Spaces

```python
from kibana import Kibana

with Kibana("http://localhost:5601", basic_auth=("elastic", "password")) as client:
    # Create a new space
    space = client.spaces.create(
        id="marketing",
        name="Marketing Team",
        description="Space for marketing team resources",
        color="#FF6B6B"
    )

    print(f"✓ Created space: {space.body['name']}")

    # List all spaces
    spaces = client.spaces.get_all()
    for s in spaces.body:
        print(f"  - {s['name']} ({s['id']})")
```

## Getting Help

If you encounter issues:

- Check the {doc}`troubleshooting/common-issues` guide
- Review the {doc}`api-reference/index` for detailed API documentation
- Browse the {doc}`examples/index` for more code samples
- Report bugs on [GitHub Issues](https://github.com/pedro-angel/kibana-py/issues)

## Additional Resources

- **{doc}`user-guide/index`** - Comprehensive user guide
- **{doc}`api-reference/index`** - Complete API reference
- **{doc}`examples/index`** - Code examples
- **[Kibana API Documentation](https://www.elastic.co/guide/en/kibana/current/api.html)** - Official Kibana API docs
