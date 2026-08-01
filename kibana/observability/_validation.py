"""APM connectivity validation and error handling utilities."""

from __future__ import annotations

import re

from kibana.observability._imports import _HTTP_OTLP_PROTOCOLS, logger

# Hard ceiling, in seconds, on the *total* wall-clock time
# `_validate_apm_connectivity` may spend across every attempt and every
# backoff sleep combined -- independent of the caller's own
# `timeout`/`max_retries` values. `configure_opentelemetry()`'s
# `validate_endpoint` path (on by default) calls this function
# synchronously, before telemetry is set up and before the caller's own code
# runs, so this budget is also the worst-case extra startup latency an
# unreachable or misconfigured APM host adds to every process that imports
# this package with validation on (issue #83). Pre-fix, the default
# `timeout=5` x `max_retries=2` (3 attempts) plus exponential backoff
# (2**0 + 2**1 = 3s) could block for up to ~18s against a host that silently
# drops packets instead of refusing the connection -- long enough to look
# like a hang, not a validation check. 5s keeps that worst case bounded to
# something noticeable but tolerable at process startup, while still
# comfortably exceeding a healthy APM server's actual handshake time
# (sub-100ms, confirmed against the local Elastic APM server during
# battle-testing -- see docs/evidence/apm-probe-83.md). Attempts and backoff
# sleeps remain useful for genuinely transient failures (a fast "connection
# refused" leaves budget for retries within the cap); the cap only cuts a
# retry/sleep short once the endpoint has already proven itself slow enough
# that letting the caller's own `timeout`/`max_retries` run to completion
# would blow past a sane startup-latency ceiling.
_PROBE_TOTAL_BUDGET_SECONDS: float = 5.0


def _validate_apm_connectivity(
    endpoint: str,
    headers: dict[str, str],
    protocol: str,
    timeout: int = 5,
    max_retries: int = 2,
) -> bool:
    """Validate APM server connectivity with retry logic and timeout handling.

    Uses `socket.create_connection`, which resolves `endpoint`'s host via
    `getaddrinfo` (honoring `/etc/hosts`) and tries every address family it
    resolves to -- IPv4 and IPv6 alike -- rather than forcing IPv4 only, so
    an IPv6-only APM host is reachable (issue #83).

    Regardless of `timeout`/`max_retries`, the total wall-clock time spent
    across all attempts and backoff sleeps is hard-capped at
    `_PROBE_TOTAL_BUDGET_SECONDS` seconds -- see that constant's comment for
    the justification. This function never blocks its caller (notably
    `configure_opentelemetry`'s synchronous `validate_endpoint` check)
    beyond that cap, even against an endpoint that hangs instead of
    refusing the connection.
    """
    import socket
    import time
    from urllib.parse import urlparse

    try:
        parsed = urlparse(endpoint)
        host = parsed.hostname or "localhost"
        if parsed.port:
            port = parsed.port
        elif protocol in _HTTP_OTLP_PROTOCOLS:
            port = 4318
        else:
            # Anything that isn't a recognized HTTP variant (including an
            # unrecognized/invalid protocol string) assumes the gRPC port.
            # This mirrors the same bias in configure_opentelemetry's
            # default-endpoint fallback (kibana/observability/_config.py) --
            # the module's own default `protocol` (when unspecified) is
            # "grpc", so an unrecognized value is treated the same way rather
            # than silently guessing the HTTP port. `_HTTP_OTLP_PROTOCOLS` is
            # the single shared source of truth for "HTTP-shaped" protocols
            # (kibana/observability/_imports.py), reused here and in
            # _config.py/_exporters.py rather than re-hardcoded.
            port = 4317

        start = time.monotonic()

        for attempt in range(max_retries + 1):
            remaining = _PROBE_TOTAL_BUDGET_SECONDS - (time.monotonic() - start)
            if remaining <= 0:
                logger.warning(
                    f"APM server connectivity probe budget "
                    f"({_PROBE_TOTAL_BUDGET_SECONDS}s) exhausted before "
                    f"reaching {host}:{port} (attempt {attempt + 1})"
                )
                break

            attempt_timeout = min(timeout, remaining)
            try:
                sock = socket.create_connection((host, port), timeout=attempt_timeout)
                sock.close()
                logger.debug(
                    f"APM server connectivity validated: {host}:{port} "
                    f"(attempt {attempt + 1})"
                )
                return True
            except OSError as e:
                # Covers connection refused, `TimeoutError`/`socket.timeout`
                # (an `OSError` subclass), and DNS failures
                # (`socket.gaierror`, also an `OSError` subclass) uniformly --
                # `create_connection` raises `OSError` for all of them.
                remaining = _PROBE_TOTAL_BUDGET_SECONDS - (time.monotonic() - start)
                if attempt < max_retries and remaining > 0:
                    delay = min(2**attempt, remaining)
                    logger.debug(
                        f"APM server not reachable at {host}:{port}: {e}, "
                        f"retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"APM server not reachable at {host}:{port}: {e} "
                        f"after {attempt + 1} attempt(s)"
                    )
        return False
    except Exception as e:
        logger.warning(f"APM server connectivity validation failed: {e}")
        return False


def validate_apm_server_availability(
    endpoint: str, headers: dict[str, str] | None = None, protocol: str = "grpc"
) -> bool:
    """Public function to validate APM server availability.

    Reaches `endpoint` over both IPv4 and IPv6 (whichever the host resolves
    to) and never blocks the caller beyond `_PROBE_TOTAL_BUDGET_SECONDS`
    seconds, even against an unresponsive endpoint -- see
    `_validate_apm_connectivity` for the details.

    Example:
        >>> from kibana.observability import validate_apm_server_availability
        >>> if validate_apm_server_availability("http://localhost:8200"):
        ...     configure_opentelemetry(enabled=True)
    """
    import kibana.observability as _obs

    if headers is None:
        headers = {}
    return _obs._validate_apm_connectivity(endpoint, headers, protocol)


def _handle_telemetry_error(operation: str, error: Exception) -> None:
    """Handle telemetry errors gracefully without interrupting main execution."""
    error_str = str(error).lower()
    if any(
        auth_term in error_str
        for auth_term in [
            "unauthorized",
            "authentication",
            "401",
            "403",
            "invalid token",
        ]
    ):
        masked_error = _mask_sensitive_info(str(error))
        logger.error(f"APM authentication failed during {operation}: {masked_error}")
        logger.error(
            "Check ELASTIC_APM_SECRET_TOKEN or OTEL_EXPORTER_OTLP_HEADERS configuration"
        )
    elif any(
        network_term in error_str
        for network_term in ["connection", "timeout", "network", "unreachable"]
    ):
        logger.warning(f"APM network error during {operation}: {error}")
        logger.warning("Check APM server availability and network connectivity")
    else:
        logger.error(f"APM configuration error during {operation}: {error}")

    logger.debug("Continuing without telemetry to avoid interrupting main execution")


def _mask_sensitive_info(text: str) -> str:
    """Mask sensitive information in error messages and logs."""
    text = re.sub(r"Bearer\s+[a-zA-Z0-9+/=]{8,}", "Bearer [REDACTED]", text)
    text = re.sub(
        r'(["\']?(?:token|key|secret)["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9+/=]{8,}(["\']?)',
        r"\1[REDACTED]\2",
        text,
        flags=re.IGNORECASE,
    )
    return text
