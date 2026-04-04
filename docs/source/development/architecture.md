# Architecture

This document provides an overview of the kibana-py architecture, design patterns, and key architectural decisions.

## Project Structure

```
kibana/                      # Main package
├── __init__.py             # Public API exports
├── _version.py             # Version string
├── exceptions.py           # Exception hierarchy
├── serializer.py           # JSON serialization
├── observability.py        # OpenTelemetry integration
├── _utils.py               # Internal utilities
├── _sync/                  # Synchronous client implementation
│   ├── __init__.py
│   └── client/
│       ├── __init__.py     # Kibana client exports
│       ├── _base.py        # BaseClient implementation
│       ├── actions.py      # ActionsClient
│       ├── spaces.py       # SpacesClient
│       ├── saved_objects.py # SavedObjectsClient
│       ├── status.py       # StatusClient
│       └── utils.py        # NamespaceClient and utilities
└── _async/                 # Asynchronous client implementation
    ├── __init__.py
    └── client/
        ├── __init__.py
        ├── _base.py        # AsyncBaseClient
        ├── actions.py      # AsyncActionsClient
        ├── spaces.py       # AsyncSpacesClient
        ├── saved_objects.py # AsyncSavedObjectsClient
        ├── status.py       # AsyncStatusClient
        └── utils.py        # AsyncNamespaceClient
```

## Core Architectural Principles

### 1. Consistency Over Convenience

All API clients follow identical patterns for similar operations:
- Space support works the same way across all clients
- Error handling is consistent
- Parameter naming follows conventions
- Response handling is uniform

### 2. Extensibility by Design

The architecture supports the full Kibana REST API:
- Base classes provide common functionality
- New clients can be added without architectural changes
- Composition and inheritance patterns scale to dozens of clients
- Plugin-specific APIs follow the same patterns

### 3. Developer Experience First

- Pythonic interfaces over direct API mapping
- Automatic configuration detection
- Clear error messages with actionable guidance
- Consistent parameter naming and behavior

### 4. Performance and Efficiency

- Zero overhead when features aren't used
- Lazy initialization of client properties
- Efficient caching with configurable TTL
- Minimal API calls through intelligent validation

## Client Hierarchy

### Base Client Architecture

```
BaseClient (transport, auth, core request handling)
├── NamespaceClient (space support, common utilities)
│   ├── ActionsClient (connector operations)
│   ├── SavedObjectsClient (saved object operations)
│   ├── SpacesClient (space management)
│   └── [Future API clients]
└── SpaceScopedKibana (space context wrapper)
```

### BaseClient

The `BaseClient` provides core functionality:

```python
class BaseClient:
    """Base client with transport and authentication."""

    def __init__(
        self,
        hosts: str | list[str] | None = None,
        *,
        api_key: str | tuple[str, str] | None = None,
        basic_auth: tuple[str, str] | None = None,
        bearer_auth: str | None = None,
        _transport: Transport | None = None,
    ):
        # Initialize transport
        # Set up authentication
        # Configure serialization
```

**Responsibilities**:
- Transport initialization and management
- Authentication header resolution
- Request execution via elastic-transport
- Response processing and error handling
- Options pattern for per-request configuration

### NamespaceClient

The `NamespaceClient` extends `BaseClient` with space support:

```python
class NamespaceClient(BaseClient):
    """Base client with space support."""

    def __init__(
        self,
        base_client: BaseClient,
        *,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ):
        # Inherit from base client
        # Set up space validation
        # Initialize cache
```

**Responsibilities**:
- Space path construction (`/s/{space_id}/api/...`)
- Space ID format validation
- Space existence validation with caching
- Cache management (5-minute TTL)
- Error enhancement with space context

### API Clients

Individual API clients inherit from `NamespaceClient`:

```python
class ActionsClient(NamespaceClient):
    """Client for Kibana Actions API."""

    def create(self, *, name: str, ..., space_id: str | None = None):
        path = self._build_space_path("/api/actions/connector", space_id)
        return self.perform_request(method="POST", path=path, body=...)
```

**Responsibilities**:
- API-specific method implementations
- Request body construction
- Response parsing
- API-specific error handling

## Key Design Patterns

### 1. Space Support Pattern

All clients that support spaces use the same pattern:

```python
def method(
    self,
    *,
    param: str,
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Method with space support."""
    # Override validation if specified
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        # Build space-aware path
        path = self._build_space_path("/api/endpoint", space_id)

        # Make request
        return self.perform_request(method="POST", path=path, body=...)
    finally:
        # Restore original setting
        self._validate_spaces = original_validate
```

**Benefits**:
- Consistent API across all clients
- Automatic space validation
- Per-operation validation override
- Efficient caching

### 2. Authentication Resolution

Authentication is resolved in order of precedence:

1. API key (string or tuple format)
2. Basic auth (username/password tuple)
3. Bearer token (string)

```python
def resolve_auth_headers(
    api_key: str | tuple[str, str] | None = None,
    basic_auth: tuple[str, str] | None = None,
    bearer_auth: str | None = None,
) -> dict[str, str]:
    """Resolve authentication to HTTP headers."""
    if api_key:
        # Handle API key
    elif basic_auth:
        # Handle basic auth
    elif bearer_auth:
        # Handle bearer token
    return headers
```

### 3. Error Handling

Custom exception hierarchy rooted at `KibanaException`:

```python
class KibanaException(Exception):
    """Base exception for all Kibana errors."""

class ApiError(KibanaException):
    """Base class for API errors."""

    def __init__(self, message: str, meta: ApiResponseMeta, body: Any):
        self.message = message
        self.meta = meta
        self.body = body

class NotFoundError(ApiError):
    """404 Not Found."""

class BadRequestError(ApiError):
    """400 Bad Request."""

class SpaceNotFoundError(NotFoundError):
    """Space not found error."""

    def __init__(self, space_id: str, *args, **kwargs):
        self.space_id = space_id
        super().__init__(*args, **kwargs)
```

HTTP status codes are mapped to specific exceptions:

```python
HTTP_EXCEPTIONS = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    # ...
}
```

### 4. Serialization

Abstract `Serializer` base class with multiple implementations:

```python
class Serializer(ABC):
    """Abstract serializer interface."""

    @abstractmethod
    def dumps(self, data: Any) -> bytes:
        """Serialize data to bytes."""

    @abstractmethod
    def loads(self, data: bytes) -> Any:
        """Deserialize bytes to data."""

class JSONSerializer(Serializer):
    """Standard library JSON serializer."""

class OrjsonSerializer(Serializer):
    """High-performance orjson serializer."""
```

The serializer is auto-selected based on availability:
- `OrjsonSerializer` if orjson is installed
- `JSONSerializer` as fallback

### 5. Options Pattern

Per-request configuration via the `options()` method:

```python
# Override request timeout
response = client.options(request_timeout=30).actions.get(id="connector-id")

# Add custom headers
response = client.options(headers={"X-Custom": "value"}).actions.get(id="connector-id")

# Combine multiple options
response = client.options(
    request_timeout=30,
    headers={"X-Custom": "value"}
).actions.get(id="connector-id")
```

## Sync/Async Architecture

### Dual Implementation

kibana-py provides both synchronous and asynchronous clients:

- **Sync**: `kibana._sync.client.*`
- **Async**: `kibana._async.client.*`

Both implementations follow the same patterns and provide identical APIs.

### Shared Components

Components shared between sync and async:
- Exception hierarchy (`exceptions.py`)
- Serialization (`serializer.py`)
- Observability (`observability.py`)
- Utilities (`_utils.py`)

### Implementation Differences

Key differences between sync and async:

```python
# Sync
class BaseClient:
    def perform_request(self, method: str, path: str, **kwargs):
        return self._transport.perform_request(method, path, **kwargs)

# Async
class AsyncBaseClient:
    async def perform_request(self, method: str, path: str, **kwargs):
        return await self._transport.perform_request(method, path, **kwargs)
```

## Observability Integration

### OpenTelemetry Support

Built-in OpenTelemetry instrumentation:

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:4317"
)
```

**Features**:
- Automatic span creation for API calls
- Trace context propagation
- Log-trace correlation
- Structured logging
- APM integration

### Instrumentation Points

- HTTP requests to Kibana API
- Space validation operations
- Cache hits/misses
- Error conditions

## Caching Strategy

### Space Validation Cache

Space validation results are cached to minimize API calls:

```python
class NamespaceClient:
    def __init__(self, ...):
        self._space_cache: dict[str, tuple[bool, float]] = {}
        self._cache_ttl: float = 300.0  # 5 minutes

    def _is_space_cached(self, space_id: str) -> bool:
        """Check if space validation is cached."""
        if space_id in self._space_cache:
            is_valid, timestamp = self._space_cache[space_id]
            if time.time() - timestamp < self._cache_ttl:
                return True
        return False
```

**Cache Characteristics**:
- 5-minute TTL by default
- Per-client cache (not global)
- Automatic invalidation on TTL expiry
- Manual cache clearing available

## Extension Points

### Adding New API Clients

To add a new API client:

1. **Inherit from NamespaceClient**:
   ```python
   class NewAPIClient(NamespaceClient):
       """Client for New API."""
   ```

2. **Implement methods**:
   ```python
   def create(self, *, name: str, space_id: str | None = None):
       path = self._build_space_path("/api/new-endpoint", space_id)
       return self.perform_request(method="POST", path=path, body=...)
   ```

3. **Add to main client**:
   ```python
   class Kibana(BaseClient):
       @property
       def new_api(self) -> NewAPIClient:
           if not hasattr(self, "_new_api"):
               self._new_api = NewAPIClient(self)
           return self._new_api
   ```

See {doc}`adding-space-support` for detailed instructions.

### Custom Authentication

To add custom authentication:

1. **Extend resolve_auth_headers**:
   ```python
   def resolve_auth_headers(..., custom_auth: str | None = None):
       if custom_auth:
           return {"X-Custom-Auth": custom_auth}
       # ... existing logic
   ```

2. **Update BaseClient**:
   ```python
   class BaseClient:
       def __init__(self, ..., custom_auth: str | None = None):
           headers = resolve_auth_headers(..., custom_auth=custom_auth)
   ```

### Custom Serializers

To add a custom serializer:

```python
class CustomSerializer(Serializer):
    """Custom serializer implementation."""

    def dumps(self, data: Any) -> bytes:
        # Custom serialization logic
        pass

    def loads(self, data: bytes) -> Any:
        # Custom deserialization logic
        pass
```

## Design Decisions

### Why NamespaceClient?

**Decision**: Create a separate `NamespaceClient` base class for space support.

**Rationale**:
- Not all Kibana APIs support spaces
- Separates concerns (base functionality vs. space support)
- Allows clients to opt-in to space support
- Provides consistent space support across all clients

**Alternatives Considered**:
- Adding space support directly to `BaseClient` (rejected: not all APIs support spaces)
- Manual space path construction in each client (rejected: inconsistent, error-prone)

### Why Lazy Property Initialization?

**Decision**: Use lazy initialization for API client properties.

**Rationale**:
- Zero overhead for unused clients
- Simpler main client initialization
- Allows per-client configuration

**Implementation**:
```python
@property
def actions(self) -> ActionsClient:
    if not hasattr(self, "_actions"):
        self._actions = ActionsClient(self)
    return self._actions
```

### Why Keyword-Only Parameters?

**Decision**: Use keyword-only parameters for all client methods.

**Rationale**:
- Prevents positional argument errors
- Makes code more readable
- Allows adding new parameters without breaking changes
- Follows Python best practices

**Implementation**:
```python
def create(
    self,
    *,  # Force keyword-only
    name: str,
    config: dict[str, Any],
):
    pass
```

### Why Separate Sync/Async Implementations?

**Decision**: Maintain separate `_sync` and `_async` packages.

**Rationale**:
- Clear separation of concerns
- No async overhead for sync users
- Easier to maintain and test
- Follows patterns from other Python clients

**Alternatives Considered**:
- Single implementation with async/await everywhere (rejected: overhead for sync users)
- Wrapper approach (rejected: complexity, performance)

## Performance Considerations

### Space Validation Overhead

Space validation adds minimal overhead:
- First call: ~50-100ms (API call)
- Cached calls: <1ms (cache lookup)
- Cache hit ratio: >95% in typical usage

### Memory Usage

- Base client: ~1KB
- Each API client: ~500 bytes
- Space cache: ~100 bytes per space
- Total for typical usage: <10KB

### Network Efficiency

- Connection pooling via elastic-transport
- HTTP keep-alive enabled by default
- Configurable retry logic
- Request/response compression support

## Testing Architecture

### Unit Tests

- Mock transport layer
- Test client logic in isolation
- Fast execution (<10 seconds total)
- High coverage (>90%)

### Integration Tests

- Real Kibana instance
- Test actual API interactions
- Resource cleanup
- Graceful degradation

See {doc}`testing` for detailed testing guidelines.

## Future Considerations

### Planned Enhancements

- **Bulk Operations**: Consistent bulk operation support across clients
- **Async Improvements**: Enhanced async patterns and concurrency
- **Plugin APIs**: Support for plugin-specific APIs
- **Advanced Caching**: Configurable cache strategies

### Extensibility

The architecture is designed to support:
- 50+ API clients without changes
- Plugin-specific APIs
- Custom authentication methods
- Advanced caching strategies
- API versioning

## Additional Resources

- {doc}`adding-space-support` - Adding space support to new clients
- {doc}`testing` - Testing patterns and guidelines
- {doc}`contributing` - Contribution guidelines
- [Kibana API Documentation](https://www.elastic.co/guide/en/kibana/current/api.html)
- [elastic-transport Documentation](https://elastic-transport-python.readthedocs.io/)
