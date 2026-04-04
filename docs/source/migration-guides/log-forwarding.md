# Log Forwarding Migration Guide

This guide helps you migrate from trace-only OpenTelemetry configuration to include log forwarding in kibana-py.

## Overview

Log forwarding is a **completely optional** enhancement to the existing OpenTelemetry integration. Your existing trace configurations will continue to work exactly as before.

### What's New

- **Log forwarding to APM servers** using OpenTelemetry logs protocol
- **Automatic trace-log correlation** when both are enabled
- **Configurable log level filtering** to control volume
- **Logger selection** to forward only relevant logs
- **Zero performance impact** when disabled (default)

### What Hasn't Changed

- **All existing trace configuration** works exactly the same
- **No breaking changes** to any existing APIs
- **Backward compatibility** is fully maintained
- **Default behavior** remains unchanged (log forwarding is opt-in)

## Migration Scenarios

### Scenario 1: Keep Existing Trace-Only Setup

**No action required.** Your existing configuration continues to work:

```bash
# Your existing .env configuration
KIBANA_OTEL_ENABLED=true
OTEL_SERVICE_NAME=my-app
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer your_token
```

```python
# Your existing code continues to work
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    endpoint="http://localhost:8200"
)
```

**Result**: Traces work exactly as before, no log forwarding.

### Scenario 2: Add Log Forwarding to Existing Setup

**Minimal change required.** Add log forwarding configuration:

```bash
# Add these lines to your existing .env
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=WARNING
KIBANA_OTEL_LOGS_LOGGERS=my-app
```

```python
# Add log forwarding parameters to existing code
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    endpoint="http://localhost:8200",
    # Add these new parameters
    logs_enabled=True,
    logs_level="WARNING",
    logs_loggers=["my-app"]
)
```

**Result**: Both traces and logs forwarded to APM with correlation.

### Scenario 3: Log Forwarding Only (No Traces)

**New configuration.** Enable logs without traces:

```bash
# Disable traces, enable logs
KIBANA_OTEL_ENABLED=false
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=ERROR
KIBANA_OTEL_LOGS_LOGGERS=my-app
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
```

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=False,           # No traces
    logs_enabled=True,       # Enable log forwarding
    logs_level="ERROR",      # Only errors
    logs_loggers=["my-app"]
)
```

**Result**: Only logs forwarded to APM, no traces.

## Step-by-Step Migration

### Step 1: Verify Current Setup

Check your current telemetry configuration:

```python
from examples.utils import print_telemetry_info

print_telemetry_info()
```

Expected output for existing setup:

```
=== Telemetry Configuration ===
Traces Enabled: True
Service Name: my-app
APM Endpoint: http://localhost:8200
Protocol: grpc
Log Forwarding Enabled: False  # This is expected
Headers:
  authorization: Bearer ***token
================================
```

### Step 2: Test Log Forwarding

Add log forwarding configuration gradually:

1. **Enable log forwarding**:
   ```bash
   export KIBANA_OTEL_LOGS_ENABLED=true
   ```

2. **Test with debug level** (temporary):
   ```bash
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG
   export KIBANA_OTEL_LOGS_LOGGERS=my-app
   ```

3. **Run a test**:
   ```python
   import logging
   from examples.utils import configure_example_telemetry, print_telemetry_info

   # Configure telemetry
   traces_enabled, logs_enabled = configure_example_telemetry()
   print_telemetry_info()

   # Test logging
   logger = logging.getLogger("my-app")
   logger.error("Test log message")

   print(f"Traces: {traces_enabled}, Logs: {logs_enabled}")
   ```

4. **Check APM**: Navigate to `http://localhost:5601/app/apm` and look for your service in the Logs section.

### Step 3: Optimize Configuration

Once log forwarding works, optimize for your environment:

1. **Set appropriate log level**:
   ```bash
   # Development
   export KIBANA_OTEL_LOGS_LEVEL=INFO

   # Production
   export KIBANA_OTEL_LOGS_LEVEL=ERROR
   ```

2. **Select relevant loggers**:
   ```bash
   # Include your application loggers
   export KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app,critical-module
   ```

3. **Test performance impact**:
   ```python
   # Monitor application performance with log forwarding enabled
   # Adjust log level if needed
   ```

### Step 4: Update Application Code

Add structured logging to your application:

```python
import logging

# Create logger for your application
logger = logging.getLogger("my-app")

# Use structured logging for better APM integration
logger.error(
    "API request failed",
    extra={
        "http_method": "POST",
        "http_path": "/api/connectors",
        "http_status_code": 400,
        "error_code": "VALIDATION_ERROR",
        "user_id": "user123"
    }
)
```

## Configuration Reference

### Environment Variables

#### Existing (Unchanged)

```bash
KIBANA_OTEL_ENABLED=true                    # Enable/disable traces
OTEL_SERVICE_NAME=my-app                    # Service name
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200  # APM endpoint
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer token  # Auth headers
OTEL_EXPORTER_OTLP_PROTOCOL=grpc           # Protocol (grpc/http)
```

#### New (Log Forwarding)

```bash
KIBANA_OTEL_LOGS_ENABLED=true              # Enable/disable log forwarding
KIBANA_OTEL_LOGS_LEVEL=WARNING             # Minimum log level
KIBANA_OTEL_LOGS_LOGGERS=kibana,my-app     # Comma-separated logger names
OTEL_LOGS_EXPORTER=otlp                    # Log exporter type
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:8200/v1/logs  # Logs endpoint (optional)
OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=grpc      # Logs protocol (optional)
```

### Programmatic Configuration

#### Existing (Unchanged)

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:8200",
    headers={"authorization": "Bearer token"},
    protocol="grpc",
    console_export=False
)
```

#### Enhanced (With Log Forwarding)

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    # Existing parameters (unchanged)
    enabled=True,
    service_name="my-app",
    exporter="otlp",
    endpoint="http://localhost:8200",
    headers={"authorization": "Bearer token"},
    protocol="grpc",
    console_export=False,

    # New log forwarding parameters
    logs_enabled=True,
    logs_level="WARNING",
    logs_loggers=["kibana", "my-app"]
)
```

## Common Migration Issues

### Issue 1: Log Forwarding Not Working

**Symptoms**:
- Traces work but no logs in APM
- `Log Forwarding Enabled: False` in telemetry status

**Solutions**:

1. **Check if enabled**:
   ```bash
   export KIBANA_OTEL_LOGS_ENABLED=true
   ```

2. **Verify logger names**:
   ```bash
   # Make sure your logger names match
   export KIBANA_OTEL_LOGS_LOGGERS=your-actual-logger-name
   ```

3. **Lower log level temporarily**:
   ```bash
   export KIBANA_OTEL_LOGS_LEVEL=DEBUG
   ```

### Issue 2: Too Many Logs

**Symptoms**:
- High volume of logs in APM
- Performance impact

**Solutions**:

1. **Raise log level**:
   ```bash
   export KIBANA_OTEL_LOGS_LEVEL=ERROR  # Only errors
   ```

2. **Limit loggers**:
   ```bash
   export KIBANA_OTEL_LOGS_LOGGERS=critical-module-only
   ```

3. **Review application logging**:
   ```python
   # Avoid high-frequency logging
   for item in items:
       # Don't log every iteration
       pass

   # Log summary instead
   logger.info(f"Processed {len(items)} items")
   ```

### Issue 3: Logs Not Correlated with Traces

**Symptoms**:
- Logs and traces appear separately in APM
- No correlation between them

**Solutions**:

1. **Enable both traces and logs**:
   ```bash
   export KIBANA_OTEL_ENABLED=true      # Traces
   export KIBANA_OTEL_LOGS_ENABLED=true # Logs
   ```

2. **Use same service name**:
   ```bash
   export OTEL_SERVICE_NAME=my-app  # Same for both
   ```

3. **Log within trace context**:
   ```python
   from kibana import Kibana
   import logging

   logger = logging.getLogger("my-app")
   client = Kibana("http://localhost:5601")

   # This creates a trace
   response = client.actions.list()

   # Log immediately (within trace context)
   logger.info(f"Retrieved {len(response.body)} connectors")
   ```

## Testing Your Migration

### 1. Backward Compatibility Test

```python
#!/usr/bin/env python3
"""Test that existing configuration still works."""

import os
from examples.utils import configure_example_telemetry, print_telemetry_info

# Clear log forwarding variables
for var in ['KIBANA_OTEL_LOGS_ENABLED', 'KIBANA_OTEL_LOGS_LEVEL']:
    if var in os.environ:
        del os.environ[var]

# Set existing trace configuration
os.environ['KIBANA_OTEL_ENABLED'] = 'true'
os.environ['OTEL_SERVICE_NAME'] = 'test-app'

# This should work exactly as before
result = configure_example_telemetry()
print_telemetry_info()

print(f"Backward compatibility: {'✅ PASS' if result else '❌ FAIL'}")
```

### 2. Log Forwarding Test

```python
#!/usr/bin/env python3
"""Test log forwarding functionality."""

import logging
from examples.utils import configure_example_telemetry, print_telemetry_info

# Enable log forwarding
traces_enabled, logs_enabled = configure_example_telemetry(logs_enabled=True)
print_telemetry_info()

if logs_enabled:
    logger = logging.getLogger("test-app")
    logger.error("Test error message", extra={"test_id": "migration-test"})
    print("✅ Log forwarding test completed - check APM for logs")
else:
    print("❌ Log forwarding not enabled")
```

### 3. Performance Test

```python
#!/usr/bin/env python3
"""Test performance impact of log forwarding."""

import time
import logging
from examples.utils import configure_example_telemetry

def performance_test(logs_enabled=False):
    configure_example_telemetry(logs_enabled=logs_enabled)
    logger = logging.getLogger("perf-test")

    start_time = time.time()
    for i in range(100):
        logger.warning(f"Performance test message {i}")
    end_time = time.time()

    return end_time - start_time

# Test without log forwarding
time_without_logs = performance_test(logs_enabled=False)

# Test with log forwarding
time_with_logs = performance_test(logs_enabled=True)

print(f"Without logs: {time_without_logs:.3f}s")
print(f"With logs: {time_with_logs:.3f}s")
print(f"Overhead: {((time_with_logs - time_without_logs) / time_without_logs * 100):.1f}%")
```

## Best Practices After Migration

### 1. Environment-Specific Configuration

**Development**:
```bash
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=DEBUG    # See everything
KIBANA_OTEL_LOGS_LOGGERS=my-app,debug
```

**Staging**:
```bash
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=WARNING  # Important events
KIBANA_OTEL_LOGS_LOGGERS=my-app
```

**Production**:
```bash
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=ERROR    # Errors only
KIBANA_OTEL_LOGS_LOGGERS=my-app,critical
```

### 2. Structured Logging Patterns

```python
import logging

logger = logging.getLogger("my-app")

# Good: Structured with context
logger.error(
    "Database connection failed",
    extra={
        "database_host": "db.example.com",
        "database_name": "myapp",
        "connection_timeout": 30,
        "retry_count": 3,
        "error_code": "CONNECTION_TIMEOUT"
    }
)

# Avoid: Unstructured strings
logger.error("Database connection to db.example.com failed after 3 retries")
```

### 3. Monitoring and Alerting

1. **Set up APM alerts** for error log patterns
2. **Monitor log volume** to avoid unexpected costs
3. **Use log correlation** to debug issues faster
4. **Create dashboards** combining traces and logs

## Rollback Plan

If you need to disable log forwarding:

### Quick Disable

```bash
export KIBANA_OTEL_LOGS_ENABLED=false
```

### Complete Removal

```bash
unset KIBANA_OTEL_LOGS_ENABLED
unset KIBANA_OTEL_LOGS_LEVEL
unset KIBANA_OTEL_LOGS_LOGGERS
unset OTEL_LOGS_EXPORTER
unset OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
unset OTEL_EXPORTER_OTLP_LOGS_PROTOCOL
```

Your application will continue working exactly as before with trace-only telemetry.

## Getting Help

### 1. Check Configuration Status

```python
from examples.utils import print_telemetry_info
print_telemetry_info()
```

### 2. Enable Debug Logging

```python
import logging
logging.getLogger("kibana.observability").setLevel(logging.DEBUG)
```

### 3. Test with Console Export

```python
from kibana import configure_opentelemetry

configure_opentelemetry(
    logs_enabled=True,
    console_export=True  # See logs in console too
)
```

### 4. Validate APM Connectivity

```bash
# Test APM server logs endpoint
curl -X POST "http://localhost:8200/v1/logs" \
     -H "Authorization: Bearer your_token" \
     -H "Content-Type: application/x-protobuf"
```

For more detailed troubleshooting, see {doc}`../troubleshooting/telemetry`.

## Additional Resources

- {doc}`../user-guide/observability` - Complete observability documentation
- {doc}`../examples/observability` - Observability examples
- {doc}`../troubleshooting/telemetry` - Telemetry troubleshooting guide

## Summary

Log forwarding is a powerful enhancement that provides complete observability when combined with existing trace functionality. The migration is:

- **✅ Completely optional** - existing setups continue to work
- **✅ Non-breaking** - no changes to existing APIs
- **✅ Incremental** - can be enabled gradually
- **✅ Reversible** - can be disabled at any time
- **✅ Zero overhead** - when disabled (default)

Start with your existing configuration, add log forwarding when ready, and enjoy complete observability with trace-log correlation in your APM dashboards.
