# Observability Examples

All examples include built-in OpenTelemetry support for distributed tracing and log forwarding.

## Overview

Learn how to:
- Configure OpenTelemetry tracing
- Enable log forwarding to APM
- Correlate logs with traces
- Monitor API operations

## Quick Start

```python
from kibana import Kibana
from examples.utils import configure_example_telemetry
import logging

# Configure telemetry
traces_enabled, logs_enabled = configure_example_telemetry(
    enabled=True,
    logs_enabled=True
)

# Create logger
logger = logging.getLogger("my-app")

# Initialize client
client = Kibana("http://localhost:5601")

# Operations are automatically traced
connector = client.actions.create(
    name="My Connector",
    connector_type_id=".index",
    config={"index": "my-index"}
)

# Logs are automatically forwarded
logger.info(
    "Connector created",
    extra={
        "connector_id": connector.body["id"],
        "connector_type": ".index"
    }
)
```

## Configuration

### Environment Variables

```bash
# Trace configuration
export KIBANA_OTEL_ENABLED=true
export OTEL_SERVICE_NAME=my-app
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200

# Log forwarding
export KIBANA_OTEL_LOGS_ENABLED=true
export KIBANA_OTEL_LOGS_LEVEL=WARNING
export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app
```

### Programmatic Configuration

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:8200"
)
```

## Structured Logging

```python
import logging

logger = logging.getLogger("my-app")

# Log with structured data
logger.info(
    "API request completed",
    extra={
        "http_method": "POST",
        "http_path": "/api/actions/connector",
        "http_status_code": 200,
        "response_time_ms": 150,
        "connector_id": "conn-123"
    }
)
```

## Log-Trace Correlation

When both traces and logs are enabled, logs automatically include trace correlation:

```python
# This creates a trace
response = client.actions.list()

# This log is correlated with the trace
logger.info(
    "Retrieved connectors",
    extra={
        "connector_count": len(response.body),
        "operation": "list_connectors"
    }
)
```

In APM, you'll see:
- The trace for `client.actions.list()`
- The log message with the same `trace_id` and `span_id`
- Ability to navigate between traces and logs

## Viewing Telemetry Data

### In Kibana APM

1. Open Kibana: http://localhost:5601/app/apm
2. Select your service name
3. View traces and logs
4. Navigate between correlated data

### Example Trace

```
Service: my-app
Operation: POST /api/actions/connector
Duration: 150ms
Status: 200

Spans:
  ├─ HTTP POST /api/actions/connector (150ms)
  │  └─ Elasticsearch index operation (45ms)
  └─ Space validation (5ms)

Logs:
  [INFO] Connector created (connector_id=conn-123)
```

## Best Practices

1. **Use meaningful logger names** for filtering
2. **Include structured data** in log extra fields
3. **Set appropriate log levels** (WARNING for production)
4. **Monitor trace performance** for slow operations
5. **Use log forwarding** for error tracking

## Automatic Configuration

With `elastic-start-local`:

```bash
./local-stack.sh -o start

# Telemetry is automatically configured
python examples/simple_index_connector.py
```

## Performance Considerations

### Log Level Filtering

```bash
# Production: Only forward important logs
export KIBANA_OTEL_LOGS_LEVEL=ERROR

# Development: Forward all logs
export KIBANA_OTEL_LOGS_LEVEL=DEBUG
```

### Logger Selection

```bash
# Forward specific loggers only
export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,critical-module
```

### Zero Overhead When Disabled

```bash
# No performance impact when disabled
export KIBANA_OTEL_ENABLED=false
export KIBANA_OTEL_LOGS_ENABLED=false
```

## Troubleshooting

### Check Telemetry Status

All examples display telemetry status:

```
📊 OpenTelemetry Status:
  ✅ Traces: Enabled (endpoint: http://localhost:8200)
  ✅ Logs: Enabled (level: WARNING, loggers: kibana,my-app)
  📡 Protocol: grpc
  🔑 Authentication: Bearer token
```

### Common Issues

1. **Traces not appearing**: Check `KIBANA_OTEL_ENABLED=true`
2. **Logs not appearing**: Check `KIBANA_OTEL_LOGS_ENABLED=true`
3. **Authentication errors**: Verify APM token

## Next Steps

- [Observability User Guide](../user-guide/observability.md)
- [Telemetry Troubleshooting](../troubleshooting/telemetry.md)

## Related Documentation

- [Observability User Guide](../user-guide/observability.md)
- [Telemetry Troubleshooting](../troubleshooting/telemetry.md)
- [Log Forwarding Migration Guide](../migration-guides/log-forwarding.md)
