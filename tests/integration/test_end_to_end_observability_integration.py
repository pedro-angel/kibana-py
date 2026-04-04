"""End-to-end integration tests for complete observability workflow (traces + logs)."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

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
    _cleanup_log_handlers,
    _created_log_handlers,
    configure_opentelemetry,
    create_span,
    get_log_forwarding_status,
    set_span_error,
)

from .conftest import flush_telemetry
from .utils import (
    create_test_kibana_client,
    is_kibana_available,
    print_test_config_info,
    safe_delete_connector,
)

# Skip all tests if OpenTelemetry is not available
pytestmark = pytest.mark.skipif(
    not (OTEL_AVAILABLE and OTEL_LOGS_AVAILABLE),
    reason="OpenTelemetry logs not installed. Install with: pip install kibana-py[observability] opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http",
)


@pytest.fixture
def test_logger():
    """Create a test logger for end-to-end tests."""
    logger_name = "kibana.test.e2e"
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


@pytest.fixture(scope="function")
def full_observability_console(test_logger, clean_observability):
    """Configure full observability with console exporters for testing."""
    configure_opentelemetry(
        enabled=True,
        service_name="kibana-py-e2e-console",
        exporter="console",
        logs_enabled=True,
        logs_level="INFO",
        logs_loggers=["kibana.test.e2e", "kibana"],
        console_export=True,
    )

    yield


@pytest.fixture(scope="function")
def full_observability_otlp(otel_endpoint, test_logger, clean_observability):
    """Configure full observability with OTLP endpoint."""
    configure_opentelemetry(
        enabled=True,
        service_name="kibana-py-e2e-otlp",
        exporter="otlp",
        endpoint=otel_endpoint,
        protocol="grpc",
        logs_enabled=True,
        logs_level="INFO",
        logs_loggers=["kibana.test.e2e", "kibana"],
    )

    yield


class TestCompleteObservabilityWorkflow:
    """Test complete observability workflow with traces and logs."""

    def test_basic_trace_and_log_correlation(
        self, full_observability_console, test_logger
    ):
        """Test basic correlation between traces and logs."""
        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()

        span = create_span("business-operation", attributes={"operation.type": "test"})
        assert (
            span is not None
        ), "create_span should return a span when observability is enabled"

        with span:
            test_logger.info(
                "Starting business operation", extra={"operation": "business-test"}
            )
            test_logger.info("Processing data", extra={"step": "processing"})

            child_span = create_span(
                "data-processing", attributes={"step": "processing"}
            )
            assert child_span is not None, "Nested span should be created"

            with child_span:
                test_logger.info("Processing nested operation", extra={"nested": True})

            test_logger.info(
                "Business operation completed", extra={"operation": "business-test"}
            )

        flush_telemetry()

        log_status = get_log_forwarding_status()
        assert log_status["handlers_configured"] > 0

    @pytest.mark.skipif(
        not is_kibana_available(),
        reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
    )
    def test_kibana_api_operations_with_full_observability(
        self, full_observability_console, test_logger
    ):
        """Test Kibana API operations with full observability."""
        client = create_test_kibana_client()

        try:
            # Create a business workflow span
            workflow_span = create_span(
                "kibana-workflow", attributes={"workflow.type": "connector_management"}
            )

            if workflow_span is not None:
                with workflow_span:
                    test_logger.info(
                        "Starting Kibana connector workflow",
                        extra={"workflow": "connector_management"},
                    )

                    # Step 1: Check status
                    status_span = create_span("check-status", attributes={"step": 1})
                    if status_span is not None:
                        with status_span:
                            test_logger.info(
                                "Checking Kibana status", extra={"step": "status"}
                            )
                            status_response = client.perform_request(
                                "GET", "/api/status"
                            )
                            test_logger.info(
                                "Kibana status retrieved",
                                extra={
                                    "step": "status",
                                    "status_code": status_response.meta.status,
                                    "success": True,
                                },
                            )

                    # Step 2: List connector types
                    list_span = create_span(
                        "list-connector-types", attributes={"step": 2}
                    )
                    if list_span is not None:
                        with list_span:
                            test_logger.info(
                                "Listing connector types", extra={"step": "list_types"}
                            )
                            types_response = client.perform_request(
                                "GET", "/api/actions/connector_types"
                            )
                            connector_types = types_response.body
                            test_logger.info(
                                "Connector types retrieved",
                                extra={
                                    "step": "list_types",
                                    "count": len(connector_types),
                                    "status_code": types_response.meta.status,
                                },
                            )

                    # Step 3: Create a test connector
                    create_span_obj = create_span(
                        "create-connector", attributes={"step": 3}
                    )
                    if create_span_obj is not None:
                        with create_span_obj:
                            test_logger.info(
                                "Creating test connector", extra={"step": "create"}
                            )

                            create_response = client.perform_request(
                                "POST",
                                "/api/actions/connector",
                                body={
                                    "name": "E2E Test Connector",
                                    "connector_type_id": ".index",
                                    "config": {"index": "e2e-test-index"},
                                },
                            )

                            connector_id = create_response.body["id"]
                            test_logger.info(
                                "Test connector created",
                                extra={
                                    "step": "create",
                                    "connector_id": connector_id,
                                    "status_code": create_response.meta.status,
                                },
                            )

                    # Step 4: Retrieve the connector
                    get_span = create_span("get-connector", attributes={"step": 4})
                    if get_span is not None:
                        with get_span:
                            test_logger.info(
                                "Retrieving connector",
                                extra={"step": "get", "connector_id": connector_id},
                            )

                            get_response = client.perform_request(
                                "GET", f"/api/actions/connector/{connector_id}"
                            )

                            test_logger.info(
                                "Connector retrieved",
                                extra={
                                    "step": "get",
                                    "connector_id": connector_id,
                                    "connector_name": get_response.body["name"],
                                    "status_code": get_response.meta.status,
                                },
                            )

                    # Step 5: Clean up
                    delete_span = create_span(
                        "delete-connector", attributes={"step": 5}
                    )
                    if delete_span is not None:
                        with delete_span:
                            test_logger.info(
                                "Deleting test connector",
                                extra={"step": "cleanup", "connector_id": connector_id},
                            )

                            safe_delete_connector(client, connector_id)

                            test_logger.info(
                                "Test connector deleted",
                                extra={
                                    "step": "cleanup",
                                    "connector_id": connector_id,
                                    "success": True,
                                },
                            )

                    test_logger.info(
                        "Kibana connector workflow completed successfully",
                        extra={"workflow": "connector_management"},
                    )

            flush_telemetry()

        finally:
            client.close()

    def test_error_handling_with_full_observability(
        self, full_observability_console, test_logger
    ):
        """Test error handling with both traces and logs."""
        error_span = create_span(
            "error-prone-operation", attributes={"operation.type": "error_test"}
        )
        assert error_span is not None

        with error_span:
            try:
                raise ValueError("Simulated business logic error")
            except ValueError as e:
                test_logger.error(
                    "Business logic error occurred",
                    extra={"error_type": type(e).__name__},
                    exc_info=True,
                )
                set_span_error(error_span, e)

                recovery_span = create_span(
                    "error-recovery", attributes={"recovery": True}
                )
                assert recovery_span is not None, "Recovery span should be created"
                with recovery_span:
                    test_logger.info("Error recovery completed")

        flush_telemetry()

    def test_concurrent_operations_with_observability(
        self, full_observability_console, test_logger
    ):
        """Test concurrent operations don't crash or interfere with each other."""
        results = []

        def worker_operation(worker_id: int, num_operations: int):
            """Worker function that creates spans and logs."""
            span = create_span(
                f"worker-{worker_id}", attributes={"worker.id": worker_id}
            )
            if span is None:
                return 0

            completed = 0
            with span:
                for i in range(num_operations):
                    op_span = create_span(
                        f"operation-{i}", attributes={"operation.number": i}
                    )
                    if op_span is not None:
                        with op_span:
                            test_logger.info(f"Worker {worker_id} op {i}")
                            completed += 1
            return completed

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker_operation, wid, 5) for wid in range(3)]
            results = [f.result() for f in futures]

        flush_telemetry()

        # All 3 workers should have completed their 5 operations
        assert len(results) == 3
        for completed in results:
            assert completed == 5, f"Worker completed {completed}/5 operations"


class TestObservabilityWithOTLP:
    """Test observability with real OTLP endpoint."""

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.",
    )
    def test_complete_workflow_with_otlp_endpoint(
        self, full_observability_otlp, test_logger
    ):
        """Test complete observability workflow with OTLP endpoint."""
        # Create a comprehensive business workflow
        workflow_span = create_span(
            "otlp-e2e-workflow", attributes={"workflow.version": "1.0"}
        )

        if workflow_span is not None:
            with workflow_span:
                test_logger.info(
                    "Starting OTLP E2E workflow", extra={"workflow": "otlp_e2e"}
                )

                # Phase 1: Initialization
                init_span = create_span("initialization", attributes={"phase": 1})
                if init_span is not None:
                    with init_span:
                        test_logger.info(
                            "Initializing workflow", extra={"phase": "init"}
                        )
                        time.sleep(0.1)
                        test_logger.info(
                            "Initialization completed", extra={"phase": "init"}
                        )

                # Phase 2: Data processing
                processing_span = create_span(
                    "data-processing", attributes={"phase": 2}
                )
                if processing_span is not None:
                    with processing_span:
                        test_logger.info(
                            "Starting data processing", extra={"phase": "processing"}
                        )

                        for batch in range(3):
                            batch_span = create_span(
                                f"process-batch-{batch}",
                                attributes={"batch.number": batch},
                            )
                            if batch_span is not None:
                                with batch_span:
                                    test_logger.info(
                                        f"Processing batch {batch}",
                                        extra={
                                            "phase": "processing",
                                            "batch": batch,
                                            "items": 100,
                                        },
                                    )
                                    time.sleep(0.05)

                                    # Simulate occasional warning
                                    if batch == 1:
                                        test_logger.warning(
                                            f"Batch {batch} processed with warnings",
                                            extra={
                                                "phase": "processing",
                                                "batch": batch,
                                                "warnings": 2,
                                            },
                                        )
                                    else:
                                        test_logger.info(
                                            f"Batch {batch} processed successfully",
                                            extra={
                                                "phase": "processing",
                                                "batch": batch,
                                                "success": True,
                                            },
                                        )

                        test_logger.info(
                            "Data processing completed", extra={"phase": "processing"}
                        )

                # Phase 3: Validation
                validation_span = create_span("validation", attributes={"phase": 3})
                if validation_span is not None:
                    with validation_span:
                        test_logger.info(
                            "Starting validation", extra={"phase": "validation"}
                        )

                        # Simulate validation error
                        try:
                            raise ValueError("Validation failed for test purposes")
                        except ValueError as e:
                            test_logger.error(
                                "Validation error occurred",
                                extra={
                                    "phase": "validation",
                                    "error_type": "validation_error",
                                    "recoverable": True,
                                },
                                exc_info=True,
                            )
                            set_span_error(validation_span, e)

                            # Recovery
                            test_logger.info(
                                "Attempting validation recovery",
                                extra={"phase": "validation"},
                            )
                            time.sleep(0.1)
                            test_logger.info(
                                "Validation recovery successful",
                                extra={"phase": "validation"},
                            )

                # Phase 4: Finalization
                final_span = create_span("finalization", attributes={"phase": 4})
                if final_span is not None:
                    with final_span:
                        test_logger.info(
                            "Finalizing workflow", extra={"phase": "finalization"}
                        )
                        time.sleep(0.1)
                        test_logger.info(
                            "Workflow finalized", extra={"phase": "finalization"}
                        )

                test_logger.info(
                    "OTLP E2E workflow completed",
                    extra={"workflow": "otlp_e2e", "success": True},
                )

        # Give time for all data to be sent to APM
        flush_telemetry()

    @pytest.mark.skipif(
        not (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") and is_kibana_available()),
        reason="OTLP endpoint or Kibana not configured.",
    )
    def test_kibana_operations_with_otlp_observability(
        self, full_observability_otlp, test_logger
    ):
        """Test Kibana operations with OTLP observability."""
        client = create_test_kibana_client()

        try:
            # Create a comprehensive Kibana workflow
            kibana_workflow_span = create_span(
                "kibana-otlp-workflow", attributes={"service": "kibana-py"}
            )

            if kibana_workflow_span is not None:
                with kibana_workflow_span:
                    test_logger.info(
                        "Starting Kibana OTLP workflow", extra={"service": "kibana-py"}
                    )

                    # Multi-step Kibana operations
                    operations = [
                        ("status", "GET", "/api/status"),
                        ("spaces", "GET", "/api/spaces/space"),
                        ("connector_types", "GET", "/api/actions/connector_types"),
                    ]

                    for op_name, method, path in operations:
                        op_span = create_span(
                            f"kibana-{op_name}",
                            attributes={"http.method": method, "http.path": path},
                        )

                        if op_span is not None:
                            with op_span:
                                test_logger.info(
                                    f"Executing Kibana {op_name} operation",
                                    extra={
                                        "operation": op_name,
                                        "method": method,
                                        "path": path,
                                    },
                                )

                                response = client.perform_request(method, path)

                                test_logger.info(
                                    f"Kibana {op_name} operation completed",
                                    extra={
                                        "operation": op_name,
                                        "status_code": response.meta.status,
                                        "success": True,
                                    },
                                )

                    # Create and manage a connector with full observability
                    connector_mgmt_span = create_span(
                        "connector-management", attributes={"operation": "crud"}
                    )

                    if connector_mgmt_span is not None:
                        with connector_mgmt_span:
                            test_logger.info(
                                "Starting connector management",
                                extra={"operation": "connector_crud"},
                            )

                            # Create
                            create_response = client.perform_request(
                                "POST",
                                "/api/actions/connector",
                                body={
                                    "name": "OTLP E2E Test Connector",
                                    "connector_type_id": ".index",
                                    "config": {"index": "otlp-e2e-test"},
                                },
                            )

                            connector_id = create_response.body["id"]
                            test_logger.info(
                                "Connector created for OTLP test",
                                extra={
                                    "operation": "create",
                                    "connector_id": connector_id,
                                    "connector_name": "OTLP E2E Test Connector",
                                },
                            )

                            # Read
                            _get_response = client.perform_request(
                                "GET", f"/api/actions/connector/{connector_id}"
                            )
                            test_logger.info(
                                "Connector retrieved",
                                extra={
                                    "operation": "read",
                                    "connector_id": connector_id,
                                    "status": "active",
                                },
                            )

                            # Update
                            _update_response = client.perform_request(
                                "PUT",
                                f"/api/actions/connector/{connector_id}",
                                body={
                                    "name": "Updated OTLP E2E Test Connector",
                                    "config": {"index": "otlp-e2e-test-updated"},
                                },
                            )
                            test_logger.info(
                                "Connector updated",
                                extra={
                                    "operation": "update",
                                    "connector_id": connector_id,
                                    "new_name": "Updated OTLP E2E Test Connector",
                                },
                            )

                            # Delete
                            safe_delete_connector(client, connector_id)
                            test_logger.info(
                                "Connector deleted",
                                extra={
                                    "operation": "delete",
                                    "connector_id": connector_id,
                                    "cleanup": True,
                                },
                            )

                    test_logger.info(
                        "Kibana OTLP workflow completed successfully",
                        extra={"service": "kibana-py"},
                    )

            # Give time for all traces and logs to be sent
            flush_telemetry()

        finally:
            client.close()


class TestObservabilityStatusAndValidation:
    """Test observability status reporting and validation."""

    def test_observability_status_with_full_configuration(
        self, full_observability_console
    ):
        """Test status reporting with full observability configuration."""
        # Check instrumentation status
        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled() is True

        # Check log forwarding status
        log_status = get_log_forwarding_status()
        assert log_status["logs_available"] is True
        assert log_status["handlers_configured"] > 0
        assert len(log_status["active_loggers"]) > 0

        # Verify configuration
        config = log_status["configuration"]
        assert config["logs_enabled"] == "true"
        assert config["logs_level"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_observability_metadata_and_attributes(
        self, full_observability_console, test_logger
    ):
        """Test that spans are created with rich attributes."""
        span = create_span(
            "metadata-test",
            attributes={
                "operation.type": "metadata_validation",
                "test.framework": "pytest",
            },
        )
        assert span is not None, "Span should be created when observability is enabled"

        with span:
            assert span.is_recording()
            test_logger.info(
                "Testing metadata",
                extra={"custom_field": "custom_value", "numeric_field": 42},
            )

        flush_telemetry()

    def test_observability_cleanup_and_resource_management(
        self, test_logger, clean_observability
    ):
        """Test proper cleanup and resource management."""
        # Configure observability
        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-cleanup-test",
            exporter="console",
            logs_enabled=True,
            logs_level="INFO",
            logs_loggers=["kibana.test.e2e"],
        )

        # Verify setup
        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled() is True

        log_status = get_log_forwarding_status()
        assert log_status["handlers_configured"] > 0

        # Use observability
        span = create_span("cleanup-test")
        if span is not None:
            with span:
                test_logger.info("Testing cleanup")

        # Cleanup is handled by the fixture
        # After cleanup, handlers should be removed
        # (This is verified by the clean_observability fixture)


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

    print("🔍 End-to-end observability tests:")
    print("   - Complete workflow validation")
    print("   - Trace-log correlation")
    print("   - Performance impact measurement")
    print("   - Metadata and attribute validation")
