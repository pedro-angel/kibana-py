# Integration Test Coverage

**Last Updated:** October 13, 2025

## Overview

This document tracks integration test coverage for all Kibana API operations in the kibana-py library. Integration tests verify that the client works correctly against a real Kibana instance.

## Test Environment

Integration tests require:
- A running Kibana instance (use `elastic-start-local/` for local testing)
- Environment variables: `KIBANA_URL`, `KIBANA_USERNAME`, `KIBANA_PASSWORD`, or `KIBANA_API_KEY`
- Tests automatically skip if Kibana is not available

Run tests with:
```bash
./tests/integration/run_integration_tests.sh
```

## Coverage Summary

| API | Sync Coverage | Async Coverage | Status |
|-----|---------------|----------------|--------|
| **Actions API** | ✅ Complete | ✅ Complete | Comprehensive |
| **Spaces API** | ✅ Complete | ✅ Complete | Comprehensive |
| **Saved Objects API** | ✅ Complete | ✅ Complete | Comprehensive |
| **Status API** | ✅ Complete | ✅ Complete | Comprehensive |
| **Observability** | ✅ Complete | N/A | Instrumentation only |

**Overall Status:** ✅ All major API operations have comprehensive integration test coverage for both sync and async clients.

---

## Detailed Coverage

### Actions API

**Test Files:**
- `test_actions_integration.py` - Synchronous client (845 lines)
- `test_async_actions_integration.py` - Asynchronous client (650+ lines)

#### Operations Coverage

| Operation | Sync Test | Async Test | Test Classes | Notes |
|-----------|-----------|------------|--------------|-------|
| **list_types()** | ✅ | ✅ | Connectivity | Lists available connector types |
| **get_all()** | ✅ | ✅ | Connectivity, CRUD | Lists all connectors |
| **create()** | ✅ | ✅ | CRUD | Creates webhook and server-log connectors |
| **get()** | ✅ | ✅ | CRUD | Retrieves connector by ID |
| **update()** | ✅ | ✅ | CRUD | Full and partial updates |
| **delete()** | ✅ | ✅ | CRUD | Handles empty response edge case |
| **execute()** | ✅ | ✅ | Execution | Tests webhook and server-log execution |

#### Test Coverage Details

**Connectivity Tests:**
- Client accessibility and initialization
- Authentication methods (basic auth, API key)
- Listing connector types with structure validation
- Getting all connectors (empty and populated states)

**CRUD Tests:**
- Creating connectors (webhook, server-log)
- Creating with all parameters vs minimal parameters
- Getting connectors by ID
- Updating connectors (full and partial updates)
- Deleting connectors with verification
- Multiple connectors with same name

**Execution Tests:**
- Executing server-log connectors
- Executing webhook connectors
- Validating execution responses

**Error Handling Tests:**
- NotFoundError for non-existent connectors
- BadRequestError for invalid types and configs
- ConflictError scenarios
- Parameter validation (required fields)

**Advanced Tests:**
- Client options (custom timeout, headers, auth switching)
- Complete lifecycle (create → get → update → execute → delete)
- Structure validation for responses
- Complex scenarios and edge cases

**Fixtures:**
- Automatic cleanup of created connectors
- Unique connector name generation
- Reusable connector configurations
- Multiple authentication method fixtures

---

### Spaces API

**Test Files:**
- `test_spaces_integration.py` - Synchronous client (400+ lines)
- `test_async_spaces_integration.py` - Asynchronous client (450+ lines)

#### Operations Coverage

| Operation | Sync Test | Async Test | Test Classes | Notes |
|-----------|-----------|------------|--------------|-------|
| **get_all()** | ✅ | ✅ | Connectivity, CRUD | Lists all spaces |
| **get()** | ✅ | ✅ | Connectivity, CRUD | Retrieves space by ID |
| **create()** | ✅ | ✅ | CRUD | Minimal and full parameter creation |
| **update()** | ✅ | ✅ | CRUD | Full and partial updates |
| **delete()** | ✅ | ✅ | CRUD | Verifies deletion |

#### Test Coverage Details

**Connectivity Tests:**
- Client accessibility
- Getting all spaces (including default space)
- Getting default space specifically
- Space structure validation

**CRUD Tests:**
- Creating spaces with minimal parameters
- Creating spaces with all optional fields (description, color, initials, disabled_features)
- Getting spaces by ID
- Updating space name and all fields
- Partial updates (preserving unchanged fields)
- Deleting spaces with verification
- Multiple space creation

**Error Handling Tests:**
- NotFoundError for non-existent spaces
- ConflictError for duplicate space IDs
- BadRequestError for invalid space IDs
- BadRequestError when deleting default space
- Parameter validation (required fields)

**Advanced Tests:**
- Complete lifecycle (create → get → update → delete)
- Special characters in names and descriptions
- Long descriptions (500+ characters)
- Client options (custom timeout, headers)
- Structure validation for responses

**Fixtures:**
- Automatic cleanup of created spaces
- Unique space ID generation
- Safe deletion helper functions

---

### Saved Objects API

**Test Files:**
- `test_saved_objects_integration.py` - Synchronous client (400+ lines)
- `test_async_saved_objects_integration.py` - Asynchronous client (350+ lines)

#### Operations Coverage

| Operation | Sync Test | Async Test | Test Classes | Notes |
|-----------|-----------|------------|--------------|-------|
| **create()** | ✅ | ✅ | CRUD | Creates with and without ID |
| **get()** | ✅ | ✅ | CRUD | Retrieves by type and ID |
| **update()** | ✅ | ✅ | CRUD | Updates attributes |
| **delete()** | ✅ | ✅ | CRUD | Deletes saved objects |
| **find()** | ✅ | ✅ | CRUD | Searches saved objects |
| **bulk_create()** | ✅ | ✅ | Bulk Operations | Creates multiple objects |
| **bulk_get()** | ✅ | ✅ | Bulk Operations | Retrieves multiple objects |
| **bulk_update()** | ✅ | ✅ | Bulk Operations | Updates multiple objects |

#### Test Coverage Details

**Connectivity Tests:**
- Client accessibility and initialization

**CRUD Tests:**
- Creating saved objects with explicit ID
- Creating saved objects without ID (auto-generated)
- Creating with overwrite flag
- Getting saved objects by type and ID
- Updating saved object attributes
- Deleting saved objects with verification
- Finding saved objects with filters

**Bulk Operations Tests:**
- Bulk creating multiple objects
- Bulk getting multiple objects
- Bulk updating multiple objects
- Handling mixed success/failure in bulk operations

**Error Handling Tests:**
- NotFoundError for non-existent objects
- ConflictError for duplicate IDs without overwrite
- BadRequestError for invalid types
- Parameter validation

**Advanced Tests:**
- Complete lifecycle operations
- Working with visualization objects
- Structure validation
- Client options support

**Fixtures:**
- Automatic cleanup of created saved objects
- Unique object ID generation
- Test visualization attributes helper
- Tracking (type, id) tuples for cleanup

---

### Status API

**Test Files:**
- `test_status_integration.py` - Synchronous client (100+ lines)
- `test_async_status_integration.py` - Asynchronous client (120+ lines)

#### Operations Coverage

| Operation | Sync Test | Async Test | Test Classes | Notes |
|-----------|-----------|------------|--------------|-------|
| **get_status()** | ✅ | ✅ | Connectivity, Structure | Retrieves Kibana status |
| **get_stats()** | ✅ | ✅ | Connectivity, Structure | Retrieves Kibana statistics |

#### Test Coverage Details

**Connectivity Tests:**
- Client accessibility
- Getting Kibana status
- Getting Kibana statistics

**Status Tests:**
- Status response structure validation
- Overall state (available/degraded/unavailable)
- Version information (number, build_hash, build_number)
- Core services status (elasticsearch, savedObjects)
- Status level validation

**Stats Tests:**
- Stats response structure validation
- Kibana info (uuid, name, version, status)
- Process information (memory, heap)
- OS information (platform, load)
- Memory metrics validation

**Response Structure Tests:**
- Overall state validation
- Version info structure
- Metrics information
- Cross-version compatibility

**Advanced Tests:**
- Healthy instance status verification
- Response structure validation
- Client options support

---

### Observability Integration

**Test File:**
- `test_observability_integration.py` - OpenTelemetry instrumentation (150+ lines)

#### Coverage

| Feature | Test Coverage | Status | Notes |
|---------|---------------|--------|-------|
| **Instrumentor Enable/Disable** | ✅ | Complete | Basic lifecycle |
| **Configuration** | ✅ | Complete | From code and environment |
| **Console Exporter** | ⚠️ Skipped | Pending | Requires elastic-transport compatibility |
| **OTLP Exporter** | ⚠️ Skipped | Pending | Requires elastic-transport compatibility |
| **Span Creation** | ⚠️ Skipped | Pending | Requires elastic-transport compatibility |

#### Test Coverage Details

**Basic Tests:**
- Instrumentor singleton pattern
- Enable/disable functionality
- Configuration from environment variables
- Configuration from code parameters

**Exporter Tests:**
- Console exporter configuration (skipped - compatibility issue)
- OTLP exporter configuration (skipped - compatibility issue)
- Span creation verification (skipped - compatibility issue)

**Configuration Tests:**
- Service name configuration
- Exporter type selection
- Endpoint configuration
- Environment variable support

**Known Issues:**
- Tests are currently skipped due to `set_node_metadata` compatibility issue with elastic-transport
- Observability functionality is implemented but requires elastic-transport updates for full integration testing

**Fixtures:**
- OTLP/APM server configuration
- Console exporter configuration
- Automatic cleanup and reset

---

## Test Quality Metrics

### Code Coverage
- All major API operations covered
- Both sync and async implementations tested
- Error handling comprehensively tested
- Edge cases and complex scenarios included

### Test Patterns
- **Automatic Configuration:** Tests use `utils.py` for zero-config setup
- **Automatic Cleanup:** All tests clean up created resources
- **Fixture-Based:** Consistent use of pytest fixtures
- **Parameterized Auth:** Tests support multiple authentication methods
- **Structure Validation:** Response structures validated against API contracts

### Test Organization
- **Connectivity Tests:** Basic client access and authentication
- **CRUD Tests:** Create, Read, Update, Delete operations
- **Error Handling Tests:** Exception types and error scenarios
- **Validation Tests:** Parameter validation and required fields
- **Complex Scenarios:** Lifecycle tests and edge cases
- **Options Tests:** Client options and configuration

---

## Maintenance Notes

### Adding New Tests

When adding new API operations or features:

1. **Create test file** following naming convention:
   - Sync: `test_{api}_integration.py`
   - Async: `test_async_{api}_integration.py`

2. **Include test classes:**
   - `Test{API}ClientConnectivity` - Basic access and auth
   - `Test{API}ClientCRUD` - CRUD operations
   - `Test{API}ClientErrorHandling` - Error scenarios
   - `Test{API}ClientValidation` - Parameter validation
   - `Test{API}ClientComplexScenarios` - Advanced tests

3. **Add fixtures:**
   - Client fixture with automatic cleanup
   - Resource tracking fixture for cleanup
   - Unique ID generation fixtures
   - Configuration fixtures

4. **Update this document:**
   - Add operation to coverage table
   - Document test coverage details
   - Update summary statistics
   - Update last modified date

### Running Tests

**All integration tests:**
```bash
./tests/integration/run_integration_tests.sh
```

**Specific test file:**
```bash
pytest tests/integration/test_actions_integration.py -v
```

**Specific test class:**
```bash
pytest tests/integration/test_actions_integration.py::TestActionsClientCRUD -v
```

**With coverage:**
```bash
pytest tests/integration/ --cov=kibana --cov-report=html
```

### Test Environment Setup

**Using elastic-start-local:**
```bash
./local-stack.sh -o start
```

**Manual configuration:**
```bash
export KIBANA_URL="http://localhost:5601"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="your-password"
# OR
export KIBANA_API_KEY="your-api-key"
```

### Cleanup

Tests automatically clean up resources, but if manual cleanup is needed:

**Actions (Connectors):**
```python
client.actions.get_all()  # List all
client.actions.delete(id="connector-id")
```

**Spaces:**
```python
client.spaces.get_all()  # List all
client.spaces.delete(id="space-id")  # Cannot delete 'default'
```

**Saved Objects:**
```python
client.saved_objects.find(type="visualization")  # Find objects
client.saved_objects.delete(type="visualization", id="object-id")
```

---

## Future Considerations

### Potential Enhancements

1. **Performance Testing:**
   - Load testing with concurrent operations
   - Bulk operation performance benchmarks
   - Connection pool behavior under load

2. **Network Resilience:**
   - Retry behavior testing
   - Timeout handling
   - Connection failure scenarios

3. **Advanced Scenarios:**
   - Cross-space operations
   - Complex saved object relationships
   - Connector execution with real external services

4. **Observability:**
   - Full span creation testing (pending elastic-transport compatibility)
   - Trace propagation verification
   - APM integration validation

5. **Security:**
   - Role-based access control testing
   - API key permission validation
   - Space isolation verification

### Not Covered (By Design)

The following are intentionally not covered by integration tests:

- **User acceptance testing** - Requires human interaction
- **Deployment scenarios** - Infrastructure-specific
- **Performance metrics gathering** - Requires specialized tooling
- **Production monitoring** - Operational concern
- **UI interactions** - This is an API client library

---

## References

- **Test Utilities:** `tests/integration/utils.py`
- **Example Usage:** `examples/` directory
- **API Documentation:** [ReadTheDocs API Reference](https://kibana-py.readthedocs.io/en/latest/api-reference/index.html)
- **Observability Guide:** [ReadTheDocs Observability](https://kibana-py.readthedocs.io/en/latest/user-guide/observability.html)
- **Integration Test Documentation:** `tests/integration/README.md`

---

## Conclusion

The kibana-py library has **comprehensive integration test coverage** across all major API operations for both synchronous and asynchronous clients. Tests follow consistent patterns, include automatic cleanup, and validate both success and error scenarios.

**Coverage Status:** ✅ Production Ready

All critical paths are tested, error handling is verified, and the test suite provides confidence for production use.
