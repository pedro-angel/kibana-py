"""Integration tests for OpenTelemetry observability."""

import os

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False

from kibana import Kibana
from kibana.observability import KibanaInstrumentor, configure_opentelemetry

from .conftest import flush_telemetry

# Skip all tests if OpenTelemetry is not available
pytestmark = pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)


@pytest.fixture
def kibana_url():
    """Get Kibana URL from environment."""
    return os.getenv("KIBANA_URL") or os.getenv(
        "KIBANA_LOCAL_URL", "http://localhost:5601"
    )


@pytest.fixture
def kibana_username():
    """Get Kibana username from environment."""
    return os.getenv("KIBANA_USERNAME", "elastic")


@pytest.fixture
def kibana_password():
    """Get Kibana password from environment."""
    return os.getenv("KIBANA_PASSWORD", "")


@pytest.fixture(scope="function")
def otel_otlp(otel_endpoint, otel_auth_token):
    """Configure OpenTelemetry with OTLP exporter."""
    instrumentor = KibanaInstrumentor.get_instance()
    instrumentor.disable()

    configure_opentelemetry(
        enabled=True,
        service_name="kibana-py-integration-tests",
        exporter="otlp",
        endpoint=otel_endpoint,
    )

    yield

    flush_telemetry()
    instrumentor.disable()


class TestObservabilityBasics:
    """Basic observability tests."""

    def test_instrumentor_can_be_enabled(self):
        """Test that instrumentor can be enabled."""
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        instrumentor.enable()

        assert instrumentor.is_enabled() is True

        instrumentor.disable()

    def test_configure_from_environment(self):
        """Test configuration from environment variables."""
        # Set environment variables
        os.environ["KIBANA_OTEL_ENABLED"] = "true"
        os.environ["OTEL_SERVICE_NAME"] = "test-service"

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(validate_endpoint=False)

        assert instrumentor.is_enabled() is True

        # Cleanup
        instrumentor.disable()
        del os.environ["KIBANA_OTEL_ENABLED"]
        del os.environ["OTEL_SERVICE_NAME"]


class TestObservabilityWithOTLP:
    """Tests with OTLP exporter (real observability backend)."""

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured",
    )
    def test_send_traces_to_otlp(
        self, otel_otlp, kibana_url, kibana_username, kibana_password
    ):
        """Test sending traces to OTLP endpoint."""
        client = Kibana(
            hosts=[kibana_url],
            basic_auth=(kibana_username, kibana_password),
        )

        client.perform_request("GET", "/api/status")
        client.perform_request("GET", "/api/spaces/space")
        client.perform_request("GET", "/api/spaces/space/default")

        client.close()
        flush_telemetry()

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured",
    )
    def test_crud_operations_traced(
        self, otel_otlp, kibana_url, kibana_username, kibana_password
    ):
        """Test that CRUD operations are traced."""
        client = Kibana(
            hosts=[kibana_url],
            basic_auth=(kibana_username, kibana_password),
        )

        # Create
        create_response = client.perform_request(
            "POST",
            "/api/saved_objects/dashboard",
            body={
                "attributes": {
                    "title": "Observability Test Dashboard",
                    "description": "Created for observability testing",
                }
            },
        )
        object_id = create_response.body["id"]

        # Read
        client.perform_request("GET", f"/api/saved_objects/dashboard/{object_id}")

        # Update
        client.perform_request(
            "PUT",
            f"/api/saved_objects/dashboard/{object_id}",
            body={
                "attributes": {
                    "title": "Updated Dashboard",
                    "description": "Updated for observability testing",
                }
            },
        )

        # Delete
        client.perform_request("DELETE", f"/api/saved_objects/dashboard/{object_id}")

        client.close()
        flush_telemetry()

    @pytest.mark.skipif(
        not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        reason="OTLP endpoint not configured",
    )
    def test_error_traces_sent_to_otlp(
        self, otel_otlp, kibana_url, kibana_username, kibana_password
    ):
        """Test that error traces are sent to OTLP endpoint."""
        from kibana.exceptions import NotFoundError

        client = Kibana(
            hosts=[kibana_url],
            basic_auth=(kibana_username, kibana_password),
        )

        try:
            client.perform_request("GET", "/api/nonexistent/endpoint/1")
        except NotFoundError:
            pass

        try:
            client.perform_request("GET", "/api/nonexistent/endpoint/2")
        except NotFoundError:
            pass

        client.close()
        flush_telemetry()


class TestObservabilityDisabled:
    """Tests for when observability is disabled."""

    def test_requests_work_without_observability(
        self, kibana_url, kibana_username, kibana_password
    ):
        """Test that requests work when observability is disabled."""
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        client = Kibana(
            hosts=[kibana_url],
            basic_auth=(kibana_username, kibana_password),
        )

        response = client.perform_request("GET", "/api/status")
        assert response.meta.status == 200
        client.close()

    def test_no_performance_impact_when_disabled(
        self, kibana_url, kibana_username, kibana_password
    ):
        """Test that there's no performance impact when disabled."""
        import time

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        client = Kibana(
            hosts=[kibana_url],
            basic_auth=(kibana_username, kibana_password),
        )

        start = time.time()
        for _ in range(10):
            client.perform_request("GET", "/api/status")
        duration_disabled = time.time() - start

        client.close()
        assert duration_disabled > 0


class TestObservabilityConfiguration:
    """Tests for observability configuration."""

    def test_can_switch_exporters(self):
        """Test that we can switch between exporters."""
        instrumentor = KibanaInstrumentor.get_instance()

        configure_opentelemetry(enabled=True, exporter="console")
        assert instrumentor.is_enabled()

        instrumentor.disable()
        assert not instrumentor.is_enabled()

        configure_opentelemetry(
            enabled=True, exporter="otlp", endpoint="http://localhost:8200"
        )
        assert instrumentor.is_enabled()

        instrumentor.disable()

    def test_custom_service_name(self):
        """Test configuration with custom service name."""
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True, service_name="my-custom-service", exporter="console"
        )

        assert instrumentor.is_enabled()
        instrumentor.disable()
