# Common Issues

This guide covers common issues you may encounter when using kibana-py and their solutions.

## Connection Issues

### Cannot Connect to Kibana

**Symptom**: Connection errors, timeouts, or "Connection refused" messages

**Causes**:
- Kibana is not running
- Incorrect URL
- Network connectivity issues
- Firewall blocking connections

**Solutions**:

1. Verify Kibana is running:
   ```bash
   curl http://localhost:5601/api/status
   ```

2. Check the URL format:
   ```python
   from kibana import Kibana

   # Correct - includes protocol
   client = Kibana("http://localhost:5601")

   # Incorrect - missing protocol
   # client = Kibana("localhost:5601")
   ```

3. Test network connectivity:
   ```bash
   # Test basic connectivity
   telnet localhost 5601

   # Test with curl
   curl -v http://localhost:5601/
   ```

4. Check firewall rules:
   ```bash
   # On Linux, check if port is open
   sudo netstat -tlnp | grep 5601

   # On macOS
   lsof -i :5601
   ```

### SSL/TLS Certificate Errors

**Symptom**: SSL certificate verification errors

**Causes**:
- Self-signed certificates
- Certificate chain issues
- Hostname mismatch

**Solutions**:

1. Disable SSL verification (development only):
   ```python
   from kibana import Kibana

   client = Kibana(
       "https://localhost:5601",
       verify_certs=False  # Not recommended for production
   )
   ```

2. Provide CA certificate:
   ```python
   from kibana import Kibana

   client = Kibana(
       "https://localhost:5601",
       ca_certs="/path/to/ca.crt"
   )
   ```

3. Use system CA bundle:
   ```python
   from kibana import Kibana
   import certifi

   client = Kibana(
       "https://localhost:5601",
       ca_certs=certifi.where()
   )
   ```

### Connection Timeouts

**Symptom**: Requests timeout before completing

**Causes**:
- Slow network
- Kibana overloaded
- Large response payloads
- Default timeout too short

**Solutions**:

1. Increase timeout:
   ```python
   from kibana import Kibana

   client = Kibana(
       "http://localhost:5601",
       request_timeout=60  # 60 seconds
   )
   ```

2. Use per-request timeout:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Override timeout for specific request
   response = client.options(request_timeout=120).actions.list()
   ```

3. Check Kibana performance:
   ```bash
   # Check Kibana status
   curl http://localhost:5601/api/status

   # Check system resources
   top
   ```

## Authentication Issues

### API Key Authentication Fails

**Symptom**: 401 Unauthorized errors with API key

**Causes**:
- Invalid or expired API key
- Incorrect API key format
- Insufficient permissions

**Solutions**:

1. Verify API key format:
   ```python
   from kibana import Kibana

   # Correct - string format
   client = Kibana(
       "http://localhost:5601",
       api_key="VnVhQ2ZHY0JDZGJrUW0tZTVhT3g6dWkybHAyYXhUTm1zeWFrdzl0dk5udw=="
   )

   # Correct - tuple format (id, api_key)
   client = Kibana(
       "http://localhost:5601",
       api_key=("VnVhQ2ZHY0JDZGJrUW0tZTVhT3g", "dWkybHAyYXhUTm1zeWFrdzl0dk5udw==")
   )
   ```

2. Test API key:
   ```bash
   # Test with curl
   curl -H "Authorization: ApiKey YOUR_API_KEY" \
        http://localhost:5601/api/status
   ```

3. Check API key permissions:
   - Log into Kibana UI
   - Navigate to Stack Management → API Keys
   - Verify the API key exists and has necessary permissions

4. Create new API key:
   ```bash
   # Using Elasticsearch API
   curl -X POST "http://localhost:9200/_security/api_key" \
        -H "Content-Type: application/json" \
        -u elastic:password \
        -d '{
          "name": "kibana-py-key",
          "role_descriptors": {
            "kibana_admin": {
              "cluster": ["all"],
              "index": [{"names": ["*"], "privileges": ["all"]}]
            }
          }
        }'
   ```

### Basic Authentication Fails

**Symptom**: 401 Unauthorized errors with username/password

**Causes**:
- Incorrect credentials
- User account disabled
- Insufficient permissions

**Solutions**:

1. Verify credentials format:
   ```python
   from kibana import Kibana

   # Correct - tuple format
   client = Kibana(
       "http://localhost:5601",
       basic_auth=("elastic", "password")
   )

   # Incorrect - string format
   # client = Kibana("http://localhost:5601", basic_auth="elastic:password")
   ```

2. Test credentials:
   ```bash
   # Test with curl
   curl -u elastic:password http://localhost:5601/api/status
   ```

3. Check user account:
   - Log into Kibana UI with the credentials
   - Verify account is active
   - Check user roles and permissions

### Bearer Token Authentication Fails

**Symptom**: 401 Unauthorized errors with bearer token

**Causes**:
- Invalid or expired token
- Token format issues
- Insufficient permissions

**Solutions**:

1. Verify token format:
   ```python
   from kibana import Kibana

   # Correct - string format
   client = Kibana(
       "http://localhost:5601",
       bearer_auth="your_bearer_token"
   )
   ```

2. Test token:
   ```bash
   # Test with curl
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://localhost:5601/api/status
   ```

3. Check token expiration:
   - Tokens may have expiration times
   - Regenerate token if expired
   - Implement token refresh logic if needed

## Space-Related Issues

### Space Not Found Error

**Symptom**: `SpaceNotFoundError` when accessing resources

**Causes**:
- Space ID doesn't exist
- Typo in space ID
- User doesn't have access to space

**Solutions**:

1. Verify space exists:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # List all spaces
   spaces = client.spaces.get_all()
   for space in spaces.body:
       print(f"Space ID: {space['id']}, Name: {space['name']}")
   ```

2. Check space ID format:
   ```python
   # Correct - use space ID, not name
   response = client.actions.list(space_id="marketing")

   # Incorrect - using space name instead of ID
   # response = client.actions.list(space_id="Marketing Space")
   ```

3. Create space if needed:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   space = client.spaces.create(
       id="marketing",
       name="Marketing Space",
       description="Space for marketing team"
   )
   ```

4. Disable space validation for performance:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Disable validation if you're sure space exists
   marketing_client = client.space("marketing", validate=False)
   ```

### Space Access Denied

**Symptom**: 403 Forbidden errors when accessing space

**Causes**:
- User doesn't have permissions for the space
- Space features disabled
- Role restrictions

**Solutions**:

1. Check user permissions:
   - Log into Kibana UI
   - Navigate to Stack Management → Users
   - Verify user has access to the space

2. Check space features:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Get space details
   space = client.spaces.get(id="marketing")
   print(f"Disabled features: {space.body.get('disabledFeatures', [])}")
   ```

3. Update user roles:
   - Assign appropriate roles that include space access
   - Use Kibana UI or Elasticsearch API to update roles

### Space Validation Performance Issues

**Symptom**: Slow performance when using space_id parameter

**Causes**:
- Space validation on every request
- Network latency
- Kibana overloaded

**Solutions**:

1. Use space-scoped client (validates once):
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Validate space once
   marketing_client = client.space("marketing")

   # No validation on subsequent calls
   connectors = marketing_client.actions.list()
   connector = marketing_client.actions.get(id="connector-id")
   ```

2. Disable validation if space is known to exist:
   ```python
   # Skip validation entirely
   marketing_client = client.space("marketing", validate=False)
   ```

3. Use caching (enabled by default):
   ```python
   # Space validation results are cached for 5 minutes by default
   # Multiple operations to same space use cached validation
   response1 = client.actions.list(space_id="marketing")  # Validates
   response2 = client.actions.get(id="id", space_id="marketing")  # Uses cache
   ```

## Connector Issues

### Connector Creation Fails

**Symptom**: Errors when creating connectors

**Causes**:
- Invalid connector type
- Missing required configuration
- Invalid secrets format
- Insufficient permissions

**Solutions**:

1. List available connector types:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Get all connector types
   types = client.actions.list_types()
   for connector_type in types.body:
       print(f"Type: {connector_type['id']}")
       print(f"Name: {connector_type['name']}")
       print(f"Enabled: {connector_type['enabled']}")
   ```

2. Check required configuration:
   ```python
   # Index connector example
   connector = client.actions.create(
       name="My Index Connector",
       connector_type_id=".index",
       config={
           "index": "my-index",  # Required
           "refresh": True,       # Optional
           "executionTimeField": None  # Optional
       }
   )
   ```

3. Verify secrets format:
   ```python
   # Webhook connector with secrets
   connector = client.actions.create(
       name="My Webhook",
       connector_type_id=".webhook",
       config={
           "url": "https://example.com/webhook",
           "method": "post",
           "headers": {}
       },
       secrets={
           "user": "username",      # If using basic auth
           "password": "password"   # If using basic auth
       }
   )
   ```

### Connector Execution Fails

**Symptom**: Errors when executing connectors

**Causes**:
- Invalid parameters
- Connector misconfigured
- Target service unavailable
- Insufficient permissions

**Solutions**:

1. Verify connector configuration:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Get connector details
   connector = client.actions.get(id="connector-id")
   print(f"Config: {connector.body['config']}")
   print(f"Type: {connector.body['connector_type_id']}")
   ```

2. Check execution parameters:
   ```python
   # Index connector execution
   result = client.actions.execute(
       id="connector-id",
       params={
           "documents": [
               {"field": "value"}
           ]
       }
   )
   ```

3. Test connector manually:
   - Use Kibana UI to test connector
   - Navigate to Stack Management → Connectors
   - Click "Test" button on the connector

4. Check connector logs:
   ```bash
   # Check Kibana logs for connector errors
   docker-compose logs kibana | grep -i connector
   ```

## Saved Objects Issues

### Saved Object Not Found

**Symptom**: 404 errors when accessing saved objects

**Causes**:
- Object doesn't exist
- Wrong object ID
- Object in different space
- Insufficient permissions

**Solutions**:

1. Verify object exists:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Search for objects
   results = client.saved_objects.find(type="visualization")
   for obj in results.body['saved_objects']:
       print(f"ID: {obj['id']}, Type: {obj['type']}")
   ```

2. Check correct space:
   ```python
   # Object might be in a different space
   results = client.saved_objects.find(
       type="visualization",
       space_id="marketing"
   )
   ```

3. Use correct object type:
   ```python
   # Common saved object types
   types = [
       "visualization",
       "dashboard",
       "index-pattern",
       "search",
       "lens",
       "map"
   ]
   ```

### Saved Object Creation Fails

**Symptom**: Errors when creating saved objects

**Causes**:
- Invalid attributes
- Missing required fields
- Type not supported
- Insufficient permissions

**Solutions**:

1. Verify required attributes:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Create with required attributes
   obj = client.saved_objects.create(
       type="visualization",
       attributes={
           "title": "My Visualization",
           "visState": "{}",  # Required for visualizations
           "uiStateJSON": "{}",
           "description": "",
           "version": 1,
           "kibanaSavedObjectMeta": {
               "searchSourceJSON": "{}"
           }
       }
   )
   ```

2. Check object type support:
   ```python
   # Some types may require specific Kibana plugins
   # Verify the type is available in your Kibana instance
   ```

3. Use bulk create for multiple objects:
   ```python
   # More efficient for multiple objects
   result = client.saved_objects.bulk_create(
       objects=[
           {
               "type": "visualization",
               "attributes": {"title": "Viz 1"}
           },
           {
               "type": "visualization",
               "attributes": {"title": "Viz 2"}
           }
       ]
   )
   ```

## Performance Issues

### Slow API Responses

**Symptom**: API calls take longer than expected

**Causes**:
- Large result sets
- Complex queries
- Kibana overloaded
- Network latency

**Solutions**:

1. Use pagination:
   ```python
   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Paginate large result sets
   page = 1
   per_page = 100

   results = client.saved_objects.find(
       type="visualization",
       page=page,
       per_page=per_page
   )
   ```

2. Filter results:
   ```python
   # Use search to filter results
   results = client.saved_objects.find(
       type="visualization",
       search="dashboard",
       search_fields=["title"]
   )
   ```

3. Use bulk operations:
   ```python
   # More efficient than individual calls
   result = client.saved_objects.bulk_get(
       objects=[
           {"type": "visualization", "id": "id1"},
           {"type": "dashboard", "id": "id2"}
       ]
   )
   ```

4. Monitor Kibana performance:
   ```bash
   # Check Kibana status
   curl http://localhost:5601/api/status

   # Check system resources
   docker stats kibana
   ```

### High Memory Usage

**Symptom**: Application uses excessive memory

**Causes**:
- Large response payloads
- Memory leaks
- Not closing clients
- Caching issues

**Solutions**:

1. Close clients properly:
   ```python
   from kibana import Kibana

   # Use context manager
   with Kibana("http://localhost:5601") as client:
       response = client.actions.list()
       # Client automatically closed

   # Or close manually
   client = Kibana("http://localhost:5601")
   try:
       response = client.actions.list()
   finally:
       client.close()
   ```

2. Process large results in chunks:
   ```python
   # Don't load all results at once
   page = 1
   while True:
       results = client.saved_objects.find(
           type="visualization",
           page=page,
           per_page=100
       )

       # Process this page
       for obj in results.body['saved_objects']:
           process_object(obj)

       # Check if more pages
       if page >= results.body['total'] // 100:
           break
       page += 1
   ```

3. Clear caches periodically:
   ```python
   # If using space-scoped clients
   # Caches are automatically cleared after TTL (5 minutes)
   # Or create new client instance if needed
   ```

## Error Handling

### Understanding Error Messages

**Common error patterns**:

```python
from kibana import Kibana
from kibana.exceptions import (
    NotFoundError,
    BadRequestError,
    ConflictError,
    SpaceNotFoundError
)

client = Kibana("http://localhost:5601")

try:
    response = client.actions.get(id="nonexistent")
except NotFoundError as e:
    print(f"Resource not found: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response body: {e.body}")
except BadRequestError as e:
    print(f"Invalid request: {e}")
except ConflictError as e:
    print(f"Resource conflict: {e}")
except SpaceNotFoundError as e:
    print(f"Space not found: {e.space_id}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Debugging API Calls

Enable debug logging to see API requests and responses:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("kibana").setLevel(logging.DEBUG)
logging.getLogger("elastic_transport").setLevel(logging.DEBUG)

# Now API calls will be logged
from kibana import Kibana
client = Kibana("http://localhost:5601")
response = client.actions.list()
```

### Handling Transient Errors

Implement retry logic for transient errors:

```python
import time
from kibana import Kibana
from kibana.exceptions import KibanaException

def retry_api_call(func, max_retries=3, delay=1):
    """Retry API call with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except KibanaException as e:
            if attempt == max_retries - 1:
                raise
            if e.status_code in [429, 503, 504]:  # Retry on these
                time.sleep(delay * (2 ** attempt))
            else:
                raise

# Usage
client = Kibana("http://localhost:5601")
response = retry_api_call(lambda: client.actions.list())
```

:::{seealso}
- {doc}`../user-guide/error-handling` - Error handling patterns
- {doc}`../user-guide/authentication` - Authentication setup
- {doc}`../user-guide/spaces` - Space management
- {doc}`telemetry` - OpenTelemetry troubleshooting
:::
