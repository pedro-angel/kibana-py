"""KibanaInstrumentor singleton, tracer-provider lifecycle, and span helpers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, NamedTuple

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
        """Install ``delegates`` and shut down the ones they replace.

        Two residuals are accepted here rather than papered over, because the
        alternatives are worse than the (bounded, rare) cost:

        * **A span may be dropped in the swap window.** ``on_end`` reads the
          delegate tuple once; a span that captured the *old* tuple can reach
          a delegate that this method has just shut down, and the SDK drops it
          with an INFO-level "Shutdown called, ignoring Span". Holding a lock
          across every ``on_end`` to close that window would put a mutex on
          the hot path of every span in the process to protect a reconfigure
          that happens a handful of times per run.
        * **Shutting down the superseded delegate is synchronous.** A
          ``BatchSpanProcessor`` whose endpoint is unreachable can spend up to
          the SDK's own join timeout (30s) in ``shutdown()``, and that time is
          spent inside the caller's ``configure_opentelemetry()`` call. Worse,
          it is spent holding ``_provider_lock`` when the swap comes from
          :func:`_install_span_processors`, so a concurrent configure blocks
          for the same stretch — and so does anything that shuts a provider
          down, since :func:`_forget_installed_processor` takes that same
          lock. Interpreter exit is exactly such a path: the SDK's atexit
          hook shuts providers down, so a process exiting during a stalled
          swap waits it out. Releasing off-thread would hide the stall, but
          also hide failures and reorder shutdowns; it is a recorded non-goal,
          not an oversight.
        """
        with self._lock:
            superseded, self._delegates = self._delegates, tuple(delegates)
        for delegate in superseded:
            try:
                delegate.shutdown()
            except Exception as e:
                logger.warning(f"Failed to shut down superseded span processor: {e}")

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
        # Clear the delegates under the lock before shutting them down: this
        # processor stays registered on the provider forever (the SDK has no
        # remove), so leaving shut-down delegates in place would keep feeding
        # every later span to them. A provider that has been shut down is also
        # no longer something to reconfigure, so stop advertising it.
        with self._lock:
            superseded, self._delegates = self._delegates, ()
        _forget_installed_processor(self)
        for delegate in superseded:
            try:
                delegate.shutdown()
            except Exception as e:
                logger.warning(f"Failed to shut down span processor: {e}")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        # One deadline shared across all delegates, each getting what is left
        # of it — the same contract as the SDK's own multi-processor. Passing
        # the full timeout to each would let N delegates take N times the
        # caller's budget, and short-circuiting on the first failure would
        # skip flushing the rest, losing spans a caller explicitly asked to
        # have flushed.
        # Monotonic, not wall clock: force_flush budgets an elapsed duration,
        # and time_ns() jumps with NTP steps and DST-free-but-still-adjustable
        # system clock changes — a backwards step would hand later delegates a
        # budget larger than the caller's, a forward step would cut them to
        # zero mid-flush.
        deadline_ns = time.monotonic_ns() + timeout_millis * 1_000_000
        flushed = True
        for delegate in self._delegates:
            remaining_ms = max(0, (deadline_ns - time.monotonic_ns()) // 1_000_000)
            if not delegate.force_flush(remaining_ms):
                flushed = False
        return flushed


# The provider kibana-py is currently tracing through, paired with the
# swappable processor it registered on it. Module-level because the OTel
# global it mirrors is module-level too, and read/written through *this*
# binding only — a split read-here/write-there binding is the bug this
# module's siblings were fixed for (#76); nothing re-exports this name.
#
# ONE name holding the pair, never two names updated in sequence: two stores
# can interleave between threads, and a mismatched (provider A, processor B)
# pair is silently fatal — every later reconfigure swaps exporters into a
# processor registered on nothing, while spans keep flowing through the old
# exporter. That is #76's own failure mode (configuration that logs success
# and changes nothing), re-entered through the back door.
_installed_provider_state: tuple[Any, _SwappableSpanProcessor] | None = None

# The provider kibana-py successfully put in the OTel process-global slot, if
# any. Deliberately NOT cleared when that provider is shut down: after a
# shutdown the tracked state above is gone, but the global slot stays occupied
# by that same dead provider (OTel fills it once per process), and the next
# configure needs to be able to say "the slot holds kibana-py's own
# shut-down provider" instead of blaming a component that does not exist.
_global_slot_provider: Any | None = None

# Held across the read-check-install-publish sequence so that decision and
# publication cannot interleave. Reentrant because a shutdown triggered
# underneath it re-enters via _forget_installed_processor.
_provider_lock = threading.RLock()


def _forget_installed_processor(processor: _SwappableSpanProcessor) -> None:
    """Stop tracking ``processor``'s provider once the processor is shut down."""
    global _installed_provider_state

    with _provider_lock:
        state = _installed_provider_state
        if state is not None and state[1] is processor:
            _installed_provider_state = None


def _global_slot_is_ours() -> bool:
    """Whether the OTel global provider is one kibana-py installed."""
    if _global_slot_provider is None or trace is None:
        return False
    return bool(trace.get_tracer_provider() is _global_slot_provider)


def _attach_span_processor(
    tracer_provider: Any, processor: _SwappableSpanProcessor
) -> None:
    """Register ``processor`` on ``tracer_provider``.

    A one-line indirection with a deliberately ``Any`` provider: identity
    comparisons against ``trace.get_tracer_provider()`` narrow a provider to
    the *API's* abstract ``TracerProvider``, which has no
    ``add_span_processor`` — an SDK-only method. The call is correct; only
    the narrowed static type is not.
    """
    tracer_provider.add_span_processor(processor)


def _processor_is_registered(tracer_provider: Any, processor: Any) -> bool:
    """Whether ``processor`` is actually registered on ``tracer_provider``.

    The tracked pair is only meaningful if the processor really sits on the
    provider; swapping exporters into a processor that does not is a silent
    no-op. The SDK exposes no public accessor, so this reads the same private
    structure the SDK itself iterates — and treats "cannot introspect" as
    "assume consistent", since refusing to reconfigure on an SDK whose
    internals were renamed would be a worse failure than trusting the pair.
    """
    active = getattr(tracer_provider, "_active_span_processor", None)
    registered = getattr(active, "_span_processors", None)
    if registered is None:
        return True
    return any(candidate is processor for candidate in registered)


class _InstallOutcome(NamedTuple):
    """What :func:`_install_span_processors` decided, under the lock.

    Every field is a *locked* observation. Callers must phrase their messages
    from these and never from a snapshot taken before the call: a check made
    outside ``_provider_lock`` describes a world another thread may already
    have changed, which is how a no-exporter call tore down a working
    configuration while both calls logged success (#76 round 3).
    """

    tracer_provider: Any | None
    is_global: bool
    applied: bool
    reconfigured: bool
    global_slot_is_ours: bool


def _install_span_processors(
    span_processors: list[Any], build_tracer_provider: Callable[[], Any]
) -> _InstallOutcome:
    """Make ``span_processors`` the live kibana-py span processors.

    ``build_tracer_provider`` is a factory, not a provider: constructing a
    ``TracerProvider`` registers an atexit flush, so one built by a caller
    that turns out not to need it (an empty configuration, or a thread that
    lost the install race) is not free. Only the branch that installs calls
    it, under the lock.

    **The empty case is decided here, not by the caller.** An empty
    ``span_processors`` never replaces live delegates: installing it would
    shut working exporters down and export nothing, which is the defect this
    whole change exists to prevent. Deciding it here is the difference
    between "no exporter *now*" and "no exporter when I last looked, several
    microseconds and one concurrent call ago".

    Returns an :class:`_InstallOutcome`. Note ``tracer_provider`` is the
    provider actually in use, which is not always a provider the caller ever
    saw: when another thread installed kibana-py's provider first, the
    installed one wins and callers must instrument through the returned one.

    Everything runs under ``_provider_lock``, including the swap that shuts
    superseded exporters down. That serializes concurrent
    ``configure_opentelemetry()`` calls — deliberately: a reconfiguration
    racing another reconfiguration is exactly how a mismatched
    provider/processor pair gets published, and the alternative (publish
    fast, release later) trades a bounded stall for silent misrouting.
    """
    global _installed_provider_state, _global_slot_provider

    with _provider_lock:
        state = _installed_provider_state
        reconfigured = state is not None

        if not span_processors:
            # Refused, both when there is a working configuration to protect
            # and when there is none: an exporter-less provider claiming the
            # process-global slot would lock out the next call that does have
            # exporters, since OTel installs that slot exactly once.
            return _InstallOutcome(
                tracer_provider=state[0] if state is not None else None,
                is_global=False,
                applied=False,
                reconfigured=reconfigured,
                global_slot_is_ours=_global_slot_is_ours(),
            )

        if state is not None:
            installed_provider, installed_processor = state
            if trace.get_tracer_provider() is installed_provider:
                if _processor_is_registered(installed_provider, installed_processor):
                    installed_processor.swap(span_processors)
                else:
                    # The tracked processor is not on the tracked provider —
                    # swapping into it would export nothing while spans keep
                    # flowing through whatever *is* registered. Repair in
                    # place: release the orphan and attach a fresh processor
                    # to the provider that is genuinely global.
                    logger.warning(
                        "Inconsistent OpenTelemetry state: kibana-py's tracked "
                        "span processor is not registered on its tracked tracer "
                        "provider (concurrent configuration, or a provider "
                        "mutated from outside). Re-attaching a processor to the "
                        "installed provider so this configuration takes effect."
                    )
                    installed_processor.swap(())
                    repaired = _SwappableSpanProcessor(span_processors)
                    _attach_span_processor(installed_provider, repaired)
                    _installed_provider_state = (installed_provider, repaired)
                return _InstallOutcome(
                    tracer_provider=installed_provider,
                    is_global=True,
                    applied=True,
                    reconfigured=True,
                    global_slot_is_ours=True,
                )

            # The tracked provider is no longer the global one, so it stops
            # being what kibana-py traces through. Release its exporters *and*
            # shut it down: leaving it alive keeps a batch processor thread,
            # its socket, and an atexit flush hook per reconfiguration.
            installed_processor.swap(())
            _discard_unused_provider(installed_provider)

        tracer_provider = build_tracer_provider()
        processor = _SwappableSpanProcessor(span_processors)
        _attach_span_processor(tracer_provider, processor)
        trace.set_tracer_provider(tracer_provider)
        is_global = bool(trace.get_tracer_provider() is tracer_provider)
        if is_global:
            # Remember what kibana-py put in the process-global slot, so that
            # a later refusal can say *whose* provider is in the way — after a
            # provider.shutdown() the tracked state is gone but the slot is
            # still occupied by our own dead provider, and blaming "another
            # component" for that would send the reader hunting a phantom.
            _global_slot_provider = tracer_provider
        _installed_provider_state = (tracer_provider, processor)
        return _InstallOutcome(
            tracer_provider=tracer_provider,
            is_global=is_global,
            applied=True,
            reconfigured=reconfigured,
            global_slot_is_ours=_global_slot_is_ours(),
        )


def _discard_unused_provider(tracer_provider: Any) -> None:
    """Shut down a provider that was built but never used.

    A ``TracerProvider`` registers an atexit flush on construction, so an
    abandoned one is not inert: it would try to flush at interpreter exit.
    """
    try:
        tracer_provider.shutdown()
    except Exception as e:
        logger.debug(f"Failed to shut down an unused tracer provider: {e}")


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
