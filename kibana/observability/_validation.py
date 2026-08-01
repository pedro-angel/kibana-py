"""APM connectivity validation and error handling utilities."""

from __future__ import annotations

import queue
import re
import threading

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
#
# This is enforced as a true wall-clock deadline for the CALLER, not merely
# "whatever `socket.create_connection`'s own `timeout` kwarg happens to
# bound": `create_connection` resolves the host via `getaddrinfo` *before*
# opening a socket at all, and `getaddrinfo` takes no timeout of its own --
# an unresponsive/misbehaving DNS resolver can hang indefinitely there,
# ahead of the connect-phase timeout we pass in ever applying (fix-round
# finding on issue #83). Each attempt therefore runs on a background daemon
# thread, and the calling thread waits for it with this budget as a hard
# ceiling (see `_probe_attempt_worker` below) -- if the worker hasn't
# reported back by the deadline, the attempt counts as failed and the
# worker is abandoned, not joined. The one honest residual: an abandoned
# worker stuck in `getaddrinfo` keeps running (until the OS resolver itself
# gives up) on its own daemon thread -- confirmed empirically that this
# does *not* block interpreter shutdown (a daemon thread is not joined at
# exit, unlike e.g. a bare `concurrent.futures.ThreadPoolExecutor`, whose
# worker threads are joined by its own atexit hook and would hang process
# exit in this same scenario -- verified directly, which is why this uses a
# plain `threading.Thread(daemon=True)` instead). So the guarantee this
# constant buys is strictly about the CALLER's wall-clock wait, not about
# how long the abandoned background thread itself keeps running.
#
# That residual COMPOUNDS under repeated calls against a persistently-hung
# host: each call that times out abandons one more probe thread, and none
# of them are ever joined or cancelled, so a caller that polls
# `validate_apm_server_availability`/`_validate_apm_connectivity` in a loop
# against a chronically unreachable/slow-DNS host accumulates one
# still-running daemon thread per call, for as long as the OS resolver
# takes to give up on each -- measured directly: 5 sequential calls against
# a stub that hangs left 5 such threads alive at once. This package's own
# call site is one-shot -- `configure_opentelemetry`'s `validate_endpoint`
# check runs once at startup, not in a loop -- so it never hits this; a
# caller that wraps this function in its own polling loop against a
# chronically-hung host is the one that would accumulate threads, and
# should own that concern itself (e.g. by not polling a host it already
# knows is chronically unreachable). No new mechanism added for this here:
# the fix is documenting the residual precisely, not a caller this package
# doesn't have.
_PROBE_TOTAL_BUDGET_SECONDS: float = 5.0


def _probe_attempt_worker(
    host: str, port: int, timeout: float, outcome: queue.Queue[Exception | None]
) -> None:
    """Attempt one connection on a background thread and report the outcome.

    Runs entirely off the calling thread so the caller can bound its own
    wait with a hard wall-clock deadline (see `_PROBE_TOTAL_BUDGET_SECONDS`)
    instead of trusting `socket.create_connection`'s `timeout` kwarg to
    cover the whole attempt -- that kwarg does not bound `getaddrinfo`,
    which `create_connection` calls first.

    Puts `None` on `outcome` on success, the raised exception on failure.
    Closes the socket itself on success -- the caller only ever cared about
    reachability, not the connection -- so a very-late arrival (one that
    completes only after the calling thread has already given up and moved
    on) cleans up after itself instead of leaking an open, un-closed socket.
    """
    import socket

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        outcome.put(None)
    except Exception as e:
        outcome.put(e)


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

    Regardless of `timeout`/`max_retries`, the total wall-clock time this
    function makes its CALLER wait -- across all attempts and backoff
    sleeps -- is hard-capped at `_PROBE_TOTAL_BUDGET_SECONDS` seconds, and
    that cap is a true wall-clock deadline enforced from the caller's side
    (each attempt runs on a background daemon thread; the calling thread
    waits on it with the remaining budget as a timeout and moves on if it
    isn't back in time), not merely whatever `create_connection`'s own
    `timeout` kwarg happens to bound -- that kwarg cannot cover the
    `getaddrinfo` resolution step, which has no timeout of its own and can
    hang independently of it. See `_PROBE_TOTAL_BUDGET_SECONDS`'s comment
    for the full justification, including the one honest residual: an
    abandoned attempt that's still stuck resolving/connecting keeps running
    in the background (confirmed harmless to the caller and to interpreter
    shutdown, since it's a daemon thread that is never joined). This
    function never blocks its caller (notably `configure_opentelemetry`'s
    synchronous `validate_endpoint` check) beyond that cap, even against an
    endpoint that hangs instead of refusing the connection -- whether it
    hangs during DNS resolution or during the TCP handshake itself.
    """
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

            # The attempt (DNS resolution + TCP connect together) runs on
            # its own background thread; this thread waits for it with
            # `attempt_timeout` as a hard wall-clock deadline of its own,
            # rather than trusting `create_connection`'s `timeout` kwarg
            # alone to bound the whole thing (see `_probe_attempt_worker`
            # and `_PROBE_TOTAL_BUDGET_SECONDS`'s comment -- issue #83
            # fix-round).
            outcome: queue.Queue[Exception | None] = queue.Queue(maxsize=1)
            worker = threading.Thread(
                target=_probe_attempt_worker,
                args=(host, port, attempt_timeout, outcome),
                daemon=True,
                name="kibana-apm-probe-attempt",
            )
            worker.start()
            try:
                error = outcome.get(timeout=attempt_timeout)
            except queue.Empty:
                # Still resolving/connecting past our own deadline. The
                # worker is abandoned here, deliberately not joined -- it's
                # a daemon thread, so it cannot block interpreter shutdown,
                # and it will finish (or not) entirely on its own, in the
                # background. This is the honest residual documented on
                # `_PROBE_TOTAL_BUDGET_SECONDS`: the guarantee is about this
                # (the caller's) wall-clock wait, not the abandoned
                # thread's lifetime.
                error = TimeoutError(
                    f"connection attempt to {host}:{port} (including DNS "
                    f"resolution) did not complete within "
                    f"{attempt_timeout:.1f}s"
                )

            if error is None:
                logger.debug(
                    f"APM server connectivity validated: {host}:{port} "
                    f"(attempt {attempt + 1})"
                )
                return True

            # Covers connection refused, `TimeoutError`/`socket.timeout` (an
            # `OSError` subclass) from within `create_connection` itself,
            # DNS failures (`socket.gaierror`, also an `OSError` subclass),
            # and the synthetic deadline-exceeded `TimeoutError` above
            # uniformly.
            remaining = _PROBE_TOTAL_BUDGET_SECONDS - (time.monotonic() - start)
            if attempt < max_retries and remaining > 0:
                delay = min(2**attempt, remaining)
                logger.debug(
                    f"APM server not reachable at {host}:{port}: {error}, "
                    f"retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                time.sleep(delay)
            else:
                logger.warning(
                    f"APM server not reachable at {host}:{port}: {error} "
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
