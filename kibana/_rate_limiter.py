"""Rate limiting for Kibana API requests.

Provides a token-bucket rate limiter that can be used to prevent
overwhelming a Kibana cluster with too many requests per second.

Example::

    from kibana import Kibana

    # Limit to 10 requests per second
    client = Kibana(
        hosts=["http://localhost:5601"],
        api_key="your_api_key",
        max_requests_per_second=10,
    )
"""

from __future__ import annotations

import asyncio
import threading
import time


class RateLimiter:
    """Thread-safe token-bucket rate limiter for synchronous operations.

    Uses the token-bucket algorithm: tokens are added at a fixed rate,
    and each request consumes one token. If no tokens are available,
    the caller blocks until one becomes available.

    :param max_per_second: Maximum requests per second (must be positive)
    """

    def __init__(self, max_per_second: float) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")

        self._max_per_second = max_per_second
        self._tokens = max_per_second  # Start full
        self._max_tokens = max_per_second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire a token, blocking until one is available.

        Loops until a full token can actually be consumed so concurrent
        callers cannot slip through after a single shared wait.
        """
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # Time until the next full token accrues
                wait = (1.0 - self._tokens) / self._max_per_second

            time.sleep(max(wait, 0.0))

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._max_tokens, self._tokens + elapsed * self._max_per_second
        )
        self._last_refill = now

    @property
    def max_per_second(self) -> float:
        """Return the configured rate limit."""
        return self._max_per_second


class AsyncRateLimiter:
    """Async-compatible token-bucket rate limiter.

    Equivalent to :class:`RateLimiter` but uses ``asyncio.sleep`` instead
    of ``time.sleep`` so it does not block the event loop.

    :param max_per_second: Maximum requests per second (must be positive)
    """

    def __init__(self, max_per_second: float) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")

        self._max_per_second = max_per_second
        self._tokens = max_per_second
        self._max_tokens = max_per_second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, awaiting until one is available.

        Loops until a full token can actually be consumed so concurrent
        callers cannot slip through after a single shared wait.
        """
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # Time until the next full token accrues
                wait = (1.0 - self._tokens) / self._max_per_second

            await asyncio.sleep(max(wait, 0.0))

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._max_tokens, self._tokens + elapsed * self._max_per_second
        )
        self._last_refill = now

    @property
    def max_per_second(self) -> float:
        """Return the configured rate limit."""
        return self._max_per_second


__all__ = ["RateLimiter", "AsyncRateLimiter"]
