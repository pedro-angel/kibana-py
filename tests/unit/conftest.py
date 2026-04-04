"""Fixtures for unit tests, including OTel cleanup between tests."""

import pytest


@pytest.fixture(autouse=True)
def _reset_otel_state():
    """Reset OpenTelemetry global state after each test.

    Tests that call ``configure_opentelemetry(enabled=True)`` register a real
    ``TracerProvider`` (sometimes with an OTLP exporter targeting localhost:4317).
    Without cleanup the provider's atexit handler fires at process exit, tries to
    flush spans to a non-existent collector, and emits noisy errors.

    This fixture forcefully shuts down any SDK tracer provider created during the
    test and disables the ``KibanaInstrumentor`` singleton so no state leaks
    between tests.
    """
    yield

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        provider = trace.get_tracer_provider()
        if isinstance(provider, SDKTracerProvider):
            # Shut down processors/exporters so the atexit handler becomes a no-op
            try:
                provider.shutdown()
            except Exception:
                pass

        # Reset the global provider to a no-op so the next test starts clean
        trace._TRACER_PROVIDER = None  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001
    except ImportError:
        pass

    try:
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()
    except ImportError:
        pass
