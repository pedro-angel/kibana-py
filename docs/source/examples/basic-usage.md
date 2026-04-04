# Basic Usage Examples

This section demonstrates the fundamental patterns for using the Kibana Python client. These examples cover client initialization, authentication, response handling, and basic configuration.

## Overview

The basic usage examples show you how to:

- Initialize the Kibana client with different authentication methods
- Use context managers for automatic resource cleanup
- Handle API responses correctly
- Configure per-request options
- Set up connection pooling and retry logic

## Example Files

### basic_usage.py

**Location**: `examples/basic_usage.py`

**Purpose**: Comprehensive demonstration of fundamental client patterns

**What You'll Learn**:
- Multiple ways to initialize the Kibana client
- Different authentication methods (API key, basic auth, bearer token)
- Using context managers for automatic cleanup
- Accessing response data correctly
- Per-request configuration with the `options()` method
- Advanced connection configuration

**When to Use**: Start here if you're new to kibana-py or need to understand the core client patterns.

## Key Concepts

### Client Initialization

The Kibana client can be initialized in several ways:

```python
from kibana import Kibana

# Simple initialization with URL only
client = Kibana("http://localhost:5601")

# With basic authentication
client = Kibana("http://localhost:5601", basic_auth=("elastic", "password"))

# With API key
client = Kibana("http://localhost:5601", api_key="your_api_key")

# With bearer token
client = Kibana("http://localhost:5601", bearer_auth="your_bearer_token")
```

### Context Manager Pattern

The recommended way to use the client is with a context manager, which automatically closes the connection:

```python
from kibana import Kibana

with Kibana("http://localhost:5601", basic_auth=("elastic", "password")) as client:
    # Use the client
    types = client.actions.list_types()
    print(f"Found {len(types.body)} connector types")
# Client is automatically closed here
```

**Why Use Context Managers?**
- Automatic resource cleanup
- Prevents connection leaks
- Cleaner, more Pythonic code
- Handles exceptions gracefully

### Response Handling

All API methods return an `ObjectApiResponse` object. Always access the `.body` attribute to get the actual data:

```python
# Correct: Access .body attribute
response = client.actions.list_types()
types = response.body  # This is the actual data
print(f"Found {len(types)} types")

# Also correct: Access metadata
print(f"HTTP Status: {response.meta.status}")
print(f"HTTP Version: {response.meta.http_version}")

# Incorrect: Don't treat response as a dictionary
# types = response["types"]  # This will fail!
```

### Per-Request Configuration

Use the `options()` method to configure individual requests without affecting the client:

```python
# Set a longer timeout for a specific request
response = client.options(request_timeout=60).actions.list_types()

# Add custom headers
response = client.options(
    headers={"X-Custom-Header": "value"}
).actions.list_types()

# Chain multiple options
response = client.options(
    request_timeout=30,
    headers={"X-Request-ID": "12345"}
).actions.list_types()
```

### Advanced Configuration

For production use, configure connection pooling, retries, and timeouts:

```python
from kibana import Kibana

client = Kibana(
    hosts=["http://localhost:5601"],
    basic_auth=("elastic", "password"),
    # Timeout settings
    request_timeout=30.0,
    # Retry configuration
    max_retries=3,
    retry_on_timeout=True,
    retry_on_status=[502, 503, 504],
    # Connection pooling
    connections_per_node=10,
)
```

## Automatic Configuration

All examples support automatic configuration from multiple sources:

1. **Environment variables**:
   ```bash
   export KIBANA_URL="http://localhost:5601"
   export KIBANA_API_KEY="your_api_key"
   # or
   export KIBANA_USERNAME="elastic"
   export KIBANA_PASSWORD="your_password"
   ```

2. **Local development setup**: If using `elastic-start-local/`, credentials are automatically read from `elastic-start-local/.env`

3. **Defaults**: Falls back to `http://localhost:5601` with no authentication

## Running the Example

```bash
# With automatic configuration
python examples/basic_usage.py

# With environment variables
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="changeme"
python examples/basic_usage.py
```

## What the Example Demonstrates

1. **Basic Initialization**: Different ways to create a Kibana client
2. **Context Manager**: Automatic resource cleanup
3. **Response Handling**: Correct way to access API response data
4. **Per-Request Options**: Customizing individual requests
5. **Connection Configuration**: Advanced settings for production use
6. **Multiple Hosts**: High availability configuration

## Next Steps

After understanding basic usage, explore:

- [Authentication Guide](../user-guide/authentication.md) - Detailed authentication patterns
- [Connector Examples](connectors/index.md) - Working with Kibana connectors
- [Error Handling](../user-guide/error-handling.md) - Exception handling patterns

## Common Patterns

### Pattern 1: Quick Script

For quick scripts or testing:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601")
try:
    # Do something
    response = client.status.get_status()
    print(response.body["status"]["overall"]["level"])
finally:
    client.close()
```

### Pattern 2: Production Application

For production applications:

```python
from kibana import Kibana

with Kibana(
    "http://localhost:5601",
    api_key="your_api_key",
    request_timeout=30.0,
    max_retries=3
) as client:
    # Application logic
    pass
```

### Pattern 3: Configuration from Environment

For flexible deployment:

```python
import os
from kibana import Kibana

kibana_url = os.getenv("KIBANA_URL", "http://localhost:5601")
api_key = os.getenv("KIBANA_API_KEY")

with Kibana(kibana_url, api_key=api_key) as client:
    # Application logic
    pass
```

## Best Practices

1. **Always use context managers** for automatic cleanup
2. **Access `.body` attribute** for response data
3. **Configure timeouts** appropriate for your use case
4. **Use environment variables** for credentials
5. **Enable retries** for production applications
6. **Handle exceptions** appropriately (see error handling guide)

## Troubleshooting

### Connection Refused

**Problem**: `ConnectionError: Connection refused`

**Solution**: Ensure Kibana is running and accessible at the specified URL

### Authentication Failed

**Problem**: `AuthenticationException: Authentication failed`

**Solution**: Verify your credentials are correct and have the necessary permissions

### Timeout Errors

**Problem**: `ConnectionTimeout: Request timed out`

**Solution**: Increase the timeout or check network connectivity:
```python
client = Kibana("http://localhost:5601", request_timeout=60.0)
```

## Related Documentation

- [Installation Guide](../installation.md)
- [Quick Start](../quickstart.md)
- [Authentication](../user-guide/authentication.md)
- [Error Handling](../user-guide/error-handling.md)
- [API Reference](../api-reference/index.rst)
