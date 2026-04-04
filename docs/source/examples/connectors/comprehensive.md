# Comprehensive Index Connector Example

**File**: `examples/connector_management.py`

This example demonstrates production-ready patterns for managing index connectors with comprehensive error handling, logging, and best practices.

## Purpose

Perfect for:
- Building production applications
- Understanding advanced patterns
- Implementing robust error handling
- Managing connector lifecycle

## What You'll Learn

- Class-based connector management
- Comprehensive error handling
- Update and delete operations
- Batch document writing
- Logging and observability integration
- Production-ready patterns

## Code Overview

The example uses a class-based approach for better organization:

### IndexConnectorExample Class

```python
class IndexConnectorExample:
    """Example class for managing index connectors."""

    def __init__(self):
        """Initialize with automatic Kibana client configuration."""
        self.index_name = "miconnectedindex"
        self.connector_name = f"Index Connector - {self.index_name}"
        self.connector_id = None
        self.client = create_kibana_client()
```

**Benefits of Class-Based Approach**:
- Encapsulates connector state
- Reusable methods
- Easier testing
- Better organization

## Key Features

### 1. Robust Connector Creation

```python
def create_index_connector(self) -> dict[str, Any]:
    """Create an index connector with error handling."""
    try:
        config = {
            "index": self.index_name,
            "refresh": True,
            "executionTimeField": "@timestamp",
        }

        response = self.client.actions.create(
            name=self.connector_name,
            connector_type_id=".index",
            config=config,
        )

        connector = response.body
        self.connector_id = connector["id"]
        logger.info(f"Created connector: {self.connector_id}")
        return connector

    except ConflictError:
        logger.warning(f"Connector '{self.connector_name}' already exists")
        return self._find_existing_connector()
    except BadRequestError as e:
        logger.error(f"Invalid configuration: {e}")
        raise
    except KibanaException as e:
        logger.error(f"Failed to create connector: {e}")
        raise
```

**Key Features**:
- Handles `ConflictError` by finding existing connector
- Logs all operations
- Provides detailed error messages
- Returns connector data for further use

### 2. Document Execution

```python
def execute_connector(self, document: dict[str, Any]) -> dict[str, Any]:
    """Execute connector to write a document."""
    if not self.connector_id:
        raise ValueError("Connector not created")

    # Add timestamp if not present
    if "@timestamp" not in document:
        document["@timestamp"] = datetime.utcnow().isoformat()

    params = {"documents": [document]}

    try:
        response = self.client.actions.execute(
            id=self.connector_id,
            params=params
        )
        result = response.body
        logger.info("Document written successfully")
        return result

    except BadRequestError as e:
        logger.error(f"Invalid parameters: {e}")
        raise
    except KibanaException as e:
        logger.error(f"Execution failed: {e}")
        raise
```

**Key Features**:
- Validates connector exists
- Automatically adds timestamp
- Comprehensive error handling
- Logs execution results

### 3. Batch Document Writing

```python
def write_sample_data(self) -> None:
    """Write multiple sample documents."""
    sample_documents = [
        {
            "message": "Application started",
            "level": "INFO",
            "service": "web-server",
        },
        {
            "message": "Database connected",
            "level": "INFO",
            "service": "database",
        },
        {
            "message": "High memory usage",
            "level": "WARNING",
            "service": "monitoring",
        },
        {
            "message": "Authentication failed",
            "level": "ERROR",
            "service": "auth-service",
        },
    ]

    for i, doc in enumerate(sample_documents, 1):
        try:
            self.execute_connector(doc)
            logger.info(f"Document {i}/{len(sample_documents)} written")
        except Exception as e:
            logger.error(f"Failed to write document {i}: {e}")
```

**Key Features**:
- Writes multiple documents
- Continues on individual failures
- Tracks progress
- Logs each operation

### 4. Connector Updates

```python
def update_connector(self, new_config: dict[str, Any]) -> dict[str, Any]:
    """Update connector configuration."""
    if not self.connector_id:
        raise ValueError("Connector not created")

    try:
        response = self.client.actions.update(
            id=self.connector_id,
            name=self.connector_name,
            config=new_config
        )
        result = response.body
        logger.info("Connector updated successfully")
        return result
    except KibanaException as e:
        logger.error(f"Update failed: {e}")
        raise
```

**Key Features**:
- Updates connector configuration
- Validates connector exists
- Error handling
- Logging

### 5. Connector Deletion

```python
def delete_connector(self) -> None:
    """Delete the connector."""
    if not self.connector_id:
        raise ValueError("Connector not created")

    try:
        self.client.actions.delete(id=self.connector_id)
        logger.info("Connector deleted")
        self.connector_id = None
    except NotFoundError:
        logger.warning("Connector not found (may already be deleted)")
        self.connector_id = None
    except KibanaException as e:
        logger.error(f"Deletion failed: {e}")
        raise
```

**Key Features**:
- Handles already-deleted connectors
- Clears connector ID on success
- Comprehensive error handling

## Production Patterns

### Pattern 1: Singleton Connector

Reuse a single connector across your application:

```python
class ConnectorManager:
    _instance = None
    _connector_id = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_connector_id(self):
        if not self._connector_id:
            self._connector_id = self._create_connector()
        return self._connector_id
```

### Pattern 2: Connection Pooling

Reuse the Kibana client:

```python
class ConnectorPool:
    def __init__(self, max_connections=10):
        self.client = Kibana(
            "http://localhost:5601",
            connections_per_node=max_connections
        )

    def write_document(self, connector_id, document):
        return self.client.actions.execute(
            id=connector_id,
            params={"documents": [document]}
        )
```

### Pattern 3: Retry Logic

Handle transient failures:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientConnector:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def execute_with_retry(self, connector_id, document):
        return self.client.actions.execute(
            id=connector_id,
            params={"documents": [document]}
        )
```

### Pattern 4: Async Batch Writing

Write documents asynchronously:

```python
import asyncio
from kibana import AsyncKibana

class AsyncConnectorWriter:
    async def write_batch(self, connector_id, documents):
        async with AsyncKibana("http://localhost:5601") as client:
            tasks = [
                client.actions.execute(
                    id=connector_id,
                    params={"documents": [doc]}
                )
                for doc in documents
            ]
            return await asyncio.gather(*tasks)
```

## Error Handling Strategies

### Strategy 1: Graceful Degradation

Continue operation even if some writes fail:

```python
def write_documents_gracefully(self, documents):
    """Write documents with graceful degradation."""
    successful = 0
    failed = 0

    for doc in documents:
        try:
            self.execute_connector(doc)
            successful += 1
        except Exception as e:
            logger.error(f"Failed to write document: {e}")
            failed += 1

    logger.info(f"Wrote {successful} documents, {failed} failed")
    return successful, failed
```

### Strategy 2: Circuit Breaker

Stop trying after repeated failures:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.is_open = False

    def call(self, func, *args, **kwargs):
        if self.is_open:
            raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
            raise
```

### Strategy 3: Dead Letter Queue

Store failed writes for later retry:

```python
class DeadLetterQueue:
    def __init__(self):
        self.failed_documents = []

    def write_with_dlq(self, connector_id, document):
        try:
            return self.client.actions.execute(
                id=connector_id,
                params={"documents": [document]}
            )
        except Exception as e:
            logger.error(f"Write failed, adding to DLQ: {e}")
            self.failed_documents.append({
                "document": document,
                "error": str(e),
                "timestamp": datetime.utcnow()
            })

    def retry_failed(self, connector_id):
        """Retry all failed documents."""
        for item in self.failed_documents[:]:
            try:
                self.client.actions.execute(
                    id=connector_id,
                    params={"documents": [item["document"]]}
                )
                self.failed_documents.remove(item)
            except Exception:
                pass
```

## Logging and Observability

### Structured Logging

```python
import logging

logger = logging.getLogger(__name__)

# Log with structured data
logger.info(
    "Connector created",
    extra={
        "connector_id": connector_id,
        "connector_type": ".index",
        "target_index": "my-index",
        "operation": "create"
    }
)
```

### OpenTelemetry Integration

```python
from kibana import configure_opentelemetry

# Enable tracing
configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:4317"
)

# All connector operations are now traced
connector = client.actions.create(...)
```

### Metrics Collection

```python
from prometheus_client import Counter, Histogram

documents_written = Counter(
    'connector_documents_written_total',
    'Total documents written via connector'
)

write_duration = Histogram(
    'connector_write_duration_seconds',
    'Time spent writing documents'
)

@write_duration.time()
def write_document(self, document):
    result = self.execute_connector(document)
    documents_written.inc()
    return result
```

## Running the Example

```bash
# Basic usage
python examples/connector_management.py

# With custom configuration
export KIBANA_URL="http://localhost:5601"
export KIBANA_API_KEY="your_api_key"
python examples/connector_management.py

# With debug logging
export LOG_LEVEL=DEBUG
python examples/connector_management.py
```

## Expected Output

```
📊 Kibana Configuration:
   URL: http://localhost:5601
   Auth: Basic authentication

=== Kibana Index Connector Example ===

1. Available connector types:
✓ Found 15 connector types
  - .email: Email
  - .index: Index (Enabled: True)
  - .server-log: Server log
  ...

2. Existing connectors:
✓ Found 2 connectors
  - Production Connector (conn-123)
  - Test Connector (conn-456)

3. Creating index connector...
Created connector: Index Connector - miconnectedindex (ID: conn-789)
Target index: miconnectedindex

4. Connector details:
{
  "id": "conn-789",
  "name": "Index Connector - miconnectedindex",
  "connector_type_id": ".index",
  "config": {
    "index": "miconnectedindex",
    "refresh": true,
    "executionTimeField": "@timestamp"
  }
}

5. Writing sample data...
Document 1/4 written successfully
Document 2/4 written successfully
Document 3/4 written successfully
Document 4/4 written successfully

6. Updating connector configuration...
Connector updated successfully

7. Writing document with updated configuration...

=== Example completed successfully! ===
Check your Elasticsearch index 'miconnectedindex' for the written documents.

Connector 'Index Connector - miconnectedindex' was created for this example.
Delete the connector? (y/N):
```

## Best Practices

### 1. Resource Management

Always clean up resources:

```python
try:
    example = IndexConnectorExample()
    example.create_index_connector()
    # Use connector
finally:
    if example.connector_id:
        example.delete_connector()
    example.close()
```

### 2. Configuration Management

Use environment variables:

```python
import os

config = {
    "index": os.getenv("TARGET_INDEX", "default-index"),
    "refresh": os.getenv("REFRESH_INDEX", "true").lower() == "true",
    "executionTimeField": os.getenv("TIMESTAMP_FIELD", "@timestamp")
}
```

### 3. Error Recovery

Implement retry logic for transient failures:

```python
max_retries = 3
for attempt in range(max_retries):
    try:
        result = example.execute_connector(document)
        break
    except Exception as e:
        if attempt == max_retries - 1:
            raise
        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
        time.sleep(2 ** attempt)
```

### 4. Monitoring

Track connector health:

```python
def check_connector_health(self):
    """Verify connector is operational."""
    try:
        connector = self.get_connector_info()
        if connector.get('is_missing_secrets'):
            logger.error("Connector has missing secrets")
            return False
        if connector.get('is_deprecated'):
            logger.warning("Connector type is deprecated")
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
```

## Next Steps

1. **Adapt for your use case**: Modify the class for your specific needs
2. **Add monitoring**: Integrate with your observability stack
3. **Implement retries**: Add resilience for production
4. **Scale horizontally**: Use multiple connectors for high throughput

## Key Takeaways

✅ **Class-based design**: Better organization and reusability

✅ **Comprehensive error handling**: Handle all failure scenarios

✅ **Logging**: Track all operations for debugging

✅ **Production patterns**: Retry logic, circuit breakers, DLQ

✅ **Observability**: Integration with tracing and metrics

## Related Examples

- [Simple Connector](simple.md) - Basic usage
- [Debug Connector](debug.md) - Troubleshooting
- [Async Patterns](../async/patterns.md) - Asynchronous operations

## Related Documentation

- [Actions API Reference](../../api-reference/actions.rst)
- [Connectors User Guide](../../user-guide/connectors.md)
- [Error Handling](../../user-guide/error-handling.md)
- [Observability](../../user-guide/observability.md)
