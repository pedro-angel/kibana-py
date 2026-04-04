# Debug Connector Example

**File**: `examples/debug_connector.py`

This example helps you understand connector APIs in detail and troubleshoot issues by showing verbose output and API responses.

## Purpose

Perfect for:
- Understanding API responses
- Troubleshooting connector issues
- Learning connector types and capabilities
- Debugging configuration problems

## What You'll Learn

- List and inspect available connector types
- View detailed API responses
- Understand connector structure
- Debug common issues
- Verify connector operations

## Code Overview

The debug example walks through each step with detailed output:

### 1. List Existing Connectors

```python
connectors_response = client.actions.get_all()
connectors = connectors_response.body
print(f"✓ Found {len(connectors)} existing connectors")
for conn in connectors:
    print(f"  - {conn.get('name', 'Unknown')} ({conn.get('id', 'No ID')})")
```

**What This Shows**:
- All connectors currently in Kibana
- Connector names and IDs
- Helps identify existing connectors before creating new ones

### 2. List Available Connector Types

```python
types_response = client.actions.list_types()
types = types_response.body
print(f"✓ Found {len(types)} connector types")
for conn_type in types:
    print(f"  - {conn_type.get('id', 'Unknown')}: {conn_type.get('name', 'Unknown')}")
    if conn_type.get("id") == ".index":
        print(f"    ✓ Index connector available: {conn_type.get('enabled', 'Unknown status')}")
```

**What This Shows**:
- All available connector types in your Kibana instance
- Whether each type is enabled
- Specific details about the index connector

### 3. Create Connector with Verbose Output

```python
response = client.actions.create(
    name="Debug Index Connector",
    connector_type_id=".index",
    config={
        "index": "miconnectedindex",
        "refresh": True,
        "executionTimeField": "@timestamp",
    },
)

print(f"✓ Response type: {type(response)}")
print(f"✓ Response meta: {response.meta}")
print(f"✓ Connector data: {response.body}")
```

**What This Shows**:
- Response object structure
- HTTP metadata (status code, headers, etc.)
- Complete connector data including all fields

### 4. Verify Connector Creation

```python
connector_data = response.body
if isinstance(connector_data, dict) and "id" in connector_data:
    connector_id = connector_data["id"]
    print(f"✓ Created connector with ID: {connector_id}")
    print(f"✓ Connector name: {connector_data.get('name', 'Unknown')}")
    print(f"✓ Connector type: {connector_data.get('connector_type_id', 'Unknown')}")
```

**What This Shows**:
- How to safely extract data from responses
- All fields returned by the API
- Connector configuration details

## Understanding Connector Types

### Common Connector Types

The debug example helps you discover available types:

```
✓ Found 15 connector types
  - .email: Email
  - .index: Index
    ✓ Index connector available: True
  - .pagerduty: PagerDuty
  - .server-log: Server log
  - .servicenow: ServiceNow
  - .slack: Slack
  - .webhook: Webhook
  ...
```

### Connector Type Details

Each connector type has:
- **`id`**: Unique identifier (e.g., `.index`, `.webhook`)
- **`name`**: Display name
- **`enabled`**: Whether it's available in your Kibana instance
- **`enabled_in_config`**: Configuration-based availability
- **`enabled_in_license`**: License-based availability

## Response Structure

### Create Response

```python
{
    "id": "abc123-def456-ghi789",
    "name": "Debug Index Connector",
    "connector_type_id": ".index",
    "is_preconfigured": False,
    "is_deprecated": False,
    "is_missing_secrets": False,
    "config": {
        "index": "miconnectedindex",
        "refresh": True,
        "executionTimeField": "@timestamp"
    },
    "is_system_action": False
}
```

### List Types Response

```python
[
    {
        "id": ".index",
        "name": "Index",
        "enabled": True,
        "enabled_in_config": True,
        "enabled_in_license": True,
        "minimum_license_required": "basic",
        "supported_feature_ids": ["alerting", "uptime", "siem"]
    },
    ...
]
```

## Debugging Techniques

### 1. Check Connector Availability

```python
types = client.actions.list_types().body
index_type = next((t for t in types if t['id'] == '.index'), None)

if not index_type:
    print("❌ Index connector not available")
elif not index_type.get('enabled'):
    print("❌ Index connector is disabled")
    print(f"   Reason: {index_type.get('disabled_reason', 'Unknown')}")
else:
    print("✓ Index connector is available")
```

### 2. Inspect API Responses

```python
response = client.actions.create(...)

# Check HTTP status
print(f"HTTP Status: {response.meta.status}")

# Check response headers
print(f"Headers: {response.meta.headers}")

# Check response body
print(f"Body: {json.dumps(response.body, indent=2)}")
```

### 3. Verify Configuration

```python
connector = client.actions.get(id=connector_id).body

print("Connector Configuration:")
print(f"  Name: {connector['name']}")
print(f"  Type: {connector['connector_type_id']}")
print(f"  Config: {json.dumps(connector['config'], indent=2)}")
print(f"  Missing secrets: {connector.get('is_missing_secrets', False)}")
```

## Common Debugging Scenarios

### Scenario 1: Connector Type Not Found

**Symptom**: Error creating connector with specific type

**Debug Steps**:
1. List all available types
2. Check if the type exists
3. Verify the type is enabled
4. Check license requirements

```python
types = client.actions.list_types().body
for t in types:
    if t['id'] == '.index':
        print(f"Enabled: {t['enabled']}")
        print(f"License: {t.get('minimum_license_required')}")
        print(f"Reason: {t.get('disabled_reason', 'N/A')}")
```

### Scenario 2: Configuration Errors

**Symptom**: `BadRequestError` when creating connector

**Debug Steps**:
1. Check required configuration fields
2. Verify field types and values
3. Review error message details

```python
try:
    connector = client.actions.create(
        name="Test",
        connector_type_id=".index",
        config={"index": "test"}  # Minimal config
    )
except BadRequestError as e:
    print(f"Configuration error: {e}")
    print(f"Response body: {e.body}")
    print(f"Status code: {e.status_code}")
```

### Scenario 3: Permission Issues

**Symptom**: `AuthorizationException` or `ForbiddenError`

**Debug Steps**:
1. Check user permissions
2. Verify API key/credentials
3. Review required privileges

```python
try:
    connectors = client.actions.get_all()
except AuthorizationException as e:
    print("❌ Insufficient permissions")
    print("   Required: actions:read, actions:create")
    print(f"   Error: {e}")
```

## Running the Example

```bash
# With automatic configuration
python examples/debug_connector.py

# With verbose output
python examples/debug_connector.py 2>&1 | tee debug_output.log
```

## Expected Output

```
📊 Kibana Configuration:
   URL: http://localhost:5601
   Auth: Basic authentication

Testing connection...
Listing existing connectors...
✓ Found 3 existing connectors
  - My Connector (conn-123)
  - Test Connector (conn-456)
  - Production Connector (conn-789)

Listing available connector types...
✓ Found 15 connector types
  - .email: Email
  - .index: Index
    ✓ Index connector available: True
  - .server-log: Server log
  - .slack: Slack
  - .webhook: Webhook
  ...

Creating index connector...
✓ Response type: <class 'elastic_transport.ObjectApiResponse'>
✓ Response meta: <ResponseMeta(status=200, http_version='1.1', ...)>
✓ Connector data: {'id': 'abc123', 'name': 'Debug Index Connector', ...}
✓ Created connector with ID: abc123
✓ Connector name: Debug Index Connector
✓ Connector type: .index

🎉 Debug connector created successfully!
   This example created a connector for debugging purposes.
Delete the debug connector? (y/N):
```

## Troubleshooting Tips

### Tip 1: Save Debug Output

```bash
python examples/debug_connector.py > debug_output.txt 2>&1
```

Review the output file to analyze API responses.

### Tip 2: Use Python Debugger

```python
import pdb

response = client.actions.create(...)
pdb.set_trace()  # Inspect response interactively
```

### Tip 3: Enable HTTP Logging

```python
import logging

# Enable HTTP request/response logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('elastic_transport').setLevel(logging.DEBUG)
```

### Tip 4: Check Kibana Logs

If connector creation fails, check Kibana server logs:

```bash
# Docker
docker logs kibana

# Systemd
journalctl -u kibana -f
```

## Next Steps

After debugging:

1. **Simple Example**: Return to basic usage
   - [View Simple Example →](simple.md)

2. **Comprehensive Example**: Production patterns
   - [View Comprehensive Example →](comprehensive.md)

3. **Error Handling**: Handle exceptions properly
   - [View Error Handling Guide →](../../user-guide/error-handling.md)

## Key Takeaways

✅ **List types first**: Understand what's available

✅ **Inspect responses**: Learn the API structure

✅ **Verify operations**: Confirm each step succeeded

✅ **Check permissions**: Ensure adequate access

✅ **Review configuration**: Validate all settings

## Related Examples

- [Simple Connector](simple.md) - Basic usage
- [Comprehensive Connector](comprehensive.md) - Production patterns
- [Error Handling](../../user-guide/error-handling.md) - Exception handling

## Related Documentation

- [Actions API Reference](../../api-reference/actions.rst)
- [Connectors User Guide](../../user-guide/connectors.md)
- [Troubleshooting](../../troubleshooting/common-issues.md)
