"""Shared imports and availability flags for observability submodules."""

from __future__ import annotations

import logging

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

# ---------- Trace SDK availability ----------
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
    except ImportError:
        OTLPSpanExporter = None  # type: ignore[misc, assignment]
        GRPC_EXPORTER_AVAILABLE = False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
            OTLPSpanExporter as HTTPOTLPSpanExporter,
        )

        HTTP_EXPORTER_AVAILABLE = True
    except ImportError:
        HTTPOTLPSpanExporter = None  # type: ignore[misc, assignment]
        HTTP_EXPORTER_AVAILABLE = False

    OTEL_AVAILABLE = True
except ImportError:
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
    logger.debug(
        "OpenTelemetry not available. "
        "Install with: pip install kibana-py[observability]"
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
    except ImportError:
        OTLPLogExporter = None  # type: ignore[misc, assignment]
        GRPC_LOG_EXPORTER_AVAILABLE = False

    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (  # noqa: F401
            OTLPLogExporter as HTTPOTLPLogExporter,
        )

        HTTP_LOG_EXPORTER_AVAILABLE = True
    except ImportError:
        HTTPOTLPLogExporter = None  # type: ignore[misc, assignment]
        HTTP_LOG_EXPORTER_AVAILABLE = False

    OTEL_LOGS_AVAILABLE = True
except ImportError:
    OTEL_LOGS_AVAILABLE = False
    GRPC_LOG_EXPORTER_AVAILABLE = False
    HTTP_LOG_EXPORTER_AVAILABLE = False
    SeverityNumber = None  # type: ignore[misc, assignment]
    set_logger_provider = None  # type: ignore[misc, assignment]
    BatchLogRecordProcessor = None  # type: ignore[misc, assignment]
    LoggerProvider = None  # type: ignore[misc, assignment]
    LoggingHandler = None  # type: ignore[misc, assignment]
    OTLPLogExporter = None  # type: ignore[misc, assignment]
    HTTPOTLPLogExporter = None  # type: ignore[misc, assignment]
    # NOTE: do not rebind OTLPSpanExporter / HTTPOTLPSpanExporter here — they
    # belong to the trace try/except above and may already be correctly
    # bound (real exporter or None) by the time this block runs. Clobbering
    # them unconditionally silently disabled working trace exporters (#70).
    logger.debug(
        "OpenTelemetry logs not available. Install with: pip install "
        "opentelemetry-exporter-otlp-proto-grpc "
        "opentelemetry-exporter-otlp-proto-http"
    )
