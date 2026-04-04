# Space Examples

Kibana Spaces allow you to organize dashboards, visualizations, and saved objects into separate, isolated areas. This section demonstrates how to create and manage spaces programmatically for multi-tenancy scenarios.

```{toctree}
:maxdepth: 2
:caption: Space Examples

simple
management
```

## Overview

The space examples show you how to:

- Create and configure Kibana spaces
- Manage space properties and features
- Perform CRUD operations on spaces
- Implement space-scoped operations
- Handle multi-tenancy scenarios

## Example Files

### simple_space.py

**Purpose**: Minimal code to create and manage a space

**What You'll Learn**:
- Create a space in ~40 lines of code
- Verify space exists
- Interactive cleanup

**When to Use**: Quick prototyping or learning space basics

[View Simple Example →](simple.md)

### space_management.py

**Purpose**: Comprehensive space management with all CRUD operations

**What You'll Learn**:
- Class-based space management
- Create, read, update, delete operations
- Space configuration options
- Error handling patterns
- Production-ready code

**When to Use**: Building applications that manage multiple spaces

[View Management Example →](management.md)

## What Are Spaces?

Spaces provide logical isolation within a single Kibana instance:

- **Separate dashboards and visualizations** for different teams
- **Control feature access** per space
- **Implement multi-tenancy** without multiple Kibana instances
- **Organize saved objects** by project, team, or environment

## Basic Space Creation

```python
from kibana import Kibana

client = Kibana("http://localhost:5601")

# Create a space
space = client.spaces.create(
    id="marketing-team",
    name="Marketing Team",
    description="Space for marketing dashboards",
    color="#FF6B6B",
    initials="MK"
)

print(f"Space URL: http://localhost:5601/s/{space.body['id']}/app/home")
```

## Space Configuration Options

### Required Fields

- **`id`**: URL-friendly identifier (lowercase, hyphens, no spaces)
- **`name`**: Display name shown in Kibana UI

### Optional Fields

- **`description`**: Detailed description of the space
- **`color`**: Hex color code for visual identification (e.g., "#FF0000")
- **`initials`**: 1-2 character abbreviation shown in space selector
- **`disabled_features`**: List of Kibana features to disable in this space

### Example with All Options

```python
space = client.spaces.create(
    id="engineering-prod",
    name="Engineering - Production",
    description="Production monitoring and dashboards for engineering team",
    color="#4ECDC4",
    initials="EP",
    disabled_features=["dev_tools", "advancedSettings"]
)
```

## Common Use Cases

### 1. Team Isolation

Create separate spaces for different teams:

```python
teams = [
    {"id": "marketing", "name": "Marketing Team", "color": "#FF6B6B"},
    {"id": "sales", "name": "Sales Team", "color": "#4ECDC4"},
    {"id": "engineering", "name": "Engineering Team", "color": "#95E1D3"}
]

for team in teams:
    client.spaces.create(**team)
```

### 2. Environment Separation

Separate development, staging, and production:

```python
environments = ["dev", "staging", "prod"]

for env in environments:
    client.spaces.create(
        id=f"app-{env}",
        name=f"Application - {env.upper()}",
        color={"dev": "#95E1D3", "staging": "#FFD93D", "prod": "#FF6B6B"}[env]
    )
```

### 3. Project-Based Organization

Create spaces for different projects:

```python
projects = ["project-alpha", "project-beta", "project-gamma"]

for project in projects:
    client.spaces.create(
        id=project,
        name=project.replace("-", " ").title(),
        description=f"Dashboards and visualizations for {project}"
    )
```

## Space-Scoped Operations

### Method 1: space_id Parameter

Pass `space_id` to individual operations:

```python
# Create connector in specific space
connector = client.actions.create(
    name="Marketing Connector",
    connector_type_id=".index",
    config={"index": "marketing-data"},
    space_id="marketing-team"
)

# Create saved object in specific space
viz = client.saved_objects.create(
    type="visualization",
    attributes={"title": "Marketing Dashboard"},
    space_id="marketing-team"
)
```

### Method 2: Space-Scoped Client

Create a client scoped to a specific space:

```python
# Create space-scoped client
marketing_client = client.space("marketing-team")

# All operations use the marketing space
connector = marketing_client.actions.create(
    name="Marketing Connector",
    connector_type_id=".index",
    config={"index": "marketing-data"}
)

viz = marketing_client.saved_objects.create(
    type="visualization",
    attributes={"title": "Marketing Dashboard"}
)
```

**Benefits of Space-Scoped Client**:
- Cleaner code for multiple operations
- Automatic space validation on creation
- No need to pass `space_id` to each method

## Disabling Features

Control which Kibana features are available in a space:

```python
# Disable developer tools and advanced settings
client.spaces.create(
    id="restricted-space",
    name="Restricted Space",
    disabled_features=["dev_tools", "advancedSettings", "indexPatterns"]
)
```

Common features to disable:
- `dev_tools` - Dev Tools console
- `advancedSettings` - Advanced Settings
- `indexPatterns` - Index Pattern management
- `savedObjectsManagement` - Saved Objects management
- `timelion` - Timelion
- `graph` - Graph

## Error Handling

```python
from kibana.exceptions import ConflictError, NotFoundError, SpaceNotFoundError

try:
    space = client.spaces.create(id="my-space", name="My Space")
except ConflictError:
    print("Space already exists")
except BadRequestError as e:
    print(f"Invalid configuration: {e}")

try:
    space = client.spaces.get(id="nonexistent")
except NotFoundError:
    print("Space not found")

try:
    # Create resource in nonexistent space
    connector = client.actions.create(
        name="Test",
        connector_type_id=".index",
        config={},
        space_id="nonexistent-space"
    )
except SpaceNotFoundError as e:
    print(f"Space does not exist: {e.space_id}")
```

## Space Validation

By default, space existence is validated and cached:

```python
# Validation enabled (default)
connector = client.actions.create(
    name="Test",
    connector_type_id=".index",
    config={},
    space_id="marketing"  # Validates space exists
)

# Disable validation for performance
fast_client = client.space("marketing", validate=False)
connector = fast_client.actions.create(
    name="Test",
    connector_type_id=".index",
    config={}
)
```

## Best Practices

### 1. Use Descriptive IDs

```python
# Good: Clear and descriptive
id="engineering-production"

# Avoid: Cryptic or unclear
id="eng-prod-1"
```

### 2. Set Colors for Visual Distinction

```python
# Use distinct colors for easy identification
spaces = {
    "dev": "#95E1D3",      # Green
    "staging": "#FFD93D",  # Yellow
    "prod": "#FF6B6B"      # Red
}
```

### 3. Document Space Purpose

```python
client.spaces.create(
    id="analytics-team",
    name="Analytics Team",
    description="Business intelligence dashboards and reports for the analytics team. Includes sales metrics, customer analytics, and performance KPIs."
)
```

### 4. Clean Up Test Spaces

```python
# Always clean up temporary spaces
try:
    # Create and use space
    space = client.spaces.create(id="test-space", name="Test")
    # ... use space ...
finally:
    client.spaces.delete(id="test-space")
```

## Next Steps

1. Start with the [Simple Example](simple.md) to understand basics
2. Study the [Management Example](management.md) for production patterns
3. Explore [Space-Scoped Operations](../../user-guide/spaces.md) in the user guide
4. Review {doc}`Multi-Tenancy Patterns <../../user-guide/spaces>` for advanced scenarios

## Related Documentation

- [Spaces API Reference](../../api-reference/spaces.rst)
- [Spaces User Guide](../../user-guide/spaces.md)
- [Space Migration Guide](../../migration-guides/space-support.md)
- [Error Handling](../../user-guide/error-handling.md)
