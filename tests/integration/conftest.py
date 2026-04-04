"""Pytest configuration for integration tests.

Loads elastic-start-local/.env variables into os.environ before test collection
so that skipif decorators and fixtures see the correct values.
"""

# Import examples.utils via importlib to avoid name collision with integration utils.
# Importing it triggers load_local_env() which injects elastic-start-local/.env into os.environ.
import importlib.util as _ilu
import os
from pathlib import Path

import pytest

_examples_utils_path = Path(__file__).parent.parent.parent / "examples" / "utils.py"
_spec = _ilu.spec_from_file_location("examples_utils", _examples_utils_path)
_examples_utils = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_examples_utils)


def flush_telemetry(timeout_ms: int = 5000) -> None:
    """Force-flush all active OTel providers (traces and logs).

    Use this instead of time.sleep() after generating spans or logs
    to ensure they are exported before assertions run.
    """
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_ms)
    except Exception:
        pass

    try:
        from opentelemetry._logs import get_logger_provider

        provider = get_logger_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_ms)
    except Exception:
        pass


@pytest.fixture
def otel_endpoint():
    """Get OTLP exporter endpoint from environment."""
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8200")


@pytest.fixture
def otel_auth_token():
    """Get OTLP authentication token from environment."""
    return os.getenv("ELASTIC_APM_SECRET_TOKEN", "")
