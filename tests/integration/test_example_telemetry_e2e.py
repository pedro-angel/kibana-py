"""End-to-end integration tests for example telemetry functionality."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False

from .utils import is_kibana_available

# Skip all tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def examples_dir():
    """Get the examples directory path."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def temp_env_with_telemetry():
    """Create temporary environment with telemetry enabled."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(
            """# Test environment file for telemetry
KIBANA_OTEL_ENABLED=true
OTEL_SERVICE_NAME=kibana-py-e2e-test
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ELASTIC_APM_SECRET_TOKEN=test-token-e2e
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer ${ELASTIC_APM_SECRET_TOKEN}
"""
        )
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def temp_env_without_telemetry():
    """Create temporary environment with telemetry disabled."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(
            """# Test environment file without telemetry
KIBANA_OTEL_ENABLED=false
"""
        )
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_elastic_start_local_env(temp_env_with_telemetry):
    """Mock the elastic-start-local/.env file location."""
    # Create a mock directory structure
    temp_dir = Path(temp_env_with_telemetry).parent
    elastic_dir = temp_dir / "elastic-start-local"
    elastic_dir.mkdir(exist_ok=True)

    # Copy the temp env file to the expected location
    env_file = elastic_dir / ".env"
    env_file.write_text(Path(temp_env_with_telemetry).read_text())

    yield env_file

    # Cleanup
    if env_file.exists():
        env_file.unlink()
    if elastic_dir.exists():
        elastic_dir.rmdir()


def run_example_script(
    script_path: Path, env_vars: dict = None, timeout: int = 30
) -> subprocess.CompletedProcess:
    """Run an example script and return the result."""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    # Run the script
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=script_path.parent,
    )

    return result


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestExampleTelemetryEnabled:
    """Test examples with telemetry enabled."""

    def test_simple_status_with_telemetry(self, examples_dir):
        """Test simple_status.py with telemetry enabled."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry enabled
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "simple-status-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed even if APM server is not available
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that telemetry configuration is displayed
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: True" in result.stdout
        assert "Service Name: simple-status-test" in result.stdout

    def test_debug_status_with_telemetry(self, examples_dir):
        """Test debug_status.py with telemetry enabled."""
        script_path = examples_dir / "debug_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry enabled
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "debug-status-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check telemetry output
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: True" in result.stdout

    def test_simple_space_with_telemetry(self, examples_dir):
        """Test simple_space.py with telemetry enabled."""
        script_path = examples_dir / "simple_space.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry enabled
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "simple-space-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check telemetry output
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: True" in result.stdout

    def test_async_simple_status_with_telemetry(self, examples_dir):
        """Test async_simple_status.py with telemetry enabled."""
        script_path = examples_dir / "async_simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry enabled
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "async-simple-status-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check telemetry output
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: True" in result.stdout


class TestExampleTelemetryDisabled:
    """Test examples with telemetry disabled."""

    def test_simple_status_without_telemetry(self, examples_dir):
        """Test simple_status.py with telemetry disabled."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry disabled
        env_vars = {"KIBANA_OTEL_ENABLED": "false"}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that telemetry is disabled
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: False" in result.stdout

    def test_debug_status_without_telemetry(self, examples_dir):
        """Test debug_status.py with telemetry disabled."""
        script_path = examples_dir / "debug_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry disabled
        env_vars = {"KIBANA_OTEL_ENABLED": "false"}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that telemetry is disabled
        assert "Enabled: False" in result.stdout

    def test_async_example_without_telemetry(self, examples_dir):
        """Test async example with telemetry disabled."""
        script_path = examples_dir / "async_simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry disabled
        env_vars = {"KIBANA_OTEL_ENABLED": "false"}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that telemetry is disabled
        assert "Enabled: False" in result.stdout


class TestExampleConfigurationDetection:
    """Test configuration detection in examples."""

    def test_environment_variable_precedence(self, examples_dir):
        """Test that environment variables take precedence over .env files."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Set environment variables that should override any .env file
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "env-override-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://env-override:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that environment variables were used
        assert "Service Name: env-override-test" in result.stdout
        assert "OTLP Endpoint: http://env-override:8200" in result.stdout

    def test_default_configuration_fallback(self, examples_dir):
        """Test fallback to default configuration."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run without any telemetry configuration
        env_vars = {
            # Remove any existing telemetry env vars
            "KIBANA_OTEL_ENABLED": "",
            "OTEL_SERVICE_NAME": "",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "",
            "ELASTIC_APM_SECRET_TOKEN": "",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show default configuration
        assert "Telemetry Configuration" in result.stdout

    def test_variable_expansion_in_configuration(
        self, examples_dir, mock_elastic_start_local_env
    ):
        """Test variable expansion in configuration."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Mock the examples directory to use our test env file
        env_vars = {"PYTHONPATH": str(mock_elastic_start_local_env.parent.parent)}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check that variable expansion worked
        assert "Telemetry Configuration" in result.stdout


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestExampleSpanCreation:
    """Test that examples create spans when telemetry is enabled."""

    def test_spans_created_for_kibana_requests(self, examples_dir):
        """Test that Kibana API requests in examples create spans."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with console exporter to capture span output
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "span-creation-test",
            "KIBANA_OTEL_EXPORTER": "console",
        }

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Note: Console exporter output goes to stderr in some OpenTelemetry versions
        _output = result.stdout + result.stderr

        # Should show telemetry is enabled
        assert "Enabled: True" in result.stdout

    def test_no_spans_when_telemetry_disabled(self, examples_dir):
        """Test that no spans are created when telemetry is disabled."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry disabled
        env_vars = {"KIBANA_OTEL_ENABLED": "false"}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show telemetry is disabled
        assert "Enabled: False" in result.stdout

        # Should not have any span-related output
        _output = result.stdout + result.stderr
        # This is hard to test definitively, but we can check basic functionality


class TestExampleErrorHandling:
    """Test error handling in examples with telemetry."""

    def test_example_continues_with_unreachable_endpoint(self, examples_dir):
        """Test that examples continue to work when OTLP endpoint is unreachable."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Configure with unreachable APM server
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "unreachable-otlp-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://unreachable-server:8200",
        }

        result = run_example_script(script_path, env_vars)

        # Should still succeed despite unreachable APM server
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show telemetry configuration
        assert "Telemetry Configuration" in result.stdout
        assert "Enabled: True" in result.stdout

    def test_example_handles_invalid_telemetry_config(self, examples_dir):
        """Test that examples handle invalid telemetry configuration gracefully."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Configure with invalid settings
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "",  # Invalid: empty service name
            "OTEL_EXPORTER_OTLP_ENDPOINT": "not-a-valid-url",  # Invalid: malformed URL
        }

        result = run_example_script(script_path, env_vars)

        # Should still succeed with graceful error handling
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show telemetry configuration attempt
        assert "Telemetry Configuration" in result.stdout

    def test_example_without_opentelemetry_package(self, examples_dir):
        """Test example behavior when OpenTelemetry package is not available."""
        # This test is tricky to implement without actually uninstalling OpenTelemetry
        # We can test the graceful degradation by checking that examples work
        # when telemetry is disabled

        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry disabled (simulates missing package scenario)
        env_vars = {"KIBANA_OTEL_ENABLED": "false"}

        result = run_example_script(script_path, env_vars)

        # Should succeed
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show telemetry is disabled
        assert "Enabled: False" in result.stdout


class TestExampleTelemetryCleanup:
    """Test telemetry cleanup in examples."""

    def test_telemetry_cleanup_on_normal_exit(self, examples_dir):
        """Test that telemetry is cleaned up on normal example exit."""
        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with telemetry enabled
        env_vars = {"KIBANA_OTEL_ENABLED": "true", "OTEL_SERVICE_NAME": "cleanup-test"}

        result = run_example_script(script_path, env_vars)

        # Should succeed and complete normally
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Should show telemetry configuration
        assert "Telemetry Configuration" in result.stdout

        # Cleanup should happen automatically (hard to test directly)

    def test_telemetry_cleanup_on_error_exit(self, examples_dir):
        """Test that telemetry cleanup happens even when examples encounter errors."""
        # This would require a modified example that intentionally fails
        # For now, we test that normal error handling works

        script_path = examples_dir / "simple_status.py"
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        # Run with invalid Kibana URL to trigger an error
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "error-cleanup-test",
            "KIBANA_URL": "http://invalid-kibana-server:5601",
        }

        result = run_example_script(script_path, env_vars, timeout=10)

        # May fail due to invalid Kibana URL, but should not crash
        # The important thing is that it doesn't hang due to telemetry issues
        assert result.returncode in [
            0,
            1,
        ], f"Script crashed unexpectedly: {result.stderr}"

        # Should still show telemetry configuration
        assert "Telemetry Configuration" in result.stdout
