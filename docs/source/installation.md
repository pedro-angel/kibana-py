# Installation

This guide covers installing kibana-py and its optional dependencies.

## Requirements

Before installing kibana-py, ensure you have:

- **Python 3.10 or higher** - The library requires Python 3.10+
- **Kibana 9.x** - Compatible with Kibana version 9.x
- **pip** - Python package installer (usually included with Python)

## Basic Installation

Install kibana-py using pip:

```bash
pip install kibana-py
```

This installs the core library with synchronous client support and all required dependencies:

- `elastic-transport` (>=9.1.0, <10) - HTTP transport layer
- `python-dateutil` - Date/time utilities
- `typing-extensions` - Extended type hints

## Optional Dependencies

kibana-py provides several optional dependency groups for additional functionality.

### Async Support

For asynchronous client support using `AsyncKibana`:

```bash
pip install kibana-py[async]
```

This installs:
- `aiohttp` (>=3, <4) - Async HTTP client library

Use this if you need to make concurrent requests or integrate with async Python applications.

### High-Performance JSON

For faster JSON serialization and deserialization:

```bash
pip install kibana-py[orjson]
```

This installs:
- `orjson` (>=3) - High-performance JSON library

The library automatically uses orjson when available, providing significant performance improvements for large payloads.

### Observability

For OpenTelemetry distributed tracing support:

```bash
pip install kibana-py[observability]
```

This installs:
- `opentelemetry-api` (>=1.20.0) - OpenTelemetry API
- `opentelemetry-sdk` (>=1.20.0) - OpenTelemetry SDK
- `opentelemetry-exporter-otlp-proto-grpc` (>=1.20.0) - OTLP gRPC exporter

Use this for production monitoring and distributed tracing. See the {doc}`user-guide/observability` guide for configuration details.

### All Optional Dependencies

To install all optional dependencies at once:

```bash
pip install kibana-py[async,orjson,observability]
```

Or use the `all` extra:

```bash
pip install kibana-py[all]
```

## Development Installation

If you're contributing to kibana-py or want to run tests:

```bash
# Clone the repository
git clone https://github.com/pedro-angel/kibana-py.git
cd kibana-py

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

The `dev` extra includes all optional dependencies plus testing and development tools:
- pytest, pytest-cov, pytest-mock, pytest-asyncio
- black, isort, ruff
- mypy, pyright
- nox

## Verifying Installation

After installation, verify that kibana-py is installed correctly:

```python
import kibana
print(kibana.__version__)
```

You can also check which optional dependencies are available:

```python
from kibana import Kibana

# Check if async support is available
try:
    from kibana import AsyncKibana
    print("✓ Async support available")
except ImportError:
    print("✗ Async support not available (install with: pip install kibana-py[async])")

# Check if orjson is available
try:
    import orjson
    print("✓ orjson available")
except ImportError:
    print("✗ orjson not available (install with: pip install kibana-py[orjson])")

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    print("✓ OpenTelemetry available")
except ImportError:
    print("✗ OpenTelemetry not available (install with: pip install kibana-py[observability])")
```

## Troubleshooting

### Python Version Issues

If you encounter errors about Python version:

```bash
# Check your Python version
python --version

# If you have multiple Python versions, use python3.10+ explicitly
python3.10 -m pip install kibana-py
```

### SSL Certificate Errors

If you encounter SSL certificate verification errors:

```python
from kibana import Kibana

# Disable certificate verification (not recommended for production)
client = Kibana(
    "https://localhost:5601",
    verify_certs=False
)

# Or provide a custom CA certificate
client = Kibana(
    "https://localhost:5601",
    ca_certs="/path/to/ca.crt"
)
```

See {doc}`troubleshooting/common-issues` for more solutions.

### Connection Issues

If you can't connect to Kibana:

1. **Verify Kibana is running**: Check that Kibana is accessible at the URL you're using
2. **Check authentication**: Ensure your credentials are correct
3. **Verify network access**: Ensure there are no firewalls blocking the connection
4. **Check Kibana version**: Ensure you're using Kibana 9.x

```python
from kibana import Kibana

# Test connection
try:
    client = Kibana("http://localhost:5601")
    status = client.status.get_status()
    print(f"✓ Connected to Kibana: {status.body['status']['overall']['level']}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
finally:
    client.close()
```

### Import Errors

If you encounter import errors:

```bash
# Ensure kibana-py is installed in the correct environment
pip list | grep kibana

# Reinstall if necessary
pip uninstall kibana-py
pip install kibana-py
```

## Upgrading

To upgrade to the latest version:

```bash
pip install --upgrade kibana-py
```

To upgrade with all optional dependencies:

```bash
pip install --upgrade kibana-py[all]
```

## Uninstalling

To remove kibana-py:

```bash
pip uninstall kibana-py
```

## Next Steps

Now that you have kibana-py installed, check out the {doc}`quickstart` guide to start using the library.

For detailed usage information, see the {doc}`user-guide/index`.
