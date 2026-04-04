# Observability Integration Tests

Comprehensive integration tests for OpenTelemetry observability (traces and logs) with real OTLP endpoint.

## Overview

These tests validate the complete observability stack:
- **Traces**: Distributed tracing of Kibana API calls
- **Logs**: Structured log forwarding to OTLP endpoint
- **Correlation**: Automatic trace-log correlation with trace_id and span_id

## Prerequisites

1. **Start the local Elastic Stack** (includes OTLP endpoint):
   ```bash
   cd elastic-start-local
   docker-compose up -d
   ```

2. **Install OpenTelemetry dependencies**:
   ```bash
   pip install kibana-py[observability]
   pip install opentelemetry-exporter-otlp-proto-grpc
   pip install opentelemetry-exporter-otlp-proto-http
   ```

3. **Wait for services to be healthy**:
   ```bash
   docker-compose ps
   ```

## Running Tests

### Quick Start (Recommended)

```bash
# Run all observability tests (traces + logs)
./tests/integration/run_observability_tests.sh

# Run only log forwarding tests
./tests/integration/run_log_forwarding_tests.sh
```

### Manual Execution

```bash
# Load environment variables
export $(grep -v '^#' elastic-start-local/.env | xargs)

# Run all observability tests
pytest tests/integration/test_*observability*.py tests/integration/test_log_*.py -v

# Run only trace tests
pytest tests/integration/test_observability_integration.py -v

# Run only log tests
pytest tests/integration/test_log_*_integration.py -v
```

### Specific Test Examples

```bash
# Test trace generation
pytest tests/integration/test_observability_integration.py::TestObservabilityWithOTLP::test_send_traces_to_otlp -v

# Test log forwarding
pytest tests/integration/test_log_forwarding_integration.py::TestOTLPLogForwarding::test_grpc_log_forwarding -v

# Test trace-log correlation
pytest tests/integration/test_log_trace_correlation_integration.py::TestTraceLogCorrelation::test_logs_include_trace_and_span_ids -v

# Test end-to-end observability
pytest tests/integration/test_end_to_end_observability_integration.py -v
```

## Test Coverage

### Trace Tests (16 tests)

**Basic Tests (2 tests)**
- ✅ Instrumentor can be enabled
- ✅ Configuration from environment variables

**Console Exporter Tests (3 tests)**
- ✅ Request creates span
- ✅ Multiple requests create multiple spans
- ✅ Error requests mark spans as errors

**OTLP Endpoint Tests (3 tests)**
- ✅ Send traces to OTLP endpoint
- ✅ CRUD operations traced
- ✅ Error traces sent to OTLP endpoint

**Span Attributes Tests (4 tests)**
- ✅ Span has HTTP method, URL, status code
- ✅ Span has query parameters

**Configuration Tests (4 tests)**
- ✅ Requests work without observability
- ✅ No performance impact when disabled
- ✅ Can switch exporters
- ✅ Custom service name

### Log Tests (50+ tests across 5 files)

**Log Forwarding Tests**
- ✅ gRPC and HTTP protocol forwarding to OTLP endpoint
- ✅ Authentication with OTLP auth tokens
- ✅ Console log exporter functionality
- ✅ Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- ✅ Multiple logger configuration
- ✅ Environment variable configuration

**Trace-Log Correlation Tests**
- ✅ Logs include trace_id and span_id when spans are active
- ✅ Logs work correctly without active spans
- ✅ Nested spans with proper correlation
- ✅ Concurrent spans with logs
- ✅ Kibana API calls with log correlation
- ✅ Error spans with correlated logs

**Performance Tests**
- ✅ Log level filtering performance
- ✅ High-volume log scenarios
- ✅ Concurrent logging performance
- ✅ Memory usage impact
- ✅ Burst and sustained logging

**Graceful Degradation Tests**
- ✅ Configuration with unreachable servers
- ✅ Network timeout handling
- ✅ Authentication failures
- ✅ SSL certificate errors
- ✅ Error recovery and resilience

**End-to-End Tests**
- ✅ Complete trace and log correlation workflow
- ✅ Kibana API operations with full observability
- ✅ Performance impact of combined traces and logs
- ✅ Metadata and attributes validation

## Environment Variables

### Kibana Configuration
```bash
KIBANA_URL=http://localhost:5601
KIBANA_USERNAME=elastic
KIBANA_PASSWORD=M5oz7Hl8
```

### OTLP Endpoint Configuration
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
ELASTIC_APM_SECRET_TOKEN=M5oz7Hl8M5oz7Hl8
```

### OpenTelemetry Trace Configuration
```bash
KIBANA_OTEL_ENABLED=true
OTEL_SERVICE_NAME=kibana-py-integration-tests
KIBANA_OTEL_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer M5oz7Hl8M5oz7Hl8
```

### OpenTelemetry Log Configuration
```bash
KIBANA_OTEL_LOGS_ENABLED=true
KIBANA_OTEL_LOGS_LEVEL=INFO
KIBANA_OTEL_LOGS_LOGGERS=kibana,kibana.observability
```

## Viewing Observability Data in Kibana

### Traces

1. **Open Kibana**: http://localhost:5601
2. **Login**: elastic / M5oz7Hl8
3. **Navigate**: Observability → Traces
4. **Select Service**: kibana-py-integration-tests
5. **View Traces**: See all API requests traced

**Example Trace:**
```
kibana.get
├─ http.method: GET
├─ http.url: /api/status
├─ http.status_code: 200
├─ duration: 45ms
└─ trace_id: 1234567890abcdef
```

### Logs

1. **Navigate**: Observability → Logs
2. **Filter by service**: service.name: kibana-py-integration-tests
3. **View correlated logs**: Click on trace_id to see related logs

**Example Log with Correlation:**
```json
{
  "message": "Kibana API request completed",
  "level": "INFO",
  "trace_id": "1234567890abcdef",
  "span_id": "abcdef123456",
  "service.name": "kibana-py-integration-tests",
  "http.method": "GET",
  "http.status_code": 200
}
```

### Trace-Log Correlation

1. **In APM**: Click on a transaction
2. **View Timeline**: See spans with timing
3. **Click "Logs"**: See correlated logs for that trace
4. **Filter by span**: See logs for specific span

This correlation allows you to:
- Debug errors by seeing logs in context of traces
- Understand request flow with detailed logging
- Correlate performance issues with log events

## Test Architecture

### Test Files

```
tests/integration/
├── test_observability_integration.py          # Trace tests (16 tests)
├── test_log_forwarding_integration.py         # Log forwarding (protocol, auth, config)
├── test_log_trace_correlation_integration.py  # Trace-log correlation
├── test_log_performance_integration.py        # Performance and filtering
├── test_log_graceful_degradation_integration.py # Error handling
└── test_end_to_end_observability_integration.py # Complete workflows
```

### Test Runner Scripts

```bash
./tests/integration/run_observability_tests.sh      # Trace tests
./tests/integration/run_log_forwarding_tests.sh     # Log tests
```

**Script Features:**
- Automatic dependency checking
- Environment validation
- Service health checks
- Helpful error messages
- Multiple execution modes

## Troubleshooting

### Tests are skipped

**Problem**: Tests show "SKIPPED"

**Solution**: Install dependencies
```bash
pip install kibana-py[observability]
pip install opentelemetry-exporter-otlp-proto-grpc
pip install opentelemetry-exporter-otlp-proto-http
```

### Cannot connect to OTLP endpoint

**Problem**: Connection errors to OTLP endpoint

**Solution**:
```bash
# Check if elastic-agent is running
docker ps | grep elastic-agent

# Restart if needed
cd elastic-start-local
docker-compose restart elastic-agent

# Verify OTLP endpoint is accessible
curl http://localhost:8200
```

### Traces/Logs not visible in Kibana

**Problem**: Tests pass but no data in Kibana

**Solution**:
1. Wait 5-10 seconds for data to be indexed
2. Check time range in Kibana (last 15 minutes)
3. Verify service name: `kibana-py-integration-tests`
4. Check OTLP endpoint logs:
   ```bash
   docker logs elastic-agent
   ```

### Module import errors

**Problem**: `ImportError: cannot import name 'configure_opentelemetry'`

**Solution**: Restart Python to reload modules
```bash
pkill python
./tests/integration/run_observability_tests.sh
```

### Performance test failures

**Problem**: Performance thresholds exceeded

**Solution**:
- Check system load
- Run with `-q` flag to skip performance tests
- Adjust thresholds if infrastructure changed

## Performance Impact

### Traces
- **Overhead**: ~1-2% per request
- **Batch Export**: Spans batched for efficiency
- **Async**: Non-blocking export

### Logs
- **Overhead**: ~2-5% depending on log level
- **Filtering**: Log level filtering reduces overhead
- **Batch Export**: Logs batched for efficiency

### Combined (Traces + Logs)
- **Total Overhead**: ~3-7% per request
- **Acceptable**: For most production use cases
- **Configurable**: Can disable logs or traces independently

## Best Practices

1. **Enable Both**: Use traces and logs together for complete observability
2. **Use Correlation**: Leverage trace_id and span_id for debugging
3. **Filter Logs**: Use appropriate log levels (INFO or WARNING in production)
4. **Test with OTLP**: Always test with real OTLP endpoint
5. **Check Kibana**: Verify data appears in Kibana UI
6. **Monitor Performance**: Track overhead in production

## References

- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Elastic APM OpenTelemetry](https://www.elastic.co/guide/en/apm/guide/current/open-telemetry.html)
- [Kibana APM UI](https://www.elastic.co/guide/en/kibana/current/apm.html)
- [OpenTelemetry Logs](https://opentelemetry.io/docs/specs/otel/logs/)
