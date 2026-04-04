# Adding Space Support to New API Clients

This guide explains how to add space support to new API clients in kibana-py using the standardized `NamespaceClient` pattern.

## Overview

The kibana-py library provides a standardized way to add space support to new API clients through the `NamespaceClient` base class. This ensures consistency across all API clients and makes it easy to add space support to new APIs with minimal code.

## Why Use NamespaceClient?

When you inherit from `NamespaceClient`, you automatically get:

- ✅ Space path construction (`/s/{space_id}/api/...`)
- ✅ Space ID format validation
- ✅ Space existence validation with caching
- ✅ Cache management (5-minute TTL by default)
- ✅ Error enhancement with space context
- ✅ Performance optimizations
- ✅ Cache statistics and monitoring
- ✅ Cache pre-warming capabilities

## Step-by-Step Implementation Guide

### Step 1: Inherit from NamespaceClient

Start by importing and inheriting from `NamespaceClient`:

```python
from kibana._sync.client.utils import NamespaceClient
from elastic_transport import ObjectApiResponse
from typing import Any

class NewAPIClient(NamespaceClient):
    """Client for the New API with space support.

    This client provides methods for interacting with the New API,
    with full support for Kibana Spaces.
    """
    pass
```

### Step 2: Add space_id Parameters to Methods

All methods that support space-scoped operations should include:
- `space_id: str | None = None` parameter
- Optional `validate_space: bool | None = None` parameter for per-operation control

```python
def create(
    self,
    *,
    name: str,
    config: dict[str, Any],
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Create a resource, optionally in a specific space.

    Args:
        name: Display name for the resource.
        config: Resource configuration.
        space_id: Space ID for space-scoped operation (optional).
        validate_space: Override space validation setting (optional).

    Returns:
        API response containing the created resource details.

    Raises:
        SpaceNotFoundError: If the specified space does not exist.
        BadRequestError: If the configuration is invalid.

    Example:
        >>> client = Kibana("http://localhost:5601")
        >>> resource = client.new_api.create(
        ...     name="My Resource",
        ...     config={"key": "value"},
        ...     space_id="marketing"
        ... )
        >>> print(resource.body["id"])
    """
```

### Step 3: Use _build_space_path() for URL Construction

The `_build_space_path()` method handles all space-related path construction and validation:

```python
def create(
    self,
    *,
    name: str,
    config: dict[str, Any],
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Create a resource, optionally in a specific space."""
    # Override validation setting if specified
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        # Build space-aware path (includes validation)
        path = self._build_space_path("/api/new-api/resource", space_id)

        # Build request body
        body = {"name": name, "config": config}

        # Make API request
        return self.perform_request(method="POST", path=path, body=body)
    finally:
        # Restore original validation setting
        self._validate_spaces = original_validate
```

### Step 4: Implement All CRUD Operations

Follow the same pattern for all operations:

```python
def get(
    self,
    *,
    id: str,
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Get a resource by ID."""
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        path = self._build_space_path(f"/api/new-api/resource/{id}", space_id)
        return self.perform_request(method="GET", path=path)
    finally:
        self._validate_spaces = original_validate

def update(
    self,
    *,
    id: str,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Update a resource."""
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        path = self._build_space_path(f"/api/new-api/resource/{id}", space_id)
        body = {}
        if name is not None:
            body["name"] = name
        if config is not None:
            body["config"] = config

        return self.perform_request(method="PUT", path=path, body=body)
    finally:
        self._validate_spaces = original_validate

def delete(
    self,
    *,
    id: str,
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Delete a resource."""
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        path = self._build_space_path(f"/api/new-api/resource/{id}", space_id)
        return self.perform_request(method="DELETE", path=path)
    finally:
        self._validate_spaces = original_validate

def get_all(
    self,
    *,
    space_id: str | None = None,
    validate_space: bool | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Get all resources."""
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        path = self._build_space_path("/api/new-api/resource", space_id)
        return self.perform_request(method="GET", path=path)
    finally:
        self._validate_spaces = original_validate
```

## Constructor Options

Your client inherits constructor options from `NamespaceClient`:

```python
# Create client with default space
client = NewAPIClient(
    base_client,
    default_space_id="marketing",  # Optional default space
    validate_spaces=True           # Enable/disable validation
)

# All operations will use "marketing" space by default
resource = client.create(name="Test", config={})

# Override default space for specific operation
resource = client.create(name="Test", config={}, space_id="sales")

# Disable validation for performance-critical operations
fast_client = NewAPIClient(base_client, validate_spaces=False)
```

## Best Practices

### 1. Always Use _build_space_path()

Never construct space paths manually:

```python
# ❌ Wrong - manual path construction
if space_id:
    path = f"/s/{space_id}/api/new-api/resource"
else:
    path = "/api/new-api/resource"

# ✅ Correct - use _build_space_path()
path = self._build_space_path("/api/new-api/resource", space_id)
```

### 2. Include Validation Override

Allow per-operation validation control:

```python
# ✅ Correct - includes validate_space parameter
def create(
    self,
    *,
    name: str,
    space_id: str | None = None,
    validate_space: bool | None = None,  # Allow override
) -> ObjectApiResponse[dict[str, Any]]:
    original_validate = self._validate_spaces
    if validate_space is not None:
        self._validate_spaces = validate_space

    try:
        # Implementation
        pass
    finally:
        self._validate_spaces = original_validate
```

### 3. Follow the try/finally Pattern

Always restore validation settings:

```python
# ✅ Correct - restores original setting
original_validate = self._validate_spaces
if validate_space is not None:
    self._validate_spaces = validate_space

try:
    # Method implementation
    pass
finally:
    self._validate_spaces = original_validate
```

### 4. Use Consistent Parameter Names

- `space_id` for the space identifier
- `validate_space` for validation override
- Always use keyword-only parameters (`*,`)

### 5. Add Proper Error Handling

Let the base class enhance errors with space context:

```python
# The base class automatically enhances errors
# No need for manual error handling for space-related errors
path = self._build_space_path("/api/new-api/resource", space_id)
# If space doesn't exist, SpaceNotFoundError is raised automatically
```

### 6. Include Comprehensive Docstrings

Document space support in all methods:

```python
def create(
    self,
    *,
    name: str,
    space_id: str | None = None,
) -> ObjectApiResponse[dict[str, Any]]:
    """Create a resource.

    Args:
        name: Display name for the resource.
        space_id: Space ID for space-scoped operation. If not provided,
            uses the default space or the client's default_space_id.

    Returns:
        API response containing the created resource.

    Raises:
        SpaceNotFoundError: If the specified space does not exist.
        BadRequestError: If the request is invalid.

    Example:
        >>> # Create in default space
        >>> resource = client.new_api.create(name="Test")
        >>>
        >>> # Create in specific space
        >>> resource = client.new_api.create(
        ...     name="Test",
        ...     space_id="marketing"
        ... )
    """
```

## Testing Your Implementation

### Unit Tests

Test space support with mocked transport:

```python
import pytest
from unittest.mock import Mock
from kibana import Kibana

class TestNewAPIClientSpaceSupport:
    def test_create_with_space_id(self, mock_transport):
        """Test resource creation with space_id parameter."""
        client = Kibana(_transport=mock_transport)

        # Mock space validation and creation
        mock_transport.perform_request.side_effect = [
            Mock(body={"id": "marketing", "name": "Marketing"}),  # Validation
            Mock(body={"id": "res-1", "name": "Test"}),  # Creation
        ]

        result = client.new_api.create(
            name="Test",
            config={"key": "value"},
            space_id="marketing"
        )

        # Verify space-scoped path was used
        calls = mock_transport.perform_request.call_args_list
        assert "/s/marketing/api/new-api/resource" in calls[1][1]["path"]

    def test_space_validation_caching(self, mock_transport):
        """Test that space validation results are cached."""
        client = Kibana(_transport=mock_transport)

        # Mock responses
        mock_transport.perform_request.side_effect = [
            Mock(body={"id": "marketing"}),  # First validation
            Mock(body={"id": "res-1"}),      # First operation
            Mock(body={"id": "res-2"}),      # Second operation (no validation)
        ]

        # First call validates space
        client.new_api.create(name="Test1", config={}, space_id="marketing")

        # Second call uses cache
        client.new_api.create(name="Test2", config={}, space_id="marketing")

        # Validation should only happen once
        assert mock_transport.perform_request.call_count == 3

    def test_space_not_found_error(self, mock_transport):
        """Test proper error handling for non-existent spaces."""
        from kibana.exceptions import NotFoundError, SpaceNotFoundError

        client = Kibana(_transport=mock_transport)

        # Mock space not found
        mock_transport.perform_request.side_effect = NotFoundError(
            message="Space not found",
            meta=Mock(status=404),
            body={"error": "Not found"}
        )

        with pytest.raises(SpaceNotFoundError) as exc_info:
            client.new_api.create(
                name="Test",
                config={},
                space_id="nonexistent"
            )

        assert exc_info.value.space_id == "nonexistent"
```

### Integration Tests

Test with real Kibana instance:

```python
import pytest
from tests.integration.utils import is_kibana_available

pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available"
)

class TestNewAPIIntegration:
    def test_space_scoped_operations(self, kibana_client, test_space):
        """Test resource operations in a real space."""
        # Create resource in test space
        resource = kibana_client.new_api.create(
            name="Integration Test",
            config={"key": "value"},
            space_id=test_space["id"]
        )

        # Verify resource exists in space
        retrieved = kibana_client.new_api.get(
            id=resource.body["id"],
            space_id=test_space["id"]
        )
        assert retrieved.body["name"] == "Integration Test"

        # Verify resource doesn't exist in default space
        from kibana.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            kibana_client.new_api.get(id=resource.body["id"])

        # Cleanup
        kibana_client.new_api.delete(
            id=resource.body["id"],
            space_id=test_space["id"]
        )
```

## Complete Example

Here's a complete example of a new API client with space support:

```python
from kibana._sync.client.utils import NamespaceClient
from elastic_transport import ObjectApiResponse
from typing import Any

class AlertsClient(NamespaceClient):
    """Client for Kibana Alerts API with space support."""

    def create(
        self,
        *,
        name: str,
        rule_type_id: str,
        params: dict[str, Any],
        schedule: dict[str, Any],
        actions: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Create an alert rule.

        Args:
            name: Display name for the alert rule.
            rule_type_id: Type of rule (e.g., "logs.alert.document.count").
            params: Rule-specific parameters.
            schedule: Schedule configuration (e.g., {"interval": "1m"}).
            actions: Actions to execute when alert fires (optional).
            space_id: Space ID for space-scoped operation (optional).
            validate_space: Override space validation setting (optional).

        Returns:
            API response containing the created alert rule.

        Raises:
            SpaceNotFoundError: If the specified space does not exist.
            BadRequestError: If the configuration is invalid.
        """
        original_validate = self._validate_spaces
        if validate_space is not None:
            self._validate_spaces = validate_space

        try:
            path = self._build_space_path("/api/alerting/rule", space_id)
            body = {
                "name": name,
                "rule_type_id": rule_type_id,
                "params": params,
                "schedule": schedule,
            }
            if actions:
                body["actions"] = actions

            return self.perform_request(method="POST", path=path, body=body)
        finally:
            self._validate_spaces = original_validate

    def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """Get an alert rule by ID."""
        original_validate = self._validate_spaces
        if validate_space is not None:
            self._validate_spaces = validate_space

        try:
            path = self._build_space_path(f"/api/alerting/rule/{id}", space_id)
            return self.perform_request(method="GET", path=path)
        finally:
            self._validate_spaces = original_validate
```

## Additional Resources

- {doc}`../user-guide/spaces` - User guide for Kibana Spaces
- {doc}`testing` - Testing guidelines including space support tests
- {doc}`architecture` - Overall project architecture
- [Kibana Spaces API Documentation](https://www.elastic.co/guide/en/kibana/current/spaces-api.html)
