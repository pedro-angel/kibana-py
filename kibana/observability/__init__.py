"""OpenTelemetry observability configuration for Kibana client.

This package was decomposed from a single ``observability.py`` module.
All public names are re-exported here so that existing imports
(``from kibana.observability import …``) continue to work unchanged.
"""

from __future__ import annotations

# Re-export configuration
from kibana.observability._config import (  # noqa: F401
    _parse_otlp_headers,
    configure_opentelemetry,
)

# Re-export exporter helpers
from kibana.observability._exporters import (  # noqa: F401
    _create_otlp_exporter,
    _create_otlp_exporter_with_error_handling,
    _create_otlp_log_exporter,
    _create_otlp_log_exporter_with_error_handling,
    _get_log_endpoint,
)

# Re-export availability flags and SDK classes
from kibana.observability._imports import (  # noqa: F401
    GRPC_LOG_EXPORTER_AVAILABLE,
    HTTP_EXPORTER_AVAILABLE,
    HTTP_LOG_EXPORTER_AVAILABLE,
    OTEL_AVAILABLE,
    OTEL_LOGS_AVAILABLE,
    BatchLogRecordProcessor,
    LoggerProvider,
    SeverityNumber,
    set_logger_provider,
)

# Re-export logging
from kibana.observability._logging import (  # noqa: F401
    OTelLogHandler,
    _cleanup_log_handlers,
    _created_log_handlers,
    _setup_log_forwarding,
    get_log_forwarding_status,
    validate_log_forwarding_configuration,
    validate_log_forwarding_connectivity,
)

# Re-export tracing primitives
from kibana.observability._tracing import (  # noqa: F401
    KibanaInstrumentor,
    _get_kibana_py_version,
    _get_opentelemetry_logs_version,
    _get_opentelemetry_version,
    _get_python_version,
    create_span,
    safe_span_operation,
    set_span_error,
    span_context,
)

# Re-export validation helpers
from kibana.observability._validation import (  # noqa: F401
    _handle_telemetry_error,
    _mask_sensitive_info,
    _validate_apm_connectivity,
    validate_apm_server_availability,
)
