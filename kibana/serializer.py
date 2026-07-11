"""Serialization classes for Kibana client."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from elastic_transport import NdjsonSerializer, TextSerializer


class Serializer:
    """Base serializer class."""

    mimetype: str = ""

    def dumps(self, data: Any) -> bytes:
        """Serialize data to bytes."""
        raise NotImplementedError

    def loads(self, data: bytes) -> Any:
        """Deserialize bytes to data."""
        raise NotImplementedError


class JSONSerializer(Serializer):
    """JSON serializer using standard library json module."""

    mimetype = "application/json"

    def dumps(self, data: Any) -> bytes:
        """
        Serialize data to JSON bytes.

        Byte/string bodies are passed through untouched so pre-encoded
        payloads survive. Handles datetime objects by converting them to
        ISO 8601 format.
        """
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        return json.dumps(data, default=self._default, ensure_ascii=False).encode(
            "utf-8"
        )

    def loads(self, data: bytes) -> Any:
        """Deserialize JSON bytes to Python objects."""
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    def _default(self, obj: Any) -> Any:
        """
        Default handler for objects that can't be serialized by json.

        Converts datetime objects to ISO 8601 format strings.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class KibanaNdjsonSerializer(NdjsonSerializer):
    """NDJSON serializer registered under Kibana's ``application/ndjson``.

    Kibana's saved-objects export/import APIs use the ``application/ndjson``
    mimetype (without the ``x-`` prefix elastic-transport registers by
    default), so the same newline-delimited JSON codec is exposed under
    that name too.
    """

    mimetype = "application/ndjson"


class RawSerializer(Serializer):
    """Pass-through serializer for pre-encoded request bodies.

    Used for mimetypes where the caller builds the body bytes itself
    (multipart uploads, arbitrary binary payloads). ``loads`` returns the
    raw bytes untouched.
    """

    mimetype = "application/octet-stream"

    def dumps(self, data: Any) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        raise TypeError(
            f"Body for mimetype {self.mimetype!r} must be bytes or str, "
            f"got {type(data).__name__}"
        )

    def loads(self, data: bytes) -> Any:
        return data


class MultipartSerializer(RawSerializer):
    """Pass-through serializer for ``multipart/form-data`` uploads.

    The caller is responsible for building the multipart body and setting a
    ``content-type`` header that includes the boundary; this serializer only
    forwards the already-encoded bytes to the transport.
    """

    mimetype = "multipart/form-data"


# Try to import orjson for optional high-performance serialization
_default_serializer: Serializer
try:
    import orjson

    class OrjsonSerializer(Serializer):
        """High-performance JSON serializer using orjson."""

        mimetype = "application/json"

        def dumps(self, data: Any) -> bytes:
            """
            Serialize data to JSON bytes using orjson.

            Byte/string bodies pass through untouched. orjson automatically
            handles datetime objects in ISO 8601 format.
            """
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return data.encode("utf-8")
            return orjson.dumps(data)  # type: ignore[no-any-return]

        def loads(self, data: bytes) -> Any:
            """Deserialize JSON bytes to Python objects using orjson."""
            if not data:
                return {}
            return orjson.loads(data)

    # Use OrjsonSerializer as default if available
    _default_serializer = OrjsonSerializer()

except ImportError:
    # Fall back to JSONSerializer if orjson is not available
    _default_serializer = JSONSerializer()


# Mapping of mimetypes to serializer instances
DEFAULT_SERIALIZERS = {
    "application/json": _default_serializer,
    "application/ndjson": KibanaNdjsonSerializer(),
    "application/x-ndjson": NdjsonSerializer(),
    "multipart/form-data": MultipartSerializer(),
    "application/octet-stream": RawSerializer(),
    "text/*": TextSerializer(),
}
