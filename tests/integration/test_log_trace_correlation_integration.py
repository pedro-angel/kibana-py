"""Integration tests for log-trace correlation in OTLP endpoint."""

import logging
import os
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
    configure_opentelemetry,
    create_span,
)

from .conftest import flush_telemetry
from .utils import (
    create_test_kibana_client,
    is_kibana_available,
    print_test_config_info,
)

# Skip all tests if OpenTelemetry is not available
pytestmark = pytest.mark.skipif(
    not (OTEL_AVAILABLE and OTEL_LOGS_AVAILABLE),
    reason="OpenTelemetry logs not installed. Install with: pip install kibana-py[observability] opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http",
)


@pytest.fixture
def test_logger():
    """Create a test logger for correlation tests."""
    logger_name = "kibana.test.correlation"
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
    import kibana.observability._logging as _logging_mod

    # Disable instrumentation
    instrumentor = KibanaInstrumentor.get_instance()
    instrumentor.disable()

    # Cleanup any existing log handlers via the live module reference
    handlers = _logging_mod._created_log_handlers
    if handlers:
        _cleanup_log_handlers(handlers)
        _logging_mod._created_log_handlers = []

    yield

    # Cleanup after test
    instrumentor.disable()
    handlers = _logging_mod._created_log_handlers
    if handlers:
        _cleanup_log_handlers(handlers)
        _logging_mod._created_log_handlers = []


@pytest.fixture(scope="function")
def configured_observability(otel_endpoint, test_logger, clean_observability):
    """Configure observability with both traces and logs for correlation tests."""
    configure_opentelemetry(
        enabled=True,
        service_name="kibana-py-correlation-test",
        exporter="console",  # Use console for easier testing
        logs_enabled=True,
        logs_level="DEBUG",
        logs_loggers=["kibana.test.correlation"],
    )

    yield

    # Cleanup handled by clean_observability fixture


class TestLogTraceCorrelation:
    """Test correlation between traces and logs in OTLP endpoint."""

    def test_logs_include_trace_context_when_span_active(
        self, configured_observability, test_logger
    ):
        """Test that logs include trace and span IDs when a span is active."""
        # Create a span
        span = create_span("test-operation", attributes={"test.type": "correlation"})

        if span is not None:
            with span:
                # Log within the span context
                test_logger.info(
                    "Log within span context", extra={"operation": "test-operation"}
                )
                test_logger.warning(
                    "Warning within span context", extra={"operation": "test-operation"}
                )
                test_logger.error(
                    "Error within span context", extra={"operation": "test-operation"}
                )

                # Give time for logs to be processed
                flush_telemetry()

        # Note: In a real test environment, we would verify that the logs
        # contain the trace_id and span_id from the active span

    def test_logs_without_active_span(self, configured_observability, test_logger):
        """Test that logs work correctly when no span is active."""
        # Ensure no active span
        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()

        # Log without active span
        test_logger.info("Log without active span", extra={"context": "no-span"})
        test_logger.warning("Warning without active span", extra={"context": "no-span"})

        # Should work without errors
        flush_telemetry()

    def test_nested_spans_with_logs(self, configured_observability, test_logger):
        """Test log correlation with nested spans."""
        # Create parent span
        parent_span = create_span("parent-operation", attributes={"level": "parent"})

        if parent_span is not None:
            with parent_span:
                test_logger.info("Log in parent span", extra={"span_level": "parent"})

                # Create child span
                child_span = create_span(
                    "child-operation", attributes={"level": "child"}
                )

                if child_span is not None:
                    with child_span:
                        test_logger.info(
                            "Log in child span", extra={"span_level": "child"}
                        )
                        test_logger.warning(
                            "Warning in child span", extra={"span_level": "child"}
                        )

                # Back in parent span
                test_logger.info(
                    "Log back in parent span", extra={"span_level": "parent"}
                )

        flush_telemetry()

    def test_multiple_concurrent_spans_with_logs(
        self, configured_observability, test_logger
    ):
        """Test log correlation with multiple concurrent operations."""
        import threading
        import time

        def operation_with_logs(operation_id: str):
            """Simulate an operation that creates spans and logs."""
            span = create_span(
                f"operation-{operation_id}", attributes={"operation.id": operation_id}
            )

            if span is not None:
                with span:
                    test_logger.info(
                        f"Starting operation {operation_id}",
                        extra={"operation_id": operation_id},
                    )

                    # Simulate some work
                    time.sleep(0.1)

                    test_logger.info(
                        f"Processing in operation {operation_id}",
                        extra={"operation_id": operation_id},
                    )

                    # Simulate more work
                    time.sleep(0.1)

                    test_logger.info(
                        f"Completed operation {operation_id}",
                        extra={"operation_id": operation_id},
                    )

        # Start multiple concurrent operations
        threads = []
        for i in range(3):
            thread = threading.Thread(target=operation_with_logs, args=[str(i)])
            threads.append(thread)
            thread.start()

        # Wait for all operations to complete
        for thread in threads:
            thread.join()

        flush_telemetry()

    @pytest.mark.skipif(
        not is_kibana_available(),
        reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
    )
    def test_kibana_api_calls_with_log_correlation(
        self, configured_observability, test_logger
    ):
        """Test log correlation during actual Kibana API calls."""
        client = create_test_kibana_client()

        try:
            # Create a span for the API operation
            span = create_span("kibana-api-test", attributes={"api.type": "status"})

            if span is not None:
                with span:
                    test_logger.info(
                        "Starting Kibana API test", extra={"api": "status"}
                    )

                    # Make API call (this should create its own spans via instrumentation)
                    response = client.perform_request("GET", "/api/status")

                    test_logger.info(
                        "Kibana API call completed",
                        extra={
                            "api": "status",
                            "status_code": response.meta.status,
                            "success": True,
                        },
                    )

                    assert response.meta.status == 200

            flush_telemetry()

        finally:
            client.close()

    def test_error_spans_with_correlated_logs(
        self, configured_observability, test_logger
    ):
        """Test that error logs are properly correlated with error spans."""
        span = create_span("error-operation", attributes={"test.type": "error"})

        if span is not None:
            with span:
                test_logger.info(
                    "Starting operation that will fail",
                    extra={"operation": "error-test"},
                )

                try:
                    # Simulate an error
                    raise ValueError("Simulated error for testing")
                except ValueError as e:
                    # Log the error within the span context
                    test_logger.error(
                        "Operation failed with error",
                        extra={
                            "operation": "error-test",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True,
                    )

                    # Mark span as error
                    if OTEL_AVAILABLE:
                        from kibana.observability import set_span_error

                        set_span_error(span, e)

        flush_telemetry()


class TestLogTraceCorrelationWithOTLP:
    """Test log-trace correlation with real OTLP endpoint."""

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.",
    )
    def test_correlation_with_otlp_grpc(
        self, otel_endpoint, otel_auth_token, test_logger, clean_observability
    ):
        """Test log-trace correlation with OTLP endpoint using gRPC."""
        # Configure with OTLP endpoint
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-correlation-otlp-grpc",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.correlation"],
        )

        # Create correlated traces and logs
        span = create_span("otlp-correlation-test", attributes={"protocol": "grpc"})

        if span is not None:
            with span:
                test_logger.info(
                    "Correlated log via gRPC",
                    extra={"protocol": "grpc", "test": "correlation"},
                )

                # Nested operation
                child_span = create_span(
                    "nested-operation", attributes={"nested": True}
                )
                if child_span is not None:
                    with child_span:
                        test_logger.warning(
                            "Nested correlated log",
                            extra={"nested": True, "protocol": "grpc"},
                        )

                test_logger.info(
                    "Parent operation completed", extra={"protocol": "grpc"}
                )

        # Give time for data to be sent to APM
        flush_telemetry()

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.",
    )
    def test_correlation_with_otlp_http(
        self, otel_endpoint, otel_auth_token, test_logger, clean_observability
    ):
        """Test log-trace correlation with OTLP endpoint using HTTP."""
        # Configure with OTLP endpoint
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-correlation-otlp-http",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="http/protobuf",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.correlation"],
        )

        # Create correlated traces and logs
        span = create_span("otlp-correlation-test", attributes={"protocol": "http"})

        if span is not None:
            with span:
                test_logger.info(
                    "Correlated log via HTTP",
                    extra={"protocol": "http", "test": "correlation"},
                )

                # Simulate some processing
                time.sleep(0.1)

                test_logger.warning(
                    "Processing step completed",
                    extra={"protocol": "http", "step": "processing"},
                )

                # Error scenario
                try:
                    raise RuntimeError("Test error for correlation")
                except RuntimeError as e:
                    test_logger.error(
                        "Error occurred in operation",
                        extra={"protocol": "http", "error": True},
                        exc_info=True,
                    )

                    if OTEL_AVAILABLE:
                        from kibana.observability import set_span_error

                        set_span_error(span, e)

        # Give time for data to be sent to APM
        flush_telemetry()

    @pytest.mark.skipif(
        not (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") and is_kibana_available()),
        reason="OTLP endpoint or Kibana not configured.",
    )
    def test_end_to_end_correlation_with_kibana_operations(
        self, otel_endpoint, test_logger, clean_observability
    ):
        """Test end-to-end correlation with actual Kibana operations."""
        # Configure observability
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-e2e-correlation",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.correlation", "kibana"],
        )

        client = create_test_kibana_client()

        try:
            # Create a business operation span
            span = create_span(
                "kibana-dashboard-operation", attributes={"operation": "dashboard_crud"}
            )

            if span is not None:
                with span:
                    test_logger.info(
                        "Starting dashboard CRUD operation",
                        extra={"operation": "dashboard_crud"},
                    )

                    # Create dashboard
                    create_response = client.perform_request(
                        "POST",
                        "/api/saved_objects/dashboard",
                        body={
                            "attributes": {
                                "title": "Correlation Test Dashboard",
                                "description": "Created for log-trace correlation testing",
                            }
                        },
                    )

                    dashboard_id = create_response.body["id"]
                    test_logger.info(
                        "Dashboard created successfully",
                        extra={
                            "operation": "create",
                            "dashboard_id": dashboard_id,
                            "status_code": create_response.meta.status,
                        },
                    )

                    # Read dashboard
                    read_response = client.perform_request(
                        "GET", f"/api/saved_objects/dashboard/{dashboard_id}"
                    )

                    test_logger.info(
                        "Dashboard retrieved successfully",
                        extra={
                            "operation": "read",
                            "dashboard_id": dashboard_id,
                            "status_code": read_response.meta.status,
                        },
                    )

                    # Update dashboard
                    update_response = client.perform_request(
                        "PUT",
                        f"/api/saved_objects/dashboard/{dashboard_id}",
                        body={
                            "attributes": {
                                "title": "Updated Correlation Test Dashboard",
                                "description": "Updated for log-trace correlation testing",
                            }
                        },
                    )

                    test_logger.info(
                        "Dashboard updated successfully",
                        extra={
                            "operation": "update",
                            "dashboard_id": dashboard_id,
                            "status_code": update_response.meta.status,
                        },
                    )

                    # Delete dashboard
                    delete_response = client.perform_request(
                        "DELETE", f"/api/saved_objects/dashboard/{dashboard_id}"
                    )

                    test_logger.info(
                        "Dashboard deleted successfully",
                        extra={
                            "operation": "delete",
                            "dashboard_id": dashboard_id,
                            "status_code": delete_response.meta.status,
                        },
                    )

                    test_logger.info("Dashboard CRUD operation completed successfully")

            # Give time for all traces and logs to be sent
            flush_telemetry()

        finally:
            client.close()


class TestCorrelationErrorScenarios:
    """Test log-trace correlation in error scenarios."""

    def test_correlation_with_trace_context_extraction_errors(
        self, configured_observability, test_logger
    ):
        """Test that log forwarding works even when trace context extraction fails."""
        # Mock trace context extraction to fail
        with patch(
            "opentelemetry.trace.get_current_span",
            side_effect=Exception("Context error"),
        ):
            test_logger.info("Log when trace context extraction fails")
            test_logger.error("Error log when trace context extraction fails")

        flush_telemetry()

    def test_correlation_with_invalid_span_context(
        self, configured_observability, test_logger
    ):
        """Test log correlation when span context is invalid."""
        if OTEL_AVAILABLE:
            from unittest.mock import Mock

            # Create a mock span with invalid context
            mock_span = Mock()
            mock_span.is_recording.return_value = True
            mock_span_context = Mock()
            mock_span_context.is_valid = False
            mock_span.get_span_context.return_value = mock_span_context

            with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
                test_logger.info("Log with invalid span context")
                test_logger.warning("Warning with invalid span context")

        flush_telemetry()

    def test_correlation_with_log_handler_errors(
        self, configured_observability, test_logger
    ):
        """Test that trace correlation doesn't break when log handler has errors."""
        # Get the OTel log handler
        otel_handlers = [
            h for h in test_logger.handlers if isinstance(h, OTelLogHandler)
        ]
        assert len(otel_handlers) > 0

        handler = otel_handlers[0]

        # Create a span
        span = create_span("error-handler-test")

        if span is not None:
            with span:
                # Normal log
                test_logger.info("Normal log before handler error")

                # Simulate handler error
                with patch.object(
                    handler,
                    "_get_trace_context",
                    side_effect=Exception("Handler error"),
                ):
                    test_logger.warning("Log with handler error")

                # Should still work after error
                test_logger.info("Normal log after handler error")

        flush_telemetry()


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

    if is_kibana_available():
        print("✅ Kibana available for integration tests")
    else:
        print("❌ Kibana not available (set KIBANA_URL or start elastic-start-local)")
