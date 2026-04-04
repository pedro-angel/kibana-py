# Authentication

The Kibana Python client supports multiple authentication methods to connect to your Kibana instance. Choose the method that best fits your security requirements and infrastructure.

## Authentication Methods

The client supports three authentication methods (in order of precedence):

1. **API Key** - Recommended for production use
2. **Basic Authentication** - Username and password
3. **Bearer Token** - OAuth or other token-based authentication

:::{note}
Only one authentication method can be used at a time. If multiple methods are provided, API key takes precedence, followed by basic auth, then bearer token.
:::

## API Key Authentication

API keys are the recommended authentication method for production environments. They provide fine-grained access control and can be easily rotated.

### String Format

```python
from kibana import Kibana

# Using base64-encoded API key string
client = Kibana(
    "http://localhost:5601",
    api_key="your_base64_encoded_api_key"
)
```

### Tuple Format

```python
# Using API key ID and secret
client = Kibana(
    "http://localhost:5601",
    api_key=("key_id", "key_secret")
)
```

### Creating API Keys

API keys can be created through the Kibana UI or Elasticsearch API:

**Via Kibana UI:**
1. Navigate to Stack Management → API Keys
2. Click "Create API key"
3. Set name, expiration, and privileges
4. Copy the generated key

**Via Elasticsearch API:**
```bash
curl -X POST "http://localhost:9200/_security/api_key" \
  -H "Content-Type: application/json" \
  -u elastic:password \
  -d '{
    "name": "kibana-client-key",
    "expiration": "30d",
    "role_descriptors": {
      "kibana_admin": {
        "cluster": ["all"],
        "index": [
          {
            "names": ["*"],
            "privileges": ["all"]
          }
        ]
      }
    }
  }'
```

### API Key Best Practices

- **Rotate regularly**: Set expiration dates and rotate keys periodically
- **Least privilege**: Grant only the permissions needed for your use case
- **Secure storage**: Store API keys in environment variables or secret management systems
- **Monitor usage**: Track API key usage and revoke unused keys

## Basic Authentication

Basic authentication uses a username and password. This method is simple but less secure than API keys.

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    basic_auth=("username", "password")
)
```

### Example with Elastic User

```python
# Using the default elastic superuser
client = Kibana(
    "http://localhost:5601",
    basic_auth=("elastic", "your_password")
)
```

### Basic Auth Best Practices

- **Use HTTPS**: Always use HTTPS in production to encrypt credentials
- **Strong passwords**: Use strong, unique passwords
- **Limited accounts**: Create dedicated service accounts with limited privileges
- **Avoid hardcoding**: Store credentials in environment variables

```python
import os

client = Kibana(
    os.getenv("KIBANA_URL", "http://localhost:5601"),
    basic_auth=(
        os.getenv("KIBANA_USERNAME"),
        os.getenv("KIBANA_PASSWORD")
    )
)
```

## Bearer Token Authentication

Bearer tokens are used for OAuth, JWT, or other token-based authentication systems.

```python
from kibana import Kibana

client = Kibana(
    "http://localhost:5601",
    bearer_auth="your_bearer_token"
)
```

### Example with OAuth Token

```python
# Assuming you've obtained an OAuth token
oauth_token = get_oauth_token()  # Your OAuth flow

client = Kibana(
    "http://localhost:5601",
    bearer_auth=oauth_token
)
```

## Per-Request Authentication

You can override authentication for specific requests using the `options()` method:

```python
from kibana import Kibana

# Initialize with default authentication
client = Kibana(
    "http://localhost:5601",
    api_key="default_api_key"
)

# Use different authentication for specific request
response = client.options(
    api_key="different_api_key"
).actions.get_all()

# Or use basic auth for a specific request
response = client.options(
    basic_auth=("admin", "admin_password")
).spaces.get_all()
```

This is useful when:
- Different operations require different privilege levels
- Implementing user impersonation
- Testing with multiple accounts

## No Authentication

For local development or testing, you can connect without authentication:

```python
from kibana import Kibana

# No authentication (only for local development)
client = Kibana("http://localhost:5601")
```

:::{warning}
Never use unauthenticated connections in production environments.
:::

## Authentication with Elastic Cloud

When connecting to Elastic Cloud, use Cloud ID with API key authentication:

```python
from kibana import Kibana

client = Kibana(
    cloud_id="your_cloud_id",
    api_key="your_api_key"
)
```

The Cloud ID can be found in your Elastic Cloud console.

## TLS/SSL Configuration

For secure connections, configure TLS/SSL settings:

### Basic TLS

```python
from kibana import Kibana

client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    verify_certs=True  # Verify SSL certificates (default: True)
)
```

### Custom CA Certificate

```python
client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    ca_certs="/path/to/ca.crt"  # Path to CA certificate bundle
)
```

### Client Certificates

```python
client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    client_cert="/path/to/client.crt",
    client_key="/path/to/client.key"
)
```

### Disable Certificate Verification

:::{warning}
Only disable certificate verification for local development or testing.
:::

```python
client = Kibana(
    "https://localhost:5601",
    api_key="your_api_key",
    verify_certs=False  # Not recommended for production
)
```

## Environment Variables

Store authentication credentials in environment variables for better security:

```bash
# Set environment variables
export KIBANA_URL="http://localhost:5601"
export KIBANA_API_KEY="your_api_key"

# Or for basic auth
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="your_password"
```

```python
import os
from kibana import Kibana

# Read from environment variables
client = Kibana(
    os.getenv("KIBANA_URL"),
    api_key=os.getenv("KIBANA_API_KEY")
)

# Or with basic auth
client = Kibana(
    os.getenv("KIBANA_URL"),
    basic_auth=(
        os.getenv("KIBANA_USERNAME"),
        os.getenv("KIBANA_PASSWORD")
    )
)
```

## Authentication Errors

Handle authentication errors gracefully:

```python
from kibana import Kibana
from kibana.exceptions import AuthenticationException, AuthorizationException

try:
    client = Kibana(
        "http://localhost:5601",
        api_key="invalid_key"
    )
    status = client.status.get_status()
except AuthenticationException as e:
    print(f"Authentication failed: {e.message}")
    # Handle invalid credentials
except AuthorizationException as e:
    print(f"Authorization failed: {e.message}")
    # Handle insufficient permissions
finally:
    client.close()
```

## Security Best Practices

### 1. Use API Keys in Production

API keys provide better security and access control than basic authentication:

```python
# Good: API key authentication
client = Kibana(
    "https://kibana.example.com",
    api_key=os.getenv("KIBANA_API_KEY")
)

# Avoid: Basic auth in production
client = Kibana(
    "https://kibana.example.com",
    basic_auth=("user", "password")  # Less secure
)
```

### 2. Always Use HTTPS

Encrypt all communication with HTTPS:

```python
# Good: HTTPS connection
client = Kibana("https://kibana.example.com", api_key="key")

# Avoid: HTTP in production
client = Kibana("http://kibana.example.com", api_key="key")
```

### 3. Store Credentials Securely

Never hardcode credentials in source code:

```python
# Good: Environment variables
client = Kibana(
    os.getenv("KIBANA_URL"),
    api_key=os.getenv("KIBANA_API_KEY")
)

# Avoid: Hardcoded credentials
client = Kibana(
    "http://localhost:5601",
    api_key="hardcoded_key_123"  # Never do this!
)
```

### 4. Implement Least Privilege

Grant only the minimum required permissions:

```python
# Create API key with limited privileges
# (via Elasticsearch API or Kibana UI)
# Then use it in your application
client = Kibana(
    "https://kibana.example.com",
    api_key="limited_privilege_key"
)
```

### 5. Rotate Credentials Regularly

Implement credential rotation:

```python
def get_current_api_key():
    """Fetch current API key from secret management system."""
    # Implement your secret rotation logic
    return fetch_from_secret_manager("kibana_api_key")

client = Kibana(
    "https://kibana.example.com",
    api_key=get_current_api_key()
)
```

### 6. Monitor Authentication Failures

Log and monitor authentication failures:

```python
import logging

logger = logging.getLogger(__name__)

try:
    client = Kibana(
        "https://kibana.example.com",
        api_key=os.getenv("KIBANA_API_KEY")
    )
    status = client.status.get_status()
except AuthenticationException as e:
    logger.error(f"Authentication failed: {e.message}")
    # Alert security team
    send_security_alert("Kibana authentication failure")
    raise
```

## Troubleshooting

### Invalid API Key

**Symptom**: `AuthenticationException: Unauthorized`

**Solutions**:
- Verify the API key is correct and not expired
- Check if the API key has been revoked
- Ensure the API key has the necessary privileges

### Connection Refused

**Symptom**: `ConnectionError: Connection refused`

**Solutions**:
- Verify Kibana is running and accessible
- Check the URL and port are correct
- Verify network connectivity and firewall rules

### SSL Certificate Errors

**Symptom**: `SSLError: certificate verify failed`

**Solutions**:
- Provide the correct CA certificate with `ca_certs`
- Verify the certificate is valid and not expired
- For testing only, disable verification with `verify_certs=False`

### Permission Denied

**Symptom**: `AuthorizationException: Forbidden`

**Solutions**:
- Verify the user/API key has the required privileges
- Check Kibana role-based access control (RBAC) settings
- Ensure the user has access to the requested resources

## Next Steps

- Learn about [Connectors](connectors.md) to create and manage actions
- Explore [Spaces](spaces.md) for multi-tenancy
- Check [Error Handling](error-handling.md) for comprehensive error management
