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

    - ``dict``/``list``: checked with ``isinstance`` rather than ``type(x)
      is dict``. orjson natively serializes ``dict``/``list`` **subclasses**
      too (confirmed empirically -- ``OrderedDict`` and a custom ``dict``/
      ``list`` subclass all serialize the same as the plain type), so a
      stricter identity check would silently skip recursing into one of
      those and let a non-finite float hidden inside slip past this guard
      undetected.
    - ``tuple``: checked by **identity** (``type(value) is tuple``), *not*
      ``isinstance`` -- unlike ``dict``/``list``, orjson rejects any tuple
      *subclass* outright as an unsupported type (confirmed empirically:
      a ``namedtuple`` raises ``TypeError: Type is not JSON serializable``
      from orjson itself, non-finite float inside or not). Walking into a
      ``namedtuple`` via ``isinstance`` and raising this guard's own
      ``SerializationError`` for a NaN inside it would be a *misleading*
      error -- the real, correct failure for that body is orjson's own
      unsupported-type ``TypeError``, not a float complaint. Plain
      ``tuple`` instances (exact type) are still walked, since orjson does
      serialize those (as a JSON array) same as a ``list``.
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

    **Cycle- and DAG-safety (round 3):** a permanent, add-and-never-remove
    ``id()``-keyed ``visited`` set tracks every ``dict``/``list``/``tuple``/
    dataclass instance the walk has already started expanding. This is
    deliberately *not* push/pop-scoped (a "currently on the path" set that
    would be removed again on backtrack): the same object always yields the
    same verdict regardless of how many times or which path reaches it, so
    skipping a re-visit is *correct*, not just an optimization. Three
    things fall out of this one rule together:

    1. A self-referential container (``d["self"] = d``) used to hang this
       walk forever -- pre-fix, orjson's own cycle detection
       (``TypeError: Recursion limit reached``, confirmed live) would have
       fired instantly, but this guard runs *before* ``orjson.dumps`` and
       never gave it the chance to. With the visited set, the second visit
       to the same object is skipped instead of re-expanded, so the walk
       always terminates; ``orjson.dumps`` then raises its own cycle error
       afterward, honestly, on the merits of the actual cycle -- this guard
       never invents a misleading message for it.
    2. A DAG (the same sub-object reachable via multiple paths, not a
       cycle -- e.g. a shared sub-dict referenced from two list elements)
       is walked once per *distinct object* instead of once per *path* to
       it, making the walk linear in graph size instead of exponential in
       path count.
    3. ``id()`` is safe to key on here specifically because every object
       the walk can reach is kept alive for the walk's entire duration by
       the references the root ``data`` argument holds (directly or
       transitively) -- CPython never reuses an id while a reference to the
       object is still live, so no two distinct containers visited during
       one call can ever collide on id(), and the set is thrown away (not
       cached across calls) the moment this function returns.

    Not verified: numpy scalar/array values. numpy is not a dependency of
    this project (orjson's ``OPT_SERIALIZE_NUMPY`` is opt-in and unused
    here) -- no claim is made about numpy inputs one way or the other. See
    docs/evidence/serializer-parity-79.md for a one-time probe in a
    disposable venv, if numpy behavior is ever needed.
    """
    stack: list[Any] = [data]
    # See "Cycle- and DAG-safety" above: permanent (add, never remove),
    # id()-keyed, scoped to this one call only.
    visited: set[int] = set()
    while stack:
        value = stack.pop()
        value_type = type(value)
        if value_type is float:
            if not math.isfinite(value):
                raise SerializationError(_NON_FINITE_FLOAT_MESSAGE)
        elif value_type in _INERT_LEAF_TYPES:
            continue
        elif isinstance(value, dict):
            if id(value) in visited:
                continue
            visited.add(id(value))
            stack.extend(value.values())
        elif isinstance(value, list) or value_type is tuple:
            if id(value) in visited:
                continue
            visited.add(id(value))
            stack.extend(value)
        elif isinstance(value, enum.Enum):
            stack.append(value.value)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            if id(value) in visited:
                continue
            visited.add(id(value))
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

        Only a ``ValueError`` whose message is *actually* the out-of-range-float
        one gets ``_NON_FINITE_FLOAT_MESSAGE`` (round 3 fix): ``json.dumps``'s
        own cycle detection (``check_circular``, on by default) also raises a
        plain ``ValueError`` -- ``"Circular reference detected"`` -- for a
        self-referential body, which a blanket ``except ValueError`` used to
        mislabel as a bad float too (confirmed live). Any other ``ValueError``
        is wrapped honestly with its own message instead, matching this
        module's other error-wrapping call sites (``str(e)``, chained via
        ``from e``) rather than inventing a misleading one.

        Matched by **prefix**, not exact equality (round 4 fix): CPython
        3.11's C-accelerated encoder raises exactly
        ``"Out of range float values are not JSON compliant"``, but 3.12+
        appends the offending value's ``repr`` -- ``"...: nan"``/``"...:
        inf"``/``"...: -inf"`` (confirmed live across 3.11.15/3.12.13/
        3.13.12/3.14.3; see docs/evidence/serializer-parity-79.md's round-4
        section). An exact-equality check missed this suffix on 3.12+ and
        fell through to the "wrap honestly" branch instead, which still
        produced a *technically accurate but non-identical* message
        (`"...compliant: nan"` instead of the canonical
        ``_NON_FINITE_FLOAT_MESSAGE``) -- breaking the cross-backend/
        cross-version message-identity guarantee on every Python newer
        than 3.11. ``str(e).startswith(_NON_FINITE_FLOAT_MESSAGE)`` matches
        on every supported version, and the raised message is always the
        canonical constant regardless of which version's suffix (if any)
        triggered the match, so the identity guarantee holds across
        versions as well as across backends.

        ``.encode("utf-8")`` runs *after* the try, not inside it: a lone
        (unpaired) UTF-16 surrogate character is a valid Python ``str`` code
        point that ``json.dumps`` happily round-trips as-is with
        ``ensure_ascii=False``, but cannot be UTF-8 encoded --
        ``UnicodeEncodeError`` (itself a ``ValueError`` subclass) used to be
        caught by the same blanket handler and mislabeled as a bad float too
        (confirmed live). It now propagates as the encoding error it actually
        is, unrelated to this guard's job.
        """
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        try:
            encoded = json.dumps(
                data, default=self._default, ensure_ascii=False, allow_nan=False
            )
        except ValueError as e:
            if str(e).startswith(_NON_FINITE_FLOAT_MESSAGE):
                raise SerializationError(_NON_FINITE_FLOAT_MESSAGE) from e
            raise SerializationError(str(e)) from e
        return encoded.encode("utf-8")

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
