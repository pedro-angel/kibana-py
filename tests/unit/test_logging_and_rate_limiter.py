"""Unit tests for the JSONFormatter and rate limiter modules."""

import json
import logging
import time

import pytest

from kibana._rate_limiter import AsyncRateLimiter, RateLimiter
from kibana.logging import JSONFormatter

# ─── JSONFormatter Tests ───────────────────────────────────────────────────────


class TestJSONFormatter:
    """Tests for JSONFormatter structured logging."""

    def test_basic_format(self):
        """Test basic log record formatting as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Hello world"
        assert data["line"] == 42
        assert "timestamp" in data

    def test_includes_source_by_default(self):
        """Test that source location is included by default."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="foo.py",
            lineno=10,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.funcName = "my_func"
        record.module = "foo"

        data = json.loads(formatter.format(record))

        assert data["module"] == "foo"
        assert data["function"] == "my_func"
        assert data["line"] == 10

    def test_exclude_source(self):
        """Test that source location can be excluded."""
        formatter = JSONFormatter(include_source=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )

        data = json.loads(formatter.format(record))

        assert "module" not in data
        assert "function" not in data
        assert "line" not in data

    def test_include_process(self):
        """Test that process/thread info can be included."""
        formatter = JSONFormatter(include_process=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )

        data = json.loads(formatter.format(record))

        assert "process" in data
        assert "thread" in data

    def test_exception_formatting(self):
        """Test that exceptions are properly formatted."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Something failed",
            args=(),
            exc_info=exc_info,
        )

        data = json.loads(formatter.format(record))

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "test error"
        assert isinstance(data["exception"]["traceback"], list)

    def test_extra_fields(self):
        """Test that extra fields from log record are included."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc-123"
        record.host = "localhost:5601"

        data = json.loads(formatter.format(record))

        assert data["request_id"] == "abc-123"
        assert data["host"] == "localhost:5601"

    def test_exclude_extras(self):
        """Test that extras can be excluded."""
        formatter = JSONFormatter(include_extras=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.custom_field = "should_not_appear"

        data = json.loads(formatter.format(record))

        assert "custom_field" not in data

    def test_static_fields(self):
        """Test that static fields are added to every record."""
        formatter = JSONFormatter(static_fields={"service": "kibana-py", "env": "test"})
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )

        data = json.loads(formatter.format(record))

        assert data["service"] == "kibana-py"
        assert data["env"] == "test"

    def test_output_is_single_line(self):
        """Test that output is a single JSON line (no newlines)."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="multi\nline\nmessage",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        # json.dumps uses \\n inside strings, so there should be no raw newlines
        assert "\n" not in output


# ─── RateLimiter Tests ─────────────────────────────────────────────────────────


class TestRateLimiter:
    """Tests for synchronous RateLimiter."""

    def test_init_valid(self):
        """Test initialization with valid rate."""
        limiter = RateLimiter(10.0)
        assert limiter.max_per_second == 10.0

    def test_init_invalid(self):
        """Test initialization with invalid rate raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            RateLimiter(0)

        with pytest.raises(ValueError, match="must be positive"):
            RateLimiter(-5)

    def test_acquire_does_not_block_with_tokens(self):
        """Test that acquire returns immediately when tokens are available."""
        limiter = RateLimiter(100.0)  # 100 rps — plenty of tokens

        start = time.monotonic()
        for _ in range(10):
            limiter.acquire()
        elapsed = time.monotonic() - start

        # Should complete nearly instantly (well under 1 second)
        assert elapsed < 0.5

    def test_acquire_throttles(self):
        """Test that acquire blocks when rate limit is hit."""
        limiter = RateLimiter(5.0)  # 5 rps

        # Exhaust all tokens quickly
        for _ in range(5):
            limiter.acquire()

        # Next acquire should take ~0.2 seconds
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start

        # Should have waited at least some time (but be lenient)
        assert elapsed >= 0.05


class TestAsyncRateLimiter:
    """Tests for async RateLimiter."""

    def test_init_valid(self):
        """Test initialization with valid rate."""
        limiter = AsyncRateLimiter(10.0)
        assert limiter.max_per_second == 10.0

    def test_init_invalid(self):
        """Test initialization with invalid rate raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            AsyncRateLimiter(0)

    @pytest.mark.asyncio
    async def test_acquire_does_not_block_with_tokens(self):
        """Test that acquire returns immediately when tokens are available."""
        limiter = AsyncRateLimiter(100.0)

        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_acquire_throttles(self):
        """Test that acquire awaits when rate limit is hit."""
        limiter = AsyncRateLimiter(5.0)

        for _ in range(5):
            await limiter.acquire()

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.05
