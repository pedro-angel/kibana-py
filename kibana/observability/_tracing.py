"""KibanaInstrumentor singleton and span helpers."""

from typing import Any

from kibana.observability._imports import (
    OTEL_AVAILABLE,
    Span,
    Status,
    StatusCode,
    Tracer,
    logger,
    trace,
)


def _get_kibana_py_version() -> str:
    """Get the kibana-py version."""
    try:
        from kibana._version import __versionstr__

        return __versionstr__
    except ImportError:
        return "unknown"


def _get_python_version() -> str:
    """Get the Python version."""
    import sys

    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _get_opentelemetry_version() -> str:
    """Get the OpenTelemetry SDK version."""
    try:
        if OTEL_AVAILABLE:
            try:
                import importlib.metadata

                return importlib.metadata.version("opentelemetry-sdk")
            except Exception:
                try:
                    import importlib.metadata

                    return importlib.metadata.version("opentelemetry-api")
                except Exception:
                    try:
                        from opentelemetry import __version__  # type: ignore

                        return str(__version__)
                    except ImportError, AttributeError:
                        return "unknown"
        else:
            return "not-installed"
    except Exception:
        return "unknown"


def _get_opentelemetry_logs_version() -> str:
    """Get the OpenTelemetry logs exporter version."""
    from kibana.observability._imports import OTEL_LOGS_AVAILABLE

    try:
        if OTEL_LOGS_AVAILABLE:
            try:
                import importlib.metadata

                return importlib.metadata.version(
                    "opentelemetry-exporter-otlp-proto-grpc"
                )
            except Exception:
                try:
                    import importlib.metadata

                    return importlib.metadata.version(
                        "opentelemetry-exporter-otlp-proto-http"
                    )
                except Exception:
                    return "unknown"
        else:
            return "not-installed"
    except Exception:
        return "unknown"


class KibanaInstrumentor:
    """OpenTelemetry instrumentor for Kibana client.

    Provides automatic tracing for Kibana API requests.
    Uses the singleton pattern — access via ``get_instance()``.
    """

    _instance: KibanaInstrumentor | None = None

    def __init__(self) -> None:
        """Initialize the instrumentor."""
        self._enabled: bool = False
        self._tracer: Any | None = None

    @classmethod
    def get_instance(cls) -> KibanaInstrumentor:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def enable(
        self,
        *,
        tracer_provider: Any | None = None,
        service_name: str = "kibana-py",
    ) -> None:
        """Enable OpenTelemetry instrumentation."""
        import kibana.observability as _obs

        if not _obs.OTEL_AVAILABLE:
            logger.warning(
                "OpenTelemetry not available. "
                "Install with: pip install kibana-py[observability]"
            )
            return

        if self._enabled:
            logger.debug("Kibana instrumentation already enabled")
            return

        if tracer_provider is None:
            tracer_provider = trace.get_tracer_provider()

        try:
            self._tracer = tracer_provider.get_tracer(
                "kibana-py",
                instrumenting_library_version=self._get_version(),
            )
        except TypeError:
            self._tracer = tracer_provider.get_tracer("kibana-py")

        self._enabled = True
        logger.info("Kibana OpenTelemetry instrumentation enabled")

    def disable(self) -> None:
        """Disable OpenTelemetry instrumentation."""
        self._enabled = False
        self._tracer = None
        logger.info("Kibana OpenTelemetry instrumentation disabled")

    def is_enabled(self) -> bool:
        """Check if instrumentation is enabled."""
        import kibana.observability as _obs

        return self._enabled and _obs.OTEL_AVAILABLE

    def get_tracer(self) -> Tracer | None:
        """Get the tracer instance."""
        return self._tracer if self._enabled else None

    def _get_version(self) -> str:
        """Get the kibana-py version."""
        return _get_kibana_py_version()


def create_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Any | None:
    """Create a new span for tracing with enhanced error handling.

    :param name: Span name
    :param attributes: Span attributes
    :return: Span instance or None if instrumentation disabled or creation fails
    """
    import kibana.observability as _obs

    if not _obs.OTEL_AVAILABLE:
        return None

    try:
        instrumentor = KibanaInstrumentor.get_instance()
        tracer = instrumentor.get_tracer()

        if tracer is None:
            return None

        span = tracer.start_span(name)

        if attributes:
            for key, value in attributes.items():
                try:
                    span.set_attribute(key, value)
                except Exception as e:
                    logger.debug(f"Failed to set span attribute {key}: {e}")

        return span
    except Exception as e:
        logger.debug(f"Failed to create span '{name}': {e}")
        return None


def set_span_error(span: Span | None, error: Exception) -> None:
    """Mark a span as error with enhanced error handling."""
    import kibana.observability as _obs

    if not _obs.OTEL_AVAILABLE or span is None:
        return

    try:
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
    except Exception as e:
        logger.debug(f"Failed to set span error: {e}")


def safe_span_operation(
    span: Span | None, operation: str, func, *args, **kwargs
) -> Any:
    """Safely execute a span operation without interrupting main execution."""
    import kibana.observability as _obs

    if not _obs.OTEL_AVAILABLE or span is None:
        return None

    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.debug(f"Failed span operation '{operation}': {e}")
        return None


class span_context:  # noqa: N801
    """Context manager for OpenTelemetry span lifecycle.

    Manages span creation, attribute setting, error recording,
    and proper span ending in a single ``with`` block.

    Example::

        with span_context("kibana.get", attributes={...}) as span:
            response = transport.perform_request(...)
            if span is not None:
                span.set_attribute("http.response.status_code", 200)
            return response

    The span is automatically ended when exiting the block.
    If an exception occurs, the span is marked as an error before
    being ended and the exception is re-raised.

    If OpenTelemetry is not available or instrumentation is disabled,
    the context manager yields ``None`` and is essentially a no-op.
    """

    def __init__(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._attributes = attributes
        self._span: Any | None = None
        self._context_token: Any | None = None

    def __enter__(self) -> Any | None:
        self._span = create_span(self._name, attributes=self._attributes)
        if self._span is not None:
            # Set the span as current so trace context propagates to logs
            from opentelemetry import context as context_api
            from opentelemetry.trace import set_span_in_context

            self._context_token = context_api.attach(set_span_in_context(self._span))
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        if self._span is None:
            return
        try:
            if exc_val is not None:
                set_span_error(self._span, exc_val)
        finally:
            try:
                self._span.end()
            except Exception as e:
                logger.debug(f"Failed to end span: {e}")
            # Detach the span from current context
            if self._context_token is not None:
                try:
                    from opentelemetry import context as context_api

                    context_api.detach(self._context_token)
                except Exception:
                    pass
