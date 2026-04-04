# Advanced Usage

This guide covers advanced features and patterns for using the Kibana Python client effectively in production environments.

## Per-Request Configuration

The `options()` method allows you to modify client settings for specific requests without creating a new client instance. This is useful for one-off configuration changes or when different operations require different settings.

### Request Timeout

Override the default timeout for specific requests:

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    api_key="your_api_key",
    request_timeout=10.0  # Default 10 seconds
)

# Use longer timeout for potentially slow operation
result = client.options(request_timeout=60.0).actions.get_all()

# Use shorter timeout for quick health check
status = client.options(request_timeout=5.0).status.get_status()
```

### Custom Headers

Add custom headers for specific requests:

```python
# Add custom headers for request tracking
result = client.options(
    headers={
        "X-Request-ID": "unique-request-id",
        "X-Custom-Header": "custom-value"
    }
).actions.get_all()

# Add headers for debugging
result = client.options(
    headers={"X-Debug": "true"}
).spaces.get_all()
```

### Per-Request Authentication

Override authentication for specific requests:

```python
# Initialize with default authentication
client = Kibana(
    "http://localhost:5601",
    api_key="default_api_key"
)

# Use different API key for specific request
result = client.options(
    api_key="admin_api_key"
).actions.create(
    name="Admin Connector",
    connector_type_id=".index",
    config={"index": "admin-logs"}
)

# Use basic auth for specific request
result = client.options(
    basic_auth=("admin", "admin_password")
).spaces.create(
    id="admin-space",
    name="Admin Space"
)
```

### Chaining Options

Options can be chained for complex configurations:

```python
# Combine multiple options
result = client.options(
    request_timeout=30.0,
    headers={"X-Request-ID": "123"}
).options(
    api_key="different_key"
).actions.get_all()
```

:::{note}
Each call to `options()` creates a new client instance with the modified settings. The original client remains unchanged.
:::

## Connection Pooling

The Kibana client uses elastic-transport for connection management, which provides built-in connection pooling.

### Connection Pool Configuration

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    api_key="your_api_key",

    # Connection pool settings
    connections_per_node=10,  # Max connections per node (default: 10)
    max_retries=3,            # Max retry attempts (default: 3)
    retry_on_timeout=True,    # Retry on timeout (default: True)
)
```

### Multiple Hosts

Configure multiple Kibana hosts for high availability:

```python
client = Kibana(
    hosts=[
        "http://kibana1.example.com:5601",
        "http://kibana2.example.com:5601",
        "http://kibana3.example.com:5601"
    ],
    api_key="your_api_key"
)
```

The client will automatically distribute requests across available hosts and handle failover.

### Connection Lifecycle

```python
from kibana import Kibana

# Create client (connections are lazy-initialized)
client = Kibana("http://localhost:5601", api_key="your_api_key")

# Make requests (connections are created as needed)
status = client.status.get_status()

# Close client when done (releases connections)
client.close()
```

### Using Context Managers

Context managers automatically handle connection lifecycle:

```python
# Synchronous client
with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    status = client.status.get_status()
    # Client is automatically closed when exiting the context

# Asynchronous client
async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
    status = await client.status.get_status()
    # Client is automatically closed when exiting the context
```

## Retry Configuration

Configure retry behavior for failed requests:

### Basic Retry Configuration

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    api_key="your_api_key",

    # Retry settings
    max_retries=3,                    # Number of retry attempts
    retry_on_timeout=True,            # Retry on timeout errors
    retry_on_status=[502, 503, 504],  # Retry on these HTTP status codes
)
```

### Custom Retry Logic

For more complex retry scenarios, implement custom retry logic:

```python
import time
from kibana import Kibana
from kibana.exceptions import ApiError

def execute_with_retry(client, operation, max_attempts=3, backoff_factor=2):
    """Execute operation with exponential backoff retry."""
    for attempt in range(max_attempts):
        try:
            return operation()
        except ApiError as e:
            if attempt == max_attempts - 1:
                raise

            # Calculate backoff time
            wait_time = backoff_factor ** attempt
            print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            time.sleep(wait_time)

# Usage
client = Kibana("http://localhost:5601", api_key="your_api_key")

result = execute_with_retry(
    client,
    lambda: client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "logs"}
    )
)
```

## TLS/SSL Configuration

Configure TLS/SSL settings for secure connections:

### Basic TLS

```python
from kibana import Kibana

client = Kibana(
    "https://kibana.example.com:5601",
    api_key="your_api_key",
    verify_certs=True  # Verify SSL certificates (default: True)
)
```

### Custom CA Certificate

Provide a custom CA certificate bundle:

```python
client = Kibana(
    "https://kibana.example.com:5601",
    api_key="your_api_key",
    ca_certs="/path/to/ca-bundle.crt"  # Path to CA certificate
)
```

### Client Certificates

Use client certificates for mutual TLS authentication:

```python
client = Kibana(
    "https://kibana.example.com:5601",
    api_key="your_api_key",
    client_cert="/path/to/client.crt",  # Client certificate
    client_key="/path/to/client.key"    # Client private key
)
```

### Disable Certificate Verification

:::{warning}
Only disable certificate verification for local development or testing. Never use this in production.
:::

```python
client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    verify_certs=False  # Disable certificate verification
)
```

### SSL Context

For advanced SSL configuration, provide a custom SSL context:

```python
import ssl
from kibana import Kibana

# Create custom SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    ssl_context=ssl_context
)
```

## Async Client Patterns

The async client provides the same API as the synchronous client but with async/await support.

### Basic Async Usage

```python
import asyncio
from kibana import AsyncKibana

async def main():
    client = AsyncKibana(
        "http://localhost:5601",
        api_key="your_api_key"
    )

    try:
        # All methods are async
        status = await client.status.get_status()
        print(status.body)
    finally:
        await client.close()

asyncio.run(main())
```

### Async Context Manager

```python
async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        status = await client.status.get_status()
        connectors = await client.actions.get_all()
        # Client is automatically closed
```

### Concurrent Operations

Execute multiple operations concurrently:

```python
import asyncio
from kibana import AsyncKibana

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        # Execute multiple operations concurrently
        status, spaces, connectors = await asyncio.gather(
            client.status.get_status(),
            client.spaces.get_all(),
            client.actions.get_all()
        )

        print(f"Status: {status.body['status']['overall']['level']}")
        print(f"Spaces: {len(spaces.body)}")
        print(f"Connectors: {len(connectors.body)}")

asyncio.run(main())
```

### Concurrent Requests with Error Handling

```python
async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        # Execute with error handling
        results = await asyncio.gather(
            client.status.get_status(),
            client.spaces.get_all(),
            client.actions.get_all(),
            return_exceptions=True  # Don't fail on first exception
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Operation {i} failed: {result}")
            else:
                print(f"Operation {i} succeeded")
```

### Async Batch Processing

Process items in batches asynchronously:

```python
async def process_connectors_batch(client, connector_ids):
    """Process a batch of connectors concurrently."""
    tasks = [
        client.actions.get(id=connector_id)
        for connector_id in connector_ids
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        # Get all connector IDs
        all_connectors = await client.actions.get_all()
        connector_ids = [c["id"] for c in all_connectors.body]

        # Process in batches of 10
        batch_size = 10
        for i in range(0, len(connector_ids), batch_size):
            batch = connector_ids[i:i + batch_size]
            results = await process_connectors_batch(client, batch)
            print(f"Processed batch {i//batch_size + 1}: {len(results)} connectors")
```

### Async Rate Limiting

Implement rate limiting for async operations:

```python
import asyncio
from asyncio import Semaphore

async def rate_limited_operation(client, semaphore, connector_id):
    """Execute operation with rate limiting."""
    async with semaphore:
        return await client.actions.get(id=connector_id)

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        # Limit to 5 concurrent requests
        semaphore = Semaphore(5)

        all_connectors = await client.actions.get_all()
        connector_ids = [c["id"] for c in all_connectors.body]

        # Execute with rate limiting
        tasks = [
            rate_limited_operation(client, semaphore, connector_id)
            for connector_id in connector_ids
        ]
        results = await asyncio.gather(*tasks)
        print(f"Processed {len(results)} connectors with rate limiting")
```

## Performance Optimization

### Connection Reuse

Reuse client instances to benefit from connection pooling:

```python
# Good: Reuse client
client = Kibana("http://localhost:5601", api_key="your_api_key")

for i in range(100):
    result = client.actions.get_all()
    # Process result

client.close()

# Avoid: Creating new client for each request
for i in range(100):
    client = Kibana("http://localhost:5601", api_key="your_api_key")
    result = client.actions.get_all()
    client.close()  # Inefficient!
```

### Batch Operations

Use bulk operations when available:

```python
# Good: Bulk create
objects = [
    {"type": "config", "attributes": {"title": f"Config {i}"}}
    for i in range(100)
]
result = client.saved_objects.bulk_create(objects)

# Avoid: Individual creates
for i in range(100):
    client.saved_objects.create(
        type="config",
        attributes={"title": f"Config {i}"}
    )
```

### Disable Space Validation

For performance-critical scenarios, disable automatic space validation:

```python
# Create space-scoped client without validation
fast_client = client.space("marketing", validate=False)

# Validation is skipped for all operations
connector = fast_client.actions.create(
    name="Fast Connector",
    connector_type_id=".index",
    config={"index": "logs"}
)
```

:::{warning}
Only disable validation when you're certain the space exists. Invalid space IDs will result in API errors.
:::

### Caching

Implement caching for frequently accessed data:

```python
from functools import lru_cache
from kibana import Kibana

class CachedKibanaClient:
    def __init__(self, client):
        self.client = client

    @lru_cache(maxsize=128)
    def get_connector(self, connector_id):
        """Get connector with caching."""
        response = self.client.actions.get(id=connector_id)
        return response.body

    @lru_cache(maxsize=32)
    def get_space(self, space_id):
        """Get space with caching."""
        response = self.client.spaces.get(id=space_id)
        return response.body

# Usage
client = Kibana("http://localhost:5601", api_key="your_api_key")
cached_client = CachedKibanaClient(client)

# First call hits API
connector = cached_client.get_connector("connector-id")

# Second call uses cache
connector = cached_client.get_connector("connector-id")  # Fast!
```

### Async for I/O-Bound Operations

Use async client for I/O-bound operations:

```python
import asyncio
from kibana import AsyncKibana

async def fetch_all_data(client):
    """Fetch multiple resources concurrently."""
    return await asyncio.gather(
        client.status.get_status(),
        client.spaces.get_all(),
        client.actions.get_all(),
        client.saved_objects.find(type="dashboard")
    )

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        # Much faster than sequential requests
        status, spaces, connectors, dashboards = await fetch_all_data(client)
```

### Request Timeout Tuning

Tune timeouts based on operation type:

```python
client = Kibana("http://localhost:5601", api_key="your_api_key")

# Fast operations: short timeout
status = client.options(request_timeout=5.0).status.get_status()

# Bulk operations: longer timeout
result = client.options(request_timeout=60.0).saved_objects.bulk_create(objects)

# Export operations: very long timeout
export = client.options(request_timeout=300.0).saved_objects.export(
    type=["dashboard", "visualization"]
)
```

## Logging and Debugging

### Enable Debug Logging

```python
import logging
from kibana import Kibana

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# The client uses the "kibana" logger
logger = logging.getLogger("kibana")
logger.setLevel(logging.DEBUG)

client = Kibana("http://localhost:5601", api_key="your_api_key")

# All requests will be logged with details
status = client.status.get_status()
```

### Custom Logging Handler

```python
import logging
from kibana import Kibana

class RequestLogger(logging.Handler):
    """Custom handler to log requests to a file."""

    def __init__(self, filename):
        super().__init__()
        self.file = open(filename, 'a')

    def emit(self, record):
        self.file.write(f"{record.getMessage()}\n")
        self.file.flush()

# Add custom handler
logger = logging.getLogger("kibana")
logger.addHandler(RequestLogger("kibana_requests.log"))
logger.setLevel(logging.DEBUG)

client = Kibana("http://localhost:5601", api_key="your_api_key")
```

### Request/Response Inspection

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Make request
response = client.actions.get_all()

# Inspect response metadata
print(f"Status: {response.meta.status}")
print(f"Headers: {response.meta.headers}")
print(f"Duration: {response.meta.duration}")

# Inspect response body
print(f"Body: {response.body}")
```

## Error Handling Patterns

### Retry with Exponential Backoff

```python
import time
from kibana import Kibana
from kibana.exceptions import ApiError, ServerError

def retry_with_backoff(func, max_attempts=3, base_delay=1):
    """Retry function with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return func()
        except ServerError as e:
            if attempt == max_attempts - 1:
                raise

            delay = base_delay * (2 ** attempt)
            print(f"Server error, retrying in {delay}s...")
            time.sleep(delay)

client = Kibana("http://localhost:5601", api_key="your_api_key")

result = retry_with_backoff(
    lambda: client.actions.get_all()
)
```

### Graceful Degradation

```python
from kibana import Kibana
from kibana.exceptions import ApiError

client = Kibana("http://localhost:5601", api_key="your_api_key")

try:
    # Try to get connectors
    connectors = client.actions.get_all()
    print(f"Found {len(connectors.body)} connectors")
except ApiError as e:
    # Fall back to empty list
    print(f"Failed to fetch connectors: {e.message}")
    connectors = []
```

### Circuit Breaker Pattern

```python
import time
from kibana import Kibana
from kibana.exceptions import ApiError

class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func()
            self.on_success()
            return result
        except ApiError as e:
            self.on_failure()
            raise

    def on_success(self):
        self.failures = 0
        self.state = "closed"

    def on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"

# Usage
client = Kibana("http://localhost:5601", api_key="your_api_key")
breaker = CircuitBreaker()

try:
    result = breaker.call(lambda: client.actions.get_all())
except Exception as e:
    print(f"Request failed: {e}")
```

## Best Practices

### 1. Use Context Managers

Always use context managers to ensure proper cleanup:

```python
# Good
with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    result = client.actions.get_all()

# Avoid
client = Kibana("http://localhost:5601", api_key="your_api_key")
result = client.actions.get_all()
# Forgot to call client.close()!
```

### 2. Reuse Client Instances

Create one client instance and reuse it:

```python
# Good
client = Kibana("http://localhost:5601", api_key="your_api_key")
for i in range(100):
    result = client.actions.get_all()
client.close()

# Avoid
for i in range(100):
    client = Kibana("http://localhost:5601", api_key="your_api_key")
    result = client.actions.get_all()
    client.close()
```

### 3. Use Async for Concurrent Operations

Use async client when you need to perform multiple operations:

```python
# Good: Concurrent async operations
async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
    results = await asyncio.gather(
        client.actions.get_all(),
        client.spaces.get_all(),
        client.status.get_status()
    )

# Avoid: Sequential sync operations
with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    actions = client.actions.get_all()
    spaces = client.spaces.get_all()
    status = client.status.get_status()
```

### 4. Handle Errors Appropriately

Catch specific exceptions and handle them appropriately:

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError, AuthenticationException

with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    try:
        connector = client.actions.get(id="connector-id")
    except NotFoundError:
        # Handle missing connector
        connector = client.actions.create(
            name="New Connector",
            connector_type_id=".index",
            config={"index": "logs"}
        )
    except AuthenticationException:
        # Handle auth failure
        print("Authentication failed, check credentials")
        raise
```

### 5. Configure Appropriate Timeouts

Set timeouts based on operation type:

```python
client = Kibana(
    "http://localhost:5601",
    api_key="your_api_key",
    request_timeout=30.0  # Default timeout
)

# Short timeout for health checks
status = client.options(request_timeout=5.0).status.get_status()

# Long timeout for bulk operations
result = client.options(request_timeout=120.0).saved_objects.bulk_create(objects)
```

## Next Steps

- Learn about [Observability](observability.md) for distributed tracing
- Explore [Error Handling](error-handling.md) for comprehensive error management
- Check [Examples](../examples/index.md) for practical code samples
- Review [API Reference](../api-reference/index.rst) for detailed API documentation
