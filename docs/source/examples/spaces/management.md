# Space Management Example

**File**: `examples/space_management.py`

Comprehensive example demonstrating all CRUD operations for Kibana Spaces with production-ready patterns.

## Overview

This example uses a class-based approach to manage spaces with:
- Create, read, update, delete operations
- Comprehensive error handling
- Resource tracking and cleanup
- Logging and status messages

## Key Features

### SpaceManager Class

```python
class SpaceManager:
    """Manages Kibana Spaces with comprehensive CRUD operations."""

    def __init__(self, client: Kibana):
        self.client = client
        self.created_spaces = []  # Track for cleanup
```

### Create Space

```python
def create_space(
    self,
    space_id: str,
    name: str,
    description: str | None = None,
    color: str | None = None,
    initials: str | None = None,
    disabled_features: list | None = None,
) -> dict:
    """Create a new Kibana space with full configuration."""
    try:
        response = self.client.spaces.create(
            id=space_id,
            name=name,
            description=description,
            color=color,
            initials=initials,
            disabled_features=disabled_features,
        )
        space = response.body
        self.created_spaces.append(space_id)
        return space
    except ConflictError:
        logger.error(f"Space '{space_id}' already exists")
        raise
```

### Update Space

```python
def update_space(
    self,
    space_id: str,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
    initials: str | None = None,
    disabled_features: list | None = None,
) -> dict:
    """Update a space's properties."""
    response = self.client.spaces.update(
        id=space_id,
        name=name,
        description=description,
        color=color,
        initials=initials,
        disabled_features=disabled_features,
    )
    return response.body
```

### Delete Space

```python
def delete_space(self, space_id: str) -> None:
    """Delete a space with verification."""
    try:
        self.client.spaces.delete(id=space_id)
        # Verify deletion
        try:
            self.client.spaces.get(id=space_id)
            logger.error(f"Space '{space_id}' still exists")
        except NotFoundError:
            logger.info(f"✓ Deleted space: {space_id}")
            self.created_spaces.remove(space_id)
    except NotFoundError:
        logger.warning(f"Space '{space_id}' not found")
```

## What the Example Demonstrates

1. **List existing spaces** - See what's already there
2. **Create new space** - With full configuration
3. **Retrieve space** - Get space details
4. **Update space** - Modify properties
5. **Create multiple spaces** - Batch operations
6. **Error handling** - Handle conflicts and not found errors
7. **Cleanup** - Remove created spaces

## Running the Example

```bash
python examples/space_management.py
```

## Expected Output

```
================================================================================
KIBANA SPACE MANAGEMENT EXAMPLE
================================================================================

1️⃣  Listing existing spaces...
   Found 1 existing space(s):
   - Default (ID: default)

2️⃣  Creating a new space...
   ✓ Created space: Marketing Team (ID: marketing-team)
   Space URL: http://localhost:5601/s/marketing-team/app/home

3️⃣  Retrieving the created space...
   Name: Marketing Team
   Description: Space for marketing team's dashboards and reports
   Color: #FF6B6B
   Disabled features: dev_tools, advancedSettings

4️⃣  Updating the space...
   New name: Marketing & Sales Team
   New description: Updated: Combined marketing and sales team space
   New color: #4ECDC4

5️⃣  Creating another space...
   ✓ Created space: Engineering Team (ID: engineering-team)

6️⃣  Listing all spaces (including new ones)...
   Total spaces: 3
      Default (ID: default)
   🆕 Marketing & Sales Team (ID: marketing-team)
   🆕 Engineering Team (ID: engineering-team)

7️⃣  Demonstrating error handling...
   ✓ Correctly handled NotFoundError for nonexistent space
   ✓ Correctly handled ConflictError for duplicate space

================================================================================
🎉 EXAMPLE COMPLETED SUCCESSFULLY
================================================================================

Created 2 space(s) during this example:
  - marketing-team
    URL: http://localhost:5601/s/marketing-team/app/home
  - engineering-team
    URL: http://localhost:5601/s/engineering-team/app/home

================================================================================
Delete the created spaces? (y/N):
```

## Production Patterns

### Pattern 1: Space Factory

```python
class SpaceFactory:
    @staticmethod
    def create_team_space(team_name: str, color: str):
        space_id = team_name.lower().replace(" ", "-")
        return {
            "id": space_id,
            "name": f"{team_name} Team",
            "description": f"Space for {team_name} team",
            "color": color,
            "initials": team_name[:2].upper()
        }
```

### Pattern 2: Space Templates

```python
SPACE_TEMPLATES = {
    "development": {
        "color": "#95E1D3",
        "disabled_features": []
    },
    "production": {
        "color": "#FF6B6B",
        "disabled_features": ["dev_tools", "advancedSettings"]
    }
}

def create_from_template(space_id, name, template_name):
    template = SPACE_TEMPLATES[template_name]
    return client.spaces.create(
        id=space_id,
        name=name,
        **template
    )
```

## Best Practices

1. **Track created spaces** for cleanup
2. **Use descriptive IDs** (lowercase, hyphens)
3. **Set colors** for visual distinction
4. **Handle errors** gracefully
5. **Verify operations** succeeded
6. **Clean up** test spaces

## Next Steps

- [Simple Example](simple.md) - Basic space creation
- [Spaces User Guide](../../user-guide/spaces.md) - Detailed documentation
- {doc}`Space-Scoped Operations <../../user-guide/spaces>`

## Related Documentation

- [Spaces API Reference](../../api-reference/spaces.rst)
- [Error Handling](../../user-guide/error-handling.md)
- [Space Migration Guide](../../migration-guides/space-support.md)
