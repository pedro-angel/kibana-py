"""Serialization classes for Kibana client."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime
from typing import Any

from elastic_transport import NdjsonSerializer, TextSerializer

from kibana.exceptions import SerializationError

# Shared message text so both backends raise the identical shape for a
# non-finite float (see #79). stdlib's C-accelerated encoder raises this exact
# wording itself when ``allow_nan=False``; kept as one constant so a future
# change to either backend can't let the two drift apart silently.
_NON_FINITE_FLOAT_MESSAGE = "Out of range float values are not JSON compliant"


def _reject_non_finite_floats(data: Any) -> None:
    """Raise ``SerializationError`` if any float anywhere in *data* is
    non-finite (NaN/Infinity/-Infinity).

    Used by :class:`OrjsonSerializer` -- orjson has no native option to
    reject these; it always silently serializes them as JSON ``null`` (see
    #79 and docs/evidence/serializer-parity-79.md for the measured overhead
    that led to shipping this walk rather than leaving the divergence).
    Walks the structure with an explicit stack rather than recursion (cheaper
    per docs/evidence/serializer-parity-79.md's measurements).

    Container checks use ``isinstance`` rather than ``type(x) is dict``:
    orjson natively serializes ``dict``/``list``/``tuple`` **subclasses**
    too (confirmed empirically -- ``OrderedDict`` and a custom ``dict``/
    ``list`` subclass all serialize the same as the plain type), so a
    stricter identity check would silently skip recursing into one of those
    and let a non-finite float hidden inside slip past this guard
    undetected -- reintroducing the exact bug this guard exists to close,
    just scoped to container subclasses. The float leaf check stays
    ``type(value) is float`` (not ``isinstance``): the opposite risk doesn't
    exist there, because orjson *rejects* real float subclasses outright as
    an unsupported type (``TypeError``) -- skipping one here just means
    that already-obscure case raises orjson's own exception instead of
    this one, never a silent success.
    """
    stack: list[Any] = [data]
    while stack:
        value = stack.pop()
        if type(value) is float:
            if not math.isfinite(value):
                raise SerializationError(_NON_FINITE_FLOAT_MESSAGE)
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)


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
        payloads survive. Handles datetime and UUID objects by converting
        them to strings (ISO 8601 and canonical UUID form respectively).

        ``allow_nan=False`` makes NaN/Infinity/-Infinity raise
        :class:`~kibana.exceptions.SerializationError` instead of silently
        emitting the invalid-JSON tokens ``NaN``/``Infinity``/``-Infinity``
        (the stdlib default) -- Kibana would reject those with a 400 anyway,
        so raising client-side surfaces the problem immediately instead of
        as an opaque server error. See #79.
        """
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        try:
            return json.dumps(
                data, default=self._default, ensure_ascii=False, allow_nan=False
            ).encode("utf-8")
        except ValueError as e:
            raise SerializationError(_NON_FINITE_FLOAT_MESSAGE) from e

    def loads(self, data: bytes) -> Any:
        """Deserialize JSON bytes to Python objects."""
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    def _default(self, obj: Any) -> Any:
        """
        Default handler for objects that can't be serialized by json.

        Converts datetime objects to ISO 8601 format strings and UUID
        objects to their canonical string form -- matching orjson's native
        handling of both types (see #79) so a body containing either
        serializes identically regardless of which backend is active.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
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

            Byte/string bodies pass through untouched. orjson natively
            handles ``datetime`` (ISO 8601) and ``uuid.UUID`` (canonical
            string form) objects the same way :class:`JSONSerializer`'s
            ``_default`` hook now does -- see #79.

            orjson has no option to reject non-finite floats -- it always
            silently serializes NaN/Infinity/-Infinity as JSON ``null``
            (confirmed against the installed orjson 3.11.9; upstream feature
            request ijl/orjson#170 is open, unresolved). ``_reject_non_finite_floats``
            walks the body first and raises
            :class:`~kibana.exceptions.SerializationError` -- the same
            exception type and message :class:`JSONSerializer` raises via
            ``allow_nan=False`` -- instead of letting orjson silently
            substitute ``null``. This does cost real CPU (measured at ~4x
            orjson's own raw serialization time on a representative ~9KB
            body -- see docs/evidence/serializer-parity-79.md): accepted
            as the right trade because (a) the absolute added cost is a few
            microseconds, negligible against any real network round trip,
            (b) orjson with this guard remains faster than the stdlib
            fallback this project already ships automatically when orjson
            isn't installed, and (c) silently discarding a caller's NaN/Inf
            value is exactly the defect #79 exists to remove -- on the
            backend most installs actually use.
            """
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return data.encode("utf-8")
            _reject_non_finite_floats(data)
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
