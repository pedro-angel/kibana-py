"""Serialization classes for Kibana client."""

import json
from datetime import datetime
from typing import Any


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

        Handles datetime objects by converting them to ISO 8601 format.
        """
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

            orjson automatically handles datetime objects in ISO 8601 format.
            """
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
}
