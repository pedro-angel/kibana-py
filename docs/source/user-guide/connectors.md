# Connectors (Actions)

Connectors, also known as Actions in Kibana, enable you to integrate with external systems for alerting, automation, and workflow orchestration. The Kibana Python client provides comprehensive support for creating, managing, and executing connectors.

## Overview

Connectors allow you to:
- Send notifications to external systems (Slack, email, webhooks)
- Write data to Elasticsearch indices
- Create tickets in external systems (ServiceNow, Jira)
- Trigger custom workflows and automations

## Connector Types

Kibana supports various connector types:

| Type | Description | Use Case |
|------|-------------|----------|
| `.index` | Elasticsearch index | Write documents to an index |
| `.webhook` | HTTP webhook | Send HTTP requests to external APIs |
| `.slack` | Slack | Send messages to Slack channels |
| `.email` | Email | Send email notifications |
| `.server-log` | Server log | Write to Kibana server logs |
| `.pagerduty` | PagerDuty | Create PagerDuty incidents |
| `.servicenow` | ServiceNow | Create ServiceNow tickets |

## Creating Connectors

### Basic Connector Creation

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Create an index connector
connector = client.actions.create(
    name="My Index Connector",
    connector_type_id=".index",
    config={
        "index": "my-logs",
        "refresh": True,
        "executionTimeField": "@timestamp"
    }
)

connector_id = connector.body["id"]
print(f"Created connector: {connector_id}")

client.close()
```

### Index Connector

Write documents to an Elasticsearch index:

```python
connector = client.actions.create(
    name="Log Writer",
    connector_type_id=".index",
    config={
        "index": "application-logs",
        "refresh": True,  # Refresh index after write
        "executionTimeField": "@timestamp"  # Add timestamp field
    }
)
```

**Configuration Options:**
- `index` (required): Target index name
- `refresh` (optional): Whether to refresh the index after writing (default: false)
- `executionTimeField` (optional): Field name for execution timestamp

### Webhook Connector

Send HTTP requests to external APIs:

```python
connector = client.actions.create(
    name="External API Webhook",
    connector_type_id=".webhook",
    config={
        "url": "https://api.example.com/webhook",
        "method": "post",
        "headers": {
            "Content-Type": "application/json",
            "X-Custom-Header": "value"
        }
    },
    secrets={
        "user": "api_user",
        "password": "api_password"
    }
)
```

**Configuration Options:**
- `url` (required): Target URL
- `method` (required): HTTP method (get, post, put, delete)
- `headers` (optional): Custom HTTP headers
- `hasAuth` (optional): Whether authentication is required

**Secrets:**
- `user`: Username for basic authentication
- `password`: Password for basic authentication

### Slack Connector

Send messages to Slack channels:

```python
connector = client.actions.create(
    name="Slack Notifications",
    connector_type_id=".slack",
    secrets={
        "webhookUrl": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    }
)
```

**Secrets:**
- `webhookUrl` (required): Slack webhook URL

### Email Connector

Send email notifications:

```python
connector = client.actions.create(
    name="Email Notifications",
    connector_type_id=".email",
    config={
        "service": "gmail",  # or "other" for custom SMTP
        "from": "alerts@example.com",
        "host": "smtp.gmail.com",
        "port": 587,
        "secure": False
    },
    secrets={
        "user": "your_email@gmail.com",
        "password": "your_app_password"
    }
)
```

**Configuration Options:**
- `service`: Email service provider (gmail, outlook, other)
- `from`: Sender email address
- `host`: SMTP server host
- `port`: SMTP server port
- `secure`: Use TLS/SSL

**Secrets:**
- `user`: Email account username
- `password`: Email account password or app password

### Server Log Connector

Write to Kibana server logs:

```python
connector = client.actions.create(
    name="Server Logger",
    connector_type_id=".server-log",
    config={}  # No configuration required
)
```

## Managing Connectors

### Get Connector by ID

```python
connector = client.actions.get(id="connector-id")
print(f"Connector name: {connector.body['name']}")
print(f"Connector type: {connector.body['connector_type_id']}")
```

### List All Connectors

```python
connectors = client.actions.get_all()

for connector in connectors.body:
    print(f"- {connector['name']} ({connector['connector_type_id']})")
```

### List Available Connector Types

```python
types = client.actions.list_types()

for connector_type in types.body:
    print(f"- {connector_type['id']}: {connector_type['name']}")
    print(f"  Enabled: {connector_type['enabled']}")
```

### Update Connector

```python
updated = client.actions.update(
    id="connector-id",
    name="Updated Connector Name",
    config={
        "index": "new-index-name",
        "refresh": True
    }
)
```

### Delete Connector

```python
client.actions.delete(id="connector-id")
print("Connector deleted successfully")
```

## Executing Connectors

### Execute Index Connector

Write documents to an index:

```python
# Single document
result = client.actions.execute(
    id=connector_id,
    params={
        "documents": [
            {
                "message": "Application started",
                "level": "INFO",
                "service": "my-app"
            }
        ]
    }
)

# Multiple documents
result = client.actions.execute(
    id=connector_id,
    params={
        "documents": [
            {"message": "Event 1", "level": "INFO"},
            {"message": "Event 2", "level": "WARNING"},
            {"message": "Event 3", "level": "ERROR"}
        ]
    }
)
```

### Execute Webhook Connector

Send HTTP request:

```python
result = client.actions.execute(
    id=connector_id,
    params={
        "body": '{"alert": "High CPU usage", "severity": "warning"}'
    }
)
```

### Execute Slack Connector

Send Slack message:

```python
result = client.actions.execute(
    id=connector_id,
    params={
        "message": "🚨 Alert: High memory usage detected on server-01"
    }
)
```

### Execute Email Connector

Send email:

```python
result = client.actions.execute(
    id=connector_id,
    params={
        "to": ["admin@example.com", "ops@example.com"],
        "subject": "Alert: System Issue Detected",
        "message": "High CPU usage detected on production server."
    }
)
```

### Execute Server Log Connector

Write to server log:

```python
result = client.actions.execute(
    id=connector_id,
    params={
        "message": "Custom log message from API",
        "level": "info"  # info, warn, error
    }
)
```

## Space-Scoped Connectors

Connectors can be created and managed within specific Kibana Spaces for multi-tenancy.

### Individual Space Parameters

```python
# Create connector in specific space
connector = client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://marketing.example.com/webhook"},
    space_id="marketing"
)

# Get connector from specific space
connector = client.actions.get(
    id=connector_id,
    space_id="marketing"
)

# Execute connector in specific space
result = client.actions.execute(
    id=connector_id,
    params={"body": '{"message": "Hello"}'},
    space_id="marketing"
)
```

### Space-Scoped Client

```python
# Create space-scoped client
marketing_client = client.space("marketing")

# All operations automatically use marketing space
connector = marketing_client.actions.create(
    name="Marketing Webhook",
    connector_type_id=".webhook",
    config={"url": "https://marketing.example.com/webhook"}
)

result = marketing_client.actions.execute(
    id=connector.body["id"],
    params={"body": '{"message": "Hello"}'}
)
```

See [Spaces](spaces.md) for more information on space-scoped operations.

## Error Handling

Handle common connector errors:

```python
from kibana import Kibana
from kibana.exceptions import (
    NotFoundError,
    ConflictError,
    BadRequestError,
    SpaceNotFoundError
)

client = Kibana("http://localhost:5601", api_key="your_api_key")

try:
    # Create connector
    connector = client.actions.create(
        name="My Connector",
        connector_type_id=".index",
        config={"index": "my-index"},
        space_id="marketing"
    )

    # Execute connector
    result = client.actions.execute(
        id=connector.body["id"],
        params={"documents": [{"message": "test"}]},
        space_id="marketing"
    )

except SpaceNotFoundError as e:
    print(f"Space not found: {e.space_id}")
except ConflictError as e:
    print(f"Connector already exists: {e.message}")
except BadRequestError as e:
    print(f"Invalid configuration: {e.message}")
except NotFoundError as e:
    print(f"Connector not found: {e.message}")
finally:
    client.close()
```

## Best Practices

### 1. Use Descriptive Names

```python
# Good: Descriptive name
connector = client.actions.create(
    name="Production Alerts - Slack #ops-team",
    connector_type_id=".slack",
    secrets={"webhookUrl": "..."}
)

# Avoid: Generic name
connector = client.actions.create(
    name="Connector 1",
    connector_type_id=".slack",
    secrets={"webhookUrl": "..."}
)
```

### 2. Store Secrets Securely

```python
import os

# Good: Environment variables
connector = client.actions.create(
    name="Slack Notifications",
    connector_type_id=".slack",
    secrets={
        "webhookUrl": os.getenv("SLACK_WEBHOOK_URL")
    }
)

# Avoid: Hardcoded secrets
connector = client.actions.create(
    name="Slack Notifications",
    connector_type_id=".slack",
    secrets={
        "webhookUrl": "https://hooks.slack.com/..."  # Don't hardcode!
    }
)
```

### 3. Handle Execution Errors

```python
try:
    result = client.actions.execute(
        id=connector_id,
        params={"documents": [{"message": "test"}]}
    )

    if result.body.get("status") == "error":
        print(f"Execution failed: {result.body.get('message')}")
    else:
        print("Execution successful")

except Exception as e:
    print(f"Failed to execute connector: {e}")
    # Implement retry logic or fallback
```

### 4. Clean Up Test Connectors

```python
# Create connector for testing
connector = client.actions.create(
    name="Test Connector",
    connector_type_id=".index",
    config={"index": "test-index"}
)

try:
    # Use connector
    result = client.actions.execute(
        id=connector.body["id"],
        params={"documents": [{"test": "data"}]}
    )
finally:
    # Always clean up
    client.actions.delete(id=connector.body["id"])
```

### 5. Use Space Isolation

```python
# Separate connectors by environment/team
dev_client = client.space("development")
prod_client = client.space("production")

# Development connector
dev_connector = dev_client.actions.create(
    name="Dev Webhook",
    connector_type_id=".webhook",
    config={"url": "https://dev.example.com/webhook"}
)

# Production connector (isolated from dev)
prod_connector = prod_client.actions.create(
    name="Prod Webhook",
    connector_type_id=".webhook",
    config={"url": "https://prod.example.com/webhook"}
)
```

## Advanced Patterns

### Connector Factory Pattern

```python
class ConnectorFactory:
    def __init__(self, client):
        self.client = client

    def create_index_connector(self, name, index):
        return self.client.actions.create(
            name=name,
            connector_type_id=".index",
            config={
                "index": index,
                "refresh": True,
                "executionTimeField": "@timestamp"
            }
        )

    def create_webhook_connector(self, name, url, headers=None):
        return self.client.actions.create(
            name=name,
            connector_type_id=".webhook",
            config={
                "url": url,
                "method": "post",
                "headers": headers or {"Content-Type": "application/json"}
            }
        )

# Usage
factory = ConnectorFactory(client)
connector = factory.create_index_connector("App Logs", "application-logs")
```

### Connector Manager Pattern

```python
class ConnectorManager:
    def __init__(self, client):
        self.client = client
        self.connectors = {}

    def get_or_create(self, name, connector_type_id, config, secrets=None):
        """Get existing connector or create new one."""
        # Check if connector exists
        all_connectors = self.client.actions.get_all()
        for conn in all_connectors.body:
            if conn["name"] == name:
                self.connectors[name] = conn["id"]
                return conn

        # Create new connector
        connector = self.client.actions.create(
            name=name,
            connector_type_id=connector_type_id,
            config=config,
            secrets=secrets
        )
        self.connectors[name] = connector.body["id"]
        return connector.body

    def execute(self, name, params):
        """Execute connector by name."""
        if name not in self.connectors:
            raise ValueError(f"Connector '{name}' not found")

        return self.client.actions.execute(
            id=self.connectors[name],
            params=params
        )

    def cleanup(self):
        """Delete all managed connectors."""
        for connector_id in self.connectors.values():
            try:
                self.client.actions.delete(id=connector_id)
            except NotFoundError:
                pass

# Usage
manager = ConnectorManager(client)

# Get or create connector
connector = manager.get_or_create(
    name="App Logger",
    connector_type_id=".index",
    config={"index": "app-logs"}
)

# Execute by name
manager.execute("App Logger", {
    "documents": [{"message": "Application started"}]
})

# Cleanup
manager.cleanup()
```

### Retry Pattern

```python
import time
from kibana.exceptions import ApiError

def execute_with_retry(client, connector_id, params, max_retries=3):
    """Execute connector with retry logic."""
    for attempt in range(max_retries):
        try:
            result = client.actions.execute(
                id=connector_id,
                params=params
            )
            return result
        except ApiError as e:
            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            time.sleep(wait_time)

# Usage
result = execute_with_retry(
    client,
    connector_id,
    {"documents": [{"message": "test"}]}
)
```

## Troubleshooting

### Connector Not Found

**Symptom**: `NotFoundError: Connector not found`

**Solutions**:
- Verify the connector ID is correct
- Check if the connector exists in the correct space
- Ensure you have permission to access the connector

```python
# List all connectors to find the correct ID
connectors = client.actions.get_all()
for conn in connectors.body:
    print(f"{conn['id']}: {conn['name']}")
```

### Invalid Configuration

**Symptom**: `BadRequestError: Invalid connector configuration`

**Solutions**:
- Verify all required configuration fields are provided
- Check field types match expected values
- Consult connector type documentation for valid options

```python
# List connector types to see configuration requirements
types = client.actions.list_types()
for t in types.body:
    if t['id'] == '.index':
        print(f"Config schema: {t.get('config_schema')}")
```

### Execution Failures

**Symptom**: Connector executes but fails to perform action

**Solutions**:
- Check connector configuration (URLs, credentials, etc.)
- Verify target system is accessible
- Review Kibana server logs for detailed error messages
- Test connectivity to external systems

```python
# Check execution result
result = client.actions.execute(
    id=connector_id,
    params={"documents": [{"test": "data"}]}
)

if result.body.get("status") == "error":
    print(f"Error: {result.body.get('message')}")
    print(f"Details: {result.body.get('serviceMessage')}")
```

### Space-Related Errors

**Symptom**: `SpaceNotFoundError: Space not found`

**Solutions**:
- Verify the space exists
- Check space ID spelling
- Ensure you have permission to access the space

```python
# List available spaces
spaces = client.spaces.get_all()
for space in spaces.body:
    print(f"{space['id']}: {space['name']}")
```

## Next Steps

- Learn about [Spaces](spaces.md) for multi-tenancy
- Explore [Saved Objects](saved-objects.md) for managing dashboards
- Check [Error Handling](error-handling.md) for comprehensive error management
- See [Examples](../examples/connectors/index.md) for practical code samples
