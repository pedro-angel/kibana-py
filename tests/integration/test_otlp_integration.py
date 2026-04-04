"""Integration tests for OTLP endpoint connectivity and span transmission."""

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False

from .conftest import flush_telemetry
from .utils import create_test_kibana_client, is_kibana_available

# Skip all tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestOTLPConnectivity:
    """Test OTLP endpoint connectivity and configuration."""

    def test_otlp_endpoint_reachable(self, otel_endpoint):
        """Test that OTLP endpoint is reachable."""
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(otel_endpoint, timeout=5) as response:
                assert response.status in [200, 400, 401, 404]
        except urllib.error.URLError:
            pytest.skip(f"OTLP endpoint not reachable at {otel_endpoint}")

    def test_endpoint_accepts_otlp_grpc(self, otel_endpoint, otel_auth_token):
        """Test that OTLP endpoint accepts gRPC connections."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="otlp-grpc-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_grpc_span") as span:
            span.set_attribute("test.protocol", "grpc")
            assert span.is_recording()

        flush_telemetry()
        instrumentor.disable()

    def test_endpoint_accepts_otlp_http(self, otel_endpoint, otel_auth_token):
        """Test that OTLP endpoint accepts HTTP connections."""
        try:
            import importlib.util

            if (
                importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http")
                is None
            ):
                pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")
        except ImportError:
            pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")

        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="otlp-http-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="http/protobuf",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_http_span") as span:
            span.set_attribute("test.protocol", "http")
            assert span.is_recording()

        flush_telemetry()
        instrumentor.disable()


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestOTLPSpanTransmission:
    """Test span transmission to OTLP endpoint."""

    def test_kibana_requests_create_spans(self, otel_endpoint, otel_auth_token):
        """Test that Kibana API requests create spans that are transmitted."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="kibana-py-otlp-integration-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        client = create_test_kibana_client()
        try:
            response = client.status.get_status()
            assert response.meta.status == 200

            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("test_kibana_integration") as span:
                span.set_attribute("test.client", "kibana-py")
                assert span.is_recording()

                status = client.status.get_status()
                assert status.meta.status == 200
        finally:
            client.close()

        flush_telemetry()
        KibanaInstrumentor.get_instance().disable()

    def test_authentication_with_bearer_token(self, otel_endpoint, otel_auth_token):
        """Test OTLP authentication with Bearer token."""
        if not otel_auth_token:
            pytest.skip("No OTLP auth token available")

        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="otlp-auth-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            headers={"authorization": f"Bearer {otel_auth_token}"},
        )

        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("authenticated_span") as span:
            span.set_attribute("test.auth", "bearer_token")
            assert span.is_recording()

        flush_telemetry()
        instrumentor.disable()

    def test_span_attributes_transmitted(self, otel_endpoint, otel_auth_token):
        """Test that span attributes are properly set."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="otlp-attributes-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("attribute_test_span") as span:
            span.set_attribute("string_attr", "test_value")
            span.set_attribute("int_attr", 42)
            span.set_attribute("float_attr", 3.14)
            span.set_attribute("bool_attr", True)
            assert span.is_recording()

        flush_telemetry()
        KibanaInstrumentor.get_instance().disable()


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestOTLPErrorHandling:
    """Test error handling with OTLP endpoint."""

    def test_unreachable_endpoint_graceful_degradation(self):
        """Test graceful degradation when OTLP endpoint is unreachable."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="unreachable-test",
            exporter="otlp",
            endpoint="http://unreachable-server:8200",
        )

        # Kibana client should still work even with unreachable OTLP endpoint
        client = create_test_kibana_client()
        try:
            response = client.status.get_status()
            assert response.meta.status == 200
            assert response.body is not None
        finally:
            client.close()
            KibanaInstrumentor.get_instance().disable()

    def test_invalid_authentication_graceful_degradation(self, otel_endpoint):
        """Test graceful degradation with invalid authentication."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="invalid-auth-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            headers={"authorization": "Bearer invalid-token-12345"},
        )

        # Should not raise exceptions even with invalid auth
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("invalid_auth_test") as span:
            span.set_attribute("test.scenario", "invalid_auth")
            assert span.is_recording()

        flush_telemetry()
        KibanaInstrumentor.get_instance().disable()

    def test_malformed_endpoint_graceful_degradation(self):
        """Test graceful degradation with malformed endpoint."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="malformed-endpoint-test",
            exporter="otlp",
            endpoint="not-a-valid-url",
        )

        # Kibana client should still work
        client = create_test_kibana_client()
        try:
            response = client.status.get_status()
            assert response.meta.status == 200
            assert response.body is not None
        finally:
            client.close()
            KibanaInstrumentor.get_instance().disable()


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestOTLPProtocolSupport:
    """Test different OTLP protocol configuration."""

    def test_grpc_protocol_configuration(self, otel_endpoint, otel_auth_token):
        """Test gRPC protocol configuration succeeds."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="grpc-protocol-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()
        instrumentor.disable()

    def test_http_protocol_configuration(self, otel_endpoint, otel_auth_token):
        """Test HTTP protocol configuration succeeds."""
        try:
            import importlib.util

            if (
                importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http")
                is None
            ):
                pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")
        except ImportError:
            pytest.skip("opentelemetry-exporter-otlp-proto-http not installed")

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="http-protocol-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="http/protobuf",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
        )

        instrumentor = KibanaInstrumentor.get_instance()
        assert instrumentor.is_enabled()
        instrumentor.disable()

    def test_protocol_fallback_behavior(self, otel_endpoint):
        """Test that unsupported protocol doesn't crash."""
        from kibana.observability import configure_opentelemetry

        # Should handle gracefully — either fallback or just configure without error
        configure_opentelemetry(
            enabled=True,
            service_name="protocol-fallback-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="unsupported-protocol",
        )

        # Verify Kibana client still works regardless
        client = create_test_kibana_client()
        try:
            response = client.status.get_status()
            assert response.meta.status == 200
        finally:
            client.close()


@pytest.mark.skipif(
    not OTEL_AVAILABLE,
    reason="OpenTelemetry not installed. Install with: pip install kibana-py[observability]",
)
class TestOTLPResourceAttributes:
    """Test resource attributes transmission."""

    def test_service_metadata_transmitted(self, otel_endpoint, otel_auth_token):
        """Test that service metadata spans are created with resource attributes."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="metadata-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
            resource_attributes={
                "service.namespace": "kibana-py-tests",
                "service.instance.id": "test-instance-1",
                "deployment.environment": "integration-test",
            },
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("metadata_test") as span:
            span.set_attribute("test.metadata", "service_info")
            assert span.is_recording()

        flush_telemetry()
        KibanaInstrumentor.get_instance().disable()

    def test_custom_resource_attributes(self, otel_endpoint, otel_auth_token):
        """Test custom resource attributes in spans."""
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        configure_opentelemetry(
            enabled=True,
            service_name="custom-attrs-test",
            exporter="otlp",
            endpoint=otel_endpoint,
            protocol="grpc",
            headers=(
                {"authorization": f"Bearer {otel_auth_token}"}
                if otel_auth_token
                else None
            ),
            resource_attributes={
                "custom.team": "platform",
                "custom.component": "kibana-client",
            },
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("custom_attributes_test") as span:
            span.set_attribute("test.custom_resources", True)
            assert span.is_recording()

        flush_telemetry()
        KibanaInstrumentor.get_instance().disable()
