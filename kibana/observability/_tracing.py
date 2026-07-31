"""KibanaInstrumentor singleton, tracer-provider lifecycle, and span helpers."""

from __future__ import annotations

import threading
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
                    except (ImportError, AttributeError):
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
    # Guards the check-then-set in get_instance(). Without it, threads that
    # raced past the ``is None`` check each built their own instance and every
    # loser's state -- including an ``enable()`` applied to it -- was silently
    # discarded when the winner's object was the one everyone else later read
    # back from ``cls._instance`` (#76).
    _instance_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the instrumentor."""
        self._enabled: bool = False
        self._tracer: Any | None = None
        self._tracer_provider: Any | None = None

    @classmethod
    def get_instance(cls) -> KibanaInstrumentor:
        """Get or create the singleton instance (thread-safe)."""
        # Double-checked locking: the fast path stays lock-free for the
        # overwhelmingly common already-created case, and only the creation
        # window is serialized.
        if cls._instance is None:
            with cls._instance_lock:
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

        # Already-enabled is only a no-op when the caller is asking for the
        # same provider we are already tracing through. A caller handing us a
        # *different* provider is asking for a rebind, and silently keeping
        # the old tracer is exactly the "configured successfully, changed
        # nothing" failure mode of #76.
        if self._enabled and (
            tracer_provider is None or tracer_provider is self._tracer_provider
        ):
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

        self._tracer_provider = tracer_provider
        self._enabled = True
        logger.info("Kibana OpenTelemetry instrumentation enabled")

    def disable(self) -> None:
        """Disable OpenTelemetry instrumentation."""
        self._enabled = False
        self._tracer = None
        self._tracer_provider = None
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


# ---------------------------------------------------------------------------
# Tracer-provider lifecycle
# ---------------------------------------------------------------------------


class _SwappableSpanProcessor:
    """A span processor whose delegates can be replaced in place.

    OpenTelemetry allows exactly one global ``TracerProvider`` per process —
    ``trace.set_tracer_provider()`` refuses every call after the first — and a
    ``TracerProvider`` can only ever have processors *added*, never removed.
    Together those two facts made ``configure_opentelemetry()`` a silent no-op
    on the second call: it built a whole new provider and exporter that
    nothing ever reached (#76).

    Registering one instance of this class on the provider gives kibana-py a
    stable slot on a provider it can no longer replace: reconfiguring swaps
    the delegate processors behind it (shutting the superseded ones down)
    instead of orphaning a provider. The provider therefore keeps exactly one
    kibana-py processor no matter how many times configuration is re-applied —
    no accumulation of dead processors and no per-span "Shutdown called,
    ignoring Span" noise from them.

    Deliberately not a subclass of the SDK's ``SpanProcessor``: that class is
    imported through this package's optional-dependency guards and is ``None``
    when the SDK is absent, which would make the class statement itself raise.
    The SDK calls processors structurally, so the duck-typed methods below are
    the whole contract.
    """

    def __init__(self, delegates: tuple[Any, ...] | list[Any] = ()) -> None:
        self._lock = threading.Lock()
        # A tuple, like the SDK's own multi-processor: readers iterate a
        # snapshot, so a swap can never be observed half-applied.
        self._delegates: tuple[Any, ...] = tuple(delegates)

    def swap(self, delegates: tuple[Any, ...] | list[Any]) -> None:
        """Install ``delegates`` and shut down the ones they replace."""
        with self._lock:
            superseded, self._delegates = self._delegates, tuple(delegates)
        for delegate in superseded:
            try:
                delegate.shutdown()
            except Exception as e:
                logger.debug(f"Failed to shut down superseded span processor: {e}")

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        for delegate in self._delegates:
            delegate.on_start(span, parent_context=parent_context)

    def _on_ending(self, span: Any) -> None:
        # Private SDK hook (``Span.end()`` calls it on the registered
        # processor). Forwarded defensively so this wrapper stays correct on
        # SDK versions both with and without it.
        for delegate in self._delegates:
            hook = getattr(delegate, "_on_ending", None)
            if hook is not None:
                hook(span)

    def on_end(self, span: Any) -> None:
        for delegate in self._delegates:
            delegate.on_end(span)

    def shutdown(self) -> None:
        for delegate in self._delegates:
            delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return all(delegate.force_flush(timeout_millis) for delegate in self._delegates)


# The provider kibana-py is currently tracing through, and the swappable
# processor it registered on it. Module-level because the OTel global they
# mirror is module-level too. Read and written through *this* binding only —
# the split read-here/write-there binding is the bug this module's siblings
# were just fixed for (#76); nothing re-exports these two names.
_installed_tracer_provider: Any | None = None
_installed_span_processor: _SwappableSpanProcessor | None = None


def _has_configured_tracer_provider() -> bool:
    """Whether kibana-py already configured a tracer provider in this process.

    Deliberately *not* the same question as
    :func:`_get_reconfigurable_tracer_provider`: a provider kibana-py had to
    keep private (because another component owns the OTel global) cannot be
    reconfigured in place, but it is still a previous configuration — the
    caller's next call is a reconfiguration and must be described as one.
    """
    return _installed_tracer_provider is not None


def _get_reconfigurable_tracer_provider() -> Any | None:
    """Return the provider kibana-py installed, if it is still the global one.

    ``None`` means there is nothing to reconfigure in place — either kibana-py
    never installed a provider, or something else replaced/reset the global
    since (tests do exactly that, and so does a component that installed its
    own provider first), in which case building a fresh one is the right move.
    """
    if _installed_tracer_provider is None or _installed_span_processor is None:
        return None
    if trace is None or trace.get_tracer_provider() is not _installed_tracer_provider:
        return None
    return _installed_tracer_provider


def _install_span_processors(tracer_provider: Any, span_processors: list[Any]) -> bool:
    """Make ``span_processors`` the live kibana-py span processors.

    Two paths, one contract — afterwards, kibana-py's spans reach exactly
    these processors and nothing this function installed earlier:

    * ``tracer_provider`` is the provider we already installed globally: the
      delegates behind our stable processor are swapped and the superseded
      ones shut down (this is what makes reconfiguration apply at all, given
      that OTel refuses to replace a global provider — #76);
    * otherwise: the previous configuration's exporters are released, our
      stable processor is attached to ``tracer_provider``, and it is offered
      to OTel as the global provider.

    Returns whether ``tracer_provider`` is now the *global* provider. ``False``
    means another component already owns the global one, so kibana-py traces
    through ``tracer_provider`` privately: its own spans are still created and
    exported (they carry the ambient context, so parent/child links across the
    two providers survive), but ``trace.get_tracer_provider()`` keeps
    returning the other component's provider. The caller must say so instead
    of implying kibana-py owns process-wide tracing.
    """
    global _installed_tracer_provider, _installed_span_processor

    reusable = _get_reconfigurable_tracer_provider()
    installed = _installed_span_processor
    if reusable is not None and tracer_provider is reusable and installed is not None:
        installed.swap(span_processors)
        return True

    # Whatever we tracked is about to stop being what kibana-py traces
    # through, so release its exporters here rather than leaving a batch
    # processor thread (and its socket) running for the rest of the process.
    if installed is not None:
        installed.swap(())

    processor = _SwappableSpanProcessor(span_processors)
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)
    _installed_tracer_provider = tracer_provider
    _installed_span_processor = processor
    return bool(trace.get_tracer_provider() is tracer_provider)


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
