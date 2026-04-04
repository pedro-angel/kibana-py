# Space Support Migration Guide

This guide helps you migrate your code to use the new space support features in kibana-py, including the `space_id` parameter pattern and space-scoped clients.

## Overview

Space support enables multi-tenancy in Kibana by allowing you to organize resources (connectors, saved objects, etc.) into isolated spaces. The kibana-py library provides consistent space support across all API clients.

### What's New

- **`space_id` parameter** on all space-aware methods
- **Space-scoped clients** via `client.space("space-id")`
- **Automatic space validation** with caching for performance
- **Consistent error handling** for space-related errors
- **Space context** in all error messages

### What Hasn't Changed

- **Default space behavior** - operations without `space_id` use the default space
- **Existing APIs** - all methods work exactly as before
- **Backward compatibility** - no breaking changes to existing code

## Migration Scenarios

### Scenario 1: Using Default Space Only

**No action required.** Your existing code continues to work:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# This works exactly as before - uses default space
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"}
)
```

**Result**: All operations use the default space, no changes needed.

### Scenario 2: Adding Space Support to Existing Code

**Minimal change required.** Add `space_id` parameter to operations:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# Before: Default space only
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"}
)

# After: Specify space
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"},
    space_id="marketing"  # Now in marketing space
)
```

**Result**: Operations execute in the specified space with automatic validation.

### Scenario 3: Multiple Operations in Same Space

**Use space-scoped client.** More efficient for multiple operations:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# Before: Repeat space_id for each operation
connector1 = client.actions.create(
    name="Connector 1",
    connector_type_id=".index",
    config={"index": "logs1"},
    space_id="marketing"
)

connector2 = client.actions.create(
    name="Connector 2",
    connector_type_id=".index",
    config={"index": "logs2"},
    space_id="marketing"
)

# After: Use space-scoped client
marketing_client = client.space("marketing")  # Validates once

connector1 = marketing_client.actions.create(
    name="Connector 1",
    connector_type_id=".index",
    config={"index": "logs1"}
    # space_id not needed - automatically uses "marketing"
)

connector2 = marketing_client.actions.create(
    name="Connector 2",
    connector_type_id=".index",
    config={"index": "logs2"}
    # space_id not needed - automatically uses "marketing"
)
```

**Result**: Better performance with single validation, cleaner code.

## Step-by-Step Migration

### Step 1: Identify Space-Aware Operations

Review your code for operations that should be space-scoped:

```python
# Space-aware operations (support space_id parameter):
client.actions.create(...)
client.actions.get(...)
client.actions.get_all(...)
client.actions.update(...)
client.actions.delete(...)
client.actions.execute(...)

client.saved_objects.create(...)
client.saved_objects.get(...)
client.saved_objects.find(...)
client.saved_objects.update(...)
client.saved_objects.delete(...)
client.saved_objects.bulk_create(...)
client.saved_objects.bulk_get(...)
client.saved_objects.bulk_update(...)
client.saved_objects.bulk_delete(...)

# Space management operations:
client.spaces.create(...)
client.spaces.get(...)
client.spaces.get_all(...)
client.spaces.update(...)
client.spaces.delete(...)
```

### Step 2: Choose Migration Pattern

**Pattern A: Individual `space_id` Parameters** (for occasional space operations)

```python
# Good for: Occasional operations in different spaces
connector = client.actions.create(
    name="Marketing Connector",
    connector_type_id=".index",
    config={"index": "marketing-logs"},
    space_id="marketing"
)

saved_obj = client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Sales Dashboard"},
    space_id="sales"
)
```

**Pattern B: Space-Scoped Client** (for multiple operations in same space)

```python
# Good for: Multiple operations in the same space
marketing_client = client.space("marketing")

connector = marketing_client.actions.create(
    name="Marketing Connector",
    connector_type_id=".index",
    config={"index": "marketing-logs"}
)

dashboard = marketing_client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Dashboard"}
)

visualization = marketing_client.saved_objects.create(
    type="visualization",
    attributes={"title": "Marketing Chart"}
)
```

### Step 3: Update Error Handling

Add space-specific error handling:

```python
from kibana import Kibana
from kibana.exceptions import SpaceNotFoundError, ConflictError

client = Kibana("http://localhost:5601", api_key="your-api-key")

try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "logs"},
        space_id="marketing"
    )
except SpaceNotFoundError as e:
    print(f"Space '{e.space_id}' does not exist")
    # Handle space not found
except ConflictError as e:
    print(f"Connector with this name already exists in space")
    # Handle conflict
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle other errors
```

### Step 4: Test Space Isolation

Verify that resources are properly isolated by space:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# Create connector in marketing space
marketing_connector = client.actions.create(
    name="Test Connector",
    connector_type_id=".index",
    config={"index": "test"},
    space_id="marketing"
)

# Verify it exists in marketing space
retrieved = client.actions.get(
    id=marketing_connector.body["id"],
    space_id="marketing"
)
print(f"✓ Found in marketing space: {retrieved.body['name']}")

# Verify it doesn't exist in default space
try:
    client.actions.get(id=marketing_connector.body["id"])
    print("❌ ERROR: Connector should not be in default space!")
except Exception:
    print("✓ Correctly isolated from default space")

# Verify it doesn't exist in sales space
try:
    client.actions.get(
        id=marketing_connector.body["id"],
        space_id="sales"
    )
    print("❌ ERROR: Connector should not be in sales space!")
except Exception:
    print("✓ Correctly isolated from sales space")
```

## Configuration and Performance

### Space Validation

By default, space existence is validated before operations:

```python
# Default: Validates space exists (recommended)
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"},
    space_id="marketing"  # Validates "marketing" exists
)

# Disable validation for performance-critical code
fast_client = client.space("marketing", validate=False)
connector = fast_client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"}
    # No validation - faster but riskier
)
```

### Validation Caching

Space validation results are cached for 5 minutes by default:

```python
# First call: Validates space exists (API call)
connector1 = client.actions.create(
    name="Connector 1",
    connector_type_id=".index",
    config={"index": "logs1"},
    space_id="marketing"
)

# Second call: Uses cached validation (no API call)
connector2 = client.actions.create(
    name="Connector 2",
    connector_type_id=".index",
    config={"index": "logs2"},
    space_id="marketing"  # Cached - much faster
)
```

The cache is automatically cleared when:
- A space is created via `client.spaces.create()`
- A space is deleted via `client.spaces.delete()`
- The cache TTL expires (5 minutes)

## Common Migration Patterns

### Pattern 1: Multi-Tenant Application

```python
from kibana import Kibana

def setup_tenant_resources(tenant_id: str):
    """Set up resources for a tenant in their dedicated space."""
    client = Kibana("http://localhost:5601", api_key="your-api-key")

    # Create space for tenant if it doesn't exist
    try:
        space = client.spaces.create(
            id=f"tenant-{tenant_id}",
            name=f"Tenant {tenant_id}",
            description=f"Dedicated space for tenant {tenant_id}"
        )
    except ConflictError:
        # Space already exists
        pass

    # Use space-scoped client for all tenant operations
    tenant_client = client.space(f"tenant-{tenant_id}")

    # Create tenant-specific resources
    connector = tenant_client.actions.create(
        name=f"Tenant {tenant_id} Connector",
        connector_type_id=".index",
        config={"index": f"tenant-{tenant_id}-logs"}
    )

    dashboard = tenant_client.saved_objects.create(
        type="dashboard",
        attributes={"title": f"Tenant {tenant_id} Dashboard"}
    )

    return {
        "space_id": f"tenant-{tenant_id}",
        "connector_id": connector.body["id"],
        "dashboard_id": dashboard.body["id"]
    }
```

### Pattern 2: Environment-Based Spaces

```python
import os
from kibana import Kibana

def get_environment_client():
    """Get a client scoped to the current environment."""
    client = Kibana("http://localhost:5601", api_key="your-api-key")

    # Use different spaces for different environments
    env = os.getenv("ENVIRONMENT", "development")
    space_map = {
        "development": "dev",
        "staging": "staging",
        "production": "prod"
    }

    space_id = space_map.get(env, "dev")
    return client.space(space_id)

# Usage
env_client = get_environment_client()

# All operations automatically use the correct environment space
connector = env_client.actions.create(
    name="App Connector",
    connector_type_id=".index",
    config={"index": "app-logs"}
)
```

### Pattern 3: Cross-Space Operations

```python
from kibana import Kibana

def copy_connector_to_space(
    client: Kibana,
    connector_id: str,
    source_space: str,
    target_space: str
):
    """Copy a connector from one space to another."""
    # Get connector from source space
    source_connector = client.actions.get(
        id=connector_id,
        space_id=source_space
    ).body

    # Create in target space
    new_connector = client.actions.create(
        name=source_connector["name"],
        connector_type_id=source_connector["connector_type_id"],
        config=source_connector["config"],
        secrets=source_connector.get("secrets", {}),
        space_id=target_space
    )

    return new_connector.body["id"]

# Usage
client = Kibana("http://localhost:5601", api_key="your-api-key")
new_id = copy_connector_to_space(
    client,
    connector_id="original-id",
    source_space="development",
    target_space="staging"
)
```

## Common Migration Issues

### Issue 1: Space Not Found Errors

**Symptoms**:
```python
SpaceNotFoundError: Space 'marketing' not found
```

**Solutions**:

1. **Verify space exists**:
   ```python
   # List all spaces
   spaces = client.spaces.get_all()
   space_ids = [s.body["id"] for s in spaces.body]
   print(f"Available spaces: {space_ids}")
   ```

2. **Create space if needed**:
   ```python
   try:
       client.spaces.create(
           id="marketing",
           name="Marketing",
           description="Marketing team space"
       )
   except ConflictError:
       # Space already exists
       pass
   ```

3. **Use correct space ID**:
   ```python
   # Space IDs are case-sensitive and use kebab-case
   # Correct:
   space_id="marketing-team"

   # Incorrect:
   space_id="Marketing Team"  # Spaces in ID
   space_id="marketing_team"  # Underscores instead of hyphens
   ```

### Issue 2: Resources Not Found in Expected Space

**Symptoms**:
```python
NotFoundError: Connector not found
```

**Solutions**:

1. **Verify resource space**:
   ```python
   # List all connectors in space
   connectors = client.actions.get_all(space_id="marketing")
   print(f"Connectors in marketing: {[c['name'] for c in connectors.body]}")
   ```

2. **Check default space**:
   ```python
   # Resource might be in default space
   try:
       connector = client.actions.get(id=connector_id)
       print("Found in default space")
   except NotFoundError:
       print("Not in default space")
   ```

3. **Search across all spaces**:
   ```python
   def find_connector_space(client, connector_id):
       """Find which space contains a connector."""
       spaces = client.spaces.get_all()

       for space in spaces.body:
           try:
               client.actions.get(
                   id=connector_id,
                   space_id=space["id"]
               )
               return space["id"]
           except NotFoundError:
               continue

       return None

   space_id = find_connector_space(client, "my-connector-id")
   print(f"Connector found in space: {space_id}")
   ```

### Issue 3: Performance Impact from Validation

**Symptoms**:
- Slow operations when using `space_id` parameter
- Many API calls for space validation

**Solutions**:

1. **Use space-scoped client** (validates once):
   ```python
   # Slow: Validates for each operation
   for i in range(100):
       client.actions.create(
           name=f"Connector {i}",
           connector_type_id=".index",
           config={"index": f"logs-{i}"},
           space_id="marketing"  # Validates 100 times (cached after first)
       )

   # Fast: Validates once
   marketing_client = client.space("marketing")
   for i in range(100):
       marketing_client.actions.create(
           name=f"Connector {i}",
           connector_type_id=".index",
           config={"index": f"logs-{i}"}
       )
   ```

2. **Disable validation** for trusted spaces:
   ```python
   # For performance-critical code where you know space exists
   fast_client = client.space("marketing", validate=False)

   # No validation overhead
   connector = fast_client.actions.create(
       name="Fast Connector",
       connector_type_id=".index",
       config={"index": "logs"}
   )
   ```

3. **Pre-warm cache**:
   ```python
   # Validate all spaces upfront
   spaces = ["marketing", "sales", "support"]
   for space_id in spaces:
       client.space(space_id)  # Validates and caches

   # Now all operations use cached validation
   for space_id in spaces:
       client.actions.create(
           name=f"Connector for {space_id}",
           connector_type_id=".index",
           config={"index": f"{space_id}-logs"},
           space_id=space_id  # Uses cache
       )
   ```

## Testing Your Migration

### 1. Backward Compatibility Test

```python
#!/usr/bin/env python3
"""Test that existing code still works without space_id."""

from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# This should work exactly as before
connector = client.actions.create(
    name="Backward Compat Test",
    connector_type_id=".index",
    config={"index": "test"}
    # No space_id - uses default space
)

print(f"✅ Backward compatibility: Created connector {connector.body['id']}")

# Cleanup
client.actions.delete(id=connector.body["id"])
```

### 2. Space Isolation Test

```python
#!/usr/bin/env python3
"""Test that resources are properly isolated by space."""

from kibana import Kibana
from kibana.exceptions import NotFoundError

client = Kibana("http://localhost:5601", api_key="your-api-key")

# Create test spaces
for space_id in ["test-space-1", "test-space-2"]:
    try:
        client.spaces.create(
            id=space_id,
            name=f"Test Space {space_id}",
            description="Temporary test space"
        )
    except:
        pass

# Create connector in space 1
connector = client.actions.create(
    name="Isolation Test",
    connector_type_id=".index",
    config={"index": "test"},
    space_id="test-space-1"
)
connector_id = connector.body["id"]

# Verify it exists in space 1
try:
    client.actions.get(id=connector_id, space_id="test-space-1")
    print("✅ Found in test-space-1")
except NotFoundError:
    print("❌ Not found in test-space-1")

# Verify it doesn't exist in space 2
try:
    client.actions.get(id=connector_id, space_id="test-space-2")
    print("❌ Should not be in test-space-2")
except NotFoundError:
    print("✅ Correctly isolated from test-space-2")

# Cleanup
client.actions.delete(id=connector_id, space_id="test-space-1")
for space_id in ["test-space-1", "test-space-2"]:
    try:
        client.spaces.delete(id=space_id)
    except:
        pass
```

### 3. Performance Test

```python
#!/usr/bin/env python3
"""Test performance impact of space validation."""

import time
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your-api-key")

# Create test space
try:
    client.spaces.create(
        id="perf-test",
        name="Performance Test",
        description="Temporary test space"
    )
except:
    pass

# Test 1: Individual space_id parameters (with caching)
start = time.time()
for i in range(10):
    connector = client.actions.create(
        name=f"Perf Test {i}",
        connector_type_id=".index",
        config={"index": f"test-{i}"},
        space_id="perf-test"
    )
    client.actions.delete(id=connector.body["id"], space_id="perf-test")
time_individual = time.time() - start

# Test 2: Space-scoped client
start = time.time()
perf_client = client.space("perf-test")
for i in range(10):
    connector = perf_client.actions.create(
        name=f"Perf Test {i}",
        connector_type_id=".index",
        config={"index": f"test-{i}"}
    )
    perf_client.actions.delete(id=connector.body["id"])
time_scoped = time.time() - start

# Test 3: No validation
start = time.time()
fast_client = client.space("perf-test", validate=False)
for i in range(10):
    connector = fast_client.actions.create(
        name=f"Perf Test {i}",
        connector_type_id=".index",
        config={"index": f"test-{i}"}
    )
    fast_client.actions.delete(id=connector.body["id"])
time_no_validation = time.time() - start

print(f"Individual space_id: {time_individual:.3f}s")
print(f"Space-scoped client: {time_scoped:.3f}s")
print(f"No validation: {time_no_validation:.3f}s")

# Cleanup
try:
    client.spaces.delete(id="perf-test")
except:
    pass
```

## Best Practices After Migration

### 1. Use Space-Scoped Clients for Multiple Operations

```python
# Good: Single validation, cleaner code
marketing_client = client.space("marketing")
connector = marketing_client.actions.create(...)
dashboard = marketing_client.saved_objects.create(...)
visualization = marketing_client.saved_objects.create(...)

# Avoid: Multiple validations, repetitive code
connector = client.actions.create(..., space_id="marketing")
dashboard = client.saved_objects.create(..., space_id="marketing")
visualization = client.saved_objects.create(..., space_id="marketing")
```

### 2. Handle Space Errors Gracefully

```python
from kibana.exceptions import SpaceNotFoundError, ConflictError

try:
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "logs"},
        space_id="marketing"
    )
except SpaceNotFoundError as e:
    # Create space if it doesn't exist
    client.spaces.create(
        id=e.space_id,
        name=e.space_id.title(),
        description=f"Auto-created space for {e.space_id}"
    )
    # Retry operation
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "logs"},
        space_id="marketing"
    )
```

### 3. Document Space Requirements

```python
def create_tenant_dashboard(
    client: Kibana,
    tenant_id: str,
    dashboard_config: dict
) -> str:
    """
    Create a dashboard for a tenant.

    Args:
        client: Kibana client instance
        tenant_id: Tenant identifier (used as space ID)
        dashboard_config: Dashboard configuration

    Returns:
        Dashboard ID

    Note:
        This function requires a space with ID matching tenant_id to exist.
        The space should be created before calling this function.
    """
    tenant_client = client.space(f"tenant-{tenant_id}")
    dashboard = tenant_client.saved_objects.create(
        type="dashboard",
        attributes=dashboard_config
    )
    return dashboard.body["id"]
```

### 4. Use Consistent Space Naming

```python
# Good: Consistent kebab-case naming
space_ids = [
    "marketing-team",
    "sales-team",
    "support-team"
]

# Avoid: Inconsistent naming
space_ids = [
    "marketing_team",  # Underscores
    "SalesTeam",       # CamelCase
    "support team"     # Spaces
]
```

## Rollback Plan

If you need to revert to default space only:

### Quick Rollback

Simply remove `space_id` parameters:

```python
# With space support
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"},
    space_id="marketing"
)

# Rollback: Remove space_id
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "logs"}
    # No space_id - back to default space
)
```

### Migrate Resources Back to Default Space

```python
def migrate_to_default_space(
    client: Kibana,
    source_space: str
):
    """Migrate all connectors from a space to default space."""
    # Get all connectors in source space
    connectors = client.actions.get_all(space_id=source_space)

    migrated = []
    for connector in connectors.body:
        # Create in default space
        new_connector = client.actions.create(
            name=connector["name"],
            connector_type_id=connector["connector_type_id"],
            config=connector["config"],
            secrets=connector.get("secrets", {})
            # No space_id - creates in default space
        )

        # Delete from source space
        client.actions.delete(
            id=connector["id"],
            space_id=source_space
        )

        migrated.append({
            "old_id": connector["id"],
            "new_id": new_connector.body["id"],
            "name": connector["name"]
        })

    return migrated
```

## Additional Resources

- {doc}`../user-guide/spaces` - Comprehensive space support documentation
- {doc}`../api-reference/spaces` - Spaces API reference
- {doc}`../examples/spaces/index` - Space usage examples
- {doc}`../development/adding-space-support` - Adding space support to new clients
- {doc}`../troubleshooting/common-issues` - Troubleshooting space-related issues

## Summary

Space support in kibana-py provides:

- **✅ Multi-tenancy** - Isolate resources by space
- **✅ Backward compatible** - Existing code works unchanged
- **✅ Consistent API** - Same pattern across all clients
- **✅ Performance optimized** - Validation caching and optional validation
- **✅ Error handling** - Clear space-specific errors
- **✅ Flexible patterns** - Individual parameters or scoped clients

Start with your existing code, add `space_id` parameters where needed, and enjoy the benefits of multi-tenant resource organization in Kibana.
