# Saved Objects Management Example

**File**: `examples/saved_objects_management.py`

Comprehensive example demonstrating all saved objects operations with production-ready patterns.

## Overview

This example shows:
- Creating objects with auto-generated and custom IDs
- Retrieving and updating objects
- Version control and optimistic concurrency
- Space-scoped operations
- Error handling

## Key Features

### SavedObjectsManager Class

```python
class SavedObjectsManager:
    """Manager class for saved objects operations."""

    def __init__(self, client):
        self.client = client
        self.created_objects = []  # Track for cleanup
```

### Create Visualization

```python
def create_visualization(self, title, obj_id=None, space_id=None):
    """Create a visualization saved object."""
    attributes = {
        "title": title,
        "visState": json.dumps({"type": "line", "params": {}}),
        "uiStateJSON": "{}",
        "description": f"Visualization created via API: {title}",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": "", "filter": []})
        },
    }

    response = client.saved_objects.create(
        type="visualization",
        attributes=attributes,
        id=obj_id,
        space_id=space_id,
    )
    saved_object = response.body
    self.created_objects.append((saved_object["type"], saved_object["id"], space_id))
    return saved_object
```

## What the Example Demonstrates

1. **Create with auto-generated ID**
2. **Create with specific ID**
3. **Retrieve objects**
4. **Update without version** (simple update)
5. **Update with version** (optimistic concurrency)
6. **Demonstrate version conflict**
7. **Delete object**
8. **Verify deletion**
9. **Space-scoped operations** (optional)

## Running the Example

```bash
python examples/saved_objects_management.py
```

## Expected Output

```
================================================================================
SAVED OBJECTS MANAGEMENT DEMO
================================================================================

================================================================================
1. CREATE WITH AUTO-GENERATED ID
================================================================================
📝 Creating visualization: Auto-Generated ID Visualization
✓ Created: abc123-def456

================================================================================
2. CREATE WITH SPECIFIC ID
================================================================================
📝 Creating visualization: Custom ID Visualization
✓ Created: custom-viz-12345678

================================================================================
3. RETRIEVE OBJECTS
================================================================================
🔍 Retrieving visualization: abc123-def456
✓ Retrieved: Auto-Generated ID Visualization
  Version: WzEsMV0=

🔍 Retrieving visualization: custom-viz-12345678
✓ Retrieved: Custom ID Visualization
  Version: WzEsMV0=

================================================================================
4. UPDATE WITHOUT VERSION
================================================================================
✏️  Updating visualization: abc123-def456
✓ Updated: Updated Auto-Generated Visualization
  New version: WzIsMV0=

================================================================================
5. UPDATE WITH VERSION (OPTIMISTIC CONCURRENCY)
================================================================================
🔍 Retrieving visualization: custom-viz-12345678
✓ Retrieved: Custom ID Visualization
  Version: WzEsMV0=

✏️  Updating visualization: custom-viz-12345678
✓ Updated: Updated Custom Visualization
  New version: WzIsMV0=

================================================================================
6. DEMONSTRATE VERSION CONFLICT
================================================================================
Attempting update with old version...
✓ Conflict detected as expected

================================================================================
7. DELETE OBJECT
================================================================================
🗑️  Deleting visualization: abc123-def456
✓ Deleted: abc123-def456

================================================================================
8. VERIFY DELETION
================================================================================
Attempting to retrieve deleted object...
✓ Object not found as expected

================================================================================
9. SPACE-SCOPED OPERATIONS (OPTIONAL)
================================================================================
Creating a test space...
✓ Created space: test-space-12345678

📝 Creating visualization: Space-Scoped Visualization
✓ Created: xyz789-abc123
  Space: test-space-12345678

🔍 Retrieving visualization: xyz789-abc123
✓ Retrieved: Space-Scoped Visualization

Verifying object is not in default space...
✓ Object not found in default space (as expected)

Cleaning up test space...
✓ Deleted space: test-space-12345678

================================================================================
DEMO COMPLETE
================================================================================

🎉 All operations completed successfully!

2 object(s) were created during this demo.
Delete all created objects? (y/N):
```

## Production Patterns

### Pattern 1: Object Factory

```python
class SavedObjectFactory:
    @staticmethod
    def create_visualization(title, vis_type="line"):
        return {
            "title": title,
            "visState": json.dumps({"type": vis_type, "params": {}}),
            "uiStateJSON": "{}",
            "description": f"{title} visualization",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"}
        }
```

### Pattern 2: Bulk Operations

```python
def create_multiple_visualizations(titles):
    """Create multiple visualizations efficiently."""
    created = []
    for title in titles:
        try:
            viz = manager.create_visualization(title)
            created.append(viz)
        except Exception as e:
            logger.error(f"Failed to create {title}: {e}")
    return created
```

### Pattern 3: Safe Updates

```python
def safe_update(obj_type, obj_id, new_attributes, max_retries=3):
    """Update with automatic retry on version conflict."""
    for attempt in range(max_retries):
        try:
            current = client.saved_objects.get(type=obj_type, id=obj_id)
            return client.saved_objects.update(
                type=obj_type,
                id=obj_id,
                attributes=new_attributes,
                version=current.body["version"]
            )
        except ConflictError:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (2 ** attempt))
```

## Best Practices

1. **Track created objects** for cleanup
2. **Use versions** for updates
3. **Handle conflicts** gracefully
4. **Validate attributes** before creation
5. **Clean up** test objects

## Next Steps

- [Saved Objects User Guide](../../user-guide/saved-objects.md)
- [API Reference](../../api-reference/saved-objects.rst)
- [Space-Scoped Operations](../spaces/index.md)

## Related Documentation

- [Saved Objects API Reference](../../api-reference/saved-objects.rst)
- [Error Handling](../../user-guide/error-handling.md)
- [Spaces](../../user-guide/spaces.md)
