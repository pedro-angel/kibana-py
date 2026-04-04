"""Pytest configuration for benchmark tests.

Provides shared fixtures for performance and resource usage benchmarks.
These tests require a running Kibana/Elastic Stack.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_integration_dir = str(Path(__file__).parent.parent / "integration")

# Make integration test utils importable
sys.path.insert(0, _integration_dir)
from utils import create_test_kibana_client, is_kibana_available  # noqa: E402

# Load .env into os.environ via examples/utils (same as integration conftest)
_examples_utils_path = Path(__file__).parent.parent.parent / "examples" / "utils.py"
_spec = importlib.util.spec_from_file_location("examples_utils", _examples_utils_path)
_examples_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_examples_utils)

# Import flush_telemetry from integration conftest via importlib
# (avoids name collision with root tests/conftest.py)
_int_conftest_path = Path(__file__).parent.parent / "integration" / "conftest.py"
_spec2 = importlib.util.spec_from_file_location(
    "integration_conftest", _int_conftest_path
)
_int_conftest = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_int_conftest)
flush_telemetry = _int_conftest.flush_telemetry

__all__ = ["flush_telemetry", "create_test_kibana_client", "is_kibana_available"]


@pytest.fixture
def performance_test_config():
    """Configuration for performance tests."""
    return {
        "num_iterations": 10,
        "warmup_iterations": 2,
        "max_overhead_ratio": 1.5,
        "max_absolute_overhead_ms": 100,
    }
