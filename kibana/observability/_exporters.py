"""Exporter creation helpers for OTLP trace and log exporters."""

from typing import Any

from kibana.observability._imports import (
    GRPC_LOG_EXPORTER_AVAILABLE,
    HTTP_EXPORTER_AVAILABLE,
    HTTP_LOG_EXPORTER_AVAILABLE,
    HTTPOTLPLogExporter,
    HTTPOTLPSpanExporter,
    OTLPLogExporter,
    OTLPSpanExporter,
    logger,
)
from kibana.observability._validation import _handle_telemetry_error


def _create_otlp_exporter(endpoint: str, headers: dict[str, str], protocol: str) -> Any:
    """Create the appropriate OTLP exporter based on protocol."""
    exporter_kwargs: dict[str, Any] = {"endpoint": endpoint}

    if headers:
        if protocol == "grpc":
            normalized_headers = {key.lower(): value for key, value in headers.items()}
            exporter_kwargs["headers"] = normalized_headers
        else:
            exporter_kwargs["headers"] = headers

    if protocol == "grpc":
        return OTLPSpanExporter(**exporter_kwargs)
    elif protocol in ("http/protobuf", "http"):
        if not HTTP_EXPORTER_AVAILABLE:
            raise ImportError(
                "HTTP OTLP exporter not available. Install with: "
                "pip install opentelemetry-exporter-otlp-proto-http"
            )
        return HTTPOTLPSpanExporter(**exporter_kwargs)
    else:
        raise ValueError(
            f"Unsupported OTLP protocol: {protocol}. Use 'grpc' or 'http/protobuf'"
        )


def _create_otlp_exporter_with_error_handling(
    endpoint: str, headers: dict[str, str], protocol: str
) -> Any | None:
    """Create OTLP exporter with comprehensive error handling."""
    import kibana.observability as _obs

    try:
        return _obs._create_otlp_exporter(endpoint, headers, protocol)
    except ImportError as e:
        logger.error(f"Missing OpenTelemetry exporter dependency: {e}")
        logger.info("Install with: pip install kibana-py[observability]")
        return None
    except ValueError as e:
        logger.error(f"Invalid OTLP configuration: {e}")
        return None
    except Exception as e:
        _handle_telemetry_error("OTLP exporter creation", e)
        return None


def _create_otlp_log_exporter(
    endpoint: str, headers: dict[str, str], protocol: str
) -> Any:
    """Create the appropriate OTLP log exporter based on protocol."""
    exporter_kwargs: dict[str, Any] = {"endpoint": endpoint}

    if headers:
        if protocol == "grpc":
            normalized_headers = {key.lower(): value for key, value in headers.items()}
            exporter_kwargs["headers"] = normalized_headers
        else:
            exporter_kwargs["headers"] = headers

    if protocol == "grpc":
        if not GRPC_LOG_EXPORTER_AVAILABLE:
            raise ImportError(
                "gRPC OTLP log exporter not available. Install with: "
                "pip install opentelemetry-exporter-otlp-proto-grpc"
            )
        return OTLPLogExporter(**exporter_kwargs)
    elif protocol in ("http/protobuf", "http"):
        if not HTTP_LOG_EXPORTER_AVAILABLE:
            raise ImportError(
                "HTTP OTLP log exporter not available. Install with: "
                "pip install opentelemetry-exporter-otlp-proto-http"
            )
        return HTTPOTLPLogExporter(**exporter_kwargs)
    else:
        raise ValueError(
            f"Unsupported OTLP protocol for logs: {protocol}. "
            "Use 'grpc' or 'http/protobuf'"
        )


def _create_otlp_log_exporter_with_error_handling(
    endpoint: str, headers: dict[str, str], protocol: str
) -> Any | None:
    """Create OTLP log exporter with comprehensive error handling."""
    import kibana.observability as _obs

    try:
        return _obs._create_otlp_log_exporter(endpoint, headers, protocol)
    except ImportError as e:
        logger.error(f"Missing OpenTelemetry log exporter dependency: {e}")
        logger.error(
            "Install log exporters with: pip install "
            "opentelemetry-exporter-otlp-proto-grpc "
            "opentelemetry-exporter-otlp-proto-http"
        )
        return None
    except ValueError as e:
        logger.error(f"Invalid OTLP log configuration: {e}")
        return None
    except Exception as e:
        _handle_telemetry_error("OTLP log exporter creation", e)
        return None


def _get_log_endpoint(base_endpoint: str, protocol: str) -> str:
    """Get the appropriate log endpoint based on the base endpoint and protocol."""
    if "/v1/logs" in base_endpoint:
        return base_endpoint
    if protocol in ("http/protobuf", "http"):
        if base_endpoint.endswith("/"):
            return f"{base_endpoint}v1/logs"
        else:
            return f"{base_endpoint}/v1/logs"
    return base_endpoint
