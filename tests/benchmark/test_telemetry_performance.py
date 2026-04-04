"""Performance validation tests for telemetry functionality."""

import statistics
import time

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False

from utils import create_test_kibana_client, is_kibana_available

# Skip all tests if Kibana is not available
pytestmark = [
    pytest.mark.skipif(
        not is_kibana_available(),
        reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
    ),
    pytest.mark.benchmark,
]


@pytest.fixture
def performance_test_config():
    """Configuration for performance tests."""
    return {
        "num_iterations": 10,
        "warmup_iterations": 2,
        "max_overhead_ratio": 1.5,  # 50% overhead maximum
        "max_absolute_overhead_ms": 100,  # 100ms absolute maximum
    }


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestTelemetryOverhead:
    """Test telemetry performance overhead."""

    def test_telemetry_enabled_vs_disabled_overhead(self, performance_test_config):
        """Test performance overhead when telemetry is enabled vs disabled."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        num_iterations = performance_test_config["num_iterations"]
        warmup_iterations = performance_test_config["warmup_iterations"]

        # Test with telemetry disabled
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        disabled_times = []
        client = create_test_kibana_client()

        try:
            # Warmup
            for _ in range(warmup_iterations):
                client.status.get_status()

            # Measure disabled performance
            for _ in range(num_iterations):
                start_time = time.perf_counter()
                client.status.get_status()
                elapsed = time.perf_counter() - start_time
                disabled_times.append(elapsed)

        finally:
            client.close()

        # Test with telemetry enabled
        configure_opentelemetry(
            enabled=True,
            service_name="performance-test",
            exporter="otlp",
            endpoint="http://localhost:8200",
        )

        enabled_times = []
        client = create_test_kibana_client()

        try:
            # Warmup
            for _ in range(warmup_iterations):
                client.status.get_status()

            # Measure enabled performance
            for _ in range(num_iterations):
                start_time = time.perf_counter()
                client.status.get_status()
                elapsed = time.perf_counter() - start_time
                enabled_times.append(elapsed)

        finally:
            client.close()
            instrumentor.disable()

        # Calculate statistics
        disabled_mean = statistics.mean(disabled_times)
        enabled_mean = statistics.mean(enabled_times)
        overhead_ratio = enabled_mean / disabled_mean if disabled_mean > 0 else 1
        absolute_overhead = (enabled_mean - disabled_mean) * 1000  # Convert to ms

        print(f"Disabled mean: {disabled_mean*1000:.2f}ms")
        print(f"Enabled mean: {enabled_mean*1000:.2f}ms")
        print(f"Overhead ratio: {overhead_ratio:.2f}x")
        print(f"Absolute overhead: {absolute_overhead:.2f}ms")

        # Validate overhead is acceptable
        assert (
            overhead_ratio <= performance_test_config["max_overhead_ratio"]
        ), f"Telemetry overhead too high: {overhead_ratio:.2f}x (max: {performance_test_config['max_overhead_ratio']}x)"

        assert (
            absolute_overhead <= performance_test_config["max_absolute_overhead_ms"]
        ), f"Absolute overhead too high: {absolute_overhead:.2f}ms (max: {performance_test_config['max_absolute_overhead_ms']}ms)"

    def test_zero_overhead_when_disabled(self, performance_test_config):
        """Test that there's truly zero overhead when telemetry is disabled."""
        from kibana.observability import KibanaInstrumentor

        # Ensure telemetry is disabled
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        num_iterations = performance_test_config["num_iterations"] * 5
        warmup_iterations = performance_test_config["warmup_iterations"]

        # Measure baseline performance (no telemetry code involved)
        baseline_times = []
        client = create_test_kibana_client()

        try:
            # Warmup
            for _ in range(warmup_iterations):
                client.perform_request("GET", "/api/status")

            for _ in range(num_iterations):
                start_time = time.perf_counter()
                # Direct API call without any telemetry involvement
                response = client.perform_request("GET", "/api/status")
                elapsed = time.perf_counter() - start_time
                baseline_times.append(elapsed)
                assert response.meta.status == 200
        finally:
            client.close()

        # Measure with telemetry disabled (but code present)
        disabled_times = []
        client = create_test_kibana_client()

        try:
            # Warmup
            for _ in range(warmup_iterations):
                client.status.get_status()

            for _ in range(num_iterations):
                start_time = time.perf_counter()
                # Use the high-level API that could have telemetry
                client.status.get_status()
                elapsed = time.perf_counter() - start_time
                disabled_times.append(elapsed)
        finally:
            client.close()

        baseline_mean = statistics.mean(baseline_times)
        disabled_mean = statistics.mean(disabled_times)
        overhead_ratio = disabled_mean / baseline_mean if baseline_mean > 0 else 1

        print(f"Baseline mean: {baseline_mean*1000:.2f}ms")
        print(f"Disabled mean: {disabled_mean*1000:.2f}ms")
        print(f"Overhead ratio: {overhead_ratio:.2f}x")

        # Should have minimal overhead (< 10%)
        assert (
            overhead_ratio <= 1.1
        ), f"Unexpected overhead when disabled: {overhead_ratio:.2f}x"


class TestMemoryUsage:
    """Test memory usage of telemetry functionality."""

    def test_memory_usage_when_disabled(self):
        """Test that memory usage is minimal when telemetry is disabled."""
        import gc

        import psutil

        from kibana.observability import KibanaInstrumentor

        # Ensure telemetry is disabled
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        # Force garbage collection
        gc.collect()

        # Measure baseline memory
        process = psutil.Process()
        baseline_memory = process.memory_info().rss

        # Create and use client without telemetry
        client = create_test_kibana_client()
        try:
            for _ in range(10):
                client.status.get_status()
        finally:
            client.close()

        # Force garbage collection
        gc.collect()

        # Measure memory after operations
        final_memory = process.memory_info().rss
        memory_increase = final_memory - baseline_memory

        print(f"Memory increase: {memory_increase / 1024 / 1024:.2f} MB")

        # 10 API calls with telemetry disabled should use very little memory
        assert (
            memory_increase < 5 * 1024 * 1024
        ), f"Excessive memory usage with telemetry disabled: {memory_increase / 1024 / 1024:.2f} MB"

    @pytest.mark.skipif(
        not OTEL_AVAILABLE,
        reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
    )
    def test_memory_usage_when_enabled(self):
        """Test memory usage when telemetry is enabled."""
        import gc

        import psutil

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        # Configure telemetry
        configure_opentelemetry(
            enabled=True, service_name="memory-test", exporter="console"
        )

        # Force garbage collection
        gc.collect()

        # Measure baseline memory
        process = psutil.Process()
        baseline_memory = process.memory_info().rss

        # Create and use client with telemetry
        client = create_test_kibana_client()
        try:
            for _ in range(10):
                client.status.get_status()
        finally:
            client.close()

        # Force garbage collection
        gc.collect()

        # Measure memory after operations
        final_memory = process.memory_info().rss
        memory_increase = final_memory - baseline_memory

        print(f"Memory increase with telemetry: {memory_increase / 1024 / 1024:.2f} MB")

        # 10 API calls with telemetry enabled should use at most 10MB
        assert (
            memory_increase < 10 * 1024 * 1024
        ), f"Excessive memory usage with telemetry: {memory_increase / 1024 / 1024:.2f} MB"

        # Cleanup
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()
