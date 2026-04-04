# Async Patterns

**Files**: `examples/async_example.py`, `examples/async_comprehensive.py`

Comprehensive examples demonstrating async patterns with the AsyncKibana client.

## Async Context Manager

```python
import asyncio
from kibana import AsyncKibana

async def main():
    # Automatic cleanup with context manager
    async with AsyncKibana("http://localhost:5601") as client:
        status = await client.status.get_status()
        print(status.body["status"]["overall"]["level"])
    # Client closed automatically

asyncio.run(main())
```

## Concurrent Operations

### Pattern 1: Gather Multiple Operations

```python
async def fetch_all(client):
    # Execute concurrently
    results = await asyncio.gather(
        client.status.get_status(),
        client.spaces.get_all(),
        client.actions.list_types()
    )

    status, spaces, types = results
    return status, spaces, types
```

### Pattern 2: Handle Exceptions

```python
async def fetch_with_error_handling(client):
    results = await asyncio.gather(
        client.status.get_status(),
        client.spaces.get_all(),
        client.actions.list_types(),
        return_exceptions=True  # Don't fail on first error
    )

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Operation {i} failed: {result}")
        else:
            print(f"Operation {i} succeeded")
```

## Options Pattern

```python
async def with_custom_options(client):
    # Custom timeout
    custom_client = client.options(request_timeout=60.0)
    response = await custom_client.status.get_status()

    # Custom headers
    headers_client = client.options(
        headers={"X-Custom-Header": "value"}
    )
    response = await headers_client.status.get_status()
```

## Complete Example

```python
import asyncio
from kibana import AsyncKibana

async def demonstrate_async_operations():
    async with AsyncKibana("http://localhost:5601") as client:
        # Get status
        print("Fetching status...")
        status = await client.status.get_status()
        print(f"Status: {status.body['status']['overall']['level']}")

        # Create connector
        print("Creating connector...")
        connector = await client.actions.create(
            name="Async Example Connector",
            connector_type_id=".server-log",
            config={}
        )
        connector_id = connector.body["id"]
        print(f"Created: {connector_id}")

        # Execute connector
        print("Executing connector...")
        result = await client.actions.execute(
            id=connector_id,
            params={"message": "Test", "level": "info"}
        )
        print(f"Execution status: {result.body['status']}")

        # Cleanup
        await client.actions.delete(id=connector_id)
        print("Connector deleted")

asyncio.run(demonstrate_async_operations())
```

## Running the Examples

```bash
# Comprehensive example
python examples/async_example.py

# Advanced patterns
python examples/async_comprehensive.py
```

## Best Practices

1. **Always use context managers** for cleanup
2. **Batch concurrent operations** with `gather()`
3. **Handle exceptions** in concurrent code
4. **Set timeouts** appropriately
5. **Use `return_exceptions=True`** to handle partial failures

## Next Steps

- [AsyncKibana API Reference](../../api-reference/async-client.rst)
- [Error Handling](../../user-guide/error-handling.md)

## Related Documentation

- [AsyncKibana API Reference](../../api-reference/async-client.rst)
- [Concurrent Operations](../../user-guide/advanced-usage.md)
