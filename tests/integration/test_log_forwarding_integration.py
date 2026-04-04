"""Integration tests for OpenTelemetry log forwarding to OTLP endpoint."""

import logging
import os
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
    OTelLogHandler,
    _cleanup_log_handlers,
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
    """Create a test logger for log forwarding tests."""
    logger_name = "kibana.test.log_forwarding"
    test_logger = logging.getLogger(logger_name)
    test_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    test_logger.handlers.clear()

    yield test_logger

    # Cleanup
    test_logger.handlers.clear()


@pytest.fixture(scope="function")
def clean_log_forwarding():
    """Ensure clean log forwarding state before and after tests."""
    import kibana.observability._logging as _logging_mod

    # Cleanup any existing log handlers via the live module reference
    # (the imported _created_log_handlers name becomes stale after
    # configure_opentelemetry replaces the list on the module)
    handlers = _logging_mod._created_log_handlers
    if handlers:
        _cleanup_log_handlers(handlers)
        _logging_mod._created_log_handlers = []

    yield

    # Cleanup after test
    handlers = _logging_mod._created_log_handlers
    if handlers:
        _cleanup_log_handlers(handlers)
        _logging_mod._created_log_handlers = []


class TestOTLPLogForwarding:
    """Test log transmission to OTLP endpoint with different protocols."""

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.",
    )
    def test_grpc_log_forwarding(
        self, otel_endpoint, otel_auth_token, test_logger, clean_log_forwarding
    ):
        """Test log forwarding to OTLP endpoint using gRPC protocol."""
        # Configure OpenTelemetry with log forwarding (gRPC)
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-grpc",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Verify log forwarding is configured
        status = get_log_forwarding_status()
        assert status["logs_available"] is True
        assert status["grpc_exporter_available"] is True
        assert status["handlers_configured"] > 0

        # Send test logs
        test_logger.info(
            "Test INFO log via gRPC", extra={"test_type": "grpc", "protocol": "grpc"}
        )
        test_logger.warning(
            "Test WARNING log via gRPC", extra={"test_type": "grpc", "protocol": "grpc"}
        )
        test_logger.error(
            "Test ERROR log via gRPC", extra={"test_type": "grpc", "protocol": "grpc"}
        )

        # Give time for logs to be sent to APM
        flush_telemetry()

        # Verify no errors occurred (logs were sent successfully)
        # Note: We can't easily verify logs were received without querying APM/Elasticsearch

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.",
    )
    def test_http_log_forwarding(
        self, otel_endpoint, otel_auth_token, test_logger, clean_log_forwarding
    ):
        """Test log forwarding to OTLP endpoint using HTTP protocol."""
        # Configure OpenTelemetry with log forwarding (HTTP)
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-http",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="http/protobuf",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Verify log forwarding is configured
        status = get_log_forwarding_status()
        assert status["logs_available"] is True
        assert status["http_exporter_available"] is True
        assert status["handlers_configured"] > 0

        # Send test logs
        test_logger.info(
            "Test INFO log via HTTP",
            extra={"test_type": "http", "protocol": "http/protobuf"},
        )
        test_logger.warning(
            "Test WARNING log via HTTP",
            extra={"test_type": "http", "protocol": "http/protobuf"},
        )
        test_logger.error(
            "Test ERROR log via HTTP",
            extra={"test_type": "http", "protocol": "http/protobuf"},
        )

        # Give time for logs to be sent to APM
        flush_telemetry()

    def test_log_forwarding_connectivity_validation(self, otel_endpoint):
        """Test connectivity validation for log forwarding endpoints."""
        # Test gRPC connectivity
        grpc_result = validate_log_forwarding_connectivity(
            endpoint=otel_endpoint,
            protocol="grpc",
            timeout=5,
        )

        # Should succeed if OTLP endpoint is running, or fail gracefully
        assert "success" in grpc_result
        assert "endpoint" in grpc_result
        assert "protocol" in grpc_result
        assert grpc_result["protocol"] == "grpc"

        # Test HTTP connectivity
        http_result = validate_log_forwarding_connectivity(
            endpoint=otel_endpoint,
            protocol="http/protobuf",
            timeout=5,
        )

        assert "success" in http_result
        assert "endpoint" in http_result
        assert "protocol" in http_result
        assert http_result["protocol"] == "http/protobuf"

    def test_authentication_with_otlp_token(
        self, otel_endpoint, otel_auth_token, test_logger, clean_log_forwarding
    ):
        """Test log forwarding with OTLP authentication token."""
        if not otel_auth_token:
            pytest.skip("OTLP auth token not configured")

        # Configure with authentication
        headers = {"authorization": f"Bearer {otel_auth_token}"}

        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-auth",
            exporter="otlp",
            endpoint=otel_endpoint,
            headers=headers,
            protocol="grpc",
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Send authenticated log
        test_logger.warning("Authenticated log message", extra={"auth_test": True})

        # Give time for log to be sent
        flush_telemetry()

    def test_log_forwarding_without_endpoint(self, test_logger, clean_log_forwarding):
        """Test log forwarding behavior when OTLP endpoint is not available."""
        # Configure with non-existent endpoint
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-no-server",
            exporter="otlp",
            endpoint="http://nonexistent:8200",
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Should still work (graceful degradation)
        test_logger.info("Log when OTLP endpoint unavailable")
        test_logger.error("Error log when OTLP endpoint unavailable")

        # No exception should be raised


class TestLogForwardingConfiguration:
    """Test log forwarding configuration validation and setup."""

    def test_log_forwarding_configuration_validation(self):
        """Test validation of log forwarding configuration."""
        # Valid configuration
        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana", "my_app"],
            endpoint="http://localhost:8200",
            protocol="grpc",
        )

        assert result["valid"] is True
        assert len(result["errors"]) == 0

        # Invalid log level
        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="INVALID",
            logs_loggers=["kibana"],
        )

        assert result["valid"] is False
        assert any("Invalid log level" in error for error in result["errors"])

        # Empty loggers list
        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=[],
        )

        assert result["valid"] is True  # Valid but with warning
        assert any("Empty logs_loggers" in warning for warning in result["warnings"])

    def test_log_forwarding_status_reporting(self, clean_log_forwarding):
        """Test log forwarding status reporting."""
        # Initial status (no configuration)
        status = get_log_forwarding_status()

        assert "logs_available" in status
        assert "grpc_exporter_available" in status
        assert "http_exporter_available" in status
        assert "handlers_configured" in status
        assert "active_loggers" in status
        assert "configuration" in status

        # Status should show no handlers initially
        assert status["handlers_configured"] == 0
        assert len(status["active_loggers"]) == 0

    def test_console_log_exporter_configuration(
        self, test_logger, clean_log_forwarding
    ):
        """Test configuration with console log exporter."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-console",
            exporter="console",
            logs_enabled=True,
            logs_level="DEBUG",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Verify configuration
        status = get_log_forwarding_status()
        assert status["handlers_configured"] > 0

        # Send test logs (should appear in console)
        test_logger.debug("Debug log to console")
        test_logger.info("Info log to console")
        test_logger.warning("Warning log to console")

        # Give time for console output
        flush_telemetry()

    def test_log_level_filtering(self, test_logger, clean_log_forwarding):
        """Test that log level filtering works correctly."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-filtering",
            exporter="console",
            logs_enabled=True,
            logs_level="WARNING",  # Only WARNING and above
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Send logs at different levels
        test_logger.debug("Debug log (should be filtered)")
        test_logger.info("Info log (should be filtered)")
        test_logger.warning("Warning log (should be forwarded)")
        test_logger.error("Error log (should be forwarded)")
        test_logger.critical("Critical log (should be forwarded)")

        # Give time for processing
        flush_telemetry()

        # Note: In a real test, we would verify that only WARNING+ logs were forwarded
        # This would require capturing the console output or querying APM


class TestLogForwardingErrorHandling:
    """Test error handling and graceful degradation in log forwarding."""

    def test_log_forwarding_with_invalid_endpoint(
        self, test_logger, clean_log_forwarding
    ):
        """Test log forwarding with invalid endpoint format."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-invalid-endpoint",
            exporter="otlp",
            endpoint="invalid-url-format",
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Should handle gracefully
        test_logger.info("Log with invalid endpoint")
        test_logger.error("Error log with invalid endpoint")

    def test_log_forwarding_without_required_dependencies(
        self, test_logger, clean_log_forwarding
    ):
        """Test behavior when required log forwarding dependencies are missing."""
        # Mock missing dependencies
        with patch("kibana.observability.OTEL_LOGS_AVAILABLE", False):
            configure_opentelemetry(
                enabled=True,
                service_name="kibana-py-log-test-no-deps",
                exporter="otlp",
                endpoint="http://localhost:8200",
                logs_enabled=True,
                logs_level="INFO",
                logs_loggers=["kibana.test.log_forwarding"],
            )

            # Should handle gracefully
            test_logger.info("Log without dependencies")

    def test_log_handler_error_recovery(self, test_logger, clean_log_forwarding):
        """Test that log handler recovers from errors gracefully."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-error-recovery",
            exporter="console",
            logs_enabled=True,
            logs_level="DEBUG",
            logs_loggers=["kibana.test.log_forwarding"],
        )

        # Get the handler
        handlers = [h for h in test_logger.handlers if isinstance(h, OTelLogHandler)]
        assert len(handlers) > 0

        handler = handlers[0]

        # Send normal log
        test_logger.info("Normal log before error")

        # Simulate error in handler (this should not crash the application)
        with patch.object(
            handler, "_forward_log", side_effect=Exception("Simulated error")
        ):
            test_logger.error("Log that causes handler error")

        # Handler should still work after error
        test_logger.info("Normal log after error")

        flush_telemetry()

    def test_multiple_logger_configuration(self, clean_log_forwarding):
        """Test configuring log forwarding for multiple loggers."""
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-log-test-multiple",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.logger1", "kibana.test.logger2", "my_app"],
        )

        # Verify multiple loggers are configured
        status = get_log_forwarding_status()
        assert status["handlers_configured"] == 3

        # Test each logger
        logger1 = logging.getLogger("kibana.test.logger1")
        logger2 = logging.getLogger("kibana.test.logger2")
        logger3 = logging.getLogger("my_app")

        logger1.info("Log from logger1")
        logger2.warning("Log from logger2")
        logger3.error("Log from my_app")

        flush_telemetry()


class TestLogForwardingEnvironmentConfiguration:
    """Test log forwarding configuration from environment variables."""

    def test_environment_variable_configuration(self, clean_log_forwarding):
        """Test log forwarding configuration from environment variables."""
        # Set environment variables
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "ERROR",
            "KIBANA_OTEL_LOGS_LOGGERS": "kibana,my_app,test_logger",
            "OTEL_SERVICE_NAME": "env-test-service",
            "KIBANA_OTEL_EXPORTER": "console",
        }

        with patch.dict(os.environ, env_vars):
            configure_opentelemetry()

            # Verify configuration from environment
            status = get_log_forwarding_status()
            assert status["configuration"]["logs_enabled"] == "true"
            assert status["configuration"]["logs_level"] == "ERROR"
            assert (
                status["configuration"]["logs_loggers"] == "kibana,my_app,test_logger"
            )

            # Should have configured 3 loggers
            assert status["handlers_configured"] == 3

    def test_otlp_token_from_environment(self, clean_log_forwarding):
        """Test OTLP auth token configuration from environment."""
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "ELASTIC_APM_SECRET_TOKEN": "test-token-123",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
            "KIBANA_OTEL_EXPORTER": "otlp",
        }

        with patch.dict(os.environ, env_vars):
            # Should configure without errors
            configure_opentelemetry()

            # Verify configuration
            status = get_log_forwarding_status()
            assert status["logs_available"] is True


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

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        print(
            f"✅ OTLP endpoint configured: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}"
        )
    else:
        print("❌ OTLP endpoint not configured (set OTEL_EXPORTER_OTLP_ENDPOINT)")
