"""Top-level ``configure_opentelemetry()`` convenience function."""

from __future__ import annotations

import os
from typing import Any

from kibana.observability._imports import (
    SERVICE_NAME,
    SERVICE_VERSION,
    BatchSpanProcessor,
    ConsoleSpanExporter,
    Resource,
    ResourceAttributes,
    TracerProvider,
    logger,
    trace,
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

    tracer_provider = TracerProvider(resource=resource)

    if exporter == "otlp":
        if endpoint is None:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        try:
            if validate_endpoint and not _obs._validate_apm_connectivity(
                endpoint, headers, protocol
            ):
                logger.warning(
                    f"APM server connectivity validation failed for {endpoint}, "
                    "continuing without telemetry"
                )
                return

            otlp_exporter = _obs._create_otlp_exporter_with_error_handling(
                endpoint, headers, protocol
            )
            if otlp_exporter is None:
                logger.warning(
                    "Failed to create OTLP exporter, continuing without telemetry"
                )
                return
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {endpoint} (protocol: {protocol})")
        except Exception as e:
            _obs._handle_telemetry_error("OTLP exporter configuration", e)
            return

    if exporter == "console" or console_export:
        try:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console exporter configured")
        except Exception as e:
            logger.error(f"Failed to configure console exporter: {e}")

    trace.set_tracer_provider(tracer_provider)

    instrumentor = _obs.KibanaInstrumentor.get_instance()
    instrumentor.enable(tracer_provider=tracer_provider, service_name=service_name)

    # Log forwarding — look up handlers through the package namespace
    # so that test patches applied to kibana.observability._created_log_handlers
    # are respected.
    if _obs._created_log_handlers:
        _obs._cleanup_log_handlers(_obs._created_log_handlers)
        _obs._created_log_handlers = []

    if logs_enabled:
        import kibana.observability._logging as _logging_mod

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

    logger.info(
        f"OpenTelemetry configured for service: {service_name} "
        f"(logs: {'enabled' if logs_enabled else 'disabled'})"
    )
