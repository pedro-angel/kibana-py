"""Shared imports and availability flags for observability submodules."""

from __future__ import annotations

import logging
import warnings

# Set up logger
logger = logging.getLogger("kibana.observability")

# ---------- OTLP protocol constants ----------
# Single source of truth for which `protocol` strings this package treats as
# "HTTP-shaped" (requires an OTLP resource path like /v1/traces, defaults to
# port 4318) vs. the full set of protocol strings recognized at all. Defined
# here -- the one module the others already depend on, directly or
# transitively, with no risk of a circular import -- and reused (not
# re-hardcoded) by:
#   * _config.py     -- default-endpoint port bias, unrecognized-protocol
#                        warning check
#   * _exporters.py  -- _get_signal_endpoint's path-append decision, and the
#                        grpc/http branches in _create_otlp_exporter /
#                        _create_otlp_log_exporter
#   * _validation.py -- _validate_apm_connectivity's port guess
_HTTP_OTLP_PROTOCOLS = frozenset({"http/protobuf", "http"})
_SUPPORTED_OTLP_PROTOCOLS = frozenset({"grpc"}) | _HTTP_OTLP_PROTOCOLS

# The `exporter` values `configure_opentelemetry` knows how to build a span
# exporter from. Anything else produces no exporter at all, which is a
# configuration worth warning about rather than applying silently (#76).
_SUPPORTED_EXPORTERS = frozenset({"otlp", "console"})


def _report_guarded_import_failure(
    component: str, error: BaseException, install_hint: str
) -> None:
    """Report why an optional import failed, without misdiagnosing it.

    A missing distribution and a broken one need opposite advice, and the
    exception type is what tells them apart. ``ImportError`` means "not
    installed" — expected, opt-in, debug-level, and "install it" is the fix.
    Anything else means the package *is* installed and blew up while
    importing (a protobuf/grpc version conflict raising ``TypeError`` is the
    classic), which is a broken environment the user cannot fix by installing
    the package again — that deserves a warning, and one that says so.
    """
    if isinstance(error, ImportError):
        logger.debug(
            f"{component} not available ({error}). Install with: {install_hint}"
        )
        return

    message = (
        f"{component} is installed but failed to import "
        f"({type(error).__name__}: {error}). The features it provides are "
        "disabled. This is a corrupted or version-mismatched install — "
        "repair or align the versions of the OpenTelemetry packages and "
        "their dependencies; re-running the install command alone will not "
        "fix it."
    )
    logger.warning(message)
    # …and again through `warnings`, because the log line alone is not
    # reliably visible: this package attaches a NullHandler to the "kibana"
    # logger, which suppresses logging's lastResort stderr fallback, so an
    # application that has not configured logging sees nothing at all. A
    # broken install should not be something you discover from telemetry
    # being mysteriously absent in production.
    warnings.warn(message, RuntimeWarning, stacklevel=2)


# ---------- Trace SDK availability ----------
# Every guard in this module catches ``Exception``, not ``ImportError`` alone.
# A *missing* distribution raises ImportError, but a *corrupted or
# version-mismatched* one raises whatever its module body raises while
# executing: AttributeError against a dependency that no longer exports a
# symbol, or -- the failure people actually hit in the wild -- TypeError out
# of generated protobuf code when protobuf and the exporter disagree about
# descriptor formats. Guessing the exception type is how a guard silently
# stops guarding, so the type is not guessed. These try blocks contain
# nothing but import statements, so the only thing the broad except can
# swallow is a broken third-party install, and the whole point of the guards
# is that such an install degrades observability instead of taking down
# ``import kibana`` for every user of this client (#76). Which failure
# happened is not swallowed: `_report_guarded_import_failure` tells the two
# apart and warns (rather than whispers "install it") when the package is
# present but broken.
try:
    from opentelemetry import trace  # noqa: F401
    from opentelemetry.sdk.resources import (  # noqa: F401
        SERVICE_NAME,
        SERVICE_VERSION,
        Resource,
    )
    from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
    from opentelemetry.sdk.trace.export import (  # noqa: F401
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.semconv.resource import ResourceAttributes  # noqa: F401
    from opentelemetry.trace import Span, Status, StatusCode, Tracer  # noqa: F401

    # The gRPC and HTTP OTLP trace exporters ship as separate, independently
    # optional distributions (opentelemetry-exporter-otlp-proto-grpc /
    # -http). Each is imported in its own nested try so that either one
    # being absent degrades only that exporter, not the whole SDK (#68).
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: F401
            OTLPSpanExporter,
        )

        GRPC_EXPORTER_AVAILABLE = True
    except Exception as e:
        _report_guarded_import_failure(
            "gRPC OTLP trace exporter",
            e,
            "pip install opentelemetry-exporter-otlp-proto-grpc",
        )
        OTLPSpanExporter = None  # type: ignore[misc, assignment]
        GRPC_EXPORTER_AVAILABLE = False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
            OTLPSpanExporter as HTTPOTLPSpanExporter,
        )

        HTTP_EXPORTER_AVAILABLE = True
    except Exception as e:
        _report_guarded_import_failure(
            "HTTP OTLP trace exporter",
            e,
            "pip install opentelemetry-exporter-otlp-proto-http",
        )
        HTTPOTLPSpanExporter = None  # type: ignore[misc, assignment]
        HTTP_EXPORTER_AVAILABLE = False

    OTEL_AVAILABLE = True
except Exception as e:
    OTEL_AVAILABLE = False
    GRPC_EXPORTER_AVAILABLE = False
    HTTP_EXPORTER_AVAILABLE = False
    OTLPSpanExporter = None  # type: ignore[misc, assignment]
    HTTPOTLPSpanExporter = None  # type: ignore[misc, assignment]
    SERVICE_NAME = None  # type: ignore[misc, assignment]
    SERVICE_VERSION = None  # type: ignore[misc, assignment]
    Resource = None  # type: ignore[misc, assignment]
    ResourceAttributes = None  # type: ignore[misc, assignment]
    Span = None  # type: ignore[misc, assignment]
    Status = None  # type: ignore[misc, assignment]
    StatusCode = None  # type: ignore[misc, assignment]
    Tracer = None  # type: ignore[misc, assignment]
    TracerProvider = None  # type: ignore[misc, assignment]
    BatchSpanProcessor = None  # type: ignore[misc, assignment]
    ConsoleSpanExporter = None  # type: ignore[misc, assignment]
    trace = None  # type: ignore[misc, assignment]
    _report_guarded_import_failure(
        "OpenTelemetry tracing SDK",
        e,
        "pip install kibana-py[observability]",
    )

# ---------- Log SDK availability ----------
try:
    from opentelemetry._logs import SeverityNumber, set_logger_provider  # noqa: F401
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler  # noqa: F401
    from opentelemetry.sdk._logs.export import (  # noqa: F401
        BatchLogRecordProcessor,
        ConsoleLogExporter,
    )

    try:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (  # noqa: F401
            OTLPLogExporter,
        )

        GRPC_LOG_EXPORTER_AVAILABLE = True
    except Exception as e:
        _report_guarded_import_failure(
            "gRPC OTLP log exporter",
            e,
            "pip install opentelemetry-exporter-otlp-proto-grpc",
        )
        OTLPLogExporter = None  # type: ignore[misc, assignment]
        GRPC_LOG_EXPORTER_AVAILABLE = False

    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (  # noqa: F401
            OTLPLogExporter as HTTPOTLPLogExporter,
        )

        HTTP_LOG_EXPORTER_AVAILABLE = True
    except Exception as e:
        _report_guarded_import_failure(
            "HTTP OTLP log exporter",
            e,
            "pip install opentelemetry-exporter-otlp-proto-http",
        )
        HTTPOTLPLogExporter = None  # type: ignore[misc, assignment]
        HTTP_LOG_EXPORTER_AVAILABLE = False

    OTEL_LOGS_AVAILABLE = True
except Exception as e:
    OTEL_LOGS_AVAILABLE = False
    GRPC_LOG_EXPORTER_AVAILABLE = False
    HTTP_LOG_EXPORTER_AVAILABLE = False
    SeverityNumber = None  # type: ignore[misc, assignment]
    set_logger_provider = None  # type: ignore[misc, assignment]
    BatchLogRecordProcessor = None  # type: ignore[misc, assignment]
    # Bound here for the same reason as every other name in this branch:
    # `_logging.py`'s `_setup_log_forwarding` imports ConsoleLogExporter from
    # this module, so leaving it unbound turns a missing logs SDK into an
    # ImportError at *call* time -- the same unbound-name defect as #68/#70,
    # just deferred by one import (#76).
    ConsoleLogExporter = None  # type: ignore[misc, assignment]
    LoggerProvider = None  # type: ignore[misc, assignment]
    LoggingHandler = None  # type: ignore[misc, assignment]
    OTLPLogExporter = None  # type: ignore[misc, assignment]
    HTTPOTLPLogExporter = None  # type: ignore[misc, assignment]
    # NOTE: do not rebind OTLPSpanExporter / HTTPOTLPSpanExporter here — they
    # belong to the trace try/except above and may already be correctly
    # bound (real exporter or None) by the time this block runs. Clobbering
    # them unconditionally silently disabled working trace exporters (#70).
    _report_guarded_import_failure(
        "OpenTelemetry logs SDK",
        e,
        "pip install opentelemetry-exporter-otlp-proto-grpc "
        "opentelemetry-exporter-otlp-proto-http",
    )
