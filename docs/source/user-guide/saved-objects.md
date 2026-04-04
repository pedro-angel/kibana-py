# Saved Objects

Saved Objects are the core entities in Kibana that represent dashboards, visualizations, index patterns, and other configuration items. The Saved Objects API allows you to programmatically create, read, update, and delete these objects.

## Overview

Saved Objects allow you to:
- Create and manage dashboards programmatically
- Import and export visualizations
- Manage index patterns and searches
- Organize objects across spaces
- Implement backup and restore workflows

## Common Saved Object Types

- **`dashboard`**: Dashboards
- **`visualization`**: Visualizations (charts, graphs, etc.)
- **`index-pattern`**: Index patterns (data views)
- **`search`**: Saved searches
- **`config`**: Kibana configuration
- **`lens`**: Lens visualizations
- **`map`**: Maps

## Creating Saved Objects

### Basic Creation

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Create a visualization
viz = client.saved_objects.create(
    type="visualization",
    attributes={
        "title": "My Visualization",
        "visState": "{}",
        "uiStateJSON": "{}",
        "description": "Created via API",
        "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"}
    },
    id="my-viz-id"  # Optional - auto-generated if not provided
)

print(f"Created: {viz.body['id']}")
client.close()
```

### Creating with References

```python
# Create visualization that references an index pattern
viz = client.saved_objects.create(
    type="visualization",
    attributes={
        "title": "Sales Chart",
        "visState": "{}",
        "uiStateJSON": "{}",
        "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"}
    },
    references=[
        {
            "id": "my-index-pattern-id",
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern"
        }
    ]
)
```

### Overwriting Existing Objects

```python
# Create or overwrite existing object
viz = client.saved_objects.create(
    type="visualization",
    attributes={"title": "My Viz"},
    id="my-viz-id",
    overwrite=True  # Overwrite if exists
)
```

## Reading Saved Objects

### Get by ID

```python
# Get a saved object
obj = client.saved_objects.get(
    type="visualization",
    id="my-viz-id"
)

print(f"Title: {obj.body['attributes']['title']}")
print(f"Version: {obj.body['version']}")
```

### Finding Objects

```python
# Search for saved objects
results = client.saved_objects.find(
    type=["dashboard", "visualization"],
    search="sales",
    page=1,
    per_page=20,
    sort_field="updated_at",
    fields=["title", "description"]
)

for obj in results.body['saved_objects']:
    print(f"- {obj['attributes']['title']} ({obj['type']})")
```

### Advanced Search

```python
# Search with KQL filter
results = client.saved_objects.find(
    type="dashboard",
    filter="dashboard.attributes.title:*sales*",
    sort_field="updated_at",
    sort_order="desc"
)
```

## Updating Saved Objects

### Basic Update

```python
# Update saved object
updated = client.saved_objects.update(
    type="visualization",
    id="my-viz-id",
    attributes={"title": "Updated Title"}
)
```

### Update with Version Control

```python
# Get current version
obj = client.saved_objects.get(type="visualization", id="my-viz-id")
current_version = obj.body["version"]

# Update with version check (optimistic concurrency control)
try:
    updated = client.saved_objects.update(
        type="visualization",
        id="my-viz-id",
        attributes={"title": "Updated Title"},
        version=current_version  # Fails if object was modified
    )
except ConflictError:
    print("Object was modified by another process")
```

## Deleting Saved Objects

### Basic Deletion

```python
# Delete a saved object
client.saved_objects.delete(
    type="visualization",
    id="my-viz-id"
)
```

### Force Delete

```python
# Force delete even if object has references
client.saved_objects.delete(
    type="visualization",
    id="my-viz-id",
    force=True
)
```

## Bulk Operations

### Bulk Create

```python
# Create multiple objects in one request
results = client.saved_objects.bulk_create(
    objects=[
        {
            "type": "dashboard",
            "attributes": {"title": "Dashboard 1"}
        },
        {
            "type": "dashboard",
            "attributes": {"title": "Dashboard 2"}
        },
        {
            "type": "visualization",
            "attributes": {"title": "Viz 1"}
        }
    ],
    overwrite=False
)

for result in results.body['saved_objects']:
    if result.get('error'):
        print(f"Error: {result['error']['message']}")
    else:
        print(f"Created: {result['id']}")
```

### Bulk Get

```python
# Get multiple objects in one request
results = client.saved_objects.bulk_get(
    objects=[
        {"type": "dashboard", "id": "dash-1"},
        {"type": "visualization", "id": "viz-1"},
        {"type": "dashboard", "id": "dash-2"}
    ]
)

for obj in results.body['saved_objects']:
    if obj.get('error'):
        print(f"Not found: {obj['id']}")
    else:
        print(f"Found: {obj['attributes']['title']}")
```

### Bulk Update

```python
# Update multiple objects in one request
results = client.saved_objects.bulk_update(
    objects=[
        {
            "type": "dashboard",
            "id": "dash-1",
            "attributes": {"title": "New Title 1"}
        },
        {
            "type": "visualization",
            "id": "viz-1",
            "attributes": {"title": "New Title 2"}
        }
    ]
)
```

## Export and Import

### Exporting Objects

```python
# Export specific objects
export_data = client.saved_objects.export(
    objects=[
        {"type": "dashboard", "id": "dash-1"},
        {"type": "visualization", "id": "viz-1"}
    ],
    include_references_deep=True,  # Include all referenced objects
    exclude_export_details=False
)

# Save to file
with open("export.ndjson", "wb") as f:
    f.write(export_data.body)
```

### Exporting by Type

```python
# Export all dashboards
export_data = client.saved_objects.export(
    type=["dashboard"],
    include_references_deep=True
)
```

### Importing Objects

```python
# Import from file
with open("export.ndjson", "rb") as f:
    import_data = f.read()

results = client.saved_objects.import_objects(
    file=import_data,
    overwrite=False,
    create_new_copies=False
)

print(f"Success: {results.body['successCount']}")
print(f"Errors: {len(results.body.get('errors', []))}")
```

### Import with Options

```python
# Import with overwrite
results = client.saved_objects.import_objects(
    file=import_data,
    overwrite=True,  # Overwrite existing objects
    create_new_copies=False
)

# Import as new copies (new IDs)
results = client.saved_objects.import_objects(
    file=import_data,
    overwrite=False,
    create_new_copies=True  # Create new objects with new IDs
)
```

## Space-Scoped Operations

### Individual Space Parameters

```python
# Create in specific space
dashboard = client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Dashboard"},
    space_id="marketing"
)

# Get from specific space
obj = client.saved_objects.get(
    type="dashboard",
    id="dash-1",
    space_id="marketing"
)

# Find in specific space
results = client.saved_objects.find(
    type=["dashboard"],
    search="sales",
    space_id="marketing"
)
```

### Space-Scoped Client

```python
# Create space-scoped client
marketing_client = client.space("marketing")

# All operations automatically use marketing space
dashboard = marketing_client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Dashboard"}
)

viz = marketing_client.saved_objects.create(
    type="visualization",
    attributes={"title": "Marketing Chart"}
)
```

### Cross-Space Operations

```python
# Export from one space
export_data = client.saved_objects.export(
    type=["dashboard"],
    space_id="development"
)

# Import to another space
results = client.saved_objects.import_objects(
    file=export_data.body,
    space_id="production",
    overwrite=False
)
```

## Best Practices

### 1. Use Version Control

```python
# Always use version control for updates
obj = client.saved_objects.get(type="dashboard", id="dash-1")
current_version = obj.body["version"]

updated = client.saved_objects.update(
    type="dashboard",
    id="dash-1",
    attributes={"title": "New Title"},
    version=current_version
)
```

### 2. Handle References Properly

```python
# Include all references when exporting
export_data = client.saved_objects.export(
    objects=[{"type": "dashboard", "id": "dash-1"}],
    include_references_deep=True  # Include visualizations, index patterns, etc.
)
```

### 3. Use Bulk Operations

```python
# More efficient than individual operations
results = client.saved_objects.bulk_create(
    objects=[
        {"type": "dashboard", "attributes": {"title": f"Dashboard {i}"}}
        for i in range(10)
    ]
)
```

### 4. Implement Backup Workflows

```python
def backup_space(client, space_id, backup_file):
    """Backup all objects from a space."""
    export_data = client.saved_objects.export(
        type=["dashboard", "visualization", "search", "index-pattern"],
        space_id=space_id,
        include_references_deep=True
    )

    with open(backup_file, "wb") as f:
        f.write(export_data.body)

    print(f"Backed up space '{space_id}' to {backup_file}")

def restore_space(client, space_id, backup_file):
    """Restore objects to a space."""
    with open(backup_file, "rb") as f:
        import_data = f.read()

    results = client.saved_objects.import_objects(
        file=import_data,
        space_id=space_id,
        overwrite=True
    )

    print(f"Restored {results.body['successCount']} objects to space '{space_id}'")
```

## Error Handling

```python
from kibana import Kibana
from kibana.exceptions import (
    NotFoundError,
    ConflictError,
    BadRequestError
)

try:
    # Create saved object
    obj = client.saved_objects.create(
        type="dashboard",
        attributes={"title": "My Dashboard"},
        space_id="marketing"
    )

    # Update with version control
    updated = client.saved_objects.update(
        type="dashboard",
        id=obj.body["id"],
        attributes={"title": "Updated Dashboard"},
        version=obj.body["version"],
        space_id="marketing"
    )

except NotFoundError as e:
    print(f"Object not found: {e.message}")
except ConflictError as e:
    print(f"Version conflict: {e.message}")
except BadRequestError as e:
    print(f"Invalid request: {e.message}")
```

## Troubleshooting

### Object Not Found

**Problem**: `NotFoundError: Saved object not found`

**Solutions**:
- Verify the object ID and type are correct
- Check if the object exists in the correct space
- Ensure you have permission to access the object

### Version Conflicts

**Problem**: `ConflictError: Version conflict`

**Solutions**:
- Fetch the latest version before updating
- Implement retry logic with exponential backoff
- Use optimistic concurrency control

### Import Failures

**Problem**: Import fails with errors

**Solutions**:
- Check for conflicting IDs (use `overwrite=True` or `create_new_copies=True`)
- Verify all referenced objects are included in the export
- Check for invalid object attributes

## Next Steps

- Learn about [Spaces](spaces.md) for multi-tenancy
- Explore [Connectors](connectors.md) for automation
- Check [Error Handling](error-handling.md) for comprehensive error management
- See [Examples](../examples/saved-objects/index.md) for practical code samples
