# Integration Tests

Integration tests that connect to a real Kibana instance with automatic configuration and cleanup.

## Prerequisites

### Option 1: Local Elastic Stack (Recommended)

1. Start the local Elastic Stack:
   ```bash
   ./local-stack.sh -o start
   ```

2. Wait for services to be healthy (check with `docker-compose ps`)

### Option 2: Manual Configuration

Set environment variables for your Kibana instance:
```bash
export KIBANA_URL=http://localhost:5601
export KIBANA_USERNAME=elastic
export KIBANA_PASSWORD=your_password
export KIBANA_API_KEY=your_api_key
```

## Running Integration Tests

### Simple (Recommended)

```bash
# Tests automatically detect configuration from elastic-start-local/.env
pytest tests/integration/
```

### With Custom Configuration

```bash
export KIBANA_URL=http://your-kibana:5601
export KIBANA_USERNAME=elastic
export KIBANA_PASSWORD=your_password

pytest tests/integration/
```

### Using the Helper Scripts

```bash
# Run all integration tests
./tests/integration/run_integration_tests.sh

# Run only space support integration tests
./tests/integration/run_space_integration_tests.sh
```

### Run Specific Test

```bash
pytest tests/integration/test_actions_integration.py::TestActionsClientConnectivity::test_list_connector_types -v
```

## Test Coverage

The integration tests cover:

- **Connection** (5 tests): Basic connectivity, context manager, multiple hosts
- **Authentication** (4 tests): Basic auth, API key, switching auth methods
- **Spaces API** (3 tests): Listing and retrieving spaces, error handling
- **Saved Objects API** (2 tests): Finding and querying saved objects
- **HTTP Methods** (4 tests): GET, POST, PUT, DELETE operations
- **Query Parameters** (3 tests): Single, multiple, and special character handling
- **Options** (3 tests): Per-request configuration, headers, timeout
- **Error Handling** (2 tests): Various error scenarios with metadata
- **Response Metadata** (3 tests): Response structure validation
- **Client Reuse** (2 tests): Multiple requests, independent instances

### Space Support Integration Tests

Comprehensive tests for the generalized space support functionality:

- **Space Validation** (8 tests): Real Kibana space validation, caching behavior, error handling
- **Space-Scoped Operations** (12 tests): End-to-end operations in different spaces, space isolation
- **Space Performance** (8 tests): Performance impact measurement, caching effectiveness
- **Space Client Factory** (4 tests): Space-scoped client behavior and validation

## Automatic Configuration

Integration tests use the same automatic configuration system as examples:

1. **Environment variables** (highest priority):
   - `KIBANA_URL`, `KIBANA_USERNAME`, `KIBANA_PASSWORD`, `KIBANA_API_KEY`

2. **Local development setup**: Reads from `elastic-start-local/.env`

3. **Defaults**: Falls back to `http://localhost:5601`

## Automatic Cleanup

- **All tests automatically clean up** resources they create
- **Connectors** created during tests are tracked and deleted after each test
- **No manual cleanup required** - tests leave no artifacts behind
- **Robust cleanup** handles API edge cases (empty DELETE responses)

## Notes

- Tests are automatically skipped if Kibana is not available
- Uses the same configuration detection as examples (no hardcoded credentials)
- All authentication methods (basic auth, API key) are tested
- Tests create temporary resources but clean them up automatically
- All HTTP methods (GET, POST, PUT, DELETE) are tested with real Kibana endpoints
- Follows the same patterns as examples for consistency
