"""Structured logging utilities for the Kibana client.

Provides a JSON log formatter that can be used independently of OpenTelemetry
for production-ready structured logging compatible with log aggregators
(ELK, Datadog, Splunk, etc.).

Example::

    import logging
    from kibana.logging import JSONFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.getLogger("kibana").addHandler(handler)
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production log aggregators.

    Outputs each log record as a single JSON line containing:
    - ``timestamp``: ISO 8601 timestamp in UTC
    - ``level``: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - ``logger``: Logger name
    - ``message``: Formatted log message
    - ``module``, ``function``, ``line``: Source location
    - ``exception``: Exception info (if present)
    - Any extra fields passed via the ``extra`` dict

    Example::

        >>> import logging
        >>> from kibana.logging import JSONFormatter
        >>>
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(JSONFormatter())
        >>> logger = logging.getLogger("kibana")
        >>> logger.addHandler(handler)
        >>> logger.setLevel(logging.DEBUG)
        >>>
        >>> logger.info("Connected to Kibana", extra={"host": "localhost:5601"})
        {"timestamp":"2026-02-28T08:00:00.000000Z","level":"INFO",...,"host":"localhost:5601"}
    """

    # Standard LogRecord attributes to exclude from extras
    _RESERVED_ATTRS = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }
    )

    def __init__(
        self,
        *,
        include_extras: bool = True,
        include_source: bool = True,
        include_process: bool = False,
        static_fields: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the JSON formatter.

        :param include_extras: Include user-supplied ``extra`` fields
        :param include_source: Include module/function/line info
        :param include_process: Include process and thread info
        :param static_fields: Static key-value pairs added to every record
        """
        super().__init__()
        self._include_extras = include_extras
        self._include_source = include_source
        self._include_process = include_process
        self._static_fields = static_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self._include_source:
            log_entry["module"] = record.module
            log_entry["function"] = record.funcName
            log_entry["line"] = record.lineno

        if self._include_process:
            log_entry["process"] = record.process
            log_entry["process_name"] = record.processName
            log_entry["thread"] = record.thread
            log_entry["thread_name"] = record.threadName

        # Add exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add stack info
        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        # Add static fields
        if self._static_fields:
            log_entry.update(self._static_fields)

        # Add user-supplied extra fields
        if self._include_extras:
            for key, value in record.__dict__.items():
                if key not in self._RESERVED_ATTRS and not key.startswith("_"):
                    try:
                        json.dumps(value)  # Test serializability
                        log_entry[key] = value
                    except (TypeError, ValueError):
                        log_entry[key] = str(value)

        return json.dumps(log_entry, default=str, ensure_ascii=False)
