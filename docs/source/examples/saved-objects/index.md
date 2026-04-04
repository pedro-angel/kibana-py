# Saved Objects Examples

Saved Objects are Kibana's core entities representing dashboards, visualizations, index patterns, and other configuration items. This section demonstrates how to manage them programmatically.

```{toctree}
:maxdepth: 2
:caption: Saved Objects Examples

management
```

## Overview

Learn how to:
- Create saved objects with and without IDs
- Retrieve and update saved objects
- Handle version control
- Work with space-scoped objects
- Manage object lifecycle

## Example File

### saved_objects_management.py

**Purpose**: Comprehensive saved objects management

**What You'll Learn**:
- CRUD operations for saved objects
- Optimistic concurrency control with versions
- Space-scoped object management
- Error handling patterns
- Bulk operations

[View Management Example →](management.md)

## What Are Saved Objects?

Saved objects store Kibana configuration and user-created content:

- **Dashboards** - Dashboard layouts and configurations
- **Visualizations** - Charts, graphs, and visual elements
- **Index Patterns** - Elasticsearch index configurations
- **Searches** - Saved search queries
- **Config** - Kibana configuration settings

## Basic Operations

### Create

```python
# Auto-generated ID
viz = client.saved_objects.create(
    type="visualization",
    attributes={
        "title": "My Visualization",
        "visState": "{}",
        "uiStateJSON": "{}",
        "description": "Created via API",
        "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"}
    }
)

# Specific ID
viz = client.saved_objects.create(
    type="visualization",
    id="my-viz-id",
    attributes={...}
)
```

### Read

```python
obj = client.saved_objects.get(
    type="visualization",
    id="my-viz-id"
)
print(obj.body["attributes"]["title"])
```

### Update

```python
updated = client.saved_objects.update(
    type="visualization",
    id="my-viz-id",
    attributes={"title": "Updated Title"}
)
```

### Delete

```python
client.saved_objects.delete(
    type="visualization",
    id="my-viz-id"
)
```

## Version Control

Saved objects support optimistic concurrency:

```python
# Get current version
obj = client.saved_objects.get(type="visualization", id="my-viz")
current_version = obj.body["version"]

# Update with version check
updated = client.saved_objects.update(
    type="visualization",
    id="my-viz",
    attributes={"title": "New Title"},
    version=current_version  # Fails if modified
)
```

## Space-Scoped Objects

Create objects in specific spaces:

```python
# Method 1: space_id parameter
viz = client.saved_objects.create(
    type="visualization",
    attributes={...},
    space_id="marketing-team"
)

# Method 2: Space-scoped client
marketing_client = client.space("marketing-team")
viz = marketing_client.saved_objects.create(
    type="visualization",
    attributes={...}
)
```

## Common Object Types

### Visualization

```python
attributes = {
    "title": "Sales Chart",
    "visState": json.dumps({"type": "line", "params": {}}),
    "uiStateJSON": "{}",
    "description": "Monthly sales visualization",
    "version": 1,
    "kibanaSavedObjectMeta": {
        "searchSourceJSON": json.dumps({"query": "", "filter": []})
    }
}
```

### Dashboard

```python
attributes = {
    "title": "Sales Dashboard",
    "description": "Overview of sales metrics",
    "panelsJSON": "[]",
    "optionsJSON": "{}",
    "version": 1,
    "timeRestore": False,
    "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"}
}
```

### Index Pattern

```python
attributes = {
    "title": "logs-*",
    "timeFieldName": "@timestamp",
    "fields": "[]",
    "fieldFormatMap": "{}"
}
```

## Error Handling

```python
from kibana.exceptions import ConflictError, NotFoundError

try:
    obj = client.saved_objects.create(
        type="visualization",
        id="my-viz",
        attributes={...}
    )
except ConflictError:
    print("Object with this ID already exists")

try:
    obj = client.saved_objects.get(type="visualization", id="nonexistent")
except NotFoundError:
    print("Object not found")

try:
    updated = client.saved_objects.update(
        type="visualization",
        id="my-viz",
        attributes={...},
        version=old_version
    )
except ConflictError:
    print("Version conflict - object was modified")
```

## Best Practices

1. **Use auto-generated IDs** unless you need specific IDs
2. **Include version** for updates to prevent conflicts
3. **Validate attributes** before creating objects
4. **Clean up** test objects
5. **Use spaces** for multi-tenancy

## Next Steps

- [Management Example](management.md) - Full CRUD operations
- [Saved Objects User Guide](../../user-guide/saved-objects.md)
- [API Reference](../../api-reference/saved-objects.rst)

## Related Documentation

- [Saved Objects API Reference](../../api-reference/saved-objects.rst)
- [Spaces](../spaces/index.md)
- [Error Handling](../../user-guide/error-handling.md)
