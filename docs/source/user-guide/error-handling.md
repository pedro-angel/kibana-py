# Error Handling

The Kibana Python client provides a comprehensive exception hierarchy for handling errors gracefully. Understanding and properly handling these exceptions is crucial for building robust applications.

## Exception Hierarchy

```
KibanaException (base)
├── ApiError (API returned error)
│   ├── BadRequestError (400)
│   ├── AuthenticationException (401)
│   ├── AuthorizationException (403)
│   ├── NotFoundError (404)
│   └── ConflictError (409)
├── SpaceError (space-related error)
│   ├── SpaceNotFoundError (space doesn't exist)
│   └── InvalidSpaceIdError (invalid space ID format)
├── TransportError (transport-level error)
│   ├── ConnectionError (connection failed)
│   ├── ConnectionTimeout (connection timeout)
│   └── SSLError (SSL/TLS error)
└── SerializationError (serialization failed)
```

## Common Exceptions

### NotFoundError

Raised when a requested resource doesn't exist.

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError

client = Kibana("http://localhost:5601", api_key="your_api_key")

try:
    connector = client.actions.get(id="nonexistent-id")
except NotFoundError as e:
    print(f"Connector not found: {e.message}")
    print(f"Status code: {e.status_code}")
    print(f"Response body: {e.body}")
```

### AuthenticationException

Raised when authentication fails.

```python
from kibana.exceptions import AuthenticationException

try:
    client = Kibana(
        "http://localhost:5601",
        api_key="invalid_key"
    )
    status = client.status.get_status()
except AuthenticationException as e:
    print(f"Authentication failed: {e.message}")
    # Handle invalid credentials
```

### AuthorizationException

Raised when the user lacks required permissions.

```python
from kibana.exceptions import AuthorizationException

try:
    spaces = client.spaces.get_all()
except AuthorizationException as e:
    print(f"Permission denied: {e.message}")
    # Handle insufficient permissions
```

### BadRequestError

Raised when the request is malformed or invalid.

```python
from kibana.exceptions import BadRequestError

try:
    connector = client.actions.create(
        name="Test",
        connector_type_id=".invalid-type",  # Invalid type
        config={}
    )
except BadRequestError as e:
    print(f"Invalid request: {e.message}")
    print(f"Details: {e.body}")
```

### ConflictError

Raised when there's a conflict (e.g., duplicate resource, version mismatch).

```python
from kibana.exceptions import ConflictError

try:
    # Update with wrong version
    client.saved_objects.update(
        type="dashboard",
        id="dash-1",
        attributes={"title": "New Title"},
        version="wrong-version"
    )
except ConflictError as e:
    print(f"Version conflict: {e.message}")
    # Fetch latest version and retry
```

### SpaceNotFoundError

Raised when a specified space doesn't exist.

```python
from kibana.exceptions import SpaceNotFoundError

try:
    connector = client.actions.create(
        name="Test",
        connector_type_id=".index",
        config={"index": "test"},
        space_id="nonexistent-space"
    )
except SpaceNotFoundError as e:
    print(f"Space not found: {e.space_id}")
    # Create the space or use a different one
```

### ConnectionError

Raised when connection to Kibana fails.

```python
from kibana.exceptions import ConnectionError

try:
    client = Kibana("http://invalid-host:5601")
    status = client.status.get_status()
except ConnectionError as e:
    print(f"Connection failed: {e.message}")
    # Handle connection failure
```

## Error Handling Patterns

### Basic Try-Except

```python
from kibana import Kibana
from kibana.exceptions import KibanaException

client = Kibana("http://localhost:5601", api_key="your_api_key")

try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
    print(f"Created: {connector.body['id']}")

except KibanaException as e:
    print(f"Error: {e.message}")
    print(f"Status: {e.status_code if hasattr(e, 'status_code') else 'N/A'}")
finally:
    client.close()
```

### Specific Exception Handling

```python
from kibana.exceptions import (
    NotFoundError,
    ConflictError,
    BadRequestError,
    AuthenticationException,
    SpaceNotFoundError
)

try:
    connector = client.actions.create(
        name="Test Connector",
        connector_type_id=".index",
        config={"index": "test"},
        space_id="marketing"
    )

except SpaceNotFoundError as e:
    print(f"Space '{e.space_id}' does not exist")
    # Create the space
    client.spaces.create(id=e.space_id, name="Marketing")
    # Retry operation

except ConflictError as e:
    print(f"Connector already exists: {e.message}")
    # Get existing connector

except BadRequestError as e:
    print(f"Invalid configuration: {e.message}")
    # Fix configuration and retry

except AuthenticationException as e:
    print(f"Authentication failed: {e.message}")
    # Refresh credentials

except NotFoundError as e:
    print(f"Resource not found: {e.message}")
    # Handle missing resource
```

### Retry Pattern

```python
import time
from kibana.exceptions import ApiError, ConnectionError

def create_connector_with_retry(client, max_retries=3):
    """Create connector with retry logic."""
    for attempt in range(max_retries):
        try:
            connector = client.actions.create(
                name="My Connector",
                connector_type_id=".index",
                config={"index": "my-index"}
            )
            return connector

        except ConnectionError as e:
            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Connection failed, retrying in {wait_time}s...")
            time.sleep(wait_time)

        except ApiError as e:
            if e.status_code >= 500:  # Server error
                if attempt == max_retries - 1:
                    raise

                wait_time = 2 ** attempt
                print(f"Server error, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # Client error, don't retry
                raise

# Usage
try:
    connector = create_connector_with_retry(client)
    print(f"Created: {connector.body['id']}")
except Exception as e:
    print(f"Failed after retries: {e}")
```

### Fallback Pattern

```python
def get_connector_with_fallback(client, connector_id, space_id=None):
    """Get connector with fallback to default space."""
    try:
        # Try to get from specified space
        return client.actions.get(id=connector_id, space_id=space_id)

    except SpaceNotFoundError:
        print(f"Space '{space_id}' not found, trying default space")
        # Fallback to default space
        return client.actions.get(id=connector_id)

    except NotFoundError:
        print(f"Connector '{connector_id}' not found in any space")
        return None
```

### Context Manager Pattern

```python
from contextlib import contextmanager

@contextmanager
def kibana_operation(client, operation_name):
    """Context manager for Kibana operations with error handling."""
    try:
        print(f"Starting {operation_name}...")
        yield
        print(f"Completed {operation_name}")

    except NotFoundError as e:
        print(f"{operation_name} failed: Resource not found - {e.message}")
        raise

    except ConflictError as e:
        print(f"{operation_name} failed: Conflict - {e.message}")
        raise

    except ApiError as e:
        print(f"{operation_name} failed: API error - {e.message}")
        raise

    except Exception as e:
        print(f"{operation_name} failed: Unexpected error - {e}")
        raise

# Usage
with kibana_operation(client, "Create connector"):
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
```

## Error Recovery Strategies

### Automatic Retry with Exponential Backoff

```python
import time
from functools import wraps

def retry_on_error(max_retries=3, backoff_factor=2):
    """Decorator for automatic retry with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, ApiError) as e:
                    if attempt == max_retries - 1:
                        raise

                    if isinstance(e, ApiError) and e.status_code < 500:
                        # Don't retry client errors
                        raise

                    wait_time = backoff_factor ** attempt
                    print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)

        return wrapper
    return decorator

# Usage
@retry_on_error(max_retries=3)
def create_connector(client):
    return client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
```

### Circuit Breaker Pattern

```python
import time

class CircuitBreaker:
    """Circuit breaker for Kibana operations."""

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker."""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result

        except Exception as e:
            self.on_failure()
            raise

    def on_success(self):
        """Handle successful call."""
        self.failures = 0
        self.state = 'closed'

    def on_failure(self):
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = 'open'

# Usage
breaker = CircuitBreaker(failure_threshold=5, timeout=60)

try:
    connector = breaker.call(
        client.actions.create,
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
except Exception as e:
    print(f"Circuit breaker prevented call or operation failed: {e}")
```

## Logging Errors

### Basic Error Logging

```python
import logging

logger = logging.getLogger(__name__)

try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
except KibanaException as e:
    logger.error(
        "Failed to create connector",
        extra={
            'error_type': type(e).__name__,
            'error_message': str(e),
            'status_code': getattr(e, 'status_code', None),
            'connector_name': "My Connector"
        }
    )
    raise
```

### Structured Error Logging

```python
import logging
import traceback

logger = logging.getLogger(__name__)

def log_error(operation, error, context=None):
    """Log error with structured information."""
    error_info = {
        'operation': operation,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }

    if hasattr(error, 'status_code'):
        error_info['status_code'] = error.status_code

    if hasattr(error, 'body'):
        error_info['response_body'] = error.body

    if context:
        error_info.update(context)

    logger.error(f"Operation failed: {operation}", extra=error_info)

# Usage
try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"},
        space_id="marketing"
    )
except KibanaException as e:
    log_error(
        "create_connector",
        e,
        context={
            'connector_name': "My Connector",
            'connector_type': ".index",
            'space_id': "marketing"
        }
    )
    raise
```

## Best Practices

### 1. Always Use Specific Exceptions

```python
# Good: Specific exception handling
try:
    connector = client.actions.get(id="conn-1")
except NotFoundError:
    # Handle not found
    pass
except AuthorizationException:
    # Handle permission denied
    pass

# Avoid: Catching all exceptions
try:
    connector = client.actions.get(id="conn-1")
except Exception:
    # Too broad
    pass
```

### 2. Provide Context in Error Messages

```python
# Good: Contextual error handling
try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"},
        space_id="marketing"
    )
except SpaceNotFoundError as e:
    print(f"Cannot create connector in space '{e.space_id}': space does not exist")
except ConflictError as e:
    print(f"Connector 'My Connector' already exists in space 'marketing'")
```

### 3. Clean Up Resources

```python
# Good: Always clean up
connector = None
try:
    connector = client.actions.create(
        name="Temp Connector",
        connector_type_id=".index",
        config={"index": "temp"}
    )
    # Use connector
    result = client.actions.execute(
        id=connector.body["id"],
        params={"documents": [{"test": "data"}]}
    )
finally:
    # Clean up even if error occurs
    if connector:
        try:
            client.actions.delete(id=connector.body["id"])
        except Exception:
            pass
```

### 4. Use Context Managers

```python
# Good: Automatic cleanup
with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"}
    )
    # Client is automatically closed
```

## Troubleshooting

### Debugging Errors

Enable debug logging to see detailed error information:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("kibana")
logger.setLevel(logging.DEBUG)

# Now you'll see detailed request/response information
try:
    connector = client.actions.create(
        name="Debug Connector",
        connector_type_id=".index",
        config={"index": "debug"}
    )
except Exception as e:
    # Detailed error information will be logged
    print(f"Error: {e}")
```

### Common Error Scenarios

1. **Authentication Failures**: Check API key/credentials
2. **Permission Denied**: Verify user has required privileges
3. **Resource Not Found**: Verify IDs and space context
4. **Connection Issues**: Check network and Kibana availability
5. **Version Conflicts**: Fetch latest version before updating

## Next Steps

- Learn about [Observability](observability.md) for distributed tracing
- Explore [Advanced Usage](advanced-usage.md) for performance optimization
- Check [Status Monitoring](status-monitoring.md) for health checks
- See [Examples](../examples/index.md) for practical code samples
