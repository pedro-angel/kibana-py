"""Fixtures for unit tests, including OTel cleanup between tests."""

import logging

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
    # A real `_setup_log_forwarding` run calls setLevel() on every configured
    # logger and never restores it, so a single test that enables log
    # forwarding would pin the shared "kibana" logger at WARNING for the rest
    # of the session — silently changing what every later test's caplog sees.
    kibana_logger = logging.getLogger("kibana")
    original_level = kibana_logger.level

    yield

    kibana_logger.setLevel(original_level)

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

    try:
        # Drop kibana-py's reference to the provider it installed, so the next
        # test starts from "nothing installed" rather than holding a
        # shut-down provider alive. (configure_opentelemetry survives this
        # either way — it re-checks that its provider is still the OTel
        # global before reusing it — but the reference would keep a dead
        # provider and its exporters reachable for the rest of the session.)
        import kibana.observability._tracing as _tracing_mod

        _tracing_mod._installed_provider_state = None
    except ImportError:
        pass
