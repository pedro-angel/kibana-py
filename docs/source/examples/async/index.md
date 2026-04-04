# Async Examples

The AsyncKibana client provides native async/await support for all Kibana APIs with the same interface as the synchronous client.

```{toctree}
:maxdepth: 2
:caption: Async Examples

patterns
```

## Overview

Learn how to:
- Use async context managers
- Execute concurrent operations
- Handle async errors
- Implement async patterns

## Example Files

### async_example.py

**Purpose**: Comprehensive async demonstration with all namespace clients

**What You'll Learn**:
- Async context manager usage
- Actions, spaces, saved objects, and status operations
- Concurrent API calls
- Options pattern

[View Comprehensive Example →](patterns.md)

### async_comprehensive.py

**Purpose**: Advanced async patterns

**What You'll Learn**:
- Concurrent operations with `asyncio.gather()`
- Per-request configuration
- Error handling in async context

[View Advanced Patterns →](patterns.md)

## Basic Async Usage

```python
import asyncio
from kibana import AsyncKibana

async def main():
    async with AsyncKibana("http://localhost:5601") as client:
        # Get status
        status = await client.status.get_status()
        print(status.body["status"]["overall"]["level"])

        # Create connector
        connector = await client.actions.create(
            name="Async Connector",
            connector_type_id=".server-log",
            config={}
        )

asyncio.run(main())
```

## Concurrent Operations

```python
async def fetch_all_data(client):
    # Execute multiple operations concurrently
    results = await asyncio.gather(
        client.status.get_status(),
        client.spaces.get_all(),
        client.actions.list_types()
    )

    status, spaces, types = results
    return status, spaces, types
```

## When to Use Async

Use AsyncKibana when:
- Making multiple concurrent API calls
- Building async web applications (FastAPI, aiohttp)
- Integrating with async frameworks
- Need high throughput with many requests

## Best Practices

1. **Use context managers** for automatic cleanup
2. **Batch operations** with `asyncio.gather()`
3. **Handle exceptions** in concurrent operations
4. **Set appropriate timeouts** for async operations

## Next Steps

- [Async Patterns](patterns.md) - Detailed examples
- [AsyncKibana API Reference](../../api-reference/async-client.rst)

## Related Documentation

- [AsyncKibana API Reference](../../api-reference/async-client.rst)
- [Error Handling](../../user-guide/error-handling.md)
