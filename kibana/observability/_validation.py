"""APM connectivity validation and error handling utilities."""

import re

from kibana.observability._imports import logger


def _validate_apm_connectivity(
    endpoint: str,
    headers: dict[str, str],
    protocol: str,
    timeout: int = 5,
    max_retries: int = 2,
) -> bool:
    """Validate APM server connectivity with retry logic and timeout handling."""
    import socket
    import time
    from urllib.parse import urlparse

    try:
        parsed = urlparse(endpoint)
        host = parsed.hostname or "localhost"
        if parsed.port:
            port = parsed.port
        elif protocol == "grpc":
            port = 4317
        else:
            port = 4318

        for attempt in range(max_retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.debug(
                        f"APM server connectivity validated: {host}:{port} "
                        f"(attempt {attempt + 1})"
                    )
                    return True
                else:
                    if attempt < max_retries:
                        delay = 2**attempt
                        logger.debug(
                            f"APM server not reachable at {host}:{port}, "
                            f"retrying in {delay}s "
                            f"(attempt {attempt + 1}/{max_retries + 1})"
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"APM server not reachable at {host}:{port} "
                            f"after {max_retries + 1} attempts"
                        )
            except TimeoutError:
                if attempt < max_retries:
                    delay = 2**attempt
                    logger.debug(
                        f"APM server connection timeout to {host}:{port}, "
                        f"retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"APM server connection timeout to {host}:{port} "
                        f"after {max_retries + 1} attempts"
                    )
            except Exception as e:
                if attempt < max_retries:
                    delay = 2**attempt
                    logger.debug(
                        f"APM server connection error to {host}:{port}: {e}, "
                        f"retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"APM server connection error to {host}:{port}: {e} "
                        f"after {max_retries + 1} attempts"
                    )
        return False
    except Exception as e:
        logger.warning(f"APM server connectivity validation failed: {e}")
        return False


def validate_apm_server_availability(
    endpoint: str, headers: dict[str, str] | None = None, protocol: str = "grpc"
) -> bool:
    """Public function to validate APM server availability.

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
