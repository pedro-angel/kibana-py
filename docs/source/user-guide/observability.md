# OpenTelemetry Observability

The Kibana Python client includes built-in OpenTelemetry support for distributed tracing and log forwarding to APM servers.

## Installation

Install with observability support:

```bash
pip install kibana-py[observability]
```

This installs:
- `opentelemetry-api` - OpenTelemetry API
- `opentelemetry-sdk` - OpenTelemetry SDK
- `opentelemetry-exporter-otlp-proto-grpc` - OTLP gRPC exporter for traces and logs

## Quick Start

### Automatic Configuration with elastic-start-local

The easiest way to get started is with the provided Elastic Stack setup, which automatically configures OpenTelemetry with APM server integration:

```bash
# Start local Elastic Stack with APM server
./local-stack.sh -o start

# Run any example - telemetry is automatically configured
python examples/simple_index_connector.py
```

The examples will automatically:
- Detect APM server configuration from `elastic-start-local/.env`
- Configure OpenTelemetry with proper authentication
- Send traces and logs to the local APM server
- Display telemetry status information including log forwarding

### Programmatic Configuration

```python
from kibana import Kibana, configure_opentelemetry

# Configure OpenTelemetry with APM server (traces and logs)
configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:8200",  # APM server endpoint
    headers={"authorization": "Bearer your_apm_token"},
    protocol="grpc",
    # Log forwarding configuration
    logs_enabled=True,
    logs_level="WARNING",
    logs_loggers=["kibana", "my-app"]
)

# Use the client - traces and logs are automatically created
client = Kibana(
    hosts=["http://localhost:5601"],
    basic_auth=("elastic", "password")
)

response = client.perform_request("GET", "/api/status")
client.close()
```

### Environment Variable Configuration

Set environment variables for APM server integration:

```bash
# Trace configuration
export KIBANA_OTEL_ENABLED=true
export OTEL_SERVICE_NAME=my-app
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your_apm_token"
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc

# Log forwarding configuration
export KIBANA_OTEL_LOGS_ENABLED=true
export KIBANA_OTEL_LOGS_LEVEL=WARNING
export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app
```

Then configure in code:

```python
from kibana import configure_opentelemetry

# Reads from environment variables
configure_opentelemetry()
```

### Automatic Configuration from .env Files

The system automatically detects configuration from `.env` files with variable expansion support:

```bash
# In elastic-start-local/.env or your project .env
KIBANA_OTEL_ENABLED=true
OTEL_SERVICE_NAME=my-kibana-app
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:${APM_LOCAL_PORT:-8200}
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer ${ELASTIC_APM_SECRET_TOKEN}
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ELASTIC_APM_SECRET_TOKEN=your_generated_token

# Log forwarding configuration
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=WARNING
KIBANA_OTEL_LOGS_LOGGERS=kibana,kibana.examples
```

Configuration precedence (highest to lowest):
1. Environment variables
2. .env file in elastic-start-local/
3. .env file in current directory
4. Default values

## Configuration Options

### Environment Variables

#### Trace Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `KIBANA_OTEL_ENABLED` | Enable/disable instrumentation | `false` |
| `OTEL_SERVICE_NAME` | Service name for traces | `kibana-py-example` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL (APM server) | `http://localhost:8200` |
| `OTEL_EXPORTER_OTLP_HEADERS` | Authentication headers | `authorization=Bearer ${ELASTIC_APM_SECRET_TOKEN}` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP protocol: `grpc`, `http/protobuf` | `grpc` |
| `ELASTIC_APM_SECRET_TOKEN` | APM server authentication token | (none) |
| `OTEL_RESOURCE_ATTRIBUTES` | Resource attributes (comma-separated) | - |

#### Log Forwarding Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `KIBANA_OTEL_LOGS_ENABLED` | Enable/disable log forwarding | `false` |
| `KIBANA_OTEL_LOGS_LEVEL` | Minimum log level to forward | `WARNING` |
| `KIBANA_OTEL_LOGS_LOGGERS` | Comma-separated logger names to forward | `kibana,kibana.examples` |
| `OTEL_LOGS_EXPORTER` | Log exporter type | `otlp` |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | Logs-specific endpoint (optional) | `{endpoint}/v1/logs` |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | Logs protocol (inherits from traces) | `{protocol}` |

### Variable Expansion

The configuration system supports variable expansion in .env files:
- `${VARIABLE_NAME}` - Expands to the value of VARIABLE_NAME
- `${VARIABLE_NAME:-default}` - Uses default if VARIABLE_NAME is not set
- Example: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:${APM_LOCAL_PORT:-8200}`

### Programmatic Configuration

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,                                           # Enable instrumentation
    service_name="my-app",                                 # Service name
    exporter="otlp",                                       # Exporter type
    endpoint="http://localhost:8200",                     # APM server endpoint
    headers={"authorization": "Bearer your_apm_token"},   # Authentication headers
    protocol="grpc",                                       # OTLP protocol
    console_export=False,                                  # Also export to console
    # Log forwarding configuration
    logs_enabled=True,                                     # Enable log forwarding
    logs_level="WARNING",                                  # Minimum log level
    logs_loggers=["kibana", "my-app"],                    # Loggers to forward
)
```

### Example Configuration Detection

The examples include utilities for automatic configuration detection:

```python
from examples.utils import get_otel_config, configure_example_telemetry, print_telemetry_info

# Get detected configuration
config = get_otel_config()
print(f"Endpoint: {config['endpoint']}")
print(f"Enabled: {config['enabled']}")

# Configure telemetry for examples
telemetry_enabled = configure_example_telemetry()

# Display telemetry status
print_telemetry_info()
```

## Log Forwarding

The Kibana Python client can automatically forward application logs to APM servers using OpenTelemetry's logging protocol. This provides complete observability by correlating logs with traces.

### Quick Start with Log Forwarding

```python
from kibana import Kibana, configure_opentelemetry
import logging

# Configure OpenTelemetry with log forwarding
configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    endpoint="http://localhost:8200",
    headers={"authorization": "Bearer your_apm_token"},
    logs_enabled=True,
    logs_level="WARNING"
)

# Create a logger
logger = logging.getLogger("my-app")

# Use the client - logs are automatically forwarded
client = Kibana(hosts=["http://localhost:5601"])

try:
    response = client.perform_request("GET", "/api/status")
    logger.info("Status check successful")
except Exception as e:
    logger.error(f"Status check failed: {e}")  # This log will be forwarded to APM
finally:
    client.close()
```

### Log Forwarding Configuration

#### Environment Variables

Enable log forwarding with environment variables:

```bash
# Enable log forwarding
export KIBANA_OTEL_LOGS_ENABLED=true

# Set minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export KIBANA_OTEL_LOGS_LEVEL=WARNING

# Specify which loggers to forward (comma-separated)
export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,my-module

# Optional: Use different endpoint for logs
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:8200/v1/logs
```

#### Programmatic Configuration

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    # Trace configuration
    enabled=True,
    service_name="my-app",
    endpoint="http://localhost:8200",

    # Log forwarding configuration
    logs_enabled=True,                    # Enable log forwarding
    logs_level="WARNING",                 # Minimum level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    logs_loggers=["kibana", "my-app"],   # Logger names to forward
)
```

#### .env File Configuration

```bash
# In your .env file
KIBANA_OTEL_ENABLED=true
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=WARNING
KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app
OTEL_SERVICE_NAME=my-application
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer your_token
```

### Log Level Filtering

Control which log levels are forwarded to reduce noise and costs:

```python
# Only forward ERROR and CRITICAL logs
configure_opentelemetry(
    logs_enabled=True,
    logs_level="ERROR"
)

# Forward all logs including DEBUG (not recommended for production)
configure_opentelemetry(
    logs_enabled=True,
    logs_level="DEBUG"
)
```

**Recommended log levels by environment:**
- **Development**: `DEBUG` or `INFO` for full visibility
- **Staging**: `WARNING` for important events and errors
- **Production**: `ERROR` for errors and critical issues only

### Logger Selection

Specify which loggers should forward logs to APM:

```python
# Forward logs from specific modules
configure_opentelemetry(
    logs_enabled=True,
    logs_loggers=["kibana", "my-app", "my-module"]
)

# Forward logs from all loggers (not recommended)
configure_opentelemetry(
    logs_enabled=True,
    logs_loggers=[""]  # Empty string matches all loggers
)
```

### Structured Logging

Use structured logging for better searchability in APM:

```python
import logging

logger = logging.getLogger("my-app")

# Simple log message
logger.error("Connection failed")

# Structured logging with extra fields
logger.error(
    "API request failed",
    extra={
        "http_method": "POST",
        "http_url": "/api/connectors",
        "http_status_code": 400,
        "error_code": "VALIDATION_ERROR",
        "user_id": "user123"
    }
)

# Using format strings for structured data
logger.warning(
    "Slow API response: %s took %dms",
    "/api/status",
    1500,
    extra={"response_time_ms": 1500, "endpoint": "/api/status"}
)
```

### Log-Trace Correlation

When both traces and logs are enabled, logs automatically include trace correlation:

```python
from kibana import Kibana, configure_opentelemetry
import logging

# Enable both traces and logs
configure_opentelemetry(
    enabled=True,
    logs_enabled=True,
    service_name="my-app"
)

logger = logging.getLogger("my-app")
client = Kibana(hosts=["http://localhost:5601"])

# This creates a trace
response = client.actions.list()

# This log will be correlated with the trace
logger.info("Retrieved %d connectors", len(response.body))

client.close()
```

In APM, you'll see:
- The trace for `client.actions.list()`
- The log message with the same `trace_id` and `span_id`
- Ability to navigate between traces and logs

### Log Attributes

Forwarded logs include rich metadata:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "ERROR",
  "message": "Connection failed",

  "service": {
    "name": "my-app",
    "version": "0.1.0",
    "language": "python"
  },

  "log": {
    "logger": "my-app",
    "level": "ERROR",
    "file": {
      "name": "main.py",
      "line": 42
    },
    "function": "connect_to_api"
  },

  "trace": {
    "trace_id": "abc123...",
    "span_id": "def456..."
  },

  "custom": {
    "http_method": "POST",
    "user_id": "user123"
  }
}
```

### Performance Considerations

#### Batch Processing

Logs are batched for efficient transmission:

```python
# Logs are automatically batched with these defaults:
# - Batch size: 512 log records
# - Batch timeout: 5 seconds
# - Queue size: 2048 log records

# For high-volume applications, you may want to adjust these
# (requires custom OpenTelemetry configuration)
```

#### Filtering Best Practices

1. **Use appropriate log levels**: Don't forward DEBUG logs in production
2. **Select specific loggers**: Only forward logs from relevant modules
3. **Implement sampling**: For very high-volume scenarios
4. **Monitor costs**: Log forwarding can impact APM server costs

#### Zero Overhead When Disabled

```python
# When logs_enabled=False, there's zero performance overhead
configure_opentelemetry(
    enabled=True,
    logs_enabled=False  # No log forwarding overhead
)
```

### Error Handling and Graceful Degradation

Log forwarding is designed to never interrupt your application:

```python
# If APM server is unavailable, logs continue to work locally
logger.error("This will appear in console even if APM is down")

# If authentication fails, log forwarding is disabled automatically
# Your application continues to work normally

# Network timeouts don't block your application
# Logs are queued and retried automatically
```

### Troubleshooting Log Forwarding

#### Check Log Forwarding Status

```python
from examples.utils import print_telemetry_info

# This shows both trace and log forwarding status
print_telemetry_info()
```

Output example:
```
📊 OpenTelemetry Status:
  ✅ Traces: Enabled (endpoint: http://localhost:8200)
  ✅ Logs: Enabled (level: WARNING, loggers: kibana,my-app)
  📡 Protocol: grpc
  🔑 Authentication: Bearer token
```

#### Common Issues

1. **Logs not appearing in APM**:
   ```bash
   # Check if log forwarding is enabled
   export KIBANA_OTEL_LOGS_ENABLED=true

   # Verify log level is appropriate
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG  # Temporarily lower level

   # Check logger names
   export KIBANA_OTEL_LOGS_LOGGERS=your-logger-name
   ```

2. **Authentication errors**:
   ```bash
   # Verify APM server accepts log data
   curl -X POST "http://localhost:8200/v1/logs" \
        -H "Authorization: Bearer your_token" \
        -H "Content-Type: application/x-protobuf"
   ```

3. **Performance issues**:
   ```python
   # Reduce log volume
   configure_opentelemetry(
       logs_enabled=True,
       logs_level="ERROR"  # Only errors and critical
   )
   ```

#### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging

# Enable debug logging for OpenTelemetry
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
logging.getLogger("kibana.observability").setLevel(logging.DEBUG)

# This will show detailed log forwarding information
configure_opentelemetry(
    logs_enabled=True,
    console_export=True  # Also see logs in console
)
```

## Span Attributes

Each Kibana API request creates a span with the following attributes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `http.method` | HTTP method | `GET`, `POST`, `PUT`, `DELETE` |
| `http.url` | Full URL with query params | `/api/status?format=json` |
| `http.status_code` | Response status code | `200`, `404`, `500` |
| `kibana.api.path` | API endpoint path | `/api/status` |
| `kibana.api.params` | Query parameters | `{"type": "dashboard"}` |

## Log Attributes

Each forwarded log record includes the following attributes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `service.name` | Service name | `my-app` |
| `service.version` | Service version | `0.1.0` |
| `service.language.name` | Programming language | `python` |
| `log.logger` | Logger name | `kibana.actions` |
| `log.level` | Log level | `ERROR` |
| `log.file.name` | Source file name | `actions.py` |
| `log.file.line` | Source line number | `123` |
| `log.function` | Function name | `create_connector` |
| `trace_id` | Trace ID (when available) | `abc123...` |
| `span_id` | Span ID (when available) | `def456...` |

## Exporters

### OTLP Exporter (Recommended)

Export to any OpenTelemetry-compatible backend (Jaeger, Tempo, Elastic APM, etc.):

```python
configure_opentelemetry(
    enabled=True,
    exporter="otlp",
    endpoint="http://localhost:4317"
)
```

### Console Exporter (Development)

Export to console for debugging:

```python
configure_opentelemetry(
    enabled=True,
    exporter="console"
)
```

### Custom Exporter

Use a custom tracer provider:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

from kibana import KibanaInstrumentor

# Create custom tracer provider
tracer_provider = TracerProvider()
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
tracer_provider.add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Set global tracer provider
trace.set_tracer_provider(tracer_provider)

# Enable Kibana instrumentation
instrumentor = KibanaInstrumentor.get_instance()
instrumentor.enable(tracer_provider=tracer_provider)
```

## Integration with Elastic APM

### Local Development with elastic-start-local

The easiest way to get started with Elastic APM integration:

```bash
# Start the full Elastic Stack with APM server
./local-stack.sh -o start

# Configuration is automatically created in elastic-start-local/.env:
# KIBANA_OTEL_ENABLED=true
# KIBANA_OTEL_LOGS_ENABLED=true
# OTEL_SERVICE_NAME=kibana-py-example
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
# OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer generated_token
# ELASTIC_APM_SECRET_TOKEN=generated_token

# Run examples - they automatically use APM configuration
python examples/simple_index_connector.py

# View traces and logs in Kibana APM
open http://localhost:5601/app/apm
```

### Production APM Server

Send traces and logs to a production Elastic APM server:

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-production-app",
    exporter="otlp",
    endpoint="https://your-apm-server:8200",
    headers={"authorization": "Bearer your-secret-token"},
    protocol="grpc",  # or "http/protobuf"
    logs_enabled=True,
    logs_level="WARNING"
)
```

Or use environment variables:

```bash
export KIBANA_OTEL_ENABLED=true
export OTEL_SERVICE_NAME=my-production-app
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your-apm-server:8200
export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your-secret-token"
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export KIBANA_OTEL_LOGS_ENABLED=true
export KIBANA_OTEL_LOGS_LEVEL=WARNING
```

### APM Server Authentication

The system supports multiple authentication methods:

1. **Bearer Token** (recommended):
   ```bash
   export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your_secret_token"
   ```

2. **API Key**:
   ```bash
   export OTEL_EXPORTER_OTLP_HEADERS="authorization=ApiKey your_api_key"
   ```

3. **Multiple Headers**:
   ```bash
   export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer token,x-custom-header=value"
   ```

### APM Server Connectivity Validation

The system automatically validates APM server connectivity:

```python
from kibana.observability import validate_apm_connection

# Check if APM server is available
is_available = validate_apm_connection(
    endpoint="http://localhost:8200",
    headers={"authorization": "Bearer your_token"}
)

if is_available:
    print("✅ APM server is available")
else:
    print("❌ APM server is not available")
```

### Viewing Traces and Logs in Kibana APM

1. **Access APM**: Navigate to http://localhost:5601/app/apm
2. **Select Service**: Look for your service name (e.g., "kibana-py-example")
3. **View Transactions**: Click on transactions to see detailed trace information
4. **View Logs**: Navigate to the "Logs" tab to see correlated log messages
5. **Filter Operations**: Look for operations like:
   - `actions.create` - Creating connectors
   - `actions.execute` - Executing connectors
   - `spaces.get` - Space operations
   - `saved_objects.create` - Saved object operations
   - `status.get` - Status checks
6. **Trace-Log Correlation**: Click on individual spans to see related log messages
7. **Log Search**: Use the logs view to search and filter log messages by level, logger, or custom attributes

## Integration with Jaeger

Send traces to Jaeger:

```bash
# Start Jaeger all-in-one
docker run -d --name jaeger \
  -p 4317:4317 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:4317"
)
```

View traces at http://localhost:16686

## Integration with Grafana Tempo

Send traces to Grafana Tempo:

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://tempo:4317"
)
```

## Disabling Instrumentation

### Programmatically

```python
from kibana import KibanaInstrumentor

instrumentor = KibanaInstrumentor.get_instance()
instrumentor.disable()
```

### Environment Variable

```bash
export KIBANA_OTEL_ENABLED=false
```

## Performance Considerations

### Sampling

To reduce overhead, use sampling:

```bash
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1  # Sample 10% of requests
```

### Batch Processing

Spans are batched by default for better performance. Configure batch size:

```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor

processor = BatchSpanProcessor(
    exporter,
    max_queue_size=2048,
    schedule_delay_millis=5000,
    max_export_batch_size=512,
)
```

## Example: Full Observability Stack

### Docker Compose

```yaml
version: '3.8'

services:
  # Jaeger for tracing
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "4317:4317"   # OTLP gRPC
      - "16686:16686" # Jaeger UI
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  # Your application
  app:
    build: .
    environment:
      - KIBANA_OTEL_ENABLED=true
      - OTEL_SERVICE_NAME=my-app
      - KIBANA_OTEL_EXPORTER=otlp
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### Python Application

```python
from kibana import Kibana, configure_opentelemetry

# Configure OpenTelemetry (reads from environment)
configure_opentelemetry()

# Use the client
client = Kibana(
    hosts=["http://kibana:5601"],
    basic_auth=("elastic", "password")
)

# All requests are automatically traced
response = client.perform_request("GET", "/api/status")
spaces = client.perform_request("GET", "/api/spaces/space")

client.close()
```

## Troubleshooting

### APM Server Connection Issues

#### Traces and Logs

1. **Check APM server availability**:
   ```bash
   curl -X GET "http://localhost:8200/"
   ```

2. **Verify authentication**:
   ```bash
   curl -H "Authorization: Bearer your_token" "http://localhost:8200/config/v1/agents"
   ```

3. **Test OTLP endpoints**:
   ```bash
   # Test traces endpoint
   curl -X POST "http://localhost:8200/v1/traces" \
        -H "Authorization: Bearer your_token" \
        -H "Content-Type: application/x-protobuf"

   # Test logs endpoint
   curl -X POST "http://localhost:8200/v1/logs" \
        -H "Authorization: Bearer your_token" \
        -H "Content-Type: application/x-protobuf"
   ```

### Configuration Issues

1. **Check telemetry status in examples**:
   ```python
   from examples.utils import print_telemetry_info
   print_telemetry_info()
   ```

2. **Verify configuration detection**:
   ```python
   from examples.utils import get_otel_config
   config = get_otel_config()
   print(f"Config: {config}")
   ```

3. **Test manual configuration**:
   ```python
   from kibana import configure_opentelemetry

   configure_opentelemetry(
       enabled=True,
       service_name="test-service",
       endpoint="http://localhost:8200",
       headers={"authorization": "Bearer your_token"},
       console_export=True  # Also log to console
   )
   ```

### Common Error Messages

1. **"APM server not available, telemetry disabled"**:
   - Check if APM server is running
   - Verify endpoint URL is correct
   - Check network connectivity

2. **"APM authentication failed"**:
   - Verify ELASTIC_APM_SECRET_TOKEN is correct
   - Check token format (Bearer vs ApiKey)
   - Ensure token has proper permissions

3. **"Protocol mismatch"**:
   - Try switching between "grpc" and "http/protobuf"
   - Check APM server protocol support
   - Verify firewall/proxy settings

4. **"Telemetry disabled"**:
   - Set KIBANA_OTEL_ENABLED=true
   - Check configuration precedence
   - Verify .env file is being read

5. **"Log forwarding disabled"**:
   - Set KIBANA_OTEL_LOGS_ENABLED=true
   - Check log level configuration (KIBANA_OTEL_LOGS_LEVEL)
   - Verify logger names (KIBANA_OTEL_LOGS_LOGGERS)
   - Ensure OpenTelemetry logs dependencies are installed

6. **"Logs not appearing in APM"**:
   - Check log level filtering (logs below configured level are not forwarded)
   - Verify logger names match your application loggers
   - Check APM server logs endpoint connectivity
   - Ensure log messages are being generated at or above configured level

### Debug Mode

1. **Check if instrumentation is enabled**:
   ```python
   from kibana import KibanaInstrumentor

   instrumentor = KibanaInstrumentor.get_instance()
   print(f"Enabled: {instrumentor.is_enabled()}")
   ```

2. **Enable debug logging**:
   ```python
   import logging

   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger("kibana.observability")
   logger.setLevel(logging.DEBUG)
   ```

3. **Verify spans are exported**:
   ```python
   configure_opentelemetry(
       enabled=True,
       exporter="console"  # See spans in console
   )
   ```

### Performance Troubleshooting

1. **High latency with telemetry enabled**:
   - Check APM server response times
   - Consider using async span processors
   - Implement sampling for high-volume scenarios

2. **Memory usage issues**:
   - Monitor span queue sizes
   - Adjust batch processor settings
   - Check for span leaks

3. **Network issues**:
   - Implement retry logic with exponential backoff
   - Use connection pooling
   - Monitor network timeouts

### Validation Scripts

Create a validation script to test your setup:

```python
#!/usr/bin/env python3
"""Validate OpenTelemetry APM integration."""

import sys
from examples.utils import get_otel_config, configure_example_telemetry, print_telemetry_info
from kibana import Kibana, configure_opentelemetry

def main():
    print("🔍 Validating OpenTelemetry APM Integration")
    print("=" * 50)

    # Check configuration
    config = get_otel_config()
    print(f"📊 Configuration detected: {config['enabled']}")
    print(f"📊 Endpoint: {config['endpoint']}")
    print(f"📊 Service: {config['service_name']}")

    # Configure telemetry
    traces_enabled, logs_enabled = configure_example_telemetry()
    print(f"📊 Traces configured: {traces_enabled}")
    print(f"📊 Logs configured: {logs_enabled}")

    # Display status
    print_telemetry_info()

    if traces_enabled or logs_enabled:
        print("✅ OpenTelemetry APM integration is working!")
        print("🔗 View traces and logs at: http://localhost:5601/app/apm")

        if traces_enabled and logs_enabled:
            print("🎯 Both traces and logs are enabled - full observability!")
        elif traces_enabled:
            print("📈 Traces only - consider enabling logs for complete observability")
        else:
            print("📝 Logs only - consider enabling traces for complete observability")
    else:
        print("❌ OpenTelemetry APM integration is not working")
        print("💡 Check APM server and configuration")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Best Practices

1. **Use meaningful service names**: Helps identify services in traces
2. **Enable sampling in production**: Reduces overhead
3. **Add custom attributes**: Enrich spans with business context
4. **Monitor exporter health**: Ensure traces are being sent
5. **Use batch processing**: Better performance than synchronous export
6. **Secure OTLP endpoints**: Use TLS and authentication
7. **Test locally first**: Use Jaeger or console exporter

## Security Considerations

- **Sensitive data**: Request/response bodies may contain sensitive data
- **Authentication**: Secure OTLP endpoints with authentication
- **Network**: Use TLS for OTLP connections
- **Sampling**: Use sampling to reduce data volume
- **PII**: Be careful not to log personally identifiable information

## Further Reading

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [Elastic APM OpenTelemetry](https://www.elastic.co/guide/en/apm/guide/current/open-telemetry.html)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/latest/)
