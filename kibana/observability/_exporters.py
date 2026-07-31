"""Exporter creation helpers for OTLP trace and log exporters."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from kibana.observability._imports import (
    _HTTP_OTLP_PROTOCOLS,
    GRPC_EXPORTER_AVAILABLE,
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
        if not GRPC_EXPORTER_AVAILABLE:
            raise ImportError(
                "gRPC OTLP exporter not available. Install with: "
                "pip install opentelemetry-exporter-otlp-proto-grpc"
            )
        return OTLPSpanExporter(**exporter_kwargs)
    elif protocol in _HTTP_OTLP_PROTOCOLS:
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
    elif protocol in _HTTP_OTLP_PROTOCOLS:
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


def _get_signal_endpoint(base_endpoint: str, protocol: str, signal_path: str) -> str:
    """Get the appropriate OTLP signal endpoint for a base endpoint and protocol.

    Shared core for :func:`_get_log_endpoint` and :func:`_get_trace_endpoint`:
    for ``http/protobuf`` (and its ``http`` alias), appends ``signal_path``
    (e.g. ``/v1/traces``) to a base endpoint that doesn't already end in it.

    The endpoint is parsed with :func:`urllib.parse.urlsplit` so both the
    "already has it" check and the append operate on the URL's *path*
    component only, never on the raw string:

    * **Anchoring.** The check is anchored to the end of the path (modulo a
      single trailing slash) via ``str.endswith``, not a plain substring
      test. A substring test would wrongly treat an endpoint that merely
      *contains* the signal path somewhere in the middle of an unrelated
      route (e.g. a gateway path like ``http://gw:8200/foo/v1/traces/bar``,
      or a differently-named sibling path like ``.../v1/traces-ingest/foo``)
      as already-correct and leave it un-suffixed -- silently reproducing the
      wrong-path defect these helpers exist to fix. The comparison is
      case-sensitive by design: URL paths are case-sensitive, so
      ``/V1/Traces`` is genuinely not ``/v1/traces`` and still needs the real
      path appended.
    * **Query/fragment preservation.** Checking or appending against the raw
      string would corrupt an endpoint that has a query string or fragment
      (e.g. ``http://h/v1/traces?foo=bar``: an anchored check against the raw
      string sees it ending in ``?foo=bar``, not ``/v1/traces``, and would
      append *after* the query, producing ``...?foo=bar/v1/traces``).
      Operating on ``urlsplit(...).path`` and reassembling with
      :func:`urllib.parse.urlunsplit` keeps the query and fragment exactly
      where they were.

    gRPC has no such HTTP resource path -- the endpoint is a bare
    ``host:port`` -- so it passes through untouched regardless (returned
    verbatim, never reassembled).
    """
    parsed = urlsplit(base_endpoint)
    path = parsed.path
    if path.rstrip("/").endswith(signal_path):
        return base_endpoint
    if protocol in _HTTP_OTLP_PROTOCOLS:
        if path.endswith("/"):
            new_path = f"{path}{signal_path.lstrip('/')}"
        else:
            new_path = f"{path}{signal_path}"
        return urlunsplit(parsed._replace(path=new_path))
    return base_endpoint


def _get_log_endpoint(base_endpoint: str, protocol: str) -> str:
    """Get the appropriate log endpoint based on the base endpoint and protocol."""
    return _get_signal_endpoint(base_endpoint, protocol, "/v1/logs")


def _get_trace_endpoint(base_endpoint: str, protocol: str) -> str:
    """Get the appropriate trace endpoint based on the base endpoint and protocol.

    Mirrors :func:`_get_log_endpoint` via the shared :func:`_get_signal_endpoint`
    core.
    """
    return _get_signal_endpoint(base_endpoint, protocol, "/v1/traces")
