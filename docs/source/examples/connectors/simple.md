# Simple Index Connector Example

**File**: `examples/simple_index_connector.py`

This example demonstrates the minimal code needed to create an index connector, write a document, and clean up resources.

## Purpose

Perfect for:
- Learning connector basics
- Quick prototyping
- Understanding the core workflow

## What You'll Learn

- Create an index connector in ~50 lines of code
- Write a document to Elasticsearch
- Handle API responses correctly
- Interactive resource cleanup

## Code Overview

The example follows a simple three-step workflow:

### 1. Create the Connector

```python
connector_response = client.actions.create(
    name="My Connected Index Connector",
    connector_type_id=".index",
    config={
        "index": "miconnectedindex",
        "refresh": True,
        "executionTimeField": "@timestamp",
    },
)

connector = connector_response.body  # Access the body attribute
connector_id = connector["id"]
```

**Key Points**:
- `connector_type_id=".index"` specifies an index connector
- `config` contains connector-specific settings
- Always access `.body` to get the actual data
- Store the `connector_id` for later operations

### 2. Write a Document

```python
document = {
    "message": "Hello from Kibana connector!",
    "level": "INFO",
    "service": "example-app",
    "@timestamp": datetime.now(UTC).isoformat(),
}

result_response = client.actions.execute(
    id=connector_id,
    params={"documents": [document]}
)

result = result_response.body
print(f"Status: {result.get('status', 'unknown')}")
```

**Key Points**:
- Documents can contain any JSON-serializable data
- The `@timestamp` field is automatically added if specified in config
- `params` must include a `documents` array
- Check the execution status in the result

### 3. Clean Up

```python
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

**Key Points**:
- Interactive cleanup prevents connector accumulation
- Handle DELETE API edge cases with verification
- Confirm deletion by attempting to retrieve the connector

## Configuration Options

### Index Connector Config

```python
config = {
    "index": "miconnectedindex",      # Required: Target index name
    "refresh": True,                   # Optional: Refresh after write (default: false)
    "executionTimeField": "@timestamp" # Optional: Field for execution timestamp
}
```

**Configuration Details**:

- **`index`** (required): The Elasticsearch index where documents will be written
- **`refresh`** (optional): If `True`, refreshes the index after writing, making documents immediately searchable (slower but ensures immediate visibility)
- **`executionTimeField`** (optional): Field name where the execution timestamp will be stored

## Document Structure

Documents can contain any fields you need:

```python
# Simple log entry
document = {
    "@timestamp": datetime.now(UTC).isoformat(),
    "message": "Application started",
    "level": "INFO"
}

# Detailed log with context
document = {
    "@timestamp": datetime.now(UTC).isoformat(),
    "message": "User login successful",
    "level": "INFO",
    "user_id": "user123",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "session_id": "sess_abc123"
}

# Metric data
document = {
    "@timestamp": datetime.now(UTC).isoformat(),
    "metric_name": "api_response_time",
    "value": 145.7,
    "unit": "ms",
    "endpoint": "/api/users",
    "method": "GET",
    "status_code": 200
}
```

## Running the Example

### With Automatic Configuration

If you're using `elastic-start-local/`:

```bash
./local-stack.sh -o start

# In another terminal
python examples/simple_index_connector.py
```

### With Environment Variables

```bash
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="changeme"

python examples/simple_index_connector.py
```

### With API Key

```bash
export KIBANA_URL="http://localhost:5601"
export KIBANA_API_KEY="your_api_key_here"

python examples/simple_index_connector.py
```

## Expected Output

```
📊 Kibana Configuration:
   URL: http://localhost:5601
   Auth: Basic authentication
   🔐 Credentials detected from elastic-start-local/.env

Creating index connector...
✓ Created connector: abc123-def456-ghi789

Writing document to index...
✓ Document written successfully
  Status: ok

✓ Connector verified: My Connected Index Connector

🎉 Success! Check your 'miconnectedindex' index in Elasticsearch.
   Connector ID: abc123-def456-ghi789
   Kibana Dev Tools: http://localhost:5601/app/dev_tools#/console
   Try this query: GET miconnectedindex/_search

Connector 'My Connected Index Connector' was created for this example.
Delete the connector? (y/N):
```

## Verifying the Results

### In Kibana Dev Tools

1. Open Kibana Dev Tools: http://localhost:5601/app/dev_tools#/console
2. Run this query:

```console
GET miconnectedindex/_search
{
  "query": {
    "match_all": {}
  }
}
```

### Using curl

```bash
curl -X GET "http://localhost:9200/miconnectedindex/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{"query": {"match_all": {}}}'
```

## Common Issues

### Issue: Connector Already Exists

**Error**: `ConflictError: Connector with this name already exists`

**Solution**: Either delete the existing connector or use a different name:

```python
import uuid
name = f"My Connector {uuid.uuid4().hex[:8]}"
```

### Issue: Index Not Found

**Error**: Documents written but index doesn't appear

**Solution**: The index is created automatically on first write. If using `refresh=False`, wait a moment or manually refresh:

```bash
POST miconnectedindex/_refresh
```

### Issue: Permission Denied

**Error**: `AuthorizationException: Insufficient permissions`

**Solution**: Ensure your user has permissions to:
- Create connectors (`actions:create`)
- Execute connectors (`actions:execute`)
- Write to the target index

## Next Steps

After mastering the simple example:

1. **Debug Example**: Learn to troubleshoot connector issues
   - [View Debug Example →](debug.md)

2. **Comprehensive Example**: Production-ready patterns
   - [View Comprehensive Example →](comprehensive.md)

3. **Space-Scoped Connectors**: Multi-tenancy support
   - [View Space Examples →](../spaces/index.md)

4. **Error Handling**: Robust exception handling
   - [View Error Handling Guide →](../../user-guide/error-handling.md)

## Key Takeaways

✅ **Simple workflow**: Create → Execute → Clean up

✅ **Response handling**: Always access `.body` attribute

✅ **Configuration**: Minimal config gets you started quickly

✅ **Cleanup**: Interactive prompts prevent resource accumulation

✅ **Verification**: Confirm operations succeeded

## Related Examples

- [Debug Connector](debug.md) - Troubleshooting and API inspection
- [Comprehensive Connector](comprehensive.md) - Production patterns
- [Space-Scoped Connector](../spaces/management.md) - Multi-tenancy
- [Async Connector](../async/patterns.md) - Asynchronous operations

## Related Documentation

- [Actions API Reference](../../api-reference/actions.rst)
- [Connectors User Guide](../../user-guide/connectors.md)
- [Error Handling](../../user-guide/error-handling.md)
