"""Top-level ``configure_opentelemetry()`` convenience function."""

from __future__ import annotations

import os
from typing import Any

from kibana.observability._imports import (
    _HTTP_OTLP_PROTOCOLS,
    _SUPPORTED_EXPORTERS,
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
    if not isinstance(exporter, str):
        # Same treatment as `logs_loggers` below: a wrong-typed argument is a
        # caller mistake to report, not an AttributeError thrown from inside
        # a telemetry setup call that the caller most likely wrapped in
        # "observability is optional" hope.
        logger.warning(f"exporter must be a string, got {type(exporter)}, using 'otlp'")
        exporter = "otlp"
    # Normalized for the same reason as `protocol` below: every downstream
    # decision is a case-sensitive `exporter == "otlp"` / `== "console"`
    # check, so an unnormalized "OTLP" matched no branch at all and produced
    # a configuration with no span exporter — which used to be applied
    # silently, shutting down the exporters that were working (#76 round 2).
    exporter = exporter.lower()
    if exporter not in _SUPPORTED_EXPORTERS:
        logger.warning(
            f"Unrecognized exporter '{exporter}': expected "
            f"{' or '.join(sorted(repr(e) for e in _SUPPORTED_EXPORTERS))}. "
            "No span exporter will be created from it."
        )
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
    #
    # The provider is passed as a factory, and whether to build it at all is
    # decided under the installer's lock: a `TracerProvider` registers an
    # atexit flush on construction, and every question this call still has to
    # answer — is there a live configuration? does this one have exporters? —
    # is only answerable without a race while that lock is held. Deciding out
    # here is what let a concurrent no-exporter call tear down a working
    # configuration it had not yet observed (#76 round 3).
    outcome = _obs._install_span_processors(
        span_processors, lambda: TracerProvider(resource=resource)
    )

    if not outcome.applied:
        # A configuration with no span exporter is never installed: over a
        # live one it would shut working exporters down and export nothing,
        # and over nothing at all it would still claim the process-global
        # provider slot — which OTel fills exactly once — locking out the
        # next call that does have exporters. Reachable from an unrecognized
        # `exporter` value and from a console exporter that failed to build.
        if outcome.reconfigured:
            logger.warning(
                "This configuration creates no span exporter, so none of it "
                "is being applied — including its log-forwarding settings. "
                "kibana-py's previous configuration is left untouched rather "
                "than silently stopped. Pass exporter='otlp' or "
                "exporter='console' (or console_export=True) to change span "
                "export."
            )
        else:
            logger.warning(
                "No span exporter was created, so nothing was configured — "
                "including log forwarding, and no tracer provider was "
                "installed. Pass exporter='otlp' or exporter='console' (or "
                "console_export=True) to export spans."
            )
        return

    tracer_provider = outcome.tracer_provider

    # Only now, once the call is known to be applied: saying "your resource
    # attributes will not change" in the same breath as "none of this is
    # being applied" would be two contradictory warnings about one call.
    if outcome.reconfigured and getattr(tracer_provider, "resource", None) != resource:
        # A provider's Resource is fixed at construction, so a changed
        # service name/resource genuinely cannot be applied to spans without
        # a new process. Say so rather than let the caller assume it took.
        # Scoped to spans on purpose: log forwarding builds a fresh
        # LoggerProvider on every call, so forwarded logs *do* pick up the
        # new attributes — an asymmetry worth naming rather than papering
        # over with a blanket "resource changes don't apply".
        logger.warning(
            "Reconfiguring the existing OpenTelemetry tracer provider: "
            "exporters are being replaced, but resource attributes (service "
            "name/version) keep the values from the first configuration "
            "for spans; forwarded logs pick up the new attributes. "
            "OpenTelemetry fixes a provider's resource at creation — restart "
            "the process to change the attributes on spans."
        )

    if not outcome.is_global:
        if outcome.global_slot_is_ours:
            # Naming the squatter matters: this one is kibana-py's own
            # earlier provider, already shut down, and telling the reader to
            # go find "another component" would send them hunting a phantom.
            logger.warning(
                "The global OpenTelemetry tracer provider slot still holds a "
                "provider kibana-py installed earlier and that has since been "
                "shut down; OpenTelemetry fills that slot exactly once per "
                "process, so it cannot be replaced. kibana-py's own spans are "
                "still created and exported with this configuration, through "
                "a tracer provider of its own, but trace.get_tracer_provider()"
                " keeps returning the shut-down one. Restart the process to "
                "get a clean global provider."
            )
        else:
            logger.warning(
                "Another component already installed the global OpenTelemetry "
                "tracer provider, and OpenTelemetry does not allow replacing "
                "it. kibana-py's own spans are still created and exported with "
                "this configuration, through a tracer provider of its own, but "
                "trace.get_tracer_provider() keeps returning the other "
                "component's provider — configure kibana-py first if you want "
                "it to own process-wide tracing."
            )

    instrumentor = _obs.KibanaInstrumentor.get_instance()
    # The provider that came *back* is the one in use — a concurrent caller
    # may have installed kibana-py's provider while this call was building
    # its own, in which case the winner is what spans must be created from.
    instrumentor.enable(tracer_provider=tracer_provider, service_name=service_name)

    # Log forwarding. `_created_log_handlers` lives in `_logging`'s module
    # namespace; read *and* write it through that one binding. Reading the
    # `kibana.observability` package attribute instead (a snapshot of the
    # empty list, taken at import time and never updated by the write below)
    # is why this cleanup branch never fired and every repeat call stacked
    # another handler on the "kibana" logger (#76).
    #
    # Known residual: the LoggerProvider behind the handlers being detached is
    # NOT shut down here, so its batch processor thread lives (idle, with no
    # handler feeding it) until process exit. That is deliberate, not an
    # oversight: `set_logger_provider()` also refuses every call after the
    # first, so the provider built by the *first* configuration is the process
    # global that unrelated code may hold loggers from — shutting it down on
    # reconfigure would break those callers to reclaim one idle thread.
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
    # that changed nothing returned above with a warning instead. Both the
    # fact and the wording come from the installer's locked observation — a
    # "have we configured before?" answer read before the lock describes a
    # world a concurrent call may already have changed.
    logger.info(
        f"OpenTelemetry {'reconfigured' if outcome.reconfigured else 'configured'} "
        f"for service: {service_name} "
        f"(logs: {'enabled' if logs_enabled else 'disabled'})"
    )
