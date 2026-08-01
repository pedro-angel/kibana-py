"""Serialization classes for Kibana client."""

from __future__ import annotations

import dataclasses
import enum
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

# Exact leaf types that never need a finiteness check or recursion, checked
# by identity (``type(value) in _INERT_LEAF_TYPES``) as a fast short-circuit
# in ``_reject_non_finite_floats`` -- see that function's docstring for why
# checking these *before* the ``enum``/``dataclasses`` branches matters for
# performance, and why identity (not ``isinstance``) is still safe there.
_INERT_LEAF_TYPES = frozenset((str, int, bool, type(None)))


def _reject_non_finite_floats(data: Any) -> None:
    """Raise ``SerializationError`` if any float anywhere in *data* is
    non-finite (NaN/Infinity/-Infinity).

    Used by :class:`OrjsonSerializer` -- orjson has no native option to
    reject these; it always silently serializes them as JSON ``null`` (see
    #79 and docs/evidence/serializer-parity-79.md for the measured overhead
    that led to shipping this walk rather than leaving the divergence).
    Walks the structure with an explicit stack rather than recursion (cheaper
    per docs/evidence/serializer-parity-79.md's measurements).

    The walk covers every type orjson will *actually serialize* the value
    of, not just plain JSON containers -- **the parity guarantee is "a
    non-finite float raises wherever a backend will actually serialize
    one", not "wherever the naive JSON containers are"**:

    - ``dict``/``list``/``tuple``: checked with ``isinstance`` rather than
      ``type(x) is dict``. orjson natively serializes ``dict``/``list``/
      ``tuple`` **subclasses** too (confirmed empirically -- ``OrderedDict``
      and a custom ``dict``/``list`` subclass all serialize the same as the
      plain type), so a stricter identity check would silently skip
      recursing into one of those and let a non-finite float hidden inside
      slip past this guard undetected.
    - ``dataclasses``: orjson serializes a dataclass **instance** natively
      (each field, recursively) with zero opt-in -- confirmed live: a
      dataclass with a NaN-valued float field serializes to ``null`` for
      that field with no exception. stdlib has no such native support
      (``JSONSerializer._default`` doesn't handle dataclasses, so it raises
      ``TypeError`` for one regardless of whether any field is finite) --
      that TypeError is correct, unrelated stdlib behavior, not part of
      this guard's job. Walked via ``dataclasses.is_dataclass(value) and
      not isinstance(value, type)`` (excluding the dataclass *class* object
      itself, which isn't a value a body would ever contain) +
      ``dataclasses.fields(value)``.
    - ``enum.Enum`` members: orjson serializes a member's ``.value``
      natively -- confirmed live: an ``Enum`` member whose value is
      ``float("nan")`` serializes to ``null``, no exception. A plain
      ``Enum`` member is never itself a ``float``/``str``/``int``/``bool``
      instance by exact type (``type(member) is not float`` even when the
      member's ``.value`` is one -- ``type()`` always returns the member's
      own class), but a mixin ``Enum`` (``class X(float, enum.Enum): ...``,
      or stdlib's ``IntEnum``/``StrEnum``) *would* pass ``isinstance(...,
      float)``/``isinstance(..., int)``/etc. Recursing into ``.value``
      whenever ``isinstance(value, enum.Enum)`` handles both the plain and
      the mixin shape uniformly through the same path, so this check must
      run before anything that would otherwise treat a mixin member as a
      plain ``float``/``int``/``str`` and skip looking at ``.value``.

    **Ordering is a deliberate, measured performance choice, not just
    correctness:** an earlier version checked ``isinstance(value,
    enum.Enum)`` and ``dataclasses.is_dataclass(value)`` *before* the
    ``dict``/``list``/inert-leaf checks, which measured 853% overhead on the
    representative ~9KB body (up from ~300%) -- because ``dataclasses.is_dataclass``
    is expensive per call, and with that ordering it ran on *every* string/int/
    bool/None leaf in the body (which vastly outnumber floats and containers
    in a typical body), not just on values that could plausibly be a
    dataclass. The current order -- float, then an identity check against
    ``_INERT_LEAF_TYPES`` (``str``/``int``/``bool``/``None``, which safely
    short-circuits without missing an ``Enum`` mixin: those never have
    ``type(member) is str``/``int``/``bool`` exactly, only ``isinstance``),
    then ``dict``, then ``list``/``tuple``, then ``Enum``, then
    ``dataclasses`` last -- measures back down to ~300% by reaching the
    expensive ``is_dataclass`` check only for values that already failed
    every cheaper, more-common check first. See
    docs/evidence/serializer-parity-79.md for both measurements.

    The float leaf check itself stays ``type(value) is float`` (not
    ``isinstance``): the opposite risk doesn't exist there, because orjson
    *rejects* real float subclasses (that aren't also an ``Enum``) outright
    as an unsupported type (``TypeError``) -- skipping one here just means
    that already-obscure case raises orjson's own exception instead of this
    one, never a silent success.

    Not verified: numpy scalar/array values. numpy is not a dependency of
    this project (orjson's ``OPT_SERIALIZE_NUMPY`` is opt-in and unused
    here) -- no claim is made about numpy inputs one way or the other. See
    docs/evidence/serializer-parity-79.md for a one-time probe in a
    disposable venv, if numpy behavior is ever needed.
    """
    stack: list[Any] = [data]
    while stack:
        value = stack.pop()
        value_type = type(value)
        if value_type is float:
            if not math.isfinite(value):
                raise SerializationError(_NON_FINITE_FLOAT_MESSAGE)
        elif value_type in _INERT_LEAF_TYPES:
            continue
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
        elif isinstance(value, enum.Enum):
            stack.append(value.value)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            stack.extend(getattr(value, f.name) for f in dataclasses.fields(value))


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
