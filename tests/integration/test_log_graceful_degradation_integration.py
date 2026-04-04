"""Integration tests for graceful degradation of log forwarding."""

import logging
import time
from unittest.mock import patch

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
    OTEL_LOGS_AVAILABLE = importlib.util.find_spec("opentelemetry._logs") is not None
except ImportError:
    OTEL_AVAILABLE = False
    OTEL_LOGS_AVAILABLE = False

from kibana.observability import (
    KibanaInstrumentor,
    OTelLogHandler,
    _cleanup_log_handlers,
    _created_log_handlers,
    _validate_apm_connectivity,
    configure_opentelemetry,
    get_log_forwarding_status,
    validate_log_forwarding_configuration,
    validate_log_forwarding_connectivity,
)

from .conftest import flush_telemetry
from .utils import print_test_config_info

# Skip all tests if OpenTelemetry is not available
pytestmark = pytest.mark.skipif(
    not (OTEL_AVAILABLE and OTEL_LOGS_AVAILABLE),
    reason="OpenTelemetry logs not installed. Install with: pip install kibana-py[observability] opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http",
)


@pytest.fixture
def test_logger():
    """Create a test logger for degradation tests."""
    logger_name = "kibana.test.degradation"
    test_logger = logging.getLogger(logger_name)
    test_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    test_logger.handlers.clear()

    yield test_logger

    # Cleanup
    test_logger.handlers.clear()


@pytest.fixture(scope="function")
def clean_observability():
    """Ensure clean observability state before and after tests."""
    # Disable instrumentation
    instrumentor = KibanaInstrumentor.get_instance()
    instrumentor.disable()

    # Cleanup any existing log handlers
    global _created_log_handlers
    if _created_log_handlers:
        _cleanup_log_handlers(_created_log_handlers)
        _created_log_handlers.clear()

    yield

    # Cleanup after test
    instrumentor.disable()
    if _created_log_handlers:
        _cleanup_log_handlers(_created_log_handlers)
        _created_log_handlers.clear()


class TestOTLPEndpointUnavailable:
    """Test behavior when OTLP endpoint is unavailable."""

    def test_configuration_with_unreachable_server(
        self, test_logger, clean_observability
    ):
        """Test configuration when OTLP endpoint is unreachable."""
        # Configure with non-existent server
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-unreachable-test",
            exporter="otlp",
            endpoint="http://nonexistent.server:8200",
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should configure without crashing
        status = get_log_forwarding_status()
        assert status["logs_available"] is True

        # Send logs - should not crash application
        test_logger.info("Log to unreachable server")
        test_logger.warning("Warning to unreachable server")
        test_logger.error("Error to unreachable server")

        # Application should continue normally
        flush_telemetry()

    def test_connectivity_validation_failure(self):
        """Test connectivity validation with unreachable server."""
        # Test connectivity to non-existent server
        result = validate_log_forwarding_connectivity(
            endpoint="http://nonexistent.server:8200",
            protocol="grpc",
            timeout=2,
        )

        assert result["success"] is False
        assert "error" in result
        assert result["endpoint"] == "http://nonexistent.server:8200"
        assert result["protocol"] == "grpc"

    def test_otlp_connectivity_validation_with_timeout(self):
        """Test OTLP connectivity validation with timeout."""
        # Use a non-routable IP to simulate timeout
        non_routable_endpoint = "http://10.255.255.1:8200"

        start_time = time.time()
        result = _validate_apm_connectivity(
            endpoint=non_routable_endpoint,
            headers={},
            protocol="grpc",
            timeout=2,
            max_retries=1,
        )
        elapsed_time = time.time() - start_time

        assert result is False
        # Should timeout reasonably quickly (with retries)
        assert elapsed_time < 10  # Should be less than 10 seconds total

    def test_log_forwarding_with_intermittent_connectivity(
        self, test_logger, clean_observability
    ):
        """Test log forwarding behavior with intermittent connectivity."""
        # Configure with a server that might be intermittently available
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-intermittent-test",
            exporter="otlp",
            endpoint="http://localhost:9999",  # Likely unavailable port
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Send logs continuously - should handle connection issues gracefully
        for i in range(10):
            test_logger.info(
                f"Intermittent connectivity test {i}", extra={"iteration": i}
            )
            time.sleep(0.1)

        # Application should continue without issues
        flush_telemetry()

    def test_server_becomes_unavailable_during_operation(
        self, test_logger, clean_observability
    ):
        """Test behavior when server becomes unavailable during operation."""
        # Start with console exporter (always available)
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-server-down-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Send initial logs
        test_logger.info("Initial log when server available")

        # Simulate server becoming unavailable by mocking the exporter
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        if otel_handlers:
            handler = otel_handlers[0]

            # Mock the forward method to simulate server failure
            with patch.object(
                handler,
                "_forward_log",
                side_effect=ConnectionError("Server unavailable"),
            ):
                # Should handle gracefully
                test_logger.warning("Log when server becomes unavailable")
                test_logger.error("Error log when server unavailable")

        # Should continue working after simulated failure
        test_logger.info("Log after server failure simulation")

        flush_telemetry()


class TestAuthenticationFailures:
    """Test authentication failure scenarios."""

    def test_invalid_authentication_token(self, test_logger, clean_observability):
        """Test behavior with invalid authentication token."""
        # Configure with invalid token
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-invalid-auth-test",
            exporter="otlp",
            endpoint="http://localhost:8200",
            headers={"authorization": "Bearer invalid-token-12345"},
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should configure without crashing
        test_logger.info("Log with invalid auth token")
        test_logger.error("Error log with invalid auth token")

        # Application should continue normally
        flush_telemetry()

    def test_missing_authentication_when_required(
        self, test_logger, clean_observability
    ):
        """Test behavior when authentication is required but missing."""
        # Configure without authentication to a server that might require it
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-no-auth-test",
            exporter="otlp",
            endpoint="http://localhost:8200",
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should handle gracefully
        test_logger.info("Log without authentication")
        test_logger.warning("Warning without authentication")

        flush_telemetry()

    def test_authentication_token_expiry_simulation(
        self, test_logger, clean_observability
    ):
        """Test behavior when authentication token expires during operation."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-token-expiry-test",
            exporter="console",  # Use console to avoid actual network calls
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Send initial logs
        test_logger.info("Log before token expiry")

        # Simulate authentication failure
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        if otel_handlers:
            handler = otel_handlers[0]

            # Mock to simulate auth failure
            with patch.object(
                handler, "_forward_log", side_effect=Exception("401 Unauthorized")
            ):
                test_logger.warning("Log during auth failure")
                test_logger.error("Error during auth failure")

        # Should recover after auth issue
        test_logger.info("Log after auth failure simulation")

        flush_telemetry()


class TestNetworkTimeoutAndRetry:
    """Test network timeout and retry logic for logs."""

    def test_network_timeout_handling(self, test_logger, clean_observability):
        """Test handling of network timeouts."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-timeout-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Get handler and simulate timeout
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        if otel_handlers:
            handler = otel_handlers[0]

            # Mock to simulate timeout
            with patch.object(
                handler, "_forward_log", side_effect=TimeoutError("Network timeout")
            ):
                test_logger.info("Log during network timeout")
                test_logger.warning("Warning during network timeout")

        # Should continue after timeout
        test_logger.info("Log after timeout simulation")

        flush_telemetry()

    def test_connection_reset_handling(self, test_logger, clean_observability):
        """Test handling of connection reset errors."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-reset-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Simulate connection reset
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        if otel_handlers:
            handler = otel_handlers[0]

            # Mock to simulate connection reset
            with patch.object(
                handler,
                "_forward_log",
                side_effect=ConnectionResetError("Connection reset by peer"),
            ):
                test_logger.info("Log during connection reset")
                test_logger.error("Error during connection reset")

        # Should recover
        test_logger.info("Log after connection reset simulation")

        flush_telemetry()

    def test_dns_resolution_failure(self, test_logger, clean_observability):
        """Test handling of DNS resolution failures."""
        # Configure with unresolvable hostname
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-dns-test",
            exporter="otlp",
            endpoint="http://unresolvable.hostname.invalid:8200",
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should handle DNS failure gracefully
        test_logger.info("Log with DNS resolution failure")
        test_logger.warning("Warning with DNS resolution failure")

        flush_telemetry()

    def test_ssl_certificate_errors(self, test_logger, clean_observability):
        """Test handling of SSL certificate errors."""
        # Configure with HTTPS endpoint that might have cert issues
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-ssl-test",
            exporter="otlp",
            endpoint="https://self-signed.badssl.com:8200",  # Known bad cert
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should handle SSL errors gracefully
        test_logger.info("Log with SSL certificate error")
        test_logger.error("Error with SSL certificate error")

        flush_telemetry()


class TestLogHandlerErrorRecovery:
    """Test log handler error recovery and resilience."""

    def test_handler_error_count_tracking(self, test_logger, clean_observability):
        """Test that handler tracks and limits error count."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-error-count-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Get handler
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        assert len(otel_handlers) > 0
        handler = otel_handlers[0]

        # Verify initial state
        assert handler._error_count == 0
        assert handler._enabled is True

        # Simulate multiple errors
        with patch.object(
            handler, "_forward_log", side_effect=Exception("Simulated error")
        ):
            for i in range(5):
                test_logger.error(f"Error log {i}")

        # Error count should increase
        assert handler._error_count == 5

        # Handler should still be enabled (below threshold)
        assert handler._enabled is True

    def test_handler_disables_after_max_errors(self, test_logger, clean_observability):
        """Test that handler disables itself after too many errors."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-max-errors-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Get handler
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        assert len(otel_handlers) > 0
        handler = otel_handlers[0]

        # Set lower threshold for testing
        handler._max_errors = 3

        # Simulate errors beyond threshold
        with patch.object(
            handler, "_forward_log", side_effect=Exception("Simulated error")
        ):
            for i in range(5):
                test_logger.error(f"Error log {i}")

        # Handler should be disabled
        assert handler._error_count > handler._max_errors
        assert handler._enabled is False

    def test_handler_recovery_after_errors(self, test_logger, clean_observability):
        """Test that handler can recover after temporary errors."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-recovery-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Get handler
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        assert len(otel_handlers) > 0
        handler = otel_handlers[0]

        # Send normal log
        test_logger.info("Normal log before errors")

        # Simulate temporary errors
        with patch.object(
            handler, "_forward_log", side_effect=Exception("Temporary error")
        ):
            test_logger.error("Error log during failure")

        # Should work normally after error
        test_logger.info("Normal log after error recovery")

        flush_telemetry()

    def test_multiple_handlers_independence(self, clean_observability):
        """Test that multiple handlers fail independently."""
        # Configure multiple loggers
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-multi-handler-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.handler1", "kibana.test.handler2"],
        )

        logger1 = logging.getLogger("kibana.test.handler1")
        logger2 = logging.getLogger("kibana.test.handler2")

        # Get handlers
        handler1 = next(
            (h for h in logger1.handlers if isinstance(h, OTelLogHandler)), None
        )
        handler2 = next(
            (h for h in logger2.handlers if isinstance(h, OTelLogHandler)), None
        )

        assert handler1 is not None
        assert handler2 is not None
        assert handler1 is not handler2  # Should be different instances

        # Simulate error in first handler only
        with patch.object(
            handler1, "_forward_log", side_effect=Exception("Handler 1 error")
        ):
            logger1.error("Error in handler 1")
            logger2.info("Normal log in handler 2")  # Should work fine

        # Both should continue working
        logger1.info("Recovery log in handler 1")
        logger2.info("Continued log in handler 2")

        flush_telemetry()


class TestConfigurationErrorHandling:
    """Test handling of configuration errors."""

    def test_invalid_log_level_configuration(self, clean_observability):
        """Test handling of invalid log level configuration."""
        # Should handle invalid log level gracefully
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-invalid-level-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INVALID_LEVEL",  # Invalid
            logs_loggers=["kibana.test.degradation"],
        )

        # Should fall back to default level
        status = get_log_forwarding_status()
        assert status["logs_available"] is True

    def test_empty_loggers_list_configuration(self, clean_observability):
        """Test handling of empty loggers list."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-empty-loggers-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=[],  # Empty list
        )

        # Should handle gracefully
        status = get_log_forwarding_status()
        assert status["logs_available"] is True
        assert status["handlers_configured"] == 0  # No handlers for empty list

    def test_invalid_protocol_configuration(self, test_logger, clean_observability):
        """Test handling of invalid protocol configuration."""
        # Should handle invalid protocol gracefully
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-invalid-protocol-test",
            exporter="otlp",
            endpoint="http://localhost:8200",
            protocol="invalid_protocol",  # Invalid
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.degradation"],
        )

        # Should continue without crashing
        test_logger.info("Log with invalid protocol config")

    def test_missing_dependencies_handling(self, test_logger, clean_observability):
        """Test handling when required dependencies are missing."""
        # Mock missing OTLP exporters
        with (
            patch("kibana.observability.GRPC_LOG_EXPORTER_AVAILABLE", False),
            patch("kibana.observability.HTTP_LOG_EXPORTER_AVAILABLE", False),
        ):

            configure_opentelemetry(
                enabled=True,
                service_name="kibana-py-missing-deps-test",
                exporter="otlp",
                endpoint="http://localhost:8200",
                protocol="grpc",
                logs_enabled=True,
                logs_level="INFO",
                logs_loggers=["kibana.test.degradation"],
            )

            # Should handle missing dependencies gracefully
            test_logger.info("Log with missing dependencies")

    def test_configuration_validation_errors(self):
        """Test configuration validation with various error conditions."""
        # Test with logs enabled but not available
        with patch("kibana.observability.OTEL_LOGS_AVAILABLE", False):
            result = validate_log_forwarding_configuration(
                logs_enabled=True,
                logs_level="INFO",
                logs_loggers=["test"],
            )

            assert result["valid"] is False
            assert any("not available" in error for error in result["errors"])

        # Test with invalid log level
        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="INVALID",
            logs_loggers=["test"],
        )

        assert result["valid"] is False
        assert any("Invalid log level" in error for error in result["errors"])


if __name__ == "__main__":
    # Print test configuration for debugging
    print_test_config_info()

    if not (OTEL_AVAILABLE and OTEL_LOGS_AVAILABLE):
        print("❌ OpenTelemetry logs not available")
        print(
            "   Install with: pip install kibana-py[observability] opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http"
        )
    else:
        print("✅ OpenTelemetry logs available")

    print("🔧 Testing graceful degradation scenarios...")
    print("   - OTLP endpoint unavailable")
    print("   - Authentication failures")
    print("   - Network timeouts and retries")
    print("   - Configuration errors")
