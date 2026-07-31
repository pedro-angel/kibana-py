"""Top-level ``configure_opentelemetry()`` convenience function."""

from __future__ import annotations

import os
from typing import Any

from kibana.observability._imports import (
    _HTTP_OTLP_PROTOCOLS,
    _SUPPORTED_OTLP_PROTOCOLS,
    SERVICE_NAME,
    SERVICE_VERSION,
    BatchSpanProcessor,
    ConsoleSpanExporter,
    Resource,
    ResourceAttributes,
    TracerProvider,
    logger,
)
from kibana.observability._tracing import (
    _get_kibana_py_version,
    _get_opentelemetry_version,
    _get_python_version,
)


def _parse_otlp_headers() -> dict[str, str]:
    """Parse OTLP headers from environment variables with APM token support."""
    headers = {}
    headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    if headers_str:
        try:
            for header_pair in headers_str.split(","):
                if "=" in header_pair:
                    key, value = header_pair.strip().split("=", 1)
                    headers[key.strip()] = value.strip()
        except Exception as e:
            logger.warning(f"Failed to parse OTLP headers: {e}")
    apm_token = os.getenv("ELASTIC_APM_SECRET_TOKEN")
    if apm_token and "authorization" not in headers:
        headers["authorization"] = f"Bearer {apm_token}"
        logger.debug("Added APM secret token to OTLP headers")
    return headers


def configure_opentelemetry(
    *,
    enabled: bool | None = None,
    service_name: str | None = None,
    exporter: str | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    protocol: str | None = None,
    console_export: bool = False,
    logs_enabled: bool | None = None,
    logs_level: str | None = None,
    logs_loggers: list[str] | None = None,
    resource: Any | None = None,
    resource_attributes: dict[str, Any] | None = None,
    validate_endpoint: bool = True,
) -> None:
    """Configure OpenTelemetry for Kibana client with APM server support.

    This is a convenience function to set up OpenTelemetry with common
    configurations, including enhanced APM server integration with
    authentication and protocol selection, and optional log forwarding.

    :param enabled: Enable/disable instrumentation
    :param service_name: Service name for traces
    :param exporter: Exporter type: ``"otlp"``, ``"console"``, or ``None``
    :param endpoint: OTLP endpoint
    :param headers: OTLP headers for authentication
    :param protocol: ``"grpc"`` or ``"http/protobuf"``
    :param console_export: Also export to console for debugging
    :param logs_enabled: Enable/disable log forwarding
    :param logs_level: Minimum log level to forward
    :param logs_loggers: Logger names to forward

    Example::

        >>> from kibana.observability import configure_opentelemetry
        >>> configure_opentelemetry(
        ...     enabled=True,
        ...     exporter="otlp",
        ...     endpoint="http://localhost:8200",
        ... )
    """
    # All lookups go through the package namespace so that test patches
    # applied to ``kibana.observability.<name>`` are respected at runtime.
    import kibana.observability as _obs

    if not _obs.OTEL_AVAILABLE:
        logger.warning(
            "OpenTelemetry not available. "
            "Install with: pip install kibana-py[observability]"
        )
        return

    if enabled is None:
        enabled = os.getenv("KIBANA_OTEL_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.debug("OpenTelemetry instrumentation disabled")
        return

    if service_name is None:
        service_name = os.getenv("OTEL_SERVICE_NAME", "kibana-py")
    if exporter is None:
        exporter = os.getenv("KIBANA_OTEL_EXPORTER", "otlp")
    if protocol is None:
        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    # Normalize once, here, before protocol drives any endpoint-shape or
    # default-port decision below (or is threaded into log forwarding). Every
    # downstream comparison is a case-sensitive `protocol in (...)`/`==`
    # check, so an unnormalized "HTTP/PROTOBUF" would silently mismatch them
    # all and never get its /v1/traces path appended, even though the OTEL
    # SDK itself doesn't care about case.
    protocol = protocol.lower()
    if protocol not in _SUPPORTED_OTLP_PROTOCOLS:
        # "Exporter creation will raise" is only true when exporter="otlp"
        # actually reaches _create_otlp_exporter below -- for exporter=
        # "console" nothing downstream ever builds an OTLP exporter, so the
        # claim must be scoped to the otlp path rather than stated
        # unconditionally.
        logger.warning(
            f"Unrecognized OTLP protocol '{protocol}', assuming gRPC-style "
            "endpoint defaults (this module's own documented bias -- see "
            "_validate_apm_connectivity); for exporter='otlp' this will "
            "still surface as a clear logged error during exporter creation"
        )
    if headers is None:
        headers = _parse_otlp_headers()

    # Log forwarding defaults
    if logs_enabled is None:
        logs_enabled = os.getenv("KIBANA_OTEL_LOGS_ENABLED", "false").lower() == "true"
    if logs_level is None:
        logs_level = os.getenv("KIBANA_OTEL_LOGS_LEVEL", "WARNING").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if logs_level not in valid_levels:
        logger.warning(f"Invalid log level '{logs_level}', using 'WARNING'")
        logs_level = "WARNING"
    if logs_loggers is None:
        loggers_env = os.getenv("KIBANA_OTEL_LOGS_LOGGERS", "kibana")
        logs_loggers = [n.strip() for n in loggers_env.split(",") if n.strip()]
    if not isinstance(logs_loggers, list):
        logger.warning(
            f"logs_loggers must be a list, got {type(logs_loggers)}, using default"
        )
        logs_loggers = ["kibana"]

    # Resource
    if resource is None:
        default_attrs = {
            SERVICE_NAME: service_name,
            "service.language.name": "python",
            "service.language.version": _get_python_version(),
            ResourceAttributes.TELEMETRY_SDK_NAME: "opentelemetry",
            ResourceAttributes.TELEMETRY_SDK_LANGUAGE: "python",
            ResourceAttributes.TELEMETRY_SDK_VERSION: _get_opentelemetry_version(),
        }
        kibana_version = _get_kibana_py_version()
        if kibana_version != "unknown":
            default_attrs[SERVICE_VERSION] = kibana_version
        if resource_attributes:
            default_attrs.update(resource_attributes)
        resource = Resource(attributes=default_attrs)

    # Reconfiguration (issue #76, problem 2). OTel installs the global tracer
    # provider exactly once per process, so building a second provider here
    # would silently orphan everything hung off it — the exporter created
    # below would never see a span, yet the success line at the end of this
    # function would still claim otherwise. Reuse the provider we installed
    # (if it is still the global one) and swap its span processors instead;
    # only the first configuration creates and installs a provider.
    tracer_provider = _obs._get_reconfigurable_tracer_provider()
    reconfiguring = tracer_provider is not None
    if tracer_provider is None:
        tracer_provider = TracerProvider(resource=resource)
    elif getattr(tracer_provider, "resource", None) != resource:
        # A provider's Resource is fixed at construction, so a changed
        # service name/resource genuinely cannot be applied to spans without
        # a new process. Say so rather than let the caller assume it took.
        logger.warning(
            "Reconfiguring the existing OpenTelemetry tracer provider: "
            "exporters are being replaced, but resource attributes (service "
            "name/version) keep the values from the first configuration — "
            "OpenTelemetry fixes a provider's resource at creation. Restart "
            "the process to change them."
        )

    span_processors: list[Any] = []

    if exporter == "otlp":
        if endpoint is None:
            # The OTLP/HTTP and OTLP/gRPC exporters listen on different default
            # ports (4318 vs. 4317) -- the fallback must match whichever
            # protocol is actually in effect, not always the gRPC port
            # (issue #77). `endpoint` here is the shared base used for both
            # traces (below) and log forwarding (later in this function), so
            # fixing it here fixes the same wrong-default-port defect for
            # both signals at once. Documented bias (shared with
            # `_validate_apm_connectivity` in `_validation.py`, via the same
            # `_HTTP_OTLP_PROTOCOLS` constant from `_imports.py`): only a
            # recognized HTTP variant gets the HTTP port; anything else
            # (including an already-warned-about unrecognized protocol)
            # assumes gRPC's port, matching this function's own "grpc"
            # default when `protocol` is unspecified.
            default_port = 4318 if protocol in _HTTP_OTLP_PROTOCOLS else 4317
            endpoint = os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", f"http://localhost:{default_port}"
            )
        try:
            if validate_endpoint and not _obs._validate_apm_connectivity(
                endpoint, headers, protocol
            ):
                logger.warning(
                    f"APM server connectivity validation failed for {endpoint}, "
                    "continuing without telemetry"
                )
                return

            # http/protobuf requires the OTLP signal-specific resource path
            # (`/v1/traces`); gRPC's endpoint is a bare host:port and passes
            # through untouched. `endpoint` itself stays the unmodified base
            # so log forwarding (which appends its own `/v1/logs` path) below
            # still sees the same base both signals were configured with.
            trace_endpoint = _obs._get_trace_endpoint(endpoint, protocol)
            otlp_exporter = _obs._create_otlp_exporter_with_error_handling(
                trace_endpoint, headers, protocol
            )
            if otlp_exporter is None:
                logger.warning(
                    "Failed to create OTLP exporter, continuing without telemetry"
                )
                return
            span_processors.append(BatchSpanProcessor(otlp_exporter))
            logger.info(
                f"OTLP exporter configured: {trace_endpoint} (protocol: {protocol})"
            )
        except Exception as e:
            _obs._handle_telemetry_error("OTLP exporter configuration", e)
            return

    if exporter == "console" or console_export:
        try:
            console_exporter = ConsoleSpanExporter()
            span_processors.append(BatchSpanProcessor(console_exporter))
            logger.info("Console exporter configured")
        except Exception as e:
            logger.error(f"Failed to configure console exporter: {e}")

    # Nothing above this line touched global state, so every early return so
    # far left any previous configuration working and untouched.
    if not _obs._install_span_processors(tracer_provider, span_processors):
        logger.warning(
            "Another component already installed the global OpenTelemetry "
            "tracer provider, and OpenTelemetry does not allow replacing it. "
            "kibana-py's own spans are still created and exported with this "
            "configuration, through a tracer provider of its own, but "
            "trace.get_tracer_provider() keeps returning the other "
            "component's provider — configure kibana-py first if you want it "
            "to own process-wide tracing."
        )

    instrumentor = _obs.KibanaInstrumentor.get_instance()
    instrumentor.enable(tracer_provider=tracer_provider, service_name=service_name)

    # Log forwarding. `_created_log_handlers` lives in `_logging`'s module
    # namespace; read *and* write it through that one binding. Reading the
    # `kibana.observability` package attribute instead (a snapshot of the
    # empty list, taken at import time and never updated by the write below)
    # is why this cleanup branch never fired and every repeat call stacked
    # another handler on the "kibana" logger (#76).
    import kibana.observability._logging as _logging_mod

    if _logging_mod._created_log_handlers:
        _obs._cleanup_log_handlers(_logging_mod._created_log_handlers)
        _logging_mod._created_log_handlers = []

    if logs_enabled:
        _logging_mod._created_log_handlers = _obs._setup_log_forwarding(
            logs_enabled=logs_enabled,
            logs_level=logs_level,
            logs_loggers=logs_loggers,
            exporter=exporter,
            endpoint=endpoint,
            headers=headers,
            protocol=protocol,
            resource=resource,
            console_export=console_export,
        )

    # Reached only when the configuration actually took effect: every path
    # that changed nothing returned above with a warning instead.
    logger.info(
        f"OpenTelemetry {'reconfigured' if reconfiguring else 'configured'} "
        f"for service: {service_name} "
        f"(logs: {'enabled' if logs_enabled else 'disabled'})"
    )
