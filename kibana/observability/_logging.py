"""OTelLogHandler and log forwarding setup."""

import logging
import os
from typing import Any

from kibana.observability._imports import SeverityNumber, logger, trace
from kibana.observability._tracing import _get_kibana_py_version, _get_python_version


class OTelLogHandler(logging.Handler):
    """Custom logging handler that forwards logs to OpenTelemetry.

    Features:
    - Automatic trace/span correlation
    - Configurable log level filtering
    - Rich metadata inclusion
    - Graceful error handling
    - Performance optimization
    """

    def __init__(
        self,
        *,
        level: int = logging.WARNING,
        logger_provider: Any | None = None,
        resource: Any | None = None,
    ) -> None:
        """Initialize the OpenTelemetry log handler."""
        super().__init__(level=level)
        self._logger_provider = logger_provider
        self._resource = resource
        self._error_count = 0
        self._max_errors = 10
        self._enabled = True

        self._otel_logger = None
        # Look up OTEL_LOGS_AVAILABLE through the package namespace
        # so test patches are respected.
        import kibana.observability as _obs

        if _obs.OTEL_LOGS_AVAILABLE and logger_provider is not None:
            try:
                self._otel_logger = logger_provider.get_logger(
                    "kibana-py",
                    version=_get_kibana_py_version(),
                    schema_url=None,
                )
            except Exception as e:
                self._handle_forwarding_error(e, None, "logger initialization")

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to OpenTelemetry."""
        import kibana.observability as _obs

        if (
            not self._enabled
            or not _obs.OTEL_LOGS_AVAILABLE
            or self._otel_logger is None
        ):
            return
        try:
            self._forward_log(record)
        except Exception as e:
            self._handle_forwarding_error(e, record, "log forwarding")

    def _forward_log(self, record: logging.LogRecord) -> None:
        """Forward log record to OpenTelemetry."""
        otel_log_record = self._create_log_record(record)
        self._otel_logger.emit(otel_log_record)  # type: ignore[union-attr]

    def _create_log_record(self, record: logging.LogRecord) -> Any:
        """Convert Python LogRecord to OpenTelemetry LogRecord format."""
        import time

        from opentelemetry._logs import LogRecord

        attributes = self._extract_attributes(record)
        trace_context = self._get_trace_context()

        return LogRecord(
            timestamp=int(record.created * 1_000_000_000),
            observed_timestamp=int(time.time_ns()),
            trace_id=trace_context.get("trace_id"),
            span_id=trace_context.get("span_id"),
            trace_flags=trace_context.get("trace_flags"),
            severity_text=record.levelname,
            severity_number=self._map_log_level_to_severity(record.levelno),
            body=record.getMessage(),
            attributes=attributes,
        )

    def _extract_attributes(self, record: logging.LogRecord) -> dict[str, Any]:
        """Extract structured attributes from log record."""
        attributes: dict[str, Any] = {}

        attributes["log.logger"] = record.name
        attributes["log.level"] = record.levelname

        if record.pathname:
            attributes["log.file.name"] = record.pathname
        if record.lineno:
            attributes["log.file.line"] = record.lineno
        if record.funcName:
            attributes["log.function"] = record.funcName
        if record.module:
            attributes["log.module"] = record.module

        if record.process:
            attributes["process.pid"] = record.process
        if record.thread:
            attributes["thread.id"] = record.thread
        if record.threadName:
            attributes["thread.name"] = record.threadName

        attributes["service.name"] = "kibana-py"
        attributes["service.language.name"] = "python"
        attributes["service.language.version"] = _get_python_version()

        kibana_version = _get_kibana_py_version()
        if kibana_version != "unknown":
            attributes["service.version"] = kibana_version

        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
                "message",
            }:
                try:
                    if isinstance(value, str | int | float | bool):
                        attributes[f"custom.{key}"] = value
                    elif value is not None:
                        attributes[f"custom.{key}"] = str(value)
                except Exception:
                    pass

        return attributes

    def _map_log_level_to_severity(self, levelno: int) -> SeverityNumber:
        """Map Python log level to OpenTelemetry severity number."""
        if levelno >= logging.CRITICAL:
            return SeverityNumber.FATAL
        elif levelno >= logging.ERROR:
            return SeverityNumber.ERROR
        elif levelno >= logging.WARNING:
            return SeverityNumber.WARN
        elif levelno >= logging.INFO:
            return SeverityNumber.INFO
        elif levelno >= logging.DEBUG:
            return SeverityNumber.DEBUG
        else:
            return SeverityNumber.TRACE

    def _get_trace_context(self) -> dict[str, Any]:
        """Get current trace and span IDs for correlation."""
        import kibana.observability as _obs

        context: dict[str, Any] = {}

        if not _obs.OTEL_AVAILABLE:
            return context

        try:
            current_span = trace.get_current_span()
            span_context = current_span.get_span_context()
            if span_context.is_valid:
                context["trace_id"] = span_context.trace_id
                context["span_id"] = span_context.span_id
                context["trace_flags"] = span_context.trace_flags
                context["trace_id_hex"] = f"{span_context.trace_id:032x}"
                context["span_id_hex"] = f"{span_context.span_id:016x}"
        except Exception as e:
            logger.debug(f"Failed to extract trace context: {e}")

        return context

    def _handle_forwarding_error(
        self, error: Exception, record: logging.LogRecord | None, operation: str
    ) -> None:
        """Handle log forwarding errors gracefully."""
        _logger = logging.getLogger("kibana.observability")

        error_msg = f"OpenTelemetry log forwarding error during {operation}: {error}"
        _logger.error(error_msg)

        self._error_count += 1
        if self._error_count > self._max_errors:
            self._enabled = False
            _logger.error(
                "OpenTelemetry log handler disabled due to "
                f"{self._max_errors} repeated errors"
            )

    def close(self) -> None:
        """Close the handler and clean up resources."""
        self._enabled = False
        super().close()


# ---------------------------------------------------------------------------
# Log forwarding setup & status
# ---------------------------------------------------------------------------

# Global variable to track created log handlers for cleanup
_created_log_handlers: list[logging.Handler] = []


def _setup_log_forwarding(
    *,
    logs_enabled: bool,
    logs_level: str,
    logs_loggers: list[str],
    exporter: str,
    endpoint: str | None,
    headers: dict[str, str],
    protocol: str,
    resource: Any,
    console_export: bool = False,
) -> list[logging.Handler]:
    """Set up log forwarding with OpenTelemetry."""
    import kibana.observability as _obs

    if not logs_enabled or not _obs.OTEL_LOGS_AVAILABLE:
        if logs_enabled and not _obs.OTEL_LOGS_AVAILABLE:
            logger.warning(
                "Log forwarding requested but OpenTelemetry logs not available"
            )
        return []

    created_handlers = []

    try:
        logger_provider = _obs.LoggerProvider(resource=resource)

        if exporter == "otlp" and endpoint:
            log_endpoint = _obs._get_log_endpoint(endpoint, protocol)
            log_exporter = _obs._create_otlp_log_exporter_with_error_handling(
                log_endpoint, headers, protocol
            )
            if log_exporter is not None:
                log_processor = _obs.BatchLogRecordProcessor(log_exporter)
                logger_provider.add_log_record_processor(log_processor)
                logger.info(
                    "OTLP log exporter configured: "
                    f"{log_endpoint} (protocol: {protocol})"
                )
            else:
                logger.warning(
                    "Failed to create OTLP log exporter, log forwarding disabled"
                )
                return []

        if exporter == "console" or console_export:
            try:
                from kibana.observability._imports import (
                    BatchLogRecordProcessor,
                    ConsoleLogExporter,
                )

                console_log_exporter = ConsoleLogExporter()
                console_log_processor = BatchLogRecordProcessor(console_log_exporter)
                logger_provider.add_log_record_processor(console_log_processor)
                logger.info("Console log exporter configured")
            except Exception as e:
                logger.error(f"Failed to configure console log exporter: {e}")

        _obs.set_logger_provider(logger_provider)

        numeric_level = getattr(logging, logs_level, logging.WARNING)

        for logger_name in logs_loggers:
            try:
                log_handler = _obs.OTelLogHandler(
                    level=numeric_level,
                    logger_provider=logger_provider,
                    resource=resource,
                )
                python_logger = logging.getLogger(logger_name)
                if (
                    python_logger.level == logging.NOTSET
                    or python_logger.level > numeric_level
                ):
                    python_logger.setLevel(numeric_level)
                python_logger.addHandler(log_handler)
                created_handlers.append(log_handler)
                logger.info(
                    "Log forwarding enabled for logger "
                    f"'{logger_name}' (level: {logs_level})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to setup log handler for logger '{logger_name}': {e}"
                )

        return created_handlers  # type: ignore[return-value]

    except Exception as e:
        _obs._handle_telemetry_error("log forwarding setup", e)
        return []


def _cleanup_log_handlers(handlers: list[logging.Handler]) -> None:
    """Clean up log handlers and remove them from loggers."""
    for handler in handlers:
        try:
            for logger_name in logging.Logger.manager.loggerDict:
                logger_obj = logging.getLogger(logger_name)
                if handler in logger_obj.handlers:
                    logger_obj.removeHandler(handler)
            handler.close()
        except Exception as e:
            logger.debug(f"Error cleaning up log handler: {e}")


def get_log_forwarding_status() -> dict[str, Any]:
    """Get the current status of log forwarding configuration."""
    import kibana.observability as _obs

    status: dict[str, Any] = {
        "logs_available": _obs.OTEL_LOGS_AVAILABLE,
        "grpc_exporter_available": _obs.GRPC_LOG_EXPORTER_AVAILABLE,
        "http_exporter_available": _obs.HTTP_LOG_EXPORTER_AVAILABLE,
        "handlers_configured": len(_created_log_handlers),
        "active_loggers": [],
        "configuration": {},
    }

    instrumentor = _obs.KibanaInstrumentor.get_instance()
    logs_enabled_actual = (
        "true" if instrumentor.is_enabled() and _created_log_handlers else "false"
    )

    status["configuration"] = {
        "logs_enabled": os.getenv("KIBANA_OTEL_LOGS_ENABLED", logs_enabled_actual),
        "logs_level": os.getenv("KIBANA_OTEL_LOGS_LEVEL", "WARNING"),
        "logs_loggers": os.getenv("KIBANA_OTEL_LOGS_LOGGERS", "kibana"),
        "logs_endpoint": os.getenv(
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "derived from traces"
        ),
        "logs_protocol": os.getenv(
            "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", "derived from traces"
        ),
    }

    for handler in _created_log_handlers:
        for logger_name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(logger_name)
            if handler in logger_obj.handlers:
                status["active_loggers"].append(
                    {
                        "name": logger_name,
                        "level": logging.getLevelName(handler.level),
                        "effective_level": logging.getLevelName(
                            logger_obj.getEffectiveLevel()
                        ),
                    }
                )

    return status


def validate_log_forwarding_configuration(
    *,
    logs_enabled: bool | None = None,
    logs_level: str | None = None,
    logs_loggers: list[str] | None = None,
    endpoint: str | None = None,
    protocol: str | None = None,
) -> dict[str, Any]:
    """Validate log forwarding configuration and return validation results."""
    import kibana.observability as _obs

    validation: dict[str, Any] = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "recommendations": [],
    }

    if logs_enabled and not _obs.OTEL_LOGS_AVAILABLE:
        validation["valid"] = False
        validation["errors"].append(
            "Log forwarding requested but OpenTelemetry logs not available. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc "
            "opentelemetry-exporter-otlp-proto-http"
        )

    if logs_level:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if logs_level.upper() not in valid_levels:
            validation["valid"] = False
            validation["errors"].append(
                "Invalid log level "
                f"'{logs_level}'. "
                f"Must be one of: {', '.join(valid_levels)}"
            )

    if logs_loggers is not None:
        if not isinstance(logs_loggers, list):
            validation["valid"] = False
            validation["errors"].append("logs_loggers must be a list of logger names")
        elif not logs_loggers:
            validation["warnings"].append(
                "Empty logs_loggers list - no logs will be forwarded"
            )
        else:
            for logger_name in logs_loggers:
                if not isinstance(logger_name, str):
                    validation["errors"].append(
                        f"Logger name must be string, got {type(logger_name)}"
                    )
                elif not logger_name.strip():
                    validation["warnings"].append(
                        "Empty logger name in logs_loggers list"
                    )

    if logs_enabled and endpoint:
        if protocol == "grpc" and not _obs.GRPC_LOG_EXPORTER_AVAILABLE:
            validation["valid"] = False
            validation["errors"].append(
                "gRPC protocol requested but gRPC log exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
            )
        elif (
            protocol in ("http", "http/protobuf")
            and not _obs.HTTP_LOG_EXPORTER_AVAILABLE
        ):
            validation["valid"] = False
            validation["errors"].append(
                "HTTP protocol requested but HTTP log exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp-proto-http"
            )

    if logs_enabled:
        if not logs_level or logs_level == "DEBUG":
            validation["recommendations"].append(
                "Consider using WARNING or ERROR log level to avoid overwhelming "
                "APM server with debug logs"
            )
        if logs_loggers and "root" in logs_loggers:
            validation["warnings"].append(
                "Forwarding root logger may capture logs from all libraries - "
                "consider using specific logger names"
            )

    return validation


def validate_log_forwarding_connectivity(
    endpoint: str,
    headers: dict[str, str] | None = None,
    protocol: str = "grpc",
    timeout: int = 5,
) -> dict[str, Any]:
    """Test connectivity to log forwarding endpoint."""
    import kibana.observability as _obs

    result = {
        "success": False,
        "endpoint": endpoint,
        "protocol": protocol,
        "error": None,
        "response_time": None,
    }

    if headers is None:
        headers = {}

    try:
        import time

        start_time = time.time()
        log_endpoint = _obs._get_log_endpoint(endpoint, protocol)
        result["log_endpoint"] = log_endpoint
        connectivity_ok = _obs._validate_apm_connectivity(
            log_endpoint, headers, protocol, timeout
        )
        result["response_time"] = time.time() - start_time
        result["success"] = connectivity_ok
        if not connectivity_ok:
            result["error"] = f"Could not connect to log endpoint {log_endpoint}"
    except Exception as e:
        result["error"] = str(e)

    return result
