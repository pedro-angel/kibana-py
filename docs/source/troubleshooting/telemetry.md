# OpenTelemetry Troubleshooting

This guide helps you diagnose and resolve common issues with OpenTelemetry integration in kibana-py, including trace instrumentation and log forwarding.

:::{seealso}
For general observability setup and configuration, see {doc}`../user-guide/observability`.
:::

## Quick Diagnosis

### Check Telemetry Status

All examples display telemetry status at startup. Look for this output:

```
📊 OpenTelemetry Status:
  ✅ Traces: Enabled (endpoint: http://localhost:8200)
  ✅ Logs: Enabled (level: WARNING, loggers: kibana,my-app)
  📡 Protocol: grpc
  🔑 Authentication: Bearer token
```

### Common Status Messages

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `✅ Logs: Enabled` | Log forwarding is working | None |
| `❌ Logs: Disabled` | Log forwarding is disabled | Enable with `KIBANA_OTEL_LOGS_ENABLED=true` |
| `⚠️ Logs: Partial` | Some loggers configured | Check logger names |
| `❌ APM server not available` | Cannot connect to APM server | Check APM server and network |

## Configuration Issues

### Log Forwarding Not Enabled

**Symptom**: `❌ Logs: Disabled` in status output

**Causes**:
- `KIBANA_OTEL_LOGS_ENABLED` not set to `true`
- Missing OpenTelemetry logs dependencies
- Configuration precedence issues

**Solutions**:

1. Enable log forwarding:
   ```bash
   export KIBANA_OTEL_LOGS_ENABLED=true
   ```

2. Check `.env` file (if using elastic-start-local):
   ```bash
   # In elastic-start-local/.env
   KIBANA_OTEL_LOGS_ENABLED=true
   ```

3. Verify dependencies:
   ```bash
   pip install kibana-py[observability]
   ```

4. Check configuration precedence:
   - Environment variables override `.env` files
   - `elastic-start-local/.env` overrides local `.env`
   - Ensure no conflicting environment variables

### Wrong Log Level Configuration

**Symptom**: Some logs missing in APM, traces work fine

**Causes**:
- Log level set too high (e.g., `ERROR` when you want `INFO` logs)
- Application using lower log levels than configured

**Solutions**:

1. Lower the log level temporarily:
   ```bash
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG  # Forward all logs
   ```

2. Check your application's log levels:
   ```python
   import logging

   logger = logging.getLogger("my-app")
   logger.info("This won't be forwarded if level is WARNING or higher")
   logger.warning("This will be forwarded if level is WARNING or lower")
   ```

3. Use appropriate levels by environment:
   ```bash
   # Development
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG

   # Staging
   export KIBANA_OTEL_LOGS_LEVEL=WARNING

   # Production
   export KIBANA_OTEL_LOGS_LEVEL=ERROR
   ```

### Incorrect Logger Names

**Symptom**: No logs forwarded despite correct level configuration

**Causes**:
- Logger names don't match `KIBANA_OTEL_LOGS_LOGGERS` configuration
- Typos in logger names
- Using `__name__` instead of explicit logger names

**Solutions**:

1. Check your logger names:
   ```python
   import logging

   # Make sure this matches KIBANA_OTEL_LOGS_LOGGERS
   logger = logging.getLogger("my-app")  # Should be in KIBANA_OTEL_LOGS_LOGGERS
   ```

2. Update logger configuration:
   ```bash
   # Include your application's logger names
   export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,my-module
   ```

3. Use wildcard for testing (not recommended for production):
   ```bash
   # Forward all loggers (expensive)
   export KIBANA_OTEL_LOGS_LOGGERS=""
   ```

4. Debug logger names:
   ```python
   import logging

   # Print logger name to verify
   logger = logging.getLogger("my-app")
   print(f"Logger name: {logger.name}")
   logger.error("Test message")
   ```

## APM Server Connectivity Issues

### APM Server Not Available

**Symptom**: `❌ APM server not available, telemetry disabled`

**Causes**:
- APM server not running
- Wrong endpoint URL
- Network connectivity issues
- Firewall blocking connections

**Solutions**:

1. Check if APM server is running:
   ```bash
   curl -X GET "http://localhost:8200/"
   ```

   Expected response:
   ```json
   {
     "build_date": "2024-01-01T00:00:00Z",
     "build_sha": "abc123",
     "version": "8.x.x"
   }
   ```

2. Verify endpoint configuration:
   ```bash
   # Check current configuration
   echo $OTEL_EXPORTER_OTLP_ENDPOINT

   # Should be APM server URL, not Kibana URL
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200  # APM server
   # NOT: http://localhost:5601  # This is Kibana
   ```

3. Test network connectivity:
   ```bash
   # Test basic connectivity
   telnet localhost 8200

   # Test with curl
   curl -v http://localhost:8200/
   ```

4. Check Docker/container setup:
   ```bash
   # If using elastic-start-local
   cd elastic-start-local
   docker-compose ps

   # APM server should be running
   docker-compose logs apm-server
   ```

### Authentication Failures

**Symptom**: `❌ APM authentication failed`

**Causes**:
- Invalid or expired APM secret token
- Wrong authentication header format
- Token permissions issues

**Solutions**:

1. Verify APM token:
   ```bash
   # Check token is set
   echo $ELASTIC_APM_SECRET_TOKEN

   # Test authentication
   curl -H "Authorization: Bearer $ELASTIC_APM_SECRET_TOKEN" \
        "http://localhost:8200/config/v1/agents"
   ```

2. Check header format:
   ```bash
   # Correct format
   export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your_token"

   # NOT: "Authorization: Bearer your_token"  # Wrong format
   ```

3. Regenerate token (if using elastic-start-local):
   ```bash
   cd elastic-start-local
   ./local-stack.sh -o stop
   ./local-stack.sh -o start  # This generates a new token
   ```

4. Test logs endpoint specifically:
   ```bash
   curl -X POST "http://localhost:8200/v1/logs" \
        -H "Authorization: Bearer $ELASTIC_APM_SECRET_TOKEN" \
        -H "Content-Type: application/x-protobuf"
   ```

### Protocol Mismatch

**Symptom**: Connection timeouts or protocol errors

**Causes**:
- APM server doesn't support configured protocol
- Network proxy issues
- Port conflicts

**Solutions**:

1. Try different protocols:
   ```bash
   # Try gRPC (default)
   export OTEL_EXPORTER_OTLP_PROTOCOL=grpc

   # Try HTTP if gRPC fails
   export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
   ```

2. Check APM server protocol support:
   ```bash
   # Check APM server configuration
   curl http://localhost:8200/config/v1/agents
   ```

3. Verify ports:
   ```bash
   # Standard APM server ports
   # 8200: HTTP/HTTPS
   # 8200: gRPC (same port, different protocol)

   netstat -an | grep 8200
   ```

## Performance Issues

### High Latency with Log Forwarding

**Symptom**: Application becomes slow when log forwarding is enabled

**Causes**:
- Too many logs being forwarded
- Synchronous log processing
- Network latency to APM server

**Solutions**:

1. Reduce log volume:
   ```bash
   # Only forward errors
   export KIBANA_OTEL_LOGS_LEVEL=ERROR

   # Limit to critical loggers
   export KIBANA_OTEL_LOGS_LOGGERS=critical-module
   ```

2. Check log frequency:
   ```python
   import logging

   logger = logging.getLogger("my-app")

   # Avoid high-frequency logging in loops
   for i in range(1000):
       # DON'T do this - creates 1000 log entries
       logger.info(f"Processing item {i}")

   # DO this instead - log summary
   logger.info(f"Processing {len(items)} items")
   # ... process items ...
   logger.info(f"Completed processing {len(items)} items")
   ```

3. Monitor APM server performance:
   ```bash
   # Check APM server response times
   curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8200/"

   # curl-format.txt:
   # time_total: %{time_total}
   ```

### Memory Usage Issues

**Symptom**: High memory usage when log forwarding is enabled

**Causes**:
- Large log messages
- Log queue buildup
- Memory leaks in log processing

**Solutions**:

1. Limit log message size:
   ```python
   import logging

   logger = logging.getLogger("my-app")

   # Avoid logging large objects
   large_data = {"key": "x" * 10000}
   logger.info("Processing data", extra={"data_size": len(str(large_data))})  # Good
   # logger.info("Processing data", extra={"data": large_data})  # Bad - too large
   ```

2. Monitor log queue:
   ```python
   # Check if logs are being processed
   import logging

   # Enable debug logging to see queue status
   logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
   ```

3. Implement log sampling:
   ```python
   import random
   import logging

   logger = logging.getLogger("my-app")

   # Sample high-frequency logs
   if random.random() < 0.1:  # 10% sampling
       logger.debug("High frequency debug message")
   ```

## Application Integration Issues

### Logs Not Correlated with Traces

**Symptom**: Logs appear in APM but not linked to traces

**Causes**:
- Traces disabled while logs enabled
- Different service names for traces and logs
- Timing issues between trace and log creation

**Solutions**:

1. Enable both traces and logs:
   ```bash
   export KIBANA_OTEL_ENABLED=true      # Enable traces
   export KIBANA_OTEL_LOGS_ENABLED=true # Enable logs
   ```

2. Use same service name:
   ```bash
   export OTEL_SERVICE_NAME=my-app  # Same for both traces and logs
   ```

3. Log within trace context:
   ```python
   from kibana import Kibana
   import logging

   logger = logging.getLogger("my-app")
   client = Kibana("http://localhost:5601")

   # This creates a trace
   response = client.actions.list()

   # Log immediately after API call (within trace context)
   logger.info(f"Retrieved {len(response.body)} connectors")

   client.close()
   ```

### Custom Attributes Not Appearing

**Symptom**: Basic logs work but custom attributes missing

**Causes**:
- Incorrect `extra` parameter usage
- Attribute name conflicts
- Serialization issues with complex objects

**Solutions**:

1. Use correct `extra` parameter:
   ```python
   import logging

   logger = logging.getLogger("my-app")

   # Correct way
   logger.info(
       "Operation completed",
       extra={
           "operation_type": "create_connector",
           "duration_ms": 150,
           "success": True
       }
   )

   # Wrong way - attributes won't be forwarded
   logger.info("Operation completed", {"operation_type": "create_connector"})
   ```

2. Avoid reserved attribute names:
   ```python
   # Avoid these reserved names
   reserved_names = ["name", "msg", "args", "levelname", "levelno", "pathname",
                    "filename", "module", "lineno", "funcName", "created",
                    "msecs", "relativeCreated", "thread", "threadName",
                    "processName", "process", "getMessage", "exc_info",
                    "exc_text", "stack_info"]

   # Use prefixed names instead
   logger.info(
       "User action",
       extra={
           "user_name": "john",      # Good
           "action_type": "login",   # Good
           # "name": "john",         # Bad - conflicts with log record name
       }
   )
   ```

3. Serialize complex objects:
   ```python
   import json
   import logging

   logger = logging.getLogger("my-app")

   complex_object = {"nested": {"data": [1, 2, 3]}}

   # Serialize complex objects
   logger.info(
       "Processing complex data",
       extra={
           "data_summary": json.dumps(complex_object),
           "data_size": len(str(complex_object))
       }
   )
   ```

## Debugging Tools and Techniques

### Enable Debug Logging

```python
import logging

# Enable debug logging for OpenTelemetry
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
logging.getLogger("kibana.observability").setLevel(logging.DEBUG)

# Enable debug logging for your application
logging.getLogger("my-app").setLevel(logging.DEBUG)

# Configure console output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Test Log Forwarding Manually

```python
#!/usr/bin/env python3
"""Test log forwarding functionality."""

import logging
import time
from examples.utils import configure_example_telemetry, print_telemetry_info

def test_log_forwarding():
    print("🧪 Testing Log Forwarding")
    print("=" * 40)

    # Configure telemetry
    traces_enabled, logs_enabled = configure_example_telemetry(logs_enabled=True)
    print_telemetry_info()

    if not logs_enabled:
        print("❌ Log forwarding not enabled")
        return False

    # Create test logger
    logger = logging.getLogger("test-app")

    # Test different log levels
    print("\n📝 Sending test logs...")
    logger.debug("Debug message - should only appear if level is DEBUG")
    logger.info("Info message - should only appear if level is INFO or lower")
    logger.warning("Warning message - should appear if level is WARNING or lower")
    logger.error("Error message - should appear if level is ERROR or lower")
    logger.critical("Critical message - should always appear")

    # Test structured logging
    logger.error(
        "Structured error message",
        extra={
            "error_code": "TEST_ERROR",
            "component": "log_forwarding_test",
            "test_id": "test-123",
            "timestamp": time.time()
        }
    )

    print("✅ Test logs sent")
    print("🔍 Check APM at: http://localhost:5601/app/apm")
    print("📋 Look for service: kibana-py-example")
    print("📝 Navigate to Logs tab to see forwarded messages")

    return True

if __name__ == "__main__":
    test_log_forwarding()
```

### Validate APM Server Logs Endpoint

```bash
#!/bin/bash
# validate_apm_logs.sh

echo "🔍 Validating APM Server Logs Endpoint"
echo "======================================"

# Check APM server is running
echo "1. Checking APM server availability..."
if curl -s -f "http://localhost:8200/" > /dev/null; then
    echo "✅ APM server is running"
else
    echo "❌ APM server is not available"
    exit 1
fi

# Check authentication
echo "2. Testing authentication..."
if [ -z "$ELASTIC_APM_SECRET_TOKEN" ]; then
    echo "❌ ELASTIC_APM_SECRET_TOKEN not set"
    exit 1
fi

if curl -s -f -H "Authorization: Bearer $ELASTIC_APM_SECRET_TOKEN" \
   "http://localhost:8200/config/v1/agents" > /dev/null; then
    echo "✅ Authentication successful"
else
    echo "❌ Authentication failed"
    exit 1
fi

# Test logs endpoint
echo "3. Testing logs endpoint..."
if curl -s -f -X POST \
   -H "Authorization: Bearer $ELASTIC_APM_SECRET_TOKEN" \
   -H "Content-Type: application/x-protobuf" \
   "http://localhost:8200/v1/logs" > /dev/null; then
    echo "✅ Logs endpoint accessible"
else
    echo "❌ Logs endpoint not accessible"
    exit 1
fi

echo "✅ All APM server checks passed"
```

### Monitor Log Forwarding Performance

```python
#!/usr/bin/env python3
"""Monitor log forwarding performance."""

import logging
import time
from examples.utils import configure_example_telemetry

def performance_test():
    # Configure telemetry
    traces_enabled, logs_enabled = configure_example_telemetry(logs_enabled=True)

    if not logs_enabled:
        print("❌ Log forwarding not enabled")
        return

    logger = logging.getLogger("perf-test")

    # Test log forwarding performance
    num_logs = 100
    start_time = time.time()

    for i in range(num_logs):
        logger.warning(
            f"Performance test log {i}",
            extra={
                "test_id": "perf-test",
                "log_number": i,
                "batch_size": num_logs
            }
        )

    end_time = time.time()
    duration = end_time - start_time

    print(f"📊 Performance Results:")
    print(f"   Logs sent: {num_logs}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Rate: {num_logs/duration:.1f} logs/sec")
    print(f"   Avg time per log: {(duration/num_logs)*1000:.2f}ms")

if __name__ == "__main__":
    performance_test()
```

## Environment-Specific Configurations

### Development Environment

```bash
# .env for development
KIBANA_OTEL_ENABLED=true
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=DEBUG          # See all logs
KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,debug
OTEL_SERVICE_NAME=my-app-dev
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
```

### Staging Environment

```bash
# .env for staging
KIBANA_OTEL_ENABLED=true
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=WARNING        # Important events only
KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app
OTEL_SERVICE_NAME=my-app-staging
OTEL_EXPORTER_OTLP_ENDPOINT=https://staging-apm.company.com:8200
```

### Production Environment

```bash
# .env for production
KIBANA_OTEL_ENABLED=true
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=ERROR          # Errors only
KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,critical
OTEL_SERVICE_NAME=my-app-prod
OTEL_EXPORTER_OTLP_ENDPOINT=https://prod-apm.company.com:8200
```

## Getting Help

### Check Example Output

Run any example to see current configuration:

```bash
python examples/simple_index_connector.py
```

Look for the telemetry status output at the beginning.

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test with Console Export

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    logs_enabled=True,
    console_export=True  # See logs in console too
)
```

### Validate Configuration

```python
from examples.utils import get_otel_config

config = get_otel_config()
print(f"Configuration: {config}")
```

### Common Resolution Steps

1. Restart APM server (if using elastic-start-local):
   ```bash
   ./local-stack.sh -o stop
   cd ..
   ./local-stack.sh -o start
   ```

2. Clear environment variables and test with defaults:
   ```bash
   unset KIBANA_OTEL_LOGS_ENABLED
   unset KIBANA_OTEL_LOGS_LEVEL
   unset KIBANA_OTEL_LOGS_LOGGERS
   python examples/simple_index_connector.py
   ```

3. Test with minimal configuration:
   ```bash
   export KIBANA_OTEL_ENABLED=true
   export KIBANA_OTEL_LOGS_ENABLED=true
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG
   export KIBANA_OTEL_LOGS_LOGGERS=""  # All loggers
   python examples/simple_index_connector.py
   ```

4. Check APM server logs:
   ```bash
   # If using elastic-start-local
   cd elastic-start-local
   docker-compose logs apm-server
   ```

:::{seealso}
- {doc}`../user-guide/observability` - Observability setup and configuration
- {doc}`../migration-guides/log-forwarding` - Log forwarding migration guide
- {doc}`common-issues` - General troubleshooting
:::
