"""Unit tests for OpenTelemetry observability."""

import logging
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestKibanaInstrumentor:
    """Tests for KibanaInstrumentor."""

    def test_get_instance_returns_singleton(self):
        """Test that get_instance returns the same instance."""
        from kibana.observability import KibanaInstrumentor

        instance1 = KibanaInstrumentor.get_instance()
        instance2 = KibanaInstrumentor.get_instance()

        assert instance1 is instance2

    def test_get_instance_is_thread_safe(self):
        """Concurrent ``get_instance()`` callers must all get the same object.

        Pre-fix ``get_instance()`` was an unsynchronized check-then-set: every
        thread that passed ``cls._instance is None`` before the winner's
        assignment built its own instance, so an ``enable()`` applied to a
        loser instance was silently lost (issue #76, problem 3).

        The race window is made deterministic rather than hoped-for: a slowed
        ``__init__`` holds every thread that got past the ``is None`` check
        inside the constructor at the same time, and a barrier makes them
        arrive together. Without a lock this fails every run, not one in a
        hundred.
        """
        import threading
        import time

        from kibana.observability import KibanaInstrumentor

        thread_count = 16
        barrier = threading.Barrier(thread_count)
        results: list[KibanaInstrumentor] = []
        results_lock = threading.Lock()
        original_instance = KibanaInstrumentor._instance
        original_init = KibanaInstrumentor.__init__

        def slow_init(self):
            time.sleep(0.05)
            original_init(self)

        def worker():
            barrier.wait(timeout=10)
            instance = KibanaInstrumentor.get_instance()
            with results_lock:
                results.append(instance)

        KibanaInstrumentor._instance = None
        KibanaInstrumentor.__init__ = slow_init
        try:
            threads = [threading.Thread(target=worker) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
        finally:
            KibanaInstrumentor.__init__ = original_init
            KibanaInstrumentor._instance = original_instance

        assert len(results) == thread_count
        assert (
            len({id(instance) for instance in results}) == 1
        ), "get_instance() handed out more than one instance under concurrency"

    def test_enable_sets_enabled_flag(self):
        """Test that enable() sets the enabled flag."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()  # Start disabled

        instrumentor.enable()

        assert instrumentor.is_enabled() is True

    def test_disable_clears_enabled_flag(self):
        """Test that disable() clears the enabled flag."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.enable()

        instrumentor.disable()

        assert instrumentor.is_enabled() is False

    def test_get_tracer_returns_none_when_disabled(self):
        """Test that get_tracer returns None when disabled."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        tracer = instrumentor.get_tracer()

        assert tracer is None

    def test_enable_with_custom_tracer_provider(self):
        """Test enabling with custom tracer provider."""
        from opentelemetry.sdk.trace import TracerProvider

        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        tracer_provider = TracerProvider()

        instrumentor.enable(tracer_provider=tracer_provider)

        assert instrumentor.is_enabled() is True
        assert instrumentor.get_tracer() is not None


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestConfigureOpenTelemetry:
    """Tests for configure_opentelemetry function."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_with_defaults(self, mock_validate):
        """Test configuration with default values."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        # Disable first
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        # Configure with enabled=True
        configure_opentelemetry(enabled=True)

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"KIBANA_OTEL_ENABLED": "true"}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_from_environment(self, mock_validate):
        """Test configuration from environment variables."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"KIBANA_OTEL_ENABLED": "false"}, clear=True)
    def test_configure_disabled_from_environment(self):
        """Test that disabled environment variable prevents configuration."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is False

    def test_configure_with_console_exporter(self):
        """Test configuration with console exporter."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True, exporter="console")

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"OTEL_SERVICE_NAME": "test-service"}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_with_custom_service_name(self, mock_validate):
        """Test configuration with custom service name."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True)

        assert instrumentor.is_enabled() is True


class _RecordingSpanExporter:
    """Minimal in-memory SpanExporter stand-in.

    A real exporter object (not a ``Mock``) so the SDK's ``BatchSpanProcessor``
    exercises its genuine export path -- these tests assert *which* exporter a
    span actually reached, which is the whole question in issue #76's
    problem 2.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.exported: list[str] = []
        self.shutdown_calls = 0

    def export(self, spans):  # noqa: ANN001
        from opentelemetry.sdk.trace.export import SpanExportResult

        self.exported.extend(span.name for span in spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.shutdown_calls += 1

    def force_flush(self, timeout_millis=30000):  # noqa: ANN001
        return True


class _RecordingLogExporter:
    """Minimal in-memory LogExporter stand-in (see _RecordingSpanExporter)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.exported: list[str] = []

    def export(self, batch):  # noqa: ANN001
        from opentelemetry.sdk._logs.export import LogExportResult

        self.exported.extend(str(item.log_record.body) for item in batch)
        return LogExportResult.SUCCESS

    def shutdown(self):
        return None

    def force_flush(self, timeout_millis=30000):  # noqa: ANN001
        return True


def _force_tracked_provider_state(tracing_mod, provider, processor):
    """Forge kibana-py's tracked (provider, processor) pair."""
    tracing_mod._installed_provider_state = (provider, processor)


def _read_tracked_provider_state(tracing_mod):
    """Read the tracked pair.

    Deliberately a plain attribute read with no fallback: a getattr default
    would let a future change that publishes nothing at all still satisfy
    every assertion built on this helper.
    """
    return tracing_mod._installed_provider_state


def _is_registered_on(tracer_provider, processor):
    """Whether ``processor`` really sits on ``tracer_provider``.

    Reads the SDK's own private structure rather than calling kibana-py's
    equivalent helper: the assertion this backs is about the SDK's actual
    state, so it must not be able to pass because the library's idea of
    "registered" agrees with the library.
    """
    active = getattr(tracer_provider, "_active_span_processor", None)
    registered = getattr(active, "_span_processors", ())
    return any(candidate is processor for candidate in registered)


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestConfigureOpenTelemetryIdempotency:
    """Repeat ``configure_opentelemetry()`` calls must be idempotent (issue #76).

    Three separate defects, one per test below: log handlers stacked on the
    "kibana" logger because the cleanup branch read a different binding than
    the one it wrote; a second configure built an exporter that was never
    reached because the global tracer provider refuses to be replaced, yet
    still logged success; and the instrumentor singleton was an unsynchronized
    check-then-set.
    """

    @pytest.fixture(autouse=True)
    def _cleanup_handlers(self):
        """Detach any handler this class's configure calls created.

        These tests deliberately attach real ``OTelLogHandler``s to the shared
        "kibana" logger; without cleanup they would leak into every later test
        in the session.
        """
        yield

        import kibana.observability._logging as _logging_mod

        handlers = _logging_mod._created_log_handlers
        if handlers:
            _logging_mod._cleanup_log_handlers(handlers)
            _logging_mod._created_log_handlers = []

    @staticmethod
    def _otel_handlers():
        from kibana.observability import OTelLogHandler

        return [
            handler
            for handler in logging.getLogger("kibana").handlers
            if isinstance(handler, OTelLogHandler)
        ]

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_log_exporter_with_error_handling")
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_repeat_configure_does_not_stack_log_handlers(
        self, mock_span_exporter, mock_log_exporter
    ):
        """Two configure calls must leave exactly one handler, first one closed.

        Pre-fix, ``_config.py`` read ``_created_log_handlers`` through the
        ``kibana.observability`` package attribute (a stale snapshot of the
        empty list captured at import time) but wrote the new handlers to
        ``kibana.observability._logging``'s module global, so the cleanup
        branch never saw anything to clean and every call stacked another
        handler on the "kibana" logger -- duplicated log export, handlers
        never closed.
        """
        from kibana.observability import configure_opentelemetry

        mock_span_exporter.side_effect = [
            _RecordingSpanExporter("first"),
            _RecordingSpanExporter("second"),
        ]
        mock_log_exporter.side_effect = [
            _RecordingLogExporter("first"),
            _RecordingLogExporter("second"),
        ]

        assert self._otel_handlers() == []

        def _configure():
            configure_opentelemetry(
                enabled=True,
                endpoint="http://localhost:8200",
                protocol="http/protobuf",
                validate_endpoint=False,
                logs_enabled=True,
                logs_loggers=["kibana"],
            )

        _configure()
        after_first = self._otel_handlers()
        assert len(after_first) == 1
        first_handler = after_first[0]

        _configure()
        after_second = self._otel_handlers()

        assert len(after_second) == 1, (
            "repeat configure stacked log handlers on the 'kibana' logger: "
            f"{after_second}"
        )
        assert after_second[0] is not first_handler
        assert first_handler not in logging.getLogger("kibana").handlers
        # close() flips _enabled to False -- the observable proof the previous
        # handler was closed, not merely dropped on the floor.
        assert first_handler._enabled is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_reconfigure_applies_new_endpoint_exporter(self, mock_span_exporter):
        """A second configure must actually route spans to the new exporter.

        Pre-fix, the second call built a fresh ``TracerProvider``, OTel
        refused the ``set_tracer_provider`` override, the instrumentor's
        ``enable()`` early-returned, and spans kept flowing to the *first*
        exporter -- while the log line still claimed "OpenTelemetry
        configured".
        """
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        first = _RecordingSpanExporter("first")
        second = _RecordingSpanExporter("second")
        mock_span_exporter.side_effect = [first, second]

        KibanaInstrumentor.get_instance().disable()

        configure_opentelemetry(
            enabled=True,
            endpoint="http://localhost:8200",
            protocol="http/protobuf",
            validate_endpoint=False,
        )
        provider_after_first = trace.get_tracer_provider()

        configure_opentelemetry(
            enabled=True,
            endpoint="http://localhost:8200?run=second",
            protocol="http/protobuf",
            validate_endpoint=False,
        )

        assert (
            trace.get_tracer_provider() is provider_after_first
        ), "reconfigure must reuse the installed provider, not orphan a new one"
        assert mock_span_exporter.call_args[0][0] == (
            "http://localhost:8200/v1/traces?run=second"
        )

        tracer = KibanaInstrumentor.get_instance().get_tracer()
        assert tracer is not None
        tracer.start_span("after-reconfigure").end()
        provider_after_first.force_flush()

        assert second.exported == [
            "after-reconfigure"
        ], "span did not reach the exporter built by the second configure"
        assert first.exported == []
        assert (
            first.shutdown_calls == 1
        ), "the superseded span processor/exporter must be shut down"

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_reconfigure_without_a_span_exporter_keeps_the_working_config(
        self, mock_span_exporter, caplog
    ):
        """A configuration that exports nothing must not be applied on top of
        one that works.

        `exporter="OTLP"` (miscased), `exporter="none"`, or a console exporter
        that fails to construct all produce an empty processor list. Applying
        that swapped the working exporter out for nothing and logged success —
        #76's own failure mode (a call that claims to have configured
        telemetry and silently stops it), re-entered from the other side.
        """
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        working = _RecordingSpanExporter("working")
        mock_span_exporter.return_value = working
        KibanaInstrumentor.get_instance().disable()

        configure_opentelemetry(
            enabled=True,
            exporter="otlp",
            endpoint="http://localhost:8200",
            protocol="http/protobuf",
            validate_endpoint=False,
        )
        provider = trace.get_tracer_provider()

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True,
                exporter="not-a-real-exporter",
                endpoint="http://localhost:8200",
                protocol="http/protobuf",
                validate_endpoint=False,
            )

        tracer = KibanaInstrumentor.get_instance().get_tracer()
        assert tracer is not None
        tracer.start_span("still-exporting").end()
        provider.force_flush()

        assert working.exported == ["still-exporting"], (
            "the working exporter must survive a configuration that creates "
            "no exporter of its own"
        )
        assert working.shutdown_calls == 0
        assert "none of it is being applied" in caplog.text
        assert (
            "configured for service" not in caplog.text
        ), "a call that changed nothing must not report success"

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_concurrent_no_exporter_configure_cannot_tear_down_a_working_one(
        self, mock_span_exporter, caplog
    ):
        """The no-exporter refusal must hold under concurrency, not just
        sequentially.

        Deciding "is there a working configuration to protect?" before taking
        the installer's lock describes a world another thread can change in
        the meantime: a call with no exporter that looked first and installed
        later still tore down a configuration published in between, and both
        calls logged success. The decision therefore belongs inside the lock,
        which is what this test pins.

        The interleaving is forced, not hoped for: the no-exporter call is
        parked at the install boundary — after every decision it makes — and
        only then does the working configuration land.
        """
        import threading

        from opentelemetry import trace

        import kibana.observability as _obs
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        working = _RecordingSpanExporter("working")
        mock_span_exporter.return_value = working
        KibanaInstrumentor.get_instance().disable()

        real_install = _obs._install_span_processors
        parked_at_install = threading.Event()
        working_installed = threading.Event()

        def gated_install(*args, **kwargs):
            if threading.current_thread().name == "no-exporter-configure":
                parked_at_install.set()
                working_installed.wait(timeout=10)
            return real_install(*args, **kwargs)

        def configure_without_exporter():
            configure_opentelemetry(
                enabled=True, exporter="bogus", validate_endpoint=False
            )

        with (
            caplog.at_level(logging.DEBUG, logger="kibana.observability"),
            patch(
                "kibana.observability._install_span_processors",
                side_effect=gated_install,
            ),
        ):
            no_exporter_thread = threading.Thread(
                target=configure_without_exporter, name="no-exporter-configure"
            )
            no_exporter_thread.start()
            assert parked_at_install.wait(
                timeout=10
            ), "the no-exporter call never reached the install boundary"

            configure_opentelemetry(
                enabled=True,
                exporter="otlp",
                endpoint="http://localhost:8200",
                protocol="http/protobuf",
                validate_endpoint=False,
            )
            working_installed.set()
            no_exporter_thread.join(timeout=30)

        assert not no_exporter_thread.is_alive()

        tracer = KibanaInstrumentor.get_instance().get_tracer()
        assert tracer is not None
        tracer.start_span("survived-the-race").end()
        trace.get_tracer_provider().force_flush()

        assert working.exported == [
            "survived-the-race"
        ], "a concurrent no-exporter call tore down the working exporter"
        assert working.shutdown_calls == 0
        assert caplog.text.count("for service:") == 1, (
            "exactly one call configured anything, so exactly one success "
            f"line is honest:\n{caplog.text}"
        )
        assert caplog.text.count("none of it is being applied") == 1

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_first_configure_without_a_span_exporter_warns(
        self, mock_span_exporter, caplog
    ):
        """With nothing configured yet there is nothing to protect, but the
        caller still has to be told that no spans will leave the process —
        and the process-global provider slot must be left alone."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        KibanaInstrumentor.get_instance().disable()

        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True, exporter="none", validate_endpoint=False
            )

        assert "nothing was configured" in caplog.text
        assert mock_span_exporter.call_count == 0
        # An exporter-less provider must not claim the process-global slot:
        # OTel fills it once, so squatting it would lock out the next call
        # that does have exporters.
        assert not isinstance(trace.get_tracer_provider(), SDKTracerProvider)

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_normalizes_exporter_case(self, mock_span_exporter):
        """``exporter="OTLP"`` must behave like ``"otlp"``.

        Every downstream check is case-sensitive, so an uppercase value used
        to match no branch and silently produce a configuration with no
        exporter at all.
        """
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        exporter = _RecordingSpanExporter("normalized")
        mock_span_exporter.return_value = exporter
        KibanaInstrumentor.get_instance().disable()

        configure_opentelemetry(
            enabled=True,
            exporter="OTLP",
            endpoint="http://localhost:8200",
            protocol="http/protobuf",
            validate_endpoint=False,
        )

        mock_span_exporter.assert_called_once()
        tracer = KibanaInstrumentor.get_instance().get_tracer()
        assert tracer is not None
        tracer.start_span("normalized-exporter").end()
        KibanaInstrumentor.get_instance()._tracer_provider.force_flush()
        assert exporter.exported == ["normalized-exporter"]

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._config.TracerProvider")
    @patch("kibana.observability._validate_apm_connectivity")
    def test_abandoned_configure_builds_no_tracer_provider(
        self, mock_validate, mock_provider_class
    ):
        """Give-up paths must not leave an abandoned provider behind.

        ``TracerProvider.__init__`` registers an atexit flush, so one built
        before the early returns outlives the call that abandoned it and
        fires at interpreter shutdown.
        """
        from kibana.observability import configure_opentelemetry

        mock_validate.return_value = False

        configure_opentelemetry(
            enabled=True, endpoint="http://localhost:8200", validate_endpoint=True
        )

        mock_provider_class.assert_not_called()

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_reconfigure_repairs_a_mismatched_tracked_pair(
        self, mock_span_exporter, caplog
    ):
        """A tracked processor that is not on the tracked provider must be
        repaired, not swapped into.

        This is the state a two-thread first-configure race produced while the
        provider and the processor were published as two separate assignments:
        the pair could interleave into (thread A's provider, thread B's
        processor). Every later reconfiguration then swapped exporters into a
        processor registered on nothing, while spans kept flowing out of the
        old exporter — configuration that logs success and changes nothing,
        which is the whole of #76.
        """
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        import kibana.observability._tracing as _tracing_mod
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        first = _RecordingSpanExporter("first")
        second = _RecordingSpanExporter("second")
        orphaned = _RecordingSpanExporter("orphaned")
        mock_span_exporter.side_effect = [first, second]
        KibanaInstrumentor.get_instance().disable()

        configure_opentelemetry(
            enabled=True,
            endpoint="http://localhost:8200",
            protocol="http/protobuf",
            validate_endpoint=False,
        )
        provider = trace.get_tracer_provider()

        # Forge the interleaved publication: the tracked provider is the one
        # that is genuinely global, but the tracked processor belongs to a
        # different provider entirely.
        orphan_provider = TracerProvider()
        orphan_processor = _tracing_mod._SwappableSpanProcessor(
            [BatchSpanProcessor(orphaned)]
        )
        orphan_provider.add_span_processor(orphan_processor)
        _force_tracked_provider_state(_tracing_mod, provider, orphan_processor)

        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True,
                endpoint="http://localhost:8200?run=second",
                protocol="http/protobuf",
                validate_endpoint=False,
            )

        tracer = KibanaInstrumentor.get_instance().get_tracer()
        assert tracer is not None
        tracer.start_span("after-repair").end()
        provider.force_flush()

        assert second.exported == ["after-repair"], (
            "the reconfigured exporter must actually receive spans, not be "
            "swapped into a processor registered on nothing"
        )
        assert orphaned.exported == []
        assert "Inconsistent OpenTelemetry state" in caplog.text
        orphan_provider.shutdown()

    def test_concurrent_first_configure_publishes_a_consistent_pair(self):
        """Racing first-configure calls must leave one coherent installation.

        The tracked processor has to be registered on the tracked provider,
        and the tracked provider has to be the OTel global — publishing those
        two facts as two separate assignments allowed them to interleave
        between threads.
        """
        import threading

        from opentelemetry import trace

        import kibana.observability._tracing as _tracing_mod
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        rounds, thread_count = 25, 4

        for round_index in range(rounds):
            # Each round is a fresh "nothing configured yet" process state.
            trace._TRACER_PROVIDER = None
            trace._TRACER_PROVIDER_SET_ONCE._done = False
            _tracing_mod._installed_provider_state = None
            _tracing_mod._global_slot_provider = None
            KibanaInstrumentor.get_instance().disable()

            barrier = threading.Barrier(thread_count)
            failures: list[BaseException] = []

            def worker():
                try:
                    barrier.wait(timeout=10)
                    configure_opentelemetry(
                        enabled=True, exporter="console", validate_endpoint=False
                    )
                except BaseException as exc:  # noqa: BLE001
                    failures.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

            assert not failures, f"round {round_index}: {failures!r}"

            provider, processor = _read_tracked_provider_state(_tracing_mod)
            assert provider is not None and processor is not None
            assert (
                trace.get_tracer_provider() is provider
            ), f"round {round_index}: tracked provider is not the global one"
            assert _is_registered_on(provider, processor), (
                f"round {round_index}: tracked processor is not registered on "
                "the tracked provider — a mismatched pair was published"
            )
            provider.shutdown()

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_reconfigure_warns_that_resource_attributes_stay_pinned(
        self, mock_span_exporter, caplog
    ):
        """A changed service name must warn instead of appearing to apply.

        An OpenTelemetry provider's ``Resource`` is fixed when the provider is
        constructed, and reconfiguration deliberately keeps the installed
        provider (that is what makes the new exporter take effect at all). So
        a second call with a different ``service_name`` changes the exporters
        but *cannot* change the service name on spans — the one thing about
        reconfiguration that genuinely does not apply, and therefore the one
        thing that must be said out loud rather than left for the caller to
        discover in the APM UI.
        """
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_span_exporter.side_effect = [
            _RecordingSpanExporter("first"),
            _RecordingSpanExporter("second"),
        ]
        KibanaInstrumentor.get_instance().disable()

        def _configure(service_name):
            configure_opentelemetry(
                enabled=True,
                service_name=service_name,
                endpoint="http://localhost:8200",
                protocol="http/protobuf",
                validate_endpoint=False,
            )

        _configure("first-service")
        provider = trace.get_tracer_provider()
        assert provider.resource.attributes["service.name"] == "first-service"

        with caplog.at_level(logging.WARNING, logger="kibana.observability"):
            _configure("second-service")

        assert "resource attributes" in caplog.text
        assert "for spans" in caplog.text, (
            "the warning must scope itself to spans: forwarded logs get a "
            "fresh logger provider per call and do pick up the new attributes"
        )
        assert trace.get_tracer_provider() is provider
        assert (
            provider.resource.attributes["service.name"] == "first-service"
        ), "spans must keep the first configuration's service name"

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_warns_but_still_exports_under_foreign_provider(
        self, mock_span_exporter, caplog
    ):
        """A global provider owned by someone else must be reported, not hidden.

        OTel allows exactly one global tracer provider per process. When
        another component got there first, kibana-py cannot own process-wide
        tracing -- and must say so -- but its *own* spans still have to be
        created and exported (through its own provider), including when the
        configuration is later changed.
        """
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        first = _RecordingSpanExporter("first")
        second = _RecordingSpanExporter("second")
        mock_span_exporter.side_effect = [first, second]

        foreign = TracerProvider()
        trace.set_tracer_provider(foreign)
        KibanaInstrumentor.get_instance().disable()

        def _configure(endpoint):
            configure_opentelemetry(
                enabled=True,
                endpoint=endpoint,
                protocol="http/protobuf",
                validate_endpoint=False,
            )

        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            _configure("http://localhost:8200")

        assert trace.get_tracer_provider() is foreign
        assert "already installed the global OpenTelemetry tracer" in caplog.text
        assert "OpenTelemetry configured for service" in caplog.text

        instrumentor = KibanaInstrumentor.get_instance()
        tracer = instrumentor.get_tracer()
        assert tracer is not None
        tracer.start_span("private-provider-span").end()
        instrumentor._tracer_provider.force_flush()
        assert first.exported == ["private-provider-span"], (
            "kibana-py must keep exporting its own spans when the global "
            "provider belongs to another component"
        )

        # ...and reconfiguration must apply there too, without leaking the
        # superseded exporter.
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            _configure("http://localhost:8200?run=second")
        tracer = KibanaInstrumentor.get_instance().get_tracer()
        tracer.start_span("after-reconfigure").end()
        KibanaInstrumentor.get_instance()._tracer_provider.force_flush()

        assert second.exported == ["after-reconfigure"]
        assert first.exported == ["private-provider-span"]
        assert first.shutdown_calls == 1
        # The wording must follow whether kibana-py had a previous
        # configuration, not whether it happens to own the global provider:
        # this second call is a reconfiguration by every meaning the caller
        # cares about, even though a fresh private provider was built for it.
        assert "OpenTelemetry reconfigured for service" in caplog.text
        assert "OpenTelemetry configured for service" not in caplog.text.replace(
            "OpenTelemetry reconfigured for service", ""
        )


class _FlushRecordingDelegate:
    """Span-processor stand-in that records the flush budget it was given."""

    def __init__(self, *, flush_result: bool = True, flush_delay: float = 0.0) -> None:
        self.flush_result = flush_result
        self.flush_delay = flush_delay
        self.flush_timeouts: list[int] = []
        self.shutdown_calls = 0
        self.ended: list[str] = []

    def on_start(self, span, parent_context=None):  # noqa: ANN001
        return None

    def on_end(self, span):  # noqa: ANN001
        self.ended.append(getattr(span, "name", "?"))

    def shutdown(self):
        self.shutdown_calls += 1

    def force_flush(self, timeout_millis=30000):  # noqa: ANN001
        import time

        self.flush_timeouts.append(timeout_millis)
        if self.flush_delay:
            time.sleep(self.flush_delay)
        return self.flush_result


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestSwappableSpanProcessor:
    """The stable processor kibana-py registers on the tracer provider."""

    def test_force_flush_shares_one_deadline_and_never_short_circuits(self):
        """Each delegate gets what is left of the caller's budget, and all of
        them get flushed.

        Handing the full timeout to every delegate lets N delegates take N
        times what the caller asked for, and stopping at the first failure
        skips flushing the rest — losing spans the caller explicitly asked to
        have flushed. This mirrors the SDK's own multi-processor contract.
        """
        import kibana.observability._tracing as _tracing_mod

        slow_failing = _FlushRecordingDelegate(flush_result=False, flush_delay=0.05)
        fast = _FlushRecordingDelegate(flush_result=True)
        processor = _tracing_mod._SwappableSpanProcessor([slow_failing, fast])

        assert (
            processor.force_flush(1000) is False
        ), "a delegate that failed to flush must be reported, not hidden"
        assert (
            fast.flush_timeouts
        ), "flushing must not short-circuit on the first failing delegate"
        # The first delegate gets (essentially) the whole budget; the second
        # gets what the first left. Compared as an inequality rather than an
        # exact 1000: the budget is a wall-clock deadline, so the first
        # delegate's share is 1000 minus however long the arithmetic itself
        # took, and pinning the exact value would make this test a clock race.
        assert 900 <= slow_failing.flush_timeouts[0] <= 1000
        assert fast.flush_timeouts[0] < slow_failing.flush_timeouts[0] - 40, (
            "the second delegate must get the remainder of the deadline "
            "(the first one slept 50ms of it), not a fresh full budget: "
            f"{slow_failing.flush_timeouts} then {fast.flush_timeouts}"
        )

    def test_shutdown_releases_delegates_and_stops_advertising_the_provider(self):
        """A shut-down processor must stop feeding spans to dead delegates and
        stop presenting its provider as reconfigurable.

        The SDK cannot remove a processor from a provider, so this processor
        stays registered forever — leaving shut-down delegates in place would
        keep handing them every later span.
        """
        import kibana.observability._tracing as _tracing_mod

        delegate = _FlushRecordingDelegate()
        processor = _tracing_mod._SwappableSpanProcessor([delegate])
        _force_tracked_provider_state(_tracing_mod, object(), processor)

        processor.shutdown()

        assert delegate.shutdown_calls == 1
        assert processor._delegates == ()
        processor.on_end(object())
        assert delegate.ended == []
        assert (
            _tracing_mod._installed_provider_state is None
        ), "a shut-down provider must not stay tracked as reconfigurable"

    @patch.dict("os.environ", {}, clear=True)
    def test_configure_after_provider_shutdown_reports_a_reconfiguration(self, caplog):
        """After a shutdown, the next call is still a *re*configuration.

        The tracked pair is gone, but the global provider slot is still held
        by the provider kibana-py put there — which is why the same call
        warns that the slot holds its own shut-down provider. Calling that
        first-time "configured" in the very next line contradicts the
        warning: two statements about one call, one of them false.
        """
        from opentelemetry import trace

        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        KibanaInstrumentor.get_instance().disable()
        configure_opentelemetry(
            enabled=True, exporter="console", validate_endpoint=False
        )
        trace.get_tracer_provider().shutdown()

        # The assertions below are about *this* call's log lines, and the
        # setup call above emitted its own "configured for service" line —
        # captured whenever the run's log level lets it through (a plain
        # `pytest --log-level=INFO` does).
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True, exporter="console", validate_endpoint=False
            )

        assert "since been shut down" in caplog.text
        assert "OpenTelemetry reconfigured for service" in caplog.text
        assert "OpenTelemetry configured for service" not in caplog.text.replace(
            "OpenTelemetry reconfigured for service", ""
        )

    def test_configure_then_provider_shutdown_clears_tracked_state(self):
        """The same, through the real path: shutting the provider down (what
        the SDK does at exit) unregisters kibana-py's tracked pair."""
        from opentelemetry import trace

        import kibana.observability._tracing as _tracing_mod
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        KibanaInstrumentor.get_instance().disable()
        configure_opentelemetry(
            enabled=True, exporter="console", validate_endpoint=False
        )
        assert _tracing_mod._installed_provider_state is not None

        trace.get_tracer_provider().shutdown()

        assert _tracing_mod._installed_provider_state is None


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestCreateSpan:
    """Tests for create_span function."""

    def test_create_span_returns_none_when_disabled(self):
        """Test that create_span returns None when instrumentation is disabled."""
        from kibana.observability import KibanaInstrumentor, create_span

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        span = create_span("test.span")

        assert span is None

    def test_create_span_with_attributes(self):
        """Test creating span with attributes."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span", attributes={"test.key": "test.value"})

        assert span is not None
        span.end()

    def test_create_span_returns_span_when_enabled(self):
        """Test that create_span returns a span when enabled."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span")

        assert span is not None
        span.end()


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestSetSpanError:
    """Tests for set_span_error function."""

    def test_set_span_error_with_none_span(self):
        """Test that set_span_error handles None span gracefully."""
        from kibana.observability import set_span_error

        # Should not raise
        set_span_error(None, Exception("test error"))

    def test_set_span_error_marks_span_as_error(self):
        """Test that set_span_error marks span as error."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            set_span_error,
        )

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span")
        error = Exception("test error")

        set_span_error(span, error)

        span.end()


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestAPMServerIntegration:
    """Tests for APM server integration features."""

    def test_parse_otlp_headers_from_env(self):
        """Test parsing OTLP headers from environment variables."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {"OTEL_EXPORTER_OTLP_HEADERS": "key1=value1,key2=value2"},
            clear=False,
        ):
            # Remove any .env-injected token so only our test headers are parsed
            import os

            old_token = os.environ.pop("ELASTIC_APM_SECRET_TOKEN", None)
            try:
                headers = _parse_otlp_headers()
                assert headers == {"key1": "value1", "key2": "value2"}
            finally:
                if old_token is not None:
                    os.environ["ELASTIC_APM_SECRET_TOKEN"] = old_token

    def test_parse_otlp_headers_with_apm_token(self):
        """Test parsing OTLP headers with APM token."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {"ELASTIC_APM_SECRET_TOKEN": "test-token-123"},
            clear=False,
        ):
            # Remove any .env-injected headers so only the token is used
            import os

            old_headers = os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)
            try:
                headers = _parse_otlp_headers()
                assert headers["authorization"] == "Bearer test-token-123"
            finally:
                if old_headers is not None:
                    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = old_headers

    def test_parse_otlp_headers_existing_auth_not_overridden(self):
        """Test that existing authorization header is not overridden."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer existing-token",
                "ELASTIC_APM_SECRET_TOKEN": "test-token-123",
            },
        ):
            headers = _parse_otlp_headers()
            assert headers["authorization"] == "Bearer existing-token"

    def test_create_otlp_exporter_grpc_protocol(self):
        """Test creating OTLP exporter with gRPC protocol."""
        from kibana.observability import _create_otlp_exporter

        exporter = _create_otlp_exporter(
            endpoint="http://localhost:4317",
            headers={"authorization": "Bearer test-token"},
            protocol="grpc",
        )
        assert exporter is not None

    @patch("kibana.observability._exporters.OTLPSpanExporter", None)
    @patch("kibana.observability._exporters.GRPC_EXPORTER_AVAILABLE", False)
    def test_create_otlp_exporter_grpc_protocol_raises_clear_error_when_absent(self):
        """When the gRPC OTLP exporter package isn't installed, creating a
        grpc-protocol exporter must raise a clear ImportError — mirroring the
        HTTP branch's existing behavior — instead of calling ``None(...)``
        and crashing with an opaque ``TypeError: 'NoneType' object is not
        callable`` that gets masked by the broad ``except Exception`` in
        ``_create_otlp_exporter_with_error_handling``."""
        from kibana.observability import _create_otlp_exporter

        with pytest.raises(ImportError, match="gRPC OTLP exporter not available"):
            _create_otlp_exporter(
                endpoint="http://localhost:4317",
                headers={"authorization": "Bearer test-token"},
                protocol="grpc",
            )

    def test_create_otlp_exporter_http_protocol(self):
        """Test creating OTLP exporter with HTTP protocol."""
        from kibana.observability import HTTP_EXPORTER_AVAILABLE, _create_otlp_exporter

        if HTTP_EXPORTER_AVAILABLE:
            exporter = _create_otlp_exporter(
                endpoint="http://localhost:4318",
                headers={"authorization": "Bearer test-token"},
                protocol="http/protobuf",
            )
            assert exporter is not None
        else:
            with pytest.raises(ImportError, match="HTTP OTLP exporter not available"):
                _create_otlp_exporter(
                    endpoint="http://localhost:4318",
                    headers={"authorization": "Bearer test-token"},
                    protocol="http/protobuf",
                )

    def test_create_otlp_exporter_invalid_protocol(self):
        """Test creating OTLP exporter with invalid protocol raises error."""
        from kibana.observability import _create_otlp_exporter

        with pytest.raises(ValueError, match="Unsupported OTLP protocol"):
            _create_otlp_exporter(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

    def test_get_trace_endpoint_with_existing_path(self):
        """Test _get_trace_endpoint with endpoint that already has traces path."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4318/v1/traces"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/traces"

    def test_get_trace_endpoint_http_protocol(self):
        """Test _get_trace_endpoint with HTTP protocol appends path."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4318"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/traces"

        endpoint_with_slash = "http://localhost:4318/"
        result = _get_trace_endpoint(endpoint_with_slash, "http/protobuf")
        assert result == "http://localhost:4318/v1/traces"

    def test_get_trace_endpoint_grpc_protocol(self):
        """Test _get_trace_endpoint with gRPC protocol uses same endpoint."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4317"
        result = _get_trace_endpoint(endpoint, "grpc")
        assert result == "http://localhost:4317"

    def test_get_trace_endpoint_http_alias_protocol(self):
        """Test _get_trace_endpoint with the 'http' protocol alias appends path."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4318"
        result = _get_trace_endpoint(endpoint, "http")
        assert result == "http://localhost:4318/v1/traces"

    def test_get_trace_endpoint_mid_path_collision_appended(self):
        """An endpoint that merely contains '/v1/traces' mid-path (not as its
        actual suffix) is not already-correct -- it must still get the real
        signal path appended, not be left untouched. Regression test for an
        unanchored substring check (``"/v1/traces" in base_endpoint``) that
        would wrongly treat this as already-correct."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://gw:8200/foo/v1/traces/bar"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://gw:8200/foo/v1/traces/bar/v1/traces"

    def test_get_trace_endpoint_suffix_with_extra_segment_appended(self):
        """A path that merely starts with the signal path but has more after
        it ('/v1/traces-ingest/...') is a different route, not the real
        OTLP signal path -- must still get it appended."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://host:8200/v1/traces-ingest/foo"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://host:8200/v1/traces-ingest/foo/v1/traces"

    def test_get_trace_endpoint_true_trailing_slash_untouched(self):
        """An endpoint that already ends in /v1/traces/ (trailing slash) is
        recognized as already-correct and left untouched."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4318/v1/traces/"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/traces/"

    def test_get_trace_endpoint_case_sensitive_not_treated_as_existing(self):
        """URL paths are case-sensitive: '/V1/Traces' is not the OTLP path
        '/v1/traces' and must still get the real path appended (pins the
        case-sensitive ruling -- no case-folding)."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://localhost:4318/V1/Traces"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/V1/Traces/v1/traces"

    def test_get_trace_endpoint_query_string_already_correct_untouched(self):
        """An already-correct endpoint with a query string must be left
        untouched -- the anchored check must compare against the URL's PATH
        component, not the raw string (which ends in the query, not the
        path)."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://h/v1/traces?foo=bar"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://h/v1/traces?foo=bar"

    def test_get_trace_endpoint_bare_host_with_query_preserves_query(self):
        """A bare host with only a query string (no path at all) must get
        /v1/traces appended to the PATH, with the query preserved in place
        -- not appended after the query string."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://h:8200?token=x"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://h:8200/v1/traces?token=x"

    def test_get_trace_endpoint_fragment_already_correct_untouched(self):
        """An already-correct endpoint with a fragment must be left
        untouched."""
        from kibana.observability import _get_trace_endpoint

        endpoint = "http://h/v1/traces#frag"
        result = _get_trace_endpoint(endpoint, "http/protobuf")
        assert result == "http://h/v1/traces#frag"

    @patch("socket.socket")
    def test_validate_apm_connectivity_success(self, mock_socket):
        """Test successful APM server connectivity validation."""
        from kibana.observability import _validate_apm_connectivity

        # Mock successful connection
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 0

        result = _validate_apm_connectivity(
            endpoint="http://localhost:8200", headers={}, protocol="grpc"
        )
        assert result is True

    @patch("socket.socket")
    def test_validate_apm_connectivity_failure(self, mock_socket):
        """Test failed APM server connectivity validation."""
        from kibana.observability import _validate_apm_connectivity

        # Mock failed connection
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 1

        result = _validate_apm_connectivity(
            endpoint="http://localhost:8200",
            headers={},
            protocol="grpc",
            max_retries=0,  # No retries for faster test
        )
        assert result is False

    @patch("socket.socket")
    def test_validate_amp_connectivity_with_retry(self, mock_socket):
        """Test APM connectivity validation with retry logic."""
        from kibana.observability import _validate_apm_connectivity

        # Mock first failure, then success
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.side_effect = [1, 0]  # Fail then succeed

        with patch("time.sleep"):  # Speed up test
            result = _validate_apm_connectivity(
                endpoint="http://localhost:8200",
                headers={},
                protocol="grpc",
                max_retries=1,
            )
        assert result is True

    @patch("socket.socket")
    def test_validate_apm_connectivity_http_protocol_uses_4318_port(self, mock_socket):
        """An http/protobuf endpoint with no explicit port must probe the
        OTLP/HTTP port 4318, not the gRPC port."""
        from kibana.observability import _validate_apm_connectivity

        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 0

        _validate_apm_connectivity(
            endpoint="http://localhost", headers={}, protocol="http/protobuf"
        )

        mock_sock_instance.connect_ex.assert_called_once_with(("localhost", 4318))

    @patch("socket.socket")
    def test_validate_apm_connectivity_unrecognized_protocol_uses_grpc_port_bias(
        self, mock_socket
    ):
        """When the endpoint has no explicit port and the protocol isn't a
        recognized HTTP variant, the port guess must default to the gRPC port
        -- aligned with _config.py's grpc-biased default-endpoint fallback,
        not hardcoded to the HTTP port regardless of protocol."""
        from kibana.observability import _validate_apm_connectivity

        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 0

        _validate_apm_connectivity(
            endpoint="http://localhost", headers={}, protocol="bogus"
        )

        mock_sock_instance.connect_ex.assert_called_once_with(("localhost", 4317))

    def test_validate_apm_server_availability_public_function(self):
        """Test public APM server availability validation function."""
        from kibana.observability import validate_apm_server_availability

        with patch("kibana.observability._validate_apm_connectivity") as mock_validate:
            mock_validate.return_value = True

            result = validate_apm_server_availability("http://localhost:8200")
            assert result is True
            mock_validate.assert_called_once()

    def test_handle_telemetry_error_authentication(self, caplog):
        """Test handling authentication-related telemetry errors."""
        from kibana.observability import _handle_telemetry_error

        error = Exception("401 Unauthorized: Invalid token")

        with caplog.at_level(
            "ERROR", logger="kibana.observability"
        ):  # Both error and remediation are at ERROR level
            _handle_telemetry_error("test operation", error)

        assert "APM authentication failed" in caplog.text
        assert "Check ELASTIC_APM_SECRET_TOKEN" in caplog.text

    def test_handle_telemetry_error_network(self, caplog):
        """Test handling network-related telemetry errors."""
        from kibana.observability import _handle_telemetry_error

        error = Exception("Connection timeout")

        with caplog.at_level(
            "WARNING", logger="kibana.observability"
        ):  # Both error and remediation are at WARNING level
            _handle_telemetry_error("test operation", error)

        assert "APM network error" in caplog.text
        assert "Check APM server availability" in caplog.text

    def test_mask_sensitive_info_bearer_token(self):
        """Test masking Bearer tokens in sensitive information."""
        from kibana.observability import _mask_sensitive_info

        text = "Authorization: Bearer abc123def456"
        masked = _mask_sensitive_info(text)
        assert "Bearer [REDACTED]" in masked
        assert "abc123def456" not in masked

    def test_mask_sensitive_info_api_key(self):
        """Test masking API keys in sensitive information."""
        from kibana.observability import _mask_sensitive_info

        text = 'token="secret123456"'
        masked = _mask_sensitive_info(text)
        assert "[REDACTED]" in masked
        assert "secret123456" not in masked

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_success(self, mock_create):
        """Test successful OTLP exporter creation with error handling."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_exporter = object()
        mock_create.return_value = mock_exporter

        result = _create_otlp_exporter_with_error_handling(
            endpoint="http://localhost:4317", headers={}, protocol="grpc"
        )
        assert result is mock_exporter

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_import_error(
        self, mock_create, caplog
    ):
        """Test OTLP exporter creation with ImportError."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_create.side_effect = ImportError("Missing dependency")

        with caplog.at_level("ERROR", logger="kibana.observability"):
            result = _create_otlp_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="grpc"
            )

        assert result is None
        assert "Missing OpenTelemetry exporter dependency" in caplog.text

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_value_error(
        self, mock_create, caplog
    ):
        """Test OTLP exporter creation with ValueError."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_create.side_effect = ValueError("Invalid configuration")

        with caplog.at_level("ERROR", logger="kibana.observability"):
            result = _create_otlp_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

        assert result is None
        assert "Invalid OTLP configuration" in caplog.text

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
            "ELASTIC_APM_SECRET_TOKEN": "test-token",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
        },
    )
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_with_apm_integration(
        self, mock_create_exporter, mock_validate
    ):
        """Test configure_opentelemetry with APM server integration."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_create_exporter.return_value = object()  # Mock exporter
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is True
        mock_validate.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        },
    )
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_opentelemetry_apm_connectivity_failure(
        self, mock_validate, caplog
    ):
        """Test configure_opentelemetry when APM connectivity fails."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = False
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry()

        assert instrumentor.is_enabled() is False
        assert "APM server connectivity validation failed" in caplog.text

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_http_protocol_appends_v1_traces(
        self, mock_create_exporter
    ):
        """http/protobuf traces must be posted to /v1/traces, not the bare root
        (issue #77) -- an explicit endpoint with no signal path gets one appended."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="http/protobuf",
            endpoint="http://localhost:8200",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200/v1/traces", {}, "http/protobuf"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_http_protocol_trailing_slash(
        self, mock_create_exporter
    ):
        """A trailing slash on the configured endpoint must not produce a
        double slash ahead of the appended signal path."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="http/protobuf",
            endpoint="http://localhost:8200/",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200/v1/traces", {}, "http/protobuf"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_http_protocol_endpoint_already_has_path(
        self, mock_create_exporter
    ):
        """An endpoint that already ends in /v1/traces must be passed through
        unchanged (no double-appending)."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="http/protobuf",
            endpoint="http://localhost:8200/v1/traces",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200/v1/traces", {}, "http/protobuf"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_grpc_protocol_endpoint_untouched(
        self, mock_create_exporter
    ):
        """gRPC endpoints must pass through untouched -- there is no
        HTTP-style /v1/traces resource path for the gRPC transport."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="grpc",
            endpoint="http://localhost:8200",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200", {}, "grpc"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_default_endpoint_http_protocol_uses_4318(
        self, mock_create_exporter
    ):
        """With no endpoint configured, http/protobuf must default to the
        OTLP/HTTP port 4318, not the gRPC port 4317 (issue #77)."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True, protocol="http/protobuf", validate_endpoint=False
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:4318/v1/traces", {}, "http/protobuf"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_default_endpoint_grpc_protocol_uses_4317(
        self, mock_create_exporter
    ):
        """With no endpoint configured, gRPC must keep defaulting to port 4317."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True, protocol="grpc", validate_endpoint=False)

        mock_create_exporter.assert_called_once_with(
            "http://localhost:4317", {}, "grpc"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_default_endpoint_http_protocol_logs_use_4318(
        self, mock_setup_logs, mock_validate
    ):
        """Log forwarding must share the same protocol-aware default endpoint
        as traces: http/protobuf defaults to port 4318, not the gRPC port 4317
        -- same defect class as the trace default, same helper family
        (issue #77)."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True, protocol="http/protobuf", logs_enabled=True
        )

        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["endpoint"] == "http://localhost:4318"

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_default_endpoint_grpc_protocol_logs_use_4317(
        self, mock_setup_logs, mock_validate
    ):
        """With no endpoint configured, gRPC log forwarding must keep
        defaulting to port 4317."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True, protocol="grpc", logs_enabled=True)

        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["endpoint"] == "http://localhost:4317"

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_http_alias_protocol_appends_v1_traces(
        self, mock_create_exporter
    ):
        """The 'http' protocol alias must get the same /v1/traces treatment
        as 'http/protobuf'."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="http",
            endpoint="http://localhost:8200",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200/v1/traces", {}, "http"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_protocol_case_normalized(
        self, mock_create_exporter
    ):
        """A mixed-case protocol string ('HTTP/PROTOBUF') must be normalized
        before it drives endpoint-shape decisions -- otherwise the
        ``protocol in ("http/protobuf", "http")`` checks silently mismatch
        and /v1/traces never gets appended, even though the exporter itself
        would still be created (the OTEL SDK doesn't care about our case)."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            protocol="HTTP/PROTOBUF",
            endpoint="http://localhost:8200",
            validate_endpoint=False,
        )

        mock_create_exporter.assert_called_once_with(
            "http://localhost:8200/v1/traces", {}, "http/protobuf"
        )

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_unsupported_protocol_warns_and_uses_grpc_default(
        self, mock_create_exporter, caplog
    ):
        """An unrecognized protocol value must not silently pick the gRPC
        default port with no diagnostic -- it must warn, and (per the aligned
        fallback bias) default the port the same way
        _validate_apm_connectivity does for an unrecognized protocol."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_create_exporter.return_value = object()
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True, protocol="BOGUS", validate_endpoint=False
            )

        assert "Unrecognized OTLP protocol 'bogus'" in caplog.text
        mock_create_exporter.assert_called_once_with(
            "http://localhost:4317", {}, "bogus"
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_configure_opentelemetry_unsupported_protocol_warning_accurate_for_console_exporter(
        self, caplog
    ):
        """The unrecognized-protocol warning must not unconditionally claim
        exporter creation will raise a clear error -- that's only true for
        exporter='otlp'; for exporter='console' nothing downstream ever
        constructs an OTLP exporter at all, so the wording must be gated on
        (or explicit about) the otlp path rather than an unconditional claim."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(enabled=True, exporter="console", protocol="BOGUS")

        assert "Unrecognized OTLP protocol 'bogus'" in caplog.text
        assert "for exporter='otlp'" in caplog.text


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestEnhancedSpanOperations:
    """Tests for enhanced span operations with error handling."""

    def test_create_span_with_error_handling(self):
        """Test create_span with enhanced error handling."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        # Should not raise even with invalid attributes
        span = create_span("test.span", attributes={"valid": "value"})
        assert span is not None
        span.end()

    def test_create_span_failure_returns_none(self):
        """Test that create_span returns None on failure."""
        from kibana.observability import KibanaInstrumentor, create_span

        # Disable instrumentation
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        span = create_span("test.span")
        assert span is None

    def test_set_span_error_with_enhanced_handling(self):
        """Test set_span_error with enhanced error handling."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            set_span_error,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        # Should not raise
        set_span_error(span, Exception("test error"))
        span.end()

    def test_safe_span_operation_success(self):
        """Test safe_span_operation with successful operation."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            safe_span_operation,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        def test_func(value):
            return value * 2

        result = safe_span_operation(span, "test operation", test_func, 5)
        assert result == 10
        span.end()

    def test_safe_span_operation_failure(self):
        """Test safe_span_operation with failing operation."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            safe_span_operation,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        def failing_func():
            raise Exception("Test failure")

        result = safe_span_operation(span, "failing operation", failing_func)
        assert result is None
        span.end()

    def test_safe_span_operation_with_none_span(self):
        """Test safe_span_operation with None span."""
        from kibana.observability import safe_span_operation

        def test_func():
            return "success"

        result = safe_span_operation(None, "test operation", test_func)
        assert result is None


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestOTelLogHandler:
    """Tests for OTelLogHandler."""

    def test_init_with_defaults(self):
        """Test OTelLogHandler initialization with default parameters."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        assert handler.level == 30  # logging.WARNING
        assert handler._enabled is True
        assert handler._error_count == 0
        assert handler._max_errors == 10

    def test_init_with_custom_level(self):
        """Test OTelLogHandler initialization with custom log level."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler(level=logging.ERROR)

        assert handler.level == logging.ERROR

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_init_with_logger_provider(self):
        """Test OTelLogHandler initialization with logger provider."""
        from unittest.mock import Mock

        from kibana.observability import OTelLogHandler, _get_kibana_py_version

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        assert handler._otel_logger is mock_logger
        mock_logger_provider.get_logger.assert_called_once_with(
            "kibana-py",
            version=_get_kibana_py_version(),
            schema_url=None,
        )

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_emit_when_logs_not_available(self):
        """Test emit method when OpenTelemetry logs not available."""
        import logging

        from kibana.observability import OTelLogHandler

        handler = OTelLogHandler()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Should not raise
        handler.emit(record)

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_emit_forwards_log_record(self):
        """Test emit method forwards log record to OpenTelemetry."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log") as mock_forward:
            handler.emit(record)
            mock_forward.assert_called_once_with(record)

    def test_emit_handles_forwarding_errors(self):
        """Test emit method handles forwarding errors gracefully."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log", side_effect=Exception("Test error")):
            with patch("sys.stderr"):  # Suppress stderr output during test
                handler.emit(record)

        assert handler._error_count == 1

    def test_emit_disables_handler_after_max_errors(self):
        """Test emit method disables handler after maximum errors."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)
        handler._max_errors = 2  # Lower threshold for testing

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log", side_effect=Exception("Test error")):
            with patch("sys.stderr"):  # Suppress stderr output during test
                # First two errors should increment count
                handler.emit(record)
                handler.emit(record)
                assert handler._error_count == 2
                assert handler._enabled is True

                # Third error should disable handler
                handler.emit(record)
                assert handler._error_count == 3
                assert handler._enabled is False

    def test_extract_attributes_basic(self):
        """Test _extract_attributes method with basic log record."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"
        record.process = 12345
        record.thread = 67890
        record.threadName = "MainThread"

        attributes = handler._extract_attributes(record)

        assert attributes["log.logger"] == "test.logger"
        assert attributes["log.level"] == "ERROR"
        assert attributes["log.file.name"] == "/path/to/test.py"
        assert attributes["log.file.line"] == 123
        assert attributes["log.function"] == "test_function"
        assert attributes["log.module"] == "test_module"
        assert attributes["process.pid"] == 12345
        assert attributes["thread.id"] == 67890
        assert attributes["thread.name"] == "MainThread"
        assert attributes["service.name"] == "kibana-py"
        assert attributes["service.language.name"] == "python"

    def test_extract_attributes_with_custom_extras(self):
        """Test _extract_attributes method with custom log record extras."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add custom attributes
        record.custom_string = "test_value"
        record.custom_int = 42
        record.custom_float = 3.14
        record.custom_bool = True
        record.custom_none = None
        record.custom_object = {"key": "value"}  # Should be converted to string

        attributes = handler._extract_attributes(record)

        assert attributes["custom.custom_string"] == "test_value"
        assert attributes["custom.custom_int"] == 42
        assert attributes["custom.custom_float"] == 3.14
        assert attributes["custom.custom_bool"] is True
        assert "custom.custom_none" not in attributes  # None values excluded
        assert attributes["custom.custom_object"] == "{'key': 'value'}"

    def test_map_log_level_to_severity(self):
        """Test _map_log_level_to_severity method."""
        import logging

        from opentelemetry._logs import SeverityNumber

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        assert (
            handler._map_log_level_to_severity(logging.CRITICAL) == SeverityNumber.FATAL
        )
        assert handler._map_log_level_to_severity(logging.ERROR) == SeverityNumber.ERROR
        assert (
            handler._map_log_level_to_severity(logging.WARNING) == SeverityNumber.WARN
        )
        assert handler._map_log_level_to_severity(logging.INFO) == SeverityNumber.INFO
        assert handler._map_log_level_to_severity(logging.DEBUG) == SeverityNumber.DEBUG
        assert handler._map_log_level_to_severity(5) == SeverityNumber.TRACE

    @patch("kibana.observability.OTEL_AVAILABLE", True)
    def test_get_trace_context_with_active_span(self):
        """Test _get_trace_context method with active span."""
        from unittest.mock import Mock, patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        # Mock active span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_span_context = Mock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x12345678901234567890123456789012
        mock_span_context.span_id = 0x1234567890123456
        mock_span_context.trace_flags = 1
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            context = handler._get_trace_context()

        assert context["trace_id"] == 0x12345678901234567890123456789012
        assert context["span_id"] == 0x1234567890123456
        assert context["trace_flags"] == 1
        assert context["trace_id_hex"] == "12345678901234567890123456789012"
        assert context["span_id_hex"] == "1234567890123456"

    @patch("kibana.observability.OTEL_AVAILABLE", True)
    def test_get_trace_context_no_active_span(self):
        """Test _get_trace_context method with no active span."""
        from unittest.mock import Mock, patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        # Mock no active span — span context is invalid
        mock_span_context = Mock()
        mock_span_context.is_valid = False
        mock_span = Mock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            context = handler._get_trace_context()

        assert context == {}

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_get_trace_context_otel_not_available(self):
        """Test _get_trace_context method when OpenTelemetry not available."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()
        context = handler._get_trace_context()

        assert context == {}

    def test_get_trace_context_handles_exceptions(self):
        """Test _get_trace_context method handles exceptions gracefully."""
        from unittest.mock import patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        with patch(
            "opentelemetry.trace.get_current_span", side_effect=Exception("Test error")
        ):
            context = handler._get_trace_context()

        assert context == {}

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_create_log_record(self):
        """Test _create_log_record method."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.created = 1234567890.123

        mock_resource = Mock()
        handler._resource = mock_resource

        with patch.object(
            handler, "_extract_attributes", return_value={"test": "attr"}
        ):
            with patch.object(
                handler, "_get_trace_context", return_value={"trace_id": 123}
            ):
                with patch("opentelemetry._logs.LogRecord") as mock_log_record:
                    handler._create_log_record(record)

                    mock_log_record.assert_called_once()
                    call_args = mock_log_record.call_args[1]

                    # Check timestamp is approximately correct (within 1ms due to floating point precision)
                    expected_timestamp = 1234567890123000000  # nanoseconds
                    actual_timestamp = call_args["timestamp"]
                    assert (
                        abs(actual_timestamp - expected_timestamp) < 1000000
                    )  # Within 1ms
                    assert call_args["severity_text"] == "ERROR"
                    from opentelemetry._logs import SeverityNumber

                    assert call_args["severity_number"] == SeverityNumber.ERROR
                    assert call_args["body"] == "Test message"
                    assert call_args["attributes"] == {"test": "attr"}
                    assert call_args["trace_id"] == 123

    def test_close_disables_handler(self):
        """Test close method disables the handler."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()
        assert handler._enabled is True

        handler.close()
        assert handler._enabled is False


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingConfiguration:
    """Tests for log forwarding configuration in configure_opentelemetry."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_with_log_forwarding_enabled(
        self, mock_setup_logs, mock_validate
    ):
        """Test configure_opentelemetry with log forwarding enabled."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            logs_enabled=True,
            logs_level="ERROR",
            logs_loggers=["kibana", "test"],
        )

        assert instrumentor.is_enabled() is True
        mock_setup_logs.assert_called_once()
        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["logs_enabled"] is True
        assert call_kwargs["logs_level"] == "ERROR"
        assert call_kwargs["logs_loggers"] == ["kibana", "test"]

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "WARNING",
            "KIBANA_OTEL_LOGS_LOGGERS": "kibana,myapp",
        },
        clear=True,
    )
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_log_forwarding_from_environment(
        self, mock_setup_logs, mock_validate
    ):
        """Test log forwarding configuration from environment variables."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True)

        mock_setup_logs.assert_called_once()
        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["logs_enabled"] is True
        assert call_kwargs["logs_level"] == "WARNING"
        assert call_kwargs["logs_loggers"] == ["kibana", "myapp"]

    @patch.dict("os.environ", {"KIBANA_OTEL_LOGS_LEVEL": "invalid"}, clear=True)
    def test_configure_invalid_log_level_uses_default(self, caplog):
        """Test that invalid log level falls back to default."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(enabled=True, logs_enabled=True)

        assert "Invalid log level 'INVALID', using 'WARNING'" in caplog.text

    def test_configure_invalid_logs_loggers_type_uses_default(self, caplog):
        """Test that invalid logs_loggers type falls back to default."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True,
                logs_enabled=True,
                logs_loggers="not_a_list",  # Should be a list
            )

        assert "logs_loggers must be a list" in caplog.text

    @patch("kibana.observability._cleanup_log_handlers")
    @patch("kibana.observability._setup_log_forwarding")
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_cleans_up_existing_handlers(
        self, mock_validate, mock_setup_logs, mock_cleanup
    ):
        """Test that configure_opentelemetry cleans up existing log handlers.

        The handler list is patched on ``kibana.observability._logging`` — the
        module that defines it, and the only binding ``configure_opentelemetry``
        reads or writes. Patching the (no longer re-exported)
        ``kibana.observability`` package attribute instead is what made this
        assertion pass while the real cleanup branch never fired (#76).
        """
        from unittest.mock import Mock

        import kibana.observability._logging as _logging_mod
        from kibana.observability import configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        original_handlers = _logging_mod._created_log_handlers
        existing = [Mock(), Mock()]
        _logging_mod._created_log_handlers = existing

        try:
            configure_opentelemetry(enabled=True, logs_enabled=True)
            mock_cleanup.assert_called_once_with(existing)
            mock_setup_logs.assert_called_once()
        finally:
            # Restore original state
            _logging_mod._created_log_handlers = original_handlers


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogExporterCreation:
    """Tests for log exporter creation functions."""

    def test_create_otlp_log_exporter_grpc(self):
        """Test creating OTLP log exporter with gRPC protocol."""
        from kibana.observability import (
            GRPC_LOG_EXPORTER_AVAILABLE,
            _create_otlp_log_exporter,
        )

        if not GRPC_LOG_EXPORTER_AVAILABLE:
            with pytest.raises(
                ImportError, match="gRPC OTLP log exporter not available"
            ):
                _create_otlp_log_exporter(
                    endpoint="http://localhost:4317",
                    headers={"authorization": "Bearer test-token"},
                    protocol="grpc",
                )
        else:
            exporter = _create_otlp_log_exporter(
                endpoint="http://localhost:4317",
                headers={"authorization": "Bearer test-token"},
                protocol="grpc",
            )
            assert exporter is not None

    def test_create_otlp_log_exporter_http(self):
        """Test creating OTLP log exporter with HTTP protocol."""
        from kibana.observability import (
            HTTP_LOG_EXPORTER_AVAILABLE,
            _create_otlp_log_exporter,
        )

        if not HTTP_LOG_EXPORTER_AVAILABLE:
            with pytest.raises(
                ImportError, match="HTTP OTLP log exporter not available"
            ):
                _create_otlp_log_exporter(
                    endpoint="http://localhost:4318",
                    headers={"authorization": "Bearer test-token"},
                    protocol="http/protobuf",
                )
        else:
            exporter = _create_otlp_log_exporter(
                endpoint="http://localhost:4318",
                headers={"authorization": "Bearer test-token"},
                protocol="http/protobuf",
            )
            assert exporter is not None

    def test_create_otlp_log_exporter_invalid_protocol(self):
        """Test creating OTLP log exporter with invalid protocol raises error."""
        from kibana.observability import _create_otlp_log_exporter

        with pytest.raises(ValueError, match="Unsupported OTLP protocol for logs"):
            _create_otlp_log_exporter(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

    def test_get_log_endpoint_with_existing_path(self):
        """Test _get_log_endpoint with endpoint that already has logs path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318/v1/logs"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

    def test_get_log_endpoint_http_protocol(self):
        """Test _get_log_endpoint with HTTP protocol appends path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

        endpoint_with_slash = "http://localhost:4318/"
        result = _get_log_endpoint(endpoint_with_slash, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

    def test_get_log_endpoint_grpc_protocol(self):
        """Test _get_log_endpoint with gRPC protocol uses same endpoint."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4317"
        result = _get_log_endpoint(endpoint, "grpc")
        assert result == "http://localhost:4317"

    def test_get_log_endpoint_http_alias_protocol(self):
        """Test _get_log_endpoint with the 'http' protocol alias appends path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318"
        result = _get_log_endpoint(endpoint, "http")
        assert result == "http://localhost:4318/v1/logs"

    def test_get_log_endpoint_mid_path_collision_appended(self):
        """Mirrors the trace-endpoint anchored-check regression: '/v1/logs'
        appearing mid-path must not be mistaken for the real signal path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://gw:8200/foo/v1/logs/bar"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://gw:8200/foo/v1/logs/bar/v1/logs"

    def test_get_log_endpoint_suffix_with_extra_segment_appended(self):
        """A '/v1/logs-ingest/...' route is not the real OTLP signal path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://host:8200/v1/logs-ingest/foo"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://host:8200/v1/logs-ingest/foo/v1/logs"

    def test_get_log_endpoint_true_trailing_slash_untouched(self):
        """An endpoint already ending in /v1/logs/ (trailing slash) is left
        untouched."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318/v1/logs/"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs/"

    def test_get_log_endpoint_case_sensitive_not_treated_as_existing(self):
        """'/V1/Logs' is not the OTLP path '/v1/logs' -- case-sensitive, no
        case-folding (pins the same ruling as the trace endpoint)."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318/V1/Logs"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/V1/Logs/v1/logs"

    def test_get_log_endpoint_query_string_already_correct_untouched(self):
        """Mirrors the trace-endpoint query-string regression: an
        already-correct endpoint with a query string must be left untouched."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://h/v1/logs?foo=bar"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://h/v1/logs?foo=bar"

    def test_get_log_endpoint_bare_host_with_query_preserves_query(self):
        """A bare host with only a query string must get /v1/logs appended
        to the PATH, with the query preserved in place."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://h:8200?token=x"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://h:8200/v1/logs?token=x"

    def test_get_log_endpoint_fragment_already_correct_untouched(self):
        """An already-correct endpoint with a fragment must be left
        untouched."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://h/v1/logs#frag"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://h/v1/logs#frag"

    @patch("kibana.observability._create_otlp_log_exporter")
    def test_create_otlp_log_exporter_with_error_handling_success(self, mock_create):
        """Test successful OTLP log exporter creation with error handling."""
        from kibana.observability import _create_otlp_log_exporter_with_error_handling

        mock_exporter = object()
        mock_create.return_value = mock_exporter

        result = _create_otlp_log_exporter_with_error_handling(
            endpoint="http://localhost:4317", headers={}, protocol="grpc"
        )
        assert result is mock_exporter

    @patch("kibana.observability._create_otlp_log_exporter")
    def test_create_otlp_log_exporter_with_error_handling_import_error(
        self, mock_create, caplog
    ):
        """Test OTLP log exporter creation with ImportError."""
        from kibana.observability import _create_otlp_log_exporter_with_error_handling

        mock_create.side_effect = ImportError("Missing log exporter dependency")

        with caplog.at_level(
            "ERROR", logger="kibana.observability"
        ):  # Both messages are now at ERROR level
            result = _create_otlp_log_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="grpc"
            )

        assert result is None
        assert "Missing OpenTelemetry log exporter dependency" in caplog.text
        assert "Install log exporters with:" in caplog.text


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingSetup:
    """Tests for log forwarding setup functions."""

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_setup_log_forwarding_logs_not_available(self, caplog):
        """Test log forwarding setup when logs not available."""
        from kibana.observability import _setup_log_forwarding

        with caplog.at_level("WARNING", logger="kibana.observability"):
            handlers = _setup_log_forwarding(
                logs_enabled=True,
                logs_level="WARNING",
                logs_loggers=["kibana"],
                exporter="otlp",
                endpoint="http://localhost:4317",
                headers={},
                protocol="grpc",
                resource=None,
            )

        assert handlers == []
        assert (
            "Log forwarding requested but OpenTelemetry logs not available"
            in caplog.text
        )

    def test_setup_log_forwarding_disabled(self):
        """Test log forwarding setup when disabled."""
        from kibana.observability import _setup_log_forwarding

        handlers = _setup_log_forwarding(
            logs_enabled=False,
            logs_level="WARNING",
            logs_loggers=["kibana"],
            exporter="otlp",
            endpoint="http://localhost:4317",
            headers={},
            protocol="grpc",
            resource=None,
        )

        assert handlers == []

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    @patch("kibana.observability.LoggerProvider")
    @patch("kibana.observability.set_logger_provider")
    @patch("kibana.observability._create_otlp_log_exporter_with_error_handling")
    @patch("kibana.observability.BatchLogRecordProcessor")
    @patch("kibana.observability.OTelLogHandler")
    @patch("logging.getLogger")
    def test_setup_log_forwarding_success(
        self,
        mock_get_logger,
        mock_handler_class,
        mock_processor_class,
        mock_create_exporter,
        mock_set_provider,
        mock_provider_class,
    ):
        """Test successful log forwarding setup."""
        from unittest.mock import Mock

        from kibana.observability import _setup_log_forwarding

        # Mock objects
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_exporter = Mock()
        mock_create_exporter.return_value = mock_exporter
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        mock_logger = Mock()
        mock_logger.level = logging.NOTSET
        mock_get_logger.return_value = mock_logger

        handlers = _setup_log_forwarding(
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana", "test"],
            exporter="otlp",
            endpoint="http://localhost:4317",
            headers={"auth": "token"},
            protocol="grpc",
            resource=Mock(),
        )

        # Verify setup calls
        mock_provider_class.assert_called_once()
        mock_create_exporter.assert_called_once_with(
            "http://localhost:4317", {"auth": "token"}, "grpc"
        )
        mock_processor_class.assert_called_once_with(mock_exporter)
        mock_provider.add_log_record_processor.assert_called_once_with(mock_processor)
        mock_set_provider.assert_called_once_with(mock_provider)

        # Verify handler creation for each logger
        assert mock_handler_class.call_count == 2
        assert mock_get_logger.call_count == 2
        mock_get_logger.assert_any_call("kibana")
        mock_get_logger.assert_any_call("test")
        assert mock_logger.addHandler.call_count == 2
        assert len(handlers) == 2

        # Verify OTelLogHandler was called with correct arguments
        handler_call_kwargs = mock_handler_class.call_args_list[0].kwargs
        assert handler_call_kwargs["level"] == logging.WARNING
        assert handler_call_kwargs["logger_provider"] is mock_provider

    def test_cleanup_log_handlers(self):
        """Test cleanup of log handlers."""
        from unittest.mock import Mock

        from kibana.observability import _cleanup_log_handlers

        # Create mock handlers and loggers
        handler1 = Mock()
        handler2 = Mock()
        mock_logger = Mock()
        mock_logger.handlers = [handler1, handler2]

        with patch("logging.Logger.manager") as mock_manager:
            mock_manager.loggerDict = {"test.logger": None}
            with patch("logging.getLogger", return_value=mock_logger):
                _cleanup_log_handlers([handler1, handler2])

        # Verify handlers were removed and closed
        assert mock_logger.removeHandler.call_count == 2
        handler1.close.assert_called_once()
        handler2.close.assert_called_once()

    def test_cleanup_survives_a_logger_created_during_the_sweep(self, caplog):
        """Cleanup must not abort when the global logger registry grows.

        ``logging.Logger.manager.loggerDict`` is process-global: any thread
        calling ``logging.getLogger("some.new.name")`` mutates it. Iterating
        it live raised "dictionary changed size during iteration" and left
        the handler attached to every logger not yet visited — the stacking
        this cleanup exists to prevent, reported at debug level where nobody
        would see it.
        """
        from kibana.observability import _cleanup_log_handlers

        target = logging.getLogger("kibana_py_test_cleanup_target")
        handler = logging.Handler()
        target.addHandler(handler)
        real_get_logger = logging.getLogger
        newcomers = []

        def get_logger_and_register_a_newcomer(name=None):
            if not newcomers:
                newcomers.append(name)
                real_get_logger("kibana_py_test_cleanup_newcomer")
            return real_get_logger(name) if name else real_get_logger()

        try:
            with (
                caplog.at_level(logging.WARNING, logger="kibana.observability"),
                patch(
                    "logging.getLogger",
                    side_effect=get_logger_and_register_a_newcomer,
                ),
            ):
                _cleanup_log_handlers([handler])

            assert handler not in target.handlers, (
                "the sweep stopped early and left the handler attached: "
                f"{caplog.text}"
            )
            assert (
                caplog.text == ""
            ), "a clean sweep must not report an error at any level"
        finally:
            target.removeHandler(handler)


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingStatus:
    """Tests for log forwarding status and diagnostics functions."""

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "ERROR",
            "KIBANA_OTEL_LOGS_LOGGERS": "kibana,test",
        },
    )
    def test_get_log_forwarding_status(self):
        """Test get_log_forwarding_status function."""
        from kibana.observability import get_log_forwarding_status

        status = get_log_forwarding_status()

        assert "logs_available" in status
        assert "grpc_exporter_available" in status
        assert "http_exporter_available" in status
        assert "handlers_configured" in status
        assert "active_loggers" in status
        assert "configuration" in status

        config = status["configuration"]
        assert config["logs_enabled"] == "true"
        assert config["logs_level"] == "ERROR"
        assert config["logs_loggers"] == "kibana,test"

    def test_validate_log_forwarding_configuration_valid(self):
        """Test validate_log_forwarding_configuration with valid config."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana", "test"],
            endpoint="http://localhost:4317",
            protocol="grpc",
        )

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_validate_log_forwarding_configuration_logs_not_available(self):
        """Test validation when logs not available."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(logs_enabled=True)

        assert result["valid"] is False
        assert any(
            "OpenTelemetry logs not available" in error for error in result["errors"]
        )

    def test_validate_log_forwarding_configuration_invalid_level(self):
        """Test validation with invalid log level."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_level="INVALID"
        )

        assert result["valid"] is False
        assert any("Invalid log level" in error for error in result["errors"])

    def test_validate_log_forwarding_configuration_invalid_loggers(self):
        """Test validation with invalid loggers."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_loggers="not_a_list"
        )

        assert result["valid"] is False
        assert any("logs_loggers must be a list" in error for error in result["errors"])

    def test_validate_log_forwarding_configuration_empty_loggers(self):
        """Test validation with empty loggers list."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_loggers=[]
        )

        assert result["valid"] is True  # Valid but with warning
        assert any(
            "Empty logs_loggers list" in warning for warning in result["warnings"]
        )

    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._get_log_endpoint")
    def test_validate_log_forwarding_connectivity_success(
        self, mock_get_endpoint, mock_validate
    ):
        """Test successful log forwarding connectivity test."""
        from kibana.observability import validate_log_forwarding_connectivity

        mock_get_endpoint.return_value = "http://localhost:4317/v1/logs"
        mock_validate.return_value = True

        result = validate_log_forwarding_connectivity(
            endpoint="http://localhost:4317", headers={"auth": "token"}, protocol="grpc"
        )

        assert result["success"] is True
        assert result["endpoint"] == "http://localhost:4317"
        assert result["log_endpoint"] == "http://localhost:4317/v1/logs"
        assert result["protocol"] == "grpc"
        assert result["error"] is None
        assert result["response_time"] is not None

    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._get_log_endpoint")
    def test_validate_log_forwarding_connectivity_failure(
        self, mock_get_endpoint, mock_validate
    ):
        """Test failed log forwarding connectivity test."""
        from kibana.observability import validate_log_forwarding_connectivity

        mock_get_endpoint.return_value = "http://localhost:4317/v1/logs"
        mock_validate.return_value = False

        result = validate_log_forwarding_connectivity(
            endpoint="http://localhost:4317", protocol="grpc"
        )

        assert result["success"] is False
        assert "Could not connect to log endpoint" in result["error"]


class TestObservabilityWithoutOpenTelemetry:
    """Tests for observability when OpenTelemetry is not installed."""

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_configure_without_otel_logs_warning(self, caplog):
        """Test that configure logs warning when OpenTelemetry not available."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(enabled=True)

        assert "OpenTelemetry not available" in caplog.text

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_create_span_without_otel_returns_none(self):
        """Test that create_span returns None when OpenTelemetry not available."""
        from kibana.observability import create_span

        span = create_span("test.span")

        assert span is None

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_set_span_error_without_otel_does_nothing(self):
        """Test that set_span_error does nothing when OpenTelemetry not available."""
        from kibana.observability import set_span_error

        # Should not raise
        set_span_error(None, Exception("test"))


def _run_with_blocked_imports(
    blocked_prefixes: tuple[str, ...],
    probe: str,
    error: str = "ImportError",
    interpreter_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Run ``probe`` in a fresh subprocess where importing any module whose
    dotted name equals (or is nested under) one of ``blocked_prefixes`` raises
    ``error``, simulating that distribution being uninstalled (``ImportError``)
    or corrupted/version-mismatched (``AttributeError`` — what a module body
    raises when it reaches for a symbol its own dependency no longer exports).

    A real subprocess is required rather than monkeypatching ``sys.modules``
    in-process: ``kibana.observability._imports`` resolves its try/except
    degradation exactly once, on first import, and the result is cached in
    ``sys.modules`` for the life of the interpreter. An in-process trick can't
    "un-import" it for a later test — only a fresh interpreter can.
    """
    setup = textwrap.dedent(f"""
        import logging
        import sys

        # `kibana/__init__.py` attaches a NullHandler to the "kibana" logger,
        # so logging's lastResort fallback never fires and anything the
        # import-time guards report would be invisible here. Configure the
        # root handler *before* importing kibana so the probe can see what a
        # user with default logging would see. WARNING level on purpose: the
        # "package is simply not installed" path is debug and must stay quiet.
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

        class _Blocker:
            _blocked = {blocked_prefixes!r}

            def find_spec(self, name, path, target=None):
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in self._blocked
                ):
                    raise {error}(f"blocked for test: {{name}}")
                return None

        sys.meta_path.insert(0, _Blocker())
        """)
    return subprocess.run(
        [
            sys.executable,
            *interpreter_args,
            "-c",
            setup + "\n" + textwrap.dedent(probe),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestImportGuardMatrix:
    """Real subprocess-isolated coverage for the conditional-import
    degradation in ``kibana/observability/_imports.py`` (issues #68, #70).

    Each case blocks a real OTEL distribution's import path via a meta path
    finder, then asserts that ``import kibana`` still succeeds and that every
    exporter/availability name lands in the state the rest of the package
    expects: never left unbound for ``_exporters.py`` to fail importing (#68),
    and never wrongly clobbered by an unrelated except-branch (#70).
    """

    PROBE = textwrap.dedent("""
        import kibana  # noqa: F401  (must not raise)
        from kibana.observability import _imports as m

        def flag(name):
            return repr(getattr(m, name, "MISSING"))

        print("OTEL_AVAILABLE=" + flag("OTEL_AVAILABLE"))
        print("GRPC_EXPORTER_AVAILABLE=" + flag("GRPC_EXPORTER_AVAILABLE"))
        print("HTTP_EXPORTER_AVAILABLE=" + flag("HTTP_EXPORTER_AVAILABLE"))
        print("OTLPSpanExporter_bound=" + repr(getattr(m, "OTLPSpanExporter", "MISSING") is not None))
        print(
            "HTTPOTLPSpanExporter_bound="
            + repr(getattr(m, "HTTPOTLPSpanExporter", "MISSING") is not None)
        )
        print("OTEL_LOGS_AVAILABLE=" + flag("OTEL_LOGS_AVAILABLE"))
        # ConsoleLogExporter belongs to the logs try/except and must be *bound*
        # (to None) by the except-branch too -- an unbound name is the same
        # crash-on-import class as #68/#70, just one import away
        # (_logging.py imports it inside _setup_log_forwarding).
        print("ConsoleLogExporter_present=" + repr(hasattr(m, "ConsoleLogExporter")))
        print(
            "ConsoleLogExporter_bound="
            + repr(getattr(m, "ConsoleLogExporter", None) is not None)
        )
        """)

    @staticmethod
    def _parse(stdout: str) -> dict:
        values = {}
        for line in stdout.splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
        return values

    @pytest.mark.parametrize(
        ("blocked", "expected"),
        [
            pytest.param(
                (),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "True",
                    "HTTP_EXPORTER_AVAILABLE": "True",
                    "OTLPSpanExporter_bound": "True",
                    "HTTPOTLPSpanExporter_bound": "True",
                    "OTEL_LOGS_AVAILABLE": "True",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "True",
                },
                id="baseline-everything-present",
            ),
            pytest.param(
                ("opentelemetry.exporter.otlp.proto.grpc",),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "True",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "True",
                    "OTEL_LOGS_AVAILABLE": "True",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "True",
                },
                id="issue68-grpc-exporter-absent-sdk-and-http-present",
            ),
            pytest.param(
                ("opentelemetry.exporter.otlp.proto.http",),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "True",
                    "HTTP_EXPORTER_AVAILABLE": "False",
                    "OTLPSpanExporter_bound": "True",
                    "HTTPOTLPSpanExporter_bound": "False",
                    "OTEL_LOGS_AVAILABLE": "True",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "True",
                },
                id="http-exporter-absent-sdk-and-grpc-present",
            ),
            pytest.param(
                # In the installed opentelemetry-exporter-otlp-proto-grpc build,
                # the grpc trace exporter's own module imports
                # ``opentelemetry.sdk._logs.ReadableLogRecord`` internally (shared
                # trace/log encoding code), so blocking ``sdk._logs`` also takes
                # down the grpc trace exporter as a real side effect — exactly the
                # "future SDK renames the private logs names" scenario #70 warns
                # about. The HTTP trace exporter has no such coupling and must
                # come through untouched: that's the assertion this case exists
                # to make (pre-fix, the logs except-branch wrongly clobbered it
                # to None too).
                ("opentelemetry.sdk._logs",),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "True",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "True",
                    "OTEL_LOGS_AVAILABLE": "False",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "False",
                },
                id="issue70-logs-absent-must-not-clobber-trace-exporters",
            ),
            pytest.param(
                ("opentelemetry.sdk",),
                {
                    "OTEL_AVAILABLE": "False",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "False",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "False",
                    "OTEL_LOGS_AVAILABLE": "False",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "False",
                },
                id="sdk-entirely-absent-api-only",
            ),
            pytest.param(
                ("opentelemetry",),
                {
                    "OTEL_AVAILABLE": "False",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "False",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "False",
                    "OTEL_LOGS_AVAILABLE": "False",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "False",
                },
                id="otel-entirely-absent",
            ),
        ],
    )
    def test_import_kibana_under_partial_install(self, blocked, expected):
        """``import kibana`` must succeed, and exporter/availability names
        must match the given partial-install combination exactly — no
        unbound name (#68) and no cross-branch clobbering (#70)."""
        result = _run_with_blocked_imports(blocked, self.PROBE)

        assert result.returncode == 0, (
            f"`import kibana` failed with blocked={blocked!r}:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert self._parse(result.stdout) == expected
        # A package that is simply not installed is an expected, opt-in
        # state: it must not be reported as a broken environment, and must
        # not warn at all in a default-logging process.
        assert "is installed but failed to import" not in result.stderr
        assert (
            result.stderr == ""
        ), f"a missing optional package must stay quiet:\n{result.stderr}"

    @pytest.mark.parametrize(
        ("blocked", "expected"),
        [
            pytest.param(
                ("opentelemetry.exporter.otlp.proto.grpc",),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "True",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "True",
                    "OTEL_LOGS_AVAILABLE": "True",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "True",
                },
                id="corrupt-grpc-exporter",
            ),
            pytest.param(
                ("opentelemetry.sdk._logs",),
                {
                    "OTEL_AVAILABLE": "True",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "True",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "True",
                    "OTEL_LOGS_AVAILABLE": "False",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "False",
                },
                id="corrupt-logs-sdk",
            ),
            pytest.param(
                ("opentelemetry",),
                {
                    "OTEL_AVAILABLE": "False",
                    "GRPC_EXPORTER_AVAILABLE": "False",
                    "HTTP_EXPORTER_AVAILABLE": "False",
                    "OTLPSpanExporter_bound": "False",
                    "HTTPOTLPSpanExporter_bound": "False",
                    "OTEL_LOGS_AVAILABLE": "False",
                    "ConsoleLogExporter_present": "True",
                    "ConsoleLogExporter_bound": "False",
                },
                id="corrupt-otel",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "error",
        [
            # AttributeError: an exporter reaching for a symbol its pinned
            # dependency no longer exports. TypeError: what a protobuf/exporter
            # version conflict actually raises out of generated descriptor
            # code — the failure people hit in the wild, and the reason the
            # guards stopped trying to enumerate exception types.
            "AttributeError",
            "TypeError",
        ],
    )
    def test_import_kibana_under_corrupted_install(self, blocked, expected, error):
        """A *corrupted* OTEL install must degrade, not kill ``import kibana``.

        The guards in ``_imports.py`` originally caught ``ImportError`` only,
        which covers a cleanly *missing* distribution. A corrupted or
        version-mismatched one fails differently: its module body executes and
        raises whatever it raises — classically ``AttributeError`` against a
        dependency that no longer exports some symbol — and that propagated
        straight out of ``import kibana`` for every user of this client,
        observability opted into or not (#76, folded-in review item).

        The expected maps are the *same* ones the ImportError matrix asserts
        for these prefixes: degradation must not depend on which exception a
        broken install happens to raise. Asserting the whole map (not just
        "it imported") is what keeps a corrupted grpc exporter from quietly
        taking the working HTTP one down with it (#70's defect class).
        """
        result = _run_with_blocked_imports(blocked, self.PROBE, error=error)

        assert result.returncode == 0, (
            f"`import kibana` crashed on a corrupted install ({blocked!r}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert self._parse(result.stdout) == expected
        # A broken install is not a missing one: it must say so, and must not
        # tell the user to install a package that is already there. Reported
        # twice on purpose — a log warning for applications that configure
        # logging, and a RuntimeWarning for those that do not, since this
        # package's own NullHandler on the "kibana" logger suppresses
        # logging's lastResort stderr fallback.
        assert (
            "is installed but failed to import" in result.stderr
        ), f"no warning for a corrupted install:\nstderr:\n{result.stderr}"
        assert "RuntimeWarning" in result.stderr, (
            "the corrupted-install report must not depend on the application "
            f"having configured logging:\nstderr:\n{result.stderr}"
        )
        assert error in result.stderr

    def test_corrupted_install_survives_warnings_as_errors(self):
        """Reporting a broken install must not become a second way to break.

        Under ``-W error`` (or a ``filterwarnings("error")`` in a test suite,
        which is a common house rule) ``warnings.warn`` *raises*. Raising it
        from inside an import guard defeats the guard for exactly the case it
        exists to survive: the exception escapes the inner ``except``, the
        *outer* guard catches it, and kibana-py concludes the whole tracing
        SDK failed — flipping ``OTEL_AVAILABLE`` off over a fault in one
        optional exporter — before that report's own warning takes
        ``import kibana`` down with it.

        The visibility fix must therefore be best-effort: if warning is fatal
        here, the log line is what remains.
        """
        expected = {
            "OTEL_AVAILABLE": "True",
            "GRPC_EXPORTER_AVAILABLE": "False",
            "HTTP_EXPORTER_AVAILABLE": "True",
            "OTLPSpanExporter_bound": "False",
            "HTTPOTLPSpanExporter_bound": "True",
            "OTEL_LOGS_AVAILABLE": "True",
            "ConsoleLogExporter_present": "True",
            "ConsoleLogExporter_bound": "True",
        }

        result = _run_with_blocked_imports(
            ("opentelemetry.exporter.otlp.proto.grpc",),
            self.PROBE,
            error="TypeError",
            # Fatal for exactly the category this fix must survive, and
            # nothing else: a blanket `-W error` would also turn any future
            # transitive DeprecationWarning into a failure of this test,
            # blaming the import guards for someone else's deprecation.
            interpreter_args=("-W", "error::RuntimeWarning"),
        )

        assert result.returncode == 0, (
            "`import kibana` died reporting a corrupted install under "
            f"-W error:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert self._parse(result.stdout) == expected, (
            "a fault in one optional exporter must not be misreported as the "
            f"whole SDK failing:\nstderr:\n{result.stderr}"
        )
        assert "is installed but failed to import" in result.stderr, (
            "the log report must survive even when warnings are fatal:\n"
            f"{result.stderr}"
        )
