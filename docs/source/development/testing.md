# Testing Guide

This guide covers testing patterns, requirements, and best practices for kibana-py.

## Testing Philosophy

kibana-py follows a comprehensive testing strategy:

- **Unit tests** for all client methods and utilities
- **Integration tests** with real Kibana instances
- **Performance tests** for caching and validation overhead
- **Error scenario tests** for edge cases and failure modes

## Test Organization

### Unit Tests Structure

```
tests/unit/
├── test_base_client.py          # Core client functionality
├── test_async_base_client.py    # Async client functionality
├── test_actions_client.py       # Actions API client
├── test_saved_objects_client.py # Saved Objects API client
├── test_spaces_client.py        # Spaces API client
├── test_status_client.py        # Status API client
├── test_exceptions.py           # Exception handling
├── test_serializer.py           # JSON serialization
└── test_utils.py                # Utility functions
```

### Integration Tests Structure

```
tests/integration/
├── conftest.py                  # Shared fixtures and utilities
├── utils.py                     # Integration test utilities
├── test_actions_integration.py  # Actions API integration
├── test_saved_objects_integration.py # Saved Objects integration
├── test_spaces_integration.py   # Spaces API integration
└── test_status_integration.py   # Status API integration
```

## Unit Testing

### Running Unit Tests

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_base_client.py

# Run specific test class
pytest tests/unit/test_base_client.py::TestBaseClientInitialization

# Run specific test
pytest tests/unit/test_base_client.py::TestBaseClientInitialization::test_init_with_transport

# Run with coverage
pytest tests/unit/ --cov=kibana --cov-report=term-missing
```

### Unit Test Patterns

#### Testing Client Methods

```python
import pytest
from unittest.mock import Mock
from kibana import Kibana
from kibana.exceptions import NotFoundError

class TestActionsClient:
    def test_get_connector_success(self, mock_transport):
        """Test successful connector retrieval."""
        # Arrange
        mock_transport.perform_request.return_value = Mock(
            body={"id": "test-id", "name": "Test Connector"},
            meta=Mock(status=200, headers={}, http_version="1.1"),
        )
        client = Kibana(_transport=mock_transport)

        # Act
        result = client.actions.get(id="test-id")

        # Assert
        assert result.body["id"] == "test-id"
        mock_transport.perform_request.assert_called_once()
```

#### Testing Space Support

```python
def test_create_with_space_id(self, mock_transport):
    """Test connector creation with space_id parameter."""
    client = Kibana(_transport=mock_transport)

    # Mock space validation
    mock_transport.perform_request.side_effect = [
        Mock(body={"id": "marketing", "name": "Marketing"}),  # Space validation
        Mock(body={"id": "conn-1", "name": "Test"}),  # Connector creation
    ]

    result = client.actions.create(
        name="Test",
        connector_type_id=".index",
        config={"index": "test"},
        space_id="marketing"
    )

    # Verify space-scoped path was used
    calls = mock_transport.perform_request.call_args_list
    assert "/s/marketing/api/actions/connector" in calls[1][1]["path"]
```

#### Testing Error Handling

```python
def test_space_not_found_error(self, mock_transport):
    """Test proper error handling for non-existent spaces."""
    client = Kibana(_transport=mock_transport)

    # Mock space not found
    from kibana.exceptions import SpaceNotFoundError
    mock_transport.perform_request.side_effect = NotFoundError(
        message="Space not found",
        meta=Mock(status=404),
        body={"error": "Not found"}
    )

    with pytest.raises(SpaceNotFoundError) as exc_info:
        client.actions.create(
            name="Test",
            connector_type_id=".index",
            config={},
            space_id="nonexistent"
        )

    assert exc_info.value.space_id == "nonexistent"
```

#### Testing Validation Caching

```python
def test_space_validation_caching(self, mock_transport):
    """Test that space validation results are cached."""
    client = Kibana(_transport=mock_transport)

    # Mock space validation and operations
    mock_transport.perform_request.side_effect = [
        Mock(body={"id": "marketing"}),  # First validation
        Mock(body={"id": "conn-1"}),     # First operation
        Mock(body={"id": "conn-2"}),     # Second operation (no validation)
    ]

    # First call should validate space
    client.actions.create(
        name="Test1",
        connector_type_id=".index",
        config={},
        space_id="marketing"
    )

    # Second call should use cache
    client.actions.create(
        name="Test2",
        connector_type_id=".index",
        config={},
        space_id="marketing"
    )

    # Space validation should only be called once
    assert mock_transport.perform_request.call_count == 3
```

### Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

```python
@pytest.fixture
def mock_transport():
    """Mock transport for unit tests."""
    from unittest.mock import Mock
    return Mock()

@pytest.fixture
def kibana_client(mock_transport):
    """Kibana client with mocked transport."""
    from kibana import Kibana
    return Kibana(_transport=mock_transport)
```

## Integration Testing

### Prerequisites

Integration tests require a running Kibana instance. The easiest way is to use the provided local Elastic Stack:

```bash
./local-stack.sh -o start
```

This creates a `.env` file with credentials that integration tests automatically detect.

### Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/

# Run specific integration test
pytest tests/integration/test_actions_integration.py

# Skip integration tests
pytest tests/unit/  # Only run unit tests
```

Integration tests are automatically skipped if `KIBANA_URL` is not set.

### Configuration

Integration tests support multiple configuration sources (in order of preference):

1. **Environment variables**:
   ```bash
   export KIBANA_URL="http://localhost:5601"
   export KIBANA_USERNAME="elastic"
   export KIBANA_PASSWORD="changeme"
   # or
   export KIBANA_API_KEY="your-api-key"
   ```

2. **Local development setup** (`elastic-start-local/.env`):
   ```
   KIBANA_URL=http://localhost:5601
   KIBANA_USERNAME=elastic
   KIBANA_PASSWORD=changeme
   ```

3. **Defaults**: `http://localhost:5601` with no authentication

### Integration Test Patterns

#### Basic Integration Test

```python
import pytest
from tests.integration.utils import create_test_kibana_client, is_kibana_available

pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

class TestActionsIntegration:
    def test_create_and_delete_connector(self, kibana_client, created_connectors):
        """Test connector lifecycle."""
        # Create connector
        response = kibana_client.actions.create(
            name="Integration Test Connector",
            connector_type_id=".index",
            config={"index": "integration-test"}
        )

        connector = response.body
        created_connectors.append(connector["id"])  # Track for cleanup

        # Verify connector exists
        retrieved = kibana_client.actions.get(id=connector["id"])
        assert retrieved.body["name"] == "Integration Test Connector"

        # Cleanup is handled by fixture
```

#### Testing Space Isolation

```python
def test_space_scoped_connector_operations(self, kibana_client, test_space, created_connectors):
    """Test connector operations in a real space."""
    # Create connector in test space
    response = kibana_client.actions.create(
        name="Space Test Connector",
        connector_type_id=".index",
        config={"index": "space-test"},
        space_id=test_space["id"]
    )

    connector = response.body
    created_connectors.append((connector["id"], test_space["id"]))

    # Verify connector exists in space
    retrieved = kibana_client.actions.get(
        id=connector["id"],
        space_id=test_space["id"]
    )
    assert retrieved.body["name"] == "Space Test Connector"

    # Verify connector doesn't exist in default space
    from kibana.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        kibana_client.actions.get(id=connector["id"])
```

### Resource Management

Integration tests must clean up all resources they create:

```python
@pytest.fixture
def created_connectors(kibana_client):
    """Track connectors created during tests for cleanup."""
    connector_ids = []
    yield connector_ids

    # Cleanup all created connectors
    for connector_id in connector_ids:
        try:
            kibana_client.actions.delete(id=connector_id)
        except Exception:
            pass  # Connector might already be deleted

@pytest.fixture
def test_space(kibana_client):
    """Create a test space and clean it up after the test."""
    import time
    space_id = f"test-space-{int(time.time())}"

    space = kibana_client.spaces.create(
        id=space_id,
        name="Integration Test Space",
        description="Temporary space for integration tests"
    )

    yield space.body

    # Cleanup
    try:
        kibana_client.spaces.delete(id=space_id)
    except Exception:
        pass  # Space might already be deleted
```

## Test Coverage

### Coverage Requirements

- **Minimum coverage**: 90% overall
- **Critical paths**: 100% coverage
- **New code**: Must maintain or improve coverage

### Generating Coverage Reports

```bash
# Run tests with coverage
pytest --cov=kibana --cov-report=term-missing --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Coverage Configuration

Coverage settings are in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["kibana"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/site-packages/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Performance Testing

### Validation Overhead Testing

```python
def test_space_validation_performance(kibana_client, benchmark):
    """Benchmark space validation with and without caching."""

    def create_with_validation():
        return kibana_client.actions.create(
            name="Perf Test",
            connector_type_id=".index",
            config={"index": "perf-test"},
            space_id="default"
        )

    # Benchmark with caching
    result = benchmark(create_with_validation)

    # Verify performance is acceptable
    assert benchmark.stats.mean < 0.1  # Less than 100ms average
```

## Best Practices

### Unit Test Quality

- ✅ Complete method coverage for all public APIs
- ✅ Space support testing for all applicable methods
- ✅ Error scenario coverage with proper exception testing
- ✅ Mock isolation with no external dependencies
- ✅ Fast execution (entire unit test suite < 10 seconds)

### Integration Test Quality

- ✅ Real Kibana interaction using elastic-start-local
- ✅ Space isolation testing to verify multi-tenancy
- ✅ Resource cleanup with no test artifacts left behind
- ✅ Configuration flexibility supporting different environments
- ✅ Graceful degradation when Kibana is not available

### Test Naming

- Use descriptive names that explain what is being tested
- Follow pattern: `test_<method>_<scenario>_<expected_result>`
- Examples:
  - `test_create_connector_success`
  - `test_get_connector_not_found`
  - `test_create_with_space_id_validates_space`

### Test Organization

- Group related tests in classes
- Use fixtures for common setup
- Keep tests independent (no shared state)
- One assertion per test when possible

## Continuous Integration

### CI Test Execution

Tests run automatically on:
- Every push to a branch
- Every pull request
- Scheduled nightly builds

### CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.14"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run unit tests
        run: |
          pytest tests/unit/ --cov=kibana --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Tests Fail Locally But Pass in CI

- Check Python version matches CI
- Ensure all dependencies are installed
- Clear pytest cache: `pytest --cache-clear`
- Check for environment-specific issues

### Integration Tests Fail

- Verify Kibana is running: `curl http://localhost:5601/api/status`
- Check credentials are correct
- Ensure Kibana version is compatible
- Review test logs for specific errors

### Coverage Drops Unexpectedly

- Run coverage locally to identify gaps
- Check if new code is missing tests
- Verify test fixtures are working correctly
- Review coverage report: `open htmlcov/index.html`

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- {doc}`contributing` - General contribution guidelines
- {doc}`adding-space-support` - Testing space support
