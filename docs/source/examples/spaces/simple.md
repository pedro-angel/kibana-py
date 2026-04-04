# Simple Space Example

**File**: `examples/simple_space.py`

Minimal example showing how to create a Kibana space, verify it exists, and clean it up.

## Quick Start

```python
from kibana import Kibana

client = Kibana("http://localhost:5601")

# Create a space
space = client.spaces.create(
    id="my-team-space",
    name="My Team Space",
    description="A space for my team's dashboards"
)

print(f"✓ Created: {space.body['id']}")
print(f"  URL: http://localhost:5601/s/{space.body['id']}/app/home")

# Verify it exists
info = client.spaces.get(id="my-team-space")
print(f"✓ Verified: {info.body['name']}")

# Clean up
client.spaces.delete(id="my-team-space")
client.close()
```

## What You'll Learn

- Create a space with minimal configuration
- Access space URL
- Verify space creation
- Delete a space

## Running the Example

```bash
python examples/simple_space.py
```

## Expected Output

```
Creating space...
✓ Created space: my-team-space
  Name: My Team Space
  Description: A space for my team's dashboards and visualizations

✓ Space verified: My Team Space

🎉 Success! Your space is ready to use.
   Space ID: my-team-space
   Access it at: http://localhost:5601/s/my-team-space/app/home

Space 'My Team Space' was created for this example.
Delete the space? (y/N):
```

## Next Steps

- [Space Management Example](management.md) - Full CRUD operations
- [Spaces User Guide](../../user-guide/spaces.md) - Detailed documentation
