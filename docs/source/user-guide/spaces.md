# Spaces

Kibana Spaces provide multi-tenancy by isolating dashboards, visualizations, connectors, and other resources. The kibana-py client library provides comprehensive space support across all API clients.

## Overview

Spaces allow you to:
- Organize resources by team, project, or environment
- Implement multi-tenancy with isolated resource access
- Control feature availability per space
- Manage permissions and access control

### Supported APIs

All the following APIs support space-scoped operations:

- **Actions API**: Connectors and actions
- **Saved Objects API**: Dashboards, visualizations, index patterns, etc.
- **Spaces API**: Space management (inherently space-aware)

## Space Support Patterns

The kibana-py library provides two complementary patterns for working with spaces:

1. **Individual Space Parameters**: Add `space_id` parameter to specific method calls
2. **Space-Scoped Clients**: Create client instances that automatically operate within a specific space

Both patterns can be used together and provide the same underlying functionality.

## Managing Spaces

### Creating a Space

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Create a space
space = client.spaces.create(
    id="marketing",
    name="Marketing Team",
    description="Space for marketing team's dashboards and visualizations",
    color="#FF6B6B",
    initials="MK",
    disabled_features=["dev_tools", "advancedSettings"]
)

print(f"Space URL: http://localhost:5601/s/{space.body['id']}/app/home")
client.close()
```

**Parameters:**
- `id` (required): Unique identifier for the space (URL-friendly, lowercase, no spaces)
- `name` (required): Display name for the space
- `description` (optional): Description of the space's purpose
- `color` (optional): Hex color code for the space (e.g., "#FF0000")
- `initials` (optional): Initials to display for the space (1-2 characters)
- `disabled_features` (optional): List of feature IDs to disable in this space

### Getting a Space

```python
# Get space by ID
space = client.spaces.get(id="marketing")
print(f"Space name: {space.body['name']}")
print(f"Description: {space.body['description']}")
```

### Listing All Spaces

```python
# Get all spaces
spaces = client.spaces.get_all()

for space in spaces.body:
    print(f"- {space['name']} ({space['id']})")
    print(f"  Color: {space.get('color', 'default')}")
    print(f"  Disabled features: {space.get('disabledFeatures', [])}")
```

### Updating a Space

```python
# Update space properties
updated = client.spaces.update(
    id="marketing",
    name="Marketing & Sales Team",
    description="Updated description for combined team",
    color="#00FF00"
)
```

### Deleting a Space

```python
# Delete a space (this also deletes all objects in the space)
client.spaces.delete(id="marketing")
print("Space deleted successfully")
```

:::{warning}
Deleting a space permanently deletes all saved objects within that space. This action cannot be undone.
:::

(space-scoped-operations)=
## Space-Scoped Operations

### Individual Space Parameters

Add the `space_id` parameter to any method that supports space-scoped operations:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Create connector in specific space
connector = client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://marketing.example.com/webhook"},
    space_id="marketing"  # Operates in 'marketing' space
)

# Create saved object in specific space
dashboard = client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Dashboard"},
    space_id="marketing"  # Same space as connector
)

# Operations without space_id use the default space
global_connector = client.actions.create(
    name="Global Webhook",
    connector_type_id=".webhook",
    config={"url": "https://global.example.com/webhook"}
    # No space_id = default space
)

client.close()
```

### Space-Scoped Clients

Create a client instance that automatically operates within a specific space:

```python
from kibana import Kibana

# Create main client
client = Kibana("http://localhost:5601", api_key="your_api_key")

# Create space-scoped client (validates space exists immediately)
marketing_client = client.space("marketing")

# All operations automatically use the marketing space
connector = marketing_client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://marketing.example.com/webhook"}
    # No space_id needed - automatically uses 'marketing'
)

dashboard = marketing_client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Dashboard"}
    # No space_id needed - automatically uses 'marketing'
)

client.close()
```

### Overriding Space Context

Even with space-scoped clients, you can override the space for specific operations:

```python
marketing_client = client.space("marketing")

# This connector goes to marketing space (default)
marketing_connector = marketing_client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://marketing.example.com/webhook"}
)

# Override to use sales space for this operation
sales_connector = marketing_client.actions.create(
    name="Sales Webhook",
    connector_type_id=".webhook",
    config={"url": "https://sales.example.com/webhook"},
    space_id="sales"  # Override default space
)

# Use default space for this operation
global_connector = marketing_client.actions.create(
    name="Global Webhook",
    connector_type_id=".webhook",
    config={"url": "https://global.example.com/webhook"},
    space_id=None  # Explicitly use default space
)
```

## Validation and Caching

### Automatic Space Validation

By default, the client validates that spaces exist before performing operations:

```python
# This will validate that 'marketing' space exists
connector = client.actions.create(
    name="Test Connector",
    connector_type_id=".index",
    config={"index": "test"},
    space_id="marketing"  # Validates space exists
)

# If space doesn't exist, raises SpaceNotFoundError
from kibana.exceptions import SpaceNotFoundError

try:
    connector = client.actions.create(
        name="Test Connector",
        connector_type_id=".index",
        config={"index": "test"},
        space_id="nonexistent"
    )
except SpaceNotFoundError as e:
    print(f"Space not found: {e.space_id}")
```

### Validation Caching

Space validation results are cached for 5 minutes by default to improve performance:

```python
# First call validates space (API call to /api/spaces/space/marketing)
connector1 = client.actions.create(
    name="Connector 1",
    connector_type_id=".index",
    config={"index": "test1"},
    space_id="marketing"
)

# Second call uses cached result (no additional API call)
connector2 = client.actions.create(
    name="Connector 2",
    connector_type_id=".index",
    config={"index": "test2"},
    space_id="marketing"  # Uses cached validation
)
```

### Disabling Validation

For performance-critical scenarios, you can disable validation:

```python
# Disable validation when creating space-scoped client
fast_client = client.space("marketing", validate=False)
connector = fast_client.actions.create(
    name="Fast Connector",
    connector_type_id=".index",
    config={"index": "test"}
    # No validation performed
)

# Disable validation for specific operation
connector = client.actions.create(
    name="Fast Connector",
    connector_type_id=".index",
    config={"index": "test"},
    space_id="marketing",
    validate_space=False  # Skip validation for this operation
)
```

(multi-tenancy)=
## Multi-Tenancy Patterns

### Team-Based Isolation

```python
# Create spaces for different teams
teams = ["engineering", "marketing", "sales", "support"]

for team in teams:
    client.spaces.create(
        id=team,
        name=f"{team.capitalize()} Team",
        description=f"Space for {team} team resources"
    )

# Create team-specific resources
engineering_client = client.space("engineering")
engineering_connector = engineering_client.actions.create(
    name="Engineering Alerts",
    connector_type_id=".slack",
    secrets={"webhookUrl": "https://hooks.slack.com/engineering"}
)

marketing_client = client.space("marketing")
marketing_dashboard = marketing_client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Marketing Metrics"}
)
```

### Environment-Based Isolation

```python
# Create spaces for different environments
environments = {
    "development": {"color": "#00FF00", "initials": "DV"},
    "staging": {"color": "#FFA500", "initials": "ST"},
    "production": {"color": "#FF0000", "initials": "PR"}
}

for env_id, config in environments.items():
    client.spaces.create(
        id=env_id,
        name=f"{env_id.capitalize()} Environment",
        description=f"Resources for {env_id} environment",
        color=config["color"],
        initials=config["initials"]
    )

# Use environment-specific clients
dev_client = client.space("development")
prod_client = client.space("production")

# Development resources
dev_connector = dev_client.actions.create(
    name="Dev Webhook",
    connector_type_id=".webhook",
    config={"url": "https://dev.example.com/webhook"}
)

# Production resources (isolated from dev)
prod_connector = prod_client.actions.create(
    name="Prod Webhook",
    connector_type_id=".webhook",
    config={"url": "https://prod.example.com/webhook"}
)
```

### Project-Based Isolation

```python
# Create space for a specific project
project_space = client.spaces.create(
    id="project-alpha",
    name="Project Alpha",
    description="Dashboards and alerts for Project Alpha",
    color="#9B59B6",
    initials="PA",
    disabled_features=["dev_tools"]  # Restrict features
)

# Create project-specific client
project_client = client.space("project-alpha")

# All project resources in isolated space
project_connector = project_client.actions.create(
    name="Project Alpha Alerts",
    connector_type_id=".slack",
    secrets={"webhookUrl": "https://hooks.slack.com/project-alpha"}
)

project_dashboard = project_client.saved_objects.create(
    type="dashboard",
    attributes={"title": "Project Alpha Dashboard"}
)
```

## Performance Considerations

### Validation Overhead

Space validation adds minimal overhead:

- **First validation**: ~10-50ms (API call to check space existence)
- **Cached validations**: <1ms (cache lookup)
- **No validation**: 0ms overhead

### When to Disable Validation

Consider disabling validation in these scenarios:

1. **High-frequency operations**: When making many requests per second
2. **Known valid spaces**: When you're certain the space exists
3. **Performance-critical paths**: When every millisecond matters
4. **Batch operations**: When processing large numbers of items

```python
# High-frequency scenario
fast_client = client.space("marketing", validate=False)
for i in range(1000):
    connector = fast_client.actions.create(
        name=f"Connector {i}",
        connector_type_id=".index",
        config={"index": f"test-{i}"}
        # No validation overhead
    )
```

## Error Handling

### Space-Specific Exceptions

```python
from kibana.exceptions import SpaceNotFoundError, InvalidSpaceIdError

try:
    connector = client.actions.create(
        name="Test Connector",
        connector_type_id=".index",
        config={"index": "test"},
        space_id="nonexistent"
    )
except SpaceNotFoundError as e:
    print(f"Space '{e.space_id}' does not exist")
    # Handle space not found
except InvalidSpaceIdError as e:
    print(f"Invalid space ID format: '{e.space_id}'")
    # Handle invalid space ID format
```

### Enhanced Error Context

All API errors include space context when relevant:

```python
try:
    connector = client.actions.get(
        id="nonexistent-connector",
        space_id="marketing"
    )
except NotFoundError as e:
    print(f"Error: {e.message}")
    # Output: "[Space: marketing] Connector not found: nonexistent-connector"
```

## Best Practices

### 1. Choose the Right Pattern

**Use Individual Space Parameters When:**
- Making occasional space-scoped operations
- Working with multiple spaces in the same code
- Need fine-grained control over each operation

```python
# Good for mixed operations
global_connector = client.actions.create(name="Global", ...)
marketing_connector = client.actions.create(name="Marketing", ..., space_id="marketing")
sales_connector = client.actions.create(name="Sales", ..., space_id="sales")
```

**Use Space-Scoped Clients When:**
- Most operations target the same space
- Building space-specific functionality
- Want to avoid repeating space_id parameters

```python
# Good for space-focused operations
marketing_client = client.space("marketing")
connector = marketing_client.actions.create(name="Webhook", ...)
dashboard = marketing_client.saved_objects.create(type="dashboard", ...)
visualization = marketing_client.saved_objects.create(type="visualization", ...)
```

### 2. Validation Strategy

**Enable Validation (Default) When:**
- Developing and testing applications
- Working with user-provided space IDs
- Space existence is uncertain

**Disable Validation When:**
- High-frequency operations (>100 requests/second)
- Batch processing large datasets
- Spaces are guaranteed to exist
- Performance is critical

### 3. Resource Management

Clean up resources in the correct spaces:

```python
def create_and_cleanup_demo():
    # Create resources in specific space
    marketing_client = client.space("marketing")

    connector = marketing_client.actions.create(
        name="Demo Connector",
        connector_type_id=".index",
        config={"index": "demo"}
    )

    dashboard = marketing_client.saved_objects.create(
        type="dashboard",
        attributes={"title": "Demo Dashboard"}
    )

    try:
        # Use resources
        result = marketing_client.actions.execute(
            id=connector.body["id"],
            params={"documents": [{"message": "demo"}]}
        )
        return result
    finally:
        # Clean up in same space
        marketing_client.actions.delete(id=connector.body["id"])
        marketing_client.saved_objects.delete(
            type="dashboard",
            id=dashboard.body["id"]
        )
```

### 4. Feature Control

Use disabled_features to control what's available in each space:

```python
# Restrict features for external users
external_space = client.spaces.create(
    id="external-users",
    name="External Users",
    description="Limited access space for external users",
    disabled_features=[
        "dev_tools",
        "advancedSettings",
        "indexPatterns",
        "savedObjectsManagement"
    ]
)

# Full features for internal team
internal_space = client.spaces.create(
    id="internal-team",
    name="Internal Team",
    description="Full access space for internal team",
    disabled_features=[]  # All features enabled
)
```

## Troubleshooting

### Space Not Found Errors

**Problem**: `SpaceNotFoundError: Space not found: marketing`

**Solutions**:
```python
# Check if space exists
try:
    space = client.spaces.get(id="marketing")
    print(f"Space exists: {space.body['name']}")
except NotFoundError:
    print("Space does not exist")
    # Create the space
    client.spaces.create(
        id="marketing",
        name="Marketing Team"
    )
```

### Permission Denied

**Problem**: `AuthorizationException: Forbidden`

**Solutions**:
```python
# Check your permissions
try:
    spaces = client.spaces.get_all()
    print("Available spaces:")
    for space in spaces.body:
        print(f"  - {space['id']}: {space['name']}")
except AuthorizationException:
    print("No permission to list spaces")
    print("Check your API key or user permissions")
```

### Resources Not Found in Expected Space

**Problem**: Created resource in one space, can't find it in another

**Solution**:
```python
# Resources are isolated by space
marketing_client = client.space("marketing")
sales_client = client.space("sales")

# Create in marketing space
connector = marketing_client.actions.create(
    name="Marketing Connector",
    connector_type_id=".index",
    config={"index": "marketing"}
)

# Won't be found in sales space
try:
    sales_connector = sales_client.actions.get(id=connector.body["id"])
except NotFoundError:
    print("Connector not found in sales space (expected)")

# Will be found in marketing space
marketing_connector = marketing_client.actions.get(id=connector.body["id"])
print(f"Found in marketing space: {marketing_connector.body['name']}")
```

## Next Steps

- Learn about [Connectors](connectors.md) for space-scoped actions
- Explore [Saved Objects](saved-objects.md) for space-scoped dashboards
- Check [Error Handling](error-handling.md) for comprehensive error management
- See [Examples](../examples/spaces/index.md) for practical code samples
