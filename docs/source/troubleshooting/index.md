# Troubleshooting

This section provides solutions to common issues you may encounter when using kibana-py.

```{toctree}
:maxdepth: 2
:caption: Troubleshooting

common-issues
telemetry
```

## Quick Links

- {doc}`telemetry` - OpenTelemetry and observability issues
- {doc}`common-issues` - General connection, authentication, and usage problems

## Getting Help

If you can't find a solution to your problem in these guides:

1. Check the [GitHub Issues](https://github.com/pedro-angel/kibana-py/issues) for similar problems
2. Review the {doc}`../user-guide/index` for detailed usage information
3. Consult the {doc}`../api-reference/index` for API documentation
4. Enable debug logging to get more information:

```python
import logging

# Enable debug logging for kibana-py
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("kibana").setLevel(logging.DEBUG)
```

## Diagnostic Tools

### Check Configuration

```python
from kibana import Kibana

client = Kibana("http://localhost:5601")
print(f"Kibana URL: {client._transport._node_configs[0].base_url}")
print(f"Authentication: {'Configured' if client._auth_headers else 'None'}")
```

### Test Connection

```python
from kibana import Kibana

try:
    client = Kibana("http://localhost:5601")
    status = client.status.get_status()
    print(f"✓ Connected to Kibana {status.body['version']['number']}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

### Enable Verbose Logging

```python
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable for specific components
logging.getLogger("kibana").setLevel(logging.DEBUG)
logging.getLogger("elastic_transport").setLevel(logging.DEBUG)
```

## Common Error Patterns

### Connection Errors

If you see connection errors, check:

- Kibana is running and accessible
- URL is correct (including protocol: `http://` or `https://`)
- Network connectivity and firewall rules
- TLS/SSL certificate issues (for HTTPS)

See {doc}`common-issues` for detailed solutions.

### Authentication Errors

If you see authentication errors (401, 403), check:

- API key or credentials are valid
- User has necessary permissions
- Authentication method matches Kibana configuration

See {doc}`common-issues` for detailed solutions.

### Space Errors

If you see space-related errors, check:

- Space ID is correct and exists
- User has access to the space
- Space validation is enabled (default)

See {doc}`common-issues` for detailed solutions.

### Observability Issues

If you have problems with OpenTelemetry integration, check:

- APM server is running and accessible
- Configuration environment variables are set
- Log forwarding is enabled if needed

See {doc}`telemetry` for detailed solutions.
