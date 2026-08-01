"""Unit tests for serializer classes."""

import dataclasses
import enum
import importlib.util
import json
import signal
import uuid
from collections import OrderedDict, namedtuple
from datetime import UTC, datetime

import pytest

from kibana.exceptions import SerializationError
from kibana.serializer import DEFAULT_SERIALIZERS, JSONSerializer, Serializer


class TestBaseSerializer:
    """Tests for base Serializer class."""

    def test_dumps_not_implemented(self):
        """Test that base Serializer.dumps raises NotImplementedError."""
        serializer = Serializer()

        with pytest.raises(NotImplementedError):
            serializer.dumps({"test": "data"})

    def test_loads_not_implemented(self):
        """Test that base Serializer.loads raises NotImplementedError."""
        serializer = Serializer()

        with pytest.raises(NotImplementedError):
            serializer.loads(b'{"test": "data"}')

    def test_mimetype_default(self):
        """Test that base Serializer has empty mimetype."""
        serializer = Serializer()
        assert serializer.mimetype == ""


class TestJSONSerializer:
    """Tests for JSONSerializer class."""

    def test_dumps_simple_dict(self):
        """Test serializing a simple dictionary."""
        serializer = JSONSerializer()
        data = {"key": "value", "number": 42}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        assert json.loads(result) == data

    def test_dumps_nested_structure(self):
        """Test serializing nested data structures."""
        serializer = JSONSerializer()
        data = {"nested": {"list": [1, 2, 3], "dict": {"inner": "value"}}}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        assert json.loads(result) == data

    def test_dumps_datetime_iso8601(self):
        """Test datetime serialization to ISO 8601 format."""
        serializer = JSONSerializer()
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=UTC)
        data = {"timestamp": dt}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert parsed["timestamp"] == "2024-01-15T10:30:45.123456+00:00"

    def test_dumps_datetime_naive(self):
        """Test naive datetime serialization."""
        serializer = JSONSerializer()
        dt = datetime(2024, 1, 15, 10, 30, 45)
        data = {"timestamp": dt}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        parsed = json.loads(result)
        # Naive datetime should still be serialized
        assert "2024-01-15T10:30:45" in parsed["timestamp"]

    def test_dumps_list_with_datetimes(self):
        """Test serializing list containing datetime objects."""
        serializer = JSONSerializer()
        dt1 = datetime(2024, 1, 15, tzinfo=UTC)
        dt2 = datetime(2024, 2, 20, tzinfo=UTC)
        data = {"dates": [dt1, dt2]}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert len(parsed["dates"]) == 2
        assert "2024-01-15" in parsed["dates"][0]
        assert "2024-02-20" in parsed["dates"][1]

    def test_loads_simple_dict(self):
        """Test deserializing a simple dictionary."""
        serializer = JSONSerializer()
        data = b'{"key": "value", "number": 42}'
        result = serializer.loads(data)

        assert result == {"key": "value", "number": 42}

    def test_loads_nested_structure(self):
        """Test deserializing nested data structures."""
        serializer = JSONSerializer()
        data = b'{"nested": {"list": [1, 2, 3], "dict": {"inner": "value"}}}'
        result = serializer.loads(data)

        assert result["nested"]["list"] == [1, 2, 3]
        assert result["nested"]["dict"]["inner"] == "value"

    def test_loads_list(self):
        """Test deserializing a list."""
        serializer = JSONSerializer()
        data = b'[1, 2, 3, "four"]'
        result = serializer.loads(data)

        assert result == [1, 2, 3, "four"]

    def test_loads_invalid_json(self):
        """Test error handling with invalid JSON."""
        serializer = JSONSerializer()
        invalid_data = b"{invalid json}"

        with pytest.raises(json.JSONDecodeError):
            serializer.loads(invalid_data)

    def test_dumps_loads_roundtrip(self):
        """Test roundtrip serialization and deserialization."""
        serializer = JSONSerializer()
        original = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        serialized = serializer.dumps(original)
        deserialized = serializer.loads(serialized)

        assert deserialized == original

    def test_mimetype(self):
        """Test that mimetype is set correctly."""
        serializer = JSONSerializer()
        assert serializer.mimetype == "application/json"

    def test_dumps_non_serializable_object_raises_type_error(self):
        """Test that non-serializable objects raise TypeError."""
        serializer = JSONSerializer()

        # Create a non-serializable object (e.g., a custom class instance)
        class CustomObject:
            pass

        data = {"obj": CustomObject()}

        with pytest.raises(TypeError) as exc_info:
            serializer.dumps(data)

        assert "is not JSON serializable" in str(exc_info.value)

    def test_dumps_set_raises_type_error(self):
        """Test that sets raise TypeError since they're not JSON serializable."""
        serializer = JSONSerializer()
        data = {"items": {1, 2, 3}}  # set is not JSON serializable

        with pytest.raises(TypeError) as exc_info:
            serializer.dumps(data)

        assert "is not JSON serializable" in str(exc_info.value)

    def test_dumps_complex_number_raises_type_error(self):
        """Test that complex numbers raise TypeError."""
        serializer = JSONSerializer()
        data = {"complex": complex(1, 2)}

        with pytest.raises(TypeError) as exc_info:
            serializer.dumps(data)

        assert "is not JSON serializable" in str(exc_info.value)


class TestOrjsonSerializer:
    """Tests for OrjsonSerializer class (if available)."""

    def test_orjson_available(self):
        """Test if orjson is available and can be imported."""
        try:
            import importlib.util

            if importlib.util.find_spec("orjson") is None:
                pytest.skip("orjson not installed")

            from kibana.serializer import OrjsonSerializer

            assert OrjsonSerializer is not None
        except ImportError:
            pytest.skip("orjson not installed")

    def test_dumps_simple_dict(self):
        """Test serializing with orjson."""
        try:
            from kibana.serializer import OrjsonSerializer
        except ImportError:
            pytest.skip("orjson not installed")

        serializer = OrjsonSerializer()
        data = {"key": "value", "number": 42}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        assert json.loads(result) == data

    def test_dumps_datetime_iso8601(self):
        """Test datetime serialization with orjson."""
        try:
            from kibana.serializer import OrjsonSerializer
        except ImportError:
            pytest.skip("orjson not installed")

        serializer = OrjsonSerializer()
        dt = datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=UTC)
        data = {"timestamp": dt}
        result = serializer.dumps(data)

        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert "2024-01-15T10:30:45" in parsed["timestamp"]

    def test_loads_simple_dict(self):
        """Test deserializing with orjson."""
        try:
            from kibana.serializer import OrjsonSerializer
        except ImportError:
            pytest.skip("orjson not installed")

        serializer = OrjsonSerializer()
        data = b'{"key": "value", "number": 42}'
        result = serializer.loads(data)

        assert result == {"key": "value", "number": 42}

    def test_mimetype(self):
        """Test that mimetype is set correctly."""
        try:
            from kibana.serializer import OrjsonSerializer
        except ImportError:
            pytest.skip("orjson not installed")

        serializer = OrjsonSerializer()
        assert serializer.mimetype == "application/json"


class TestDefaultSerializers:
    """Tests for DEFAULT_SERIALIZERS mapping."""

    def test_default_serializers_exists(self):
        """Test that DEFAULT_SERIALIZERS mapping exists."""
        assert DEFAULT_SERIALIZERS is not None
        assert isinstance(DEFAULT_SERIALIZERS, dict)

    def test_application_json_mapped(self):
        """Test that application/json mimetype is mapped."""
        assert "application/json" in DEFAULT_SERIALIZERS
        serializer = DEFAULT_SERIALIZERS["application/json"]
        assert serializer.mimetype == "application/json"

    def test_default_serializer_works(self):
        """Test that default serializer can serialize and deserialize."""
        serializer = DEFAULT_SERIALIZERS["application/json"]
        data = {"test": "value"}

        serialized = serializer.dumps(data)
        deserialized = serializer.loads(serialized)

        assert deserialized == data

    def test_default_serializer_type(self):
        """Test that default serializer is either JSONSerializer or OrjsonSerializer."""
        serializer = DEFAULT_SERIALIZERS["application/json"]

        # Should be either JSONSerializer or OrjsonSerializer depending on availability
        try:
            import importlib.util

            if importlib.util.find_spec("orjson") is not None:
                from kibana.serializer import OrjsonSerializer

                # If orjson is available, default should be OrjsonSerializer
                assert isinstance(serializer, JSONSerializer | OrjsonSerializer)
            else:
                # If orjson is not available, default should be JSONSerializer
                assert isinstance(serializer, JSONSerializer)
        except ImportError:
            # If orjson is not available, default should be JSONSerializer
            assert isinstance(serializer, JSONSerializer)

    def test_fallback_to_json_serializer_when_orjson_unavailable(self):
        """Test that the module falls back to JSONSerializer when orjson is unavailable."""
        import importlib
        import sys

        import kibana.serializer

        # Snapshot the module's original attributes. reload() rebuilds the
        # serializer classes as *new* objects; restoring this snapshot in the
        # finally (instead of a second reload) puts the original class
        # identities back, so tests that run afterward and compare against
        # import-time references still match under any test order. See #34.
        original_attrs = kibana.serializer.__dict__.copy()

        # Temporarily hide orjson from imports
        orjson_module = sys.modules.get("orjson")
        if orjson_module:
            sys.modules["orjson"] = None

        try:
            # Reload the serializer module to trigger the fallback import logic
            importlib.reload(kibana.serializer)

            # Check that the default serializer is JSONSerializer
            from kibana.serializer import DEFAULT_SERIALIZERS, JSONSerializer

            serializer = DEFAULT_SERIALIZERS["application/json"]
            assert isinstance(serializer, JSONSerializer)

        finally:
            # Restore orjson module
            if orjson_module:
                sys.modules["orjson"] = orjson_module
            # Restore the exact original module state (original class identities)
            # instead of reloading, which would create fresh identities.
            kibana.serializer.__dict__.clear()
            kibana.serializer.__dict__.update(original_attrs)


# --- #79: stdlib/orjson request-body JSON semantics parity -----------------
#
# The bug: request-body JSON semantics diverged by backend.
#   - NaN/Infinity/-Infinity: stdlib (pre-fix) emitted the invalid-JSON
#     tokens ``NaN``/``Infinity``/``-Infinity`` (Kibana 400s on those);
#     orjson silently serialized them as JSON ``null`` (silent data loss).
#   - UUID: stdlib raised bare ``TypeError`` (no ``_default`` support);
#     orjson already serialized it natively to its canonical string form.
#
# "Forcing the stdlib path" for this matrix means instantiating
# ``JSONSerializer`` directly -- it is unconditionally defined regardless of
# whether orjson is installed (see kibana/serializer.py), so no module-reload
# seam is needed the way ``test_fallback_to_json_serializer_when_orjson_unavailable``
# above needs one for testing *selection* logic. This matrix tests *behavior*,
# so it instantiates each serializer class directly -- the same seam
# TestJSONSerializer/TestOrjsonSerializer already use.
#
# Both NaN/Infinity and UUID are now fixed identically on both backends (see
# ``_reject_non_finite_floats`` and ``OrjsonSerializer.dumps`` in
# kibana/serializer.py, and docs/evidence/serializer-parity-79.md for the
# overhead measurements and the decision to ship the guard rather than leave
# the divergence). No xfail/skip is needed for the non-finite-float cases
# below any more -- both backends are asserted to raise identically.


def _orjson_installed() -> bool:
    return importlib.util.find_spec("orjson") is not None


def _make_serializer(backend: str):
    """Build a fresh serializer instance for *backend* ("stdlib"/"orjson")."""
    if backend == "stdlib":
        return JSONSerializer()
    from kibana.serializer import OrjsonSerializer

    return OrjsonSerializer()


def _backend_param(backend: str) -> "pytest.param":
    if backend == "orjson" and not _orjson_installed():
        return pytest.param(
            backend, marks=pytest.mark.skip(reason="orjson not installed"), id=backend
        )
    return pytest.param(backend, id=backend)


NON_FINITE_BACKENDS = [_backend_param("stdlib"), _backend_param("orjson")]
PARITY_BACKENDS = [_backend_param("stdlib"), _backend_param("orjson")]


class TestNonFiniteFloatParity:
    """#79 requirement 1: NaN/Infinity/-Infinity anywhere in a body raises a
    clear, catchable ``SerializationError`` -- not a silent ``null``
    (orjson, pre-fix) or an invalid-JSON token Kibana 400s on (stdlib,
    pre-fix) -- identically on both backends.
    """

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(float("nan"), id="nan"),
            pytest.param(float("inf"), id="inf"),
            pytest.param(float("-inf"), id="neg-inf"),
        ],
    )
    def test_top_level_non_finite_float_raises_serialization_error(
        self, backend, value
    ):
        serializer = _make_serializer(backend)
        with pytest.raises(SerializationError):
            serializer.dumps({"v": value})

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    def test_nested_non_finite_float_raises_serialization_error(self, backend):
        """NaN two levels deep, inside a list -- not just a top-level value."""
        serializer = _make_serializer(backend)
        with pytest.raises(SerializationError):
            serializer.dumps({"outer": {"inner": [1, 2, float("nan")]}})

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    def test_non_finite_float_in_list_raises_serialization_error(self, backend):
        serializer = _make_serializer(backend)
        with pytest.raises(SerializationError):
            serializer.dumps({"values": [1.0, 2.0, float("-inf")]})

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    def test_non_finite_float_inside_dict_subclass_still_raises(self, backend):
        """Regression pin: a guard using ``type(x) is dict`` would silently
        skip recursing into a dict *subclass* (confirmed empirically that
        orjson itself serializes ``OrderedDict``/custom dict subclasses
        natively, same as plain ``dict``) -- reintroducing the exact silent
        data-loss bug this fix closes, just scoped to container subclasses.
        """
        serializer = _make_serializer(backend)
        with pytest.raises(SerializationError):
            serializer.dumps(OrderedDict({"a": 1, "b": float("nan")}))

    def test_error_type_and_message_identical_across_backends(self):
        """#79 requirement 3: the *same* exception type and *same* message
        shape on both backends -- not just "both raise something"."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        with pytest.raises(SerializationError) as stdlib_exc:
            JSONSerializer().dumps({"v": float("nan")})
        with pytest.raises(SerializationError) as orjson_exc:
            OrjsonSerializer().dumps({"v": float("nan")})

        assert type(stdlib_exc.value) is type(orjson_exc.value) is SerializationError
        assert str(stdlib_exc.value) == str(orjson_exc.value)

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    def test_error_message_shape(self, backend):
        """Pin the exact message both backends raise so a refactor can't
        silently change the wording (or let the two drift apart) without a
        test catching it."""
        serializer = _make_serializer(backend)
        with pytest.raises(SerializationError) as exc_info:
            serializer.dumps({"v": float("nan")})
        assert str(exc_info.value) == "Out of range float values are not JSON compliant"

    @pytest.mark.parametrize("backend", NON_FINITE_BACKENDS)
    def test_normal_floats_still_serialize(self, backend):
        """Guard against a too-broad fix rejecting ordinary finite floats."""
        serializer = _make_serializer(backend)
        result = serializer.dumps({"v": 3.14, "neg": -2.5, "zero": 0.0})
        assert json.loads(result) == {"v": 3.14, "neg": -2.5, "zero": 0.0}


class TestUUIDSerializationParity:
    """#79 requirement 2: UUID values serialize identically (to their string
    form) on both backends."""

    @pytest.mark.parametrize("backend", PARITY_BACKENDS)
    def test_uuid_serializes_to_canonical_string(self, backend):
        serializer = _make_serializer(backend)
        u = uuid.UUID("5284d425-7649-4ae6-baec-dfeaf0419cf7")
        result = serializer.dumps({"id": u})
        assert json.loads(result) == {"id": "5284d425-7649-4ae6-baec-dfeaf0419cf7"}

    @pytest.mark.parametrize("backend", PARITY_BACKENDS)
    def test_uuid_in_list_serializes_to_canonical_strings(self, backend):
        serializer = _make_serializer(backend)
        ids = [uuid.UUID(int=1), uuid.UUID(int=2)]
        result = serializer.dumps({"ids": ids})
        assert json.loads(result) == {"ids": [str(ids[0]), str(ids[1])]}

    @pytest.mark.parametrize("backend", PARITY_BACKENDS)
    def test_nested_uuid_serializes_to_canonical_string(self, backend):
        serializer = _make_serializer(backend)
        u = uuid.UUID(int=42)
        result = serializer.dumps({"outer": {"inner": {"id": u}}})
        assert json.loads(result) == {"outer": {"inner": {"id": str(u)}}}

    def test_cross_backend_uuid_output_is_value_identical(self):
        """Same input, same decoded JSON value on both backends -- not just
        'both happen to round-trip', which a message-shape regression on one
        backend could still pass."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        data = {
            "id": uuid.UUID("5284d425-7649-4ae6-baec-dfeaf0419cf7"),
            "nested": {"ids": [uuid.UUID(int=1), uuid.UUID(int=2)]},
        }

        stdlib_out = JSONSerializer().dumps(data)
        orjson_out = OrjsonSerializer().dumps(data)

        assert json.loads(stdlib_out) == json.loads(orjson_out)


class TestCrossBackendEqualityForNormalBodies:
    """A normal (no NaN/Infinity, no UUID edge case) body must decode to the
    same value on both backends -- the #79 fix must not regress ordinary
    payloads."""

    def test_normal_body_equal_across_backends(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        data = {
            "name": "test",
            "count": 42,
            "score": 3.14,
            "active": True,
            "tags": ["a", "b", "c"],
            "nested": {"key": "value", "list": [1, 2, 3]},
            "nothing": None,
        }
        stdlib_out = JSONSerializer().dumps(data)
        orjson_out = OrjsonSerializer().dumps(data)
        assert json.loads(stdlib_out) == json.loads(orjson_out) == data


# --- #79 fix-round (spec review BLOCKER): dataclasses and Enum members -----
#
# orjson serializes a dataclass **instance** (each field, recursively) and an
# Enum **member's** ``.value`` NATIVELY, with zero opt-in -- confirmed live
# (see docs/evidence/serializer-parity-79.md's fix-round section): a NaN
# hidden in either silently became JSON ``null``, the same defect #79 exists
# to close, just for two more types ``_reject_non_finite_floats`` didn't
# originally walk into.
#
# Parity boundary (intentional, documented, not a gap): stdlib has no
# ``_default`` support for dataclasses or Enum at all, so ``JSONSerializer``
# raises ``TypeError`` for either regardless of whether any field/value is
# finite -- that TypeError is stdlib's own pre-existing, correct behavior for
# an unsupported type (unchanged, out of scope), not a divergence this guard
# needs to close. The guarantee this issue makes is "a non-finite float
# raises wherever a backend will actually serialize one" -- stdlib never
# serializes a dataclass/Enum at all, so there is nothing to guard there.


@dataclasses.dataclass
class _PointForTests:
    x: float
    y: float


@dataclasses.dataclass
class _OuterForTests:
    inner: _PointForTests
    tag: str


class _ColorForTests(enum.Enum):
    OK = 1.0
    BAD = float("nan")


class TestDataclassAndEnumNonFiniteFloatParity:
    """Fix-round regression tests for the spec-review BLOCKER."""

    def test_orjson_rejects_nan_inside_dataclass_field(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        with pytest.raises(SerializationError) as exc_info:
            OrjsonSerializer().dumps({"p": _PointForTests(x=1.0, y=float("nan"))})
        # [round-3 minor] message-content pin, not just the exception type --
        # a dataclass field is exactly the case the BLOCKER added coverage for.
        assert str(exc_info.value) == "Out of range float values are not JSON compliant"

    def test_orjson_rejects_nan_inside_nested_dataclass_field(self):
        """NaN two dataclass levels deep, not just the outer one."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        outer = _OuterForTests(inner=_PointForTests(x=1.0, y=float("-inf")), tag="t")
        with pytest.raises(SerializationError):
            OrjsonSerializer().dumps({"o": outer})

    def test_orjson_rejects_nan_inside_dataclass_in_list(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        points = [_PointForTests(x=1.0, y=2.0), _PointForTests(x=1.0, y=float("inf"))]
        with pytest.raises(SerializationError):
            OrjsonSerializer().dumps({"points": points})

    def test_orjson_accepts_dataclass_with_all_finite_fields(self):
        """Guard against a too-broad fix rejecting ordinary dataclasses."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        result = OrjsonSerializer().dumps({"p": _PointForTests(x=1.0, y=2.0)})
        assert json.loads(result) == {"p": {"x": 1.0, "y": 2.0}}

    def test_orjson_rejects_nan_inside_enum_value(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        with pytest.raises(SerializationError) as exc_info:
            OrjsonSerializer().dumps({"c": _ColorForTests.BAD})
        # [round-3 minor] message-content pin, not just the exception type --
        # an Enum value is exactly the case the BLOCKER added coverage for.
        assert str(exc_info.value) == "Out of range float values are not JSON compliant"

    def test_orjson_accepts_enum_with_finite_value(self):
        """Guard against a too-broad fix rejecting ordinary Enum members."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        result = OrjsonSerializer().dumps({"c": _ColorForTests.OK})
        assert json.loads(result) == {"c": 1.0}

    def test_stdlib_raises_typeerror_for_dataclass_regardless_of_field_values(self):
        """Pin the parity boundary: stdlib's TypeError for a dataclass is
        pre-existing, correct, unrelated behavior -- not part of this guard,
        and not expected to become a SerializationError."""
        with pytest.raises(TypeError):
            JSONSerializer().dumps({"p": _PointForTests(x=1.0, y=1.0)})

    def test_stdlib_raises_typeerror_for_enum_regardless_of_value(self):
        with pytest.raises(TypeError):
            JSONSerializer().dumps({"c": _ColorForTests.OK})


# --- #79 round 3 (code-quality review): cycles, error honesty, tuple subclasses ---
#
# [BLOCKER 1] ``_reject_non_finite_floats`` had no cycle tracking -- a
# self-referential dict/list hung the thread forever (pre-fix, orjson's own
# cycle detection -- ``TypeError: Recursion limit reached``, confirmed live
# -- fired instantly; the guard now runs *first* and never returned to let
# it). Fixed with a permanent (add, never remove) id()-based visited set for
# containers -- see ``_reject_non_finite_floats``'s docstring for why this is
# correct (not just an optimization) and why id() is safe to key on here.
#
# [BLOCKER 2] stdlib's blanket ``except ValueError`` mislabeled ANY
# ``ValueError`` as the non-finite-float message -- including
# ``ValueError: Circular reference detected`` (stdlib's own, pre-existing
# cycle detection, confirmed live -- unrelated to floats) and
# ``UnicodeEncodeError`` (a ``ValueError`` subclass) from the ``.encode
# ("utf-8")`` that used to run *inside* the try (a lone surrogate character
# becomes "out of range float"). Fixed: ``.encode`` moved outside the try;
# inside, only a `ValueError` whose message actually matches the real
# out-of-range-float text gets the float message -- anything else is
# wrapped honestly with its own message, chained via ``from e``.
#
# [MAJOR] The guard walked into tuple *subclasses* via ``isinstance``, but
# orjson rejects any tuple subclass outright (confirmed live:
# ``TypeError: Type is not JSON serializable: Point`` for a namedtuple) --
# so a namedtuple with a NaN field got a misleading "bad float" instead of
# the correct unsupported-type error. Fixed: ``type(value) is tuple``
# identity for the tuple branch (plain tuples still walked); ``isinstance``
# stays for ``dict``/``list`` only, where orjson genuinely treats subclasses
# transparently (confirmed live in round 1/round 2's fix-round section).


def _run_with_alarm_timeout(seconds: int, fn, *args, **kwargs):
    """Run ``fn(*args, **kwargs)``, but fail fast instead of hanging if it
    doesn't return within *seconds*.

    Used to prove a cycle guard actually terminates rather than looping
    forever -- per the code-quality review's own instruction ("use a
    timeout guard in the test"), not an actual multi-minute hang in the
    suite. POSIX-only (``SIGALRM``); skips on a platform without it (this
    project's CI matrix doesn't include Windows -- see .github/workflows).
    """
    if not hasattr(signal, "alarm"):
        pytest.skip("signal.alarm not available on this platform")

    class _HangTimeout(Exception):
        pass

    def _handler(signum, frame):
        raise _HangTimeout(f"did not return within {seconds}s -- suspected hang")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class TestCycleSafety:
    """[BLOCKER 1] A self-referential dict/list must not hang the guard."""

    def test_self_referential_dict_does_not_hang_orjson(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        d: dict = {}
        d["self"] = d

        with pytest.raises(Exception) as exc_info:
            _run_with_alarm_timeout(5, OrjsonSerializer().dumps, d)
        # A prompt, real error -- never a hang, and never our own
        # SerializationError misrepresenting an unrelated cycle as a bad float.
        assert "suspected hang" not in str(exc_info.value)
        assert not isinstance(exc_info.value, SerializationError)

    def test_self_referential_list_does_not_hang_orjson(self):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        lst: list = []
        lst.append(lst)

        with pytest.raises(Exception) as exc_info:
            _run_with_alarm_timeout(5, OrjsonSerializer().dumps, {"l": lst})
        assert "suspected hang" not in str(exc_info.value)
        assert not isinstance(exc_info.value, SerializationError)

    def test_self_referential_dict_does_not_hang_stdlib(self):
        """stdlib's own ``json.dumps`` already detects cycles
        (``check_circular``, on by default) -- this was never actually
        broken on the stdlib side, but pins it as a parity regression test
        alongside the orjson fix, and exercises the BLOCKER 2 error-honesty
        fix at the same time (see ``TestStdlibErrorHonesty`` below for the
        message-content assertion)."""
        d: dict = {}
        d["self"] = d

        with pytest.raises(Exception) as exc_info:
            _run_with_alarm_timeout(5, JSONSerializer().dumps, d)
        assert "suspected hang" not in str(exc_info.value)

    def test_diamond_shaped_dag_is_not_exponential(self):
        """Not a cycle -- the same sub-object reachable via multiple paths
        (a DAG). The permanent visited-set makes this linear in the number
        of distinct objects instead of exponential in the number of paths
        to reach them. Empirically calibrated (see docs/evidence/serializer-parity-79.md):
        24 levels of doubling fan-out times out (>5s) against a
        push-without-memoization walk, and completes in a fraction of a
        second with the visited set -- so this genuinely fails pre-fix
        rather than merely asserting a shape that happens to stay cheap at
        a smaller depth."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        shared: dict = {"v": 1.0}
        # 24 levels of doubling fan-out through the *same* shared object --
        # 2**24 (~16.7M) paths to `shared` without memoization, 1 distinct
        # object with it.
        level = shared
        for _ in range(24):
            level = {"a": level, "b": level}

        # Must complete quickly -- proves the memoization, not just correctness.
        _run_with_alarm_timeout(5, OrjsonSerializer().dumps, level)


class TestStdlibErrorHonesty:
    """[BLOCKER 2] stdlib's ``except ValueError`` must not mislabel an
    unrelated ``ValueError`` as the non-finite-float message.
    """

    def test_circular_dict_does_not_get_the_float_message(self):
        d: dict = {}
        d["self"] = d

        with pytest.raises(SerializationError) as exc_info:
            JSONSerializer().dumps(d)

        assert str(exc_info.value) != "Out of range float values are not JSON compliant"
        assert "circular" in str(exc_info.value).lower()

    def test_lone_surrogate_does_not_get_the_float_message(self):
        """A lone (unpaired) UTF-16 surrogate is a valid Python str code
        point but cannot be UTF-8 encoded -- ``json.dumps`` itself succeeds
        (the value passes straight through with ``ensure_ascii=False``);
        ``.encode("utf-8")`` on the result is what fails
        (``UnicodeEncodeError``, a ``ValueError`` subclass)."""
        with pytest.raises(Exception) as exc_info:
            JSONSerializer().dumps({"v": "\ud800"})

        # Whatever surfaces, it must not be mislabeled as the float message.
        assert str(exc_info.value) != "Out of range float values are not JSON compliant"
        if isinstance(exc_info.value, SerializationError):
            assert "Out of range float" not in str(exc_info.value)

    def test_normal_finite_nan_message_is_unaffected(self):
        """Regression pin: the real non-finite-float case must still get
        its own message, unchanged, after narrowing the except-ValueError
        branch to match on it specifically."""
        with pytest.raises(SerializationError) as exc_info:
            JSONSerializer().dumps({"v": float("nan")})
        assert str(exc_info.value) == "Out of range float values are not JSON compliant"


class TestTupleSubclassNotWalked:
    """[MAJOR] The guard must not walk into tuple *subclasses*
    (``namedtuple``) -- orjson rejects any tuple subclass outright as an
    unsupported type, so walking into one and finding a NaN must not
    produce a misleading "bad float" instead of the correct
    unsupported-type error. Plain tuples (exact type) are still walked.
    """

    def test_namedtuple_with_nan_raises_orjsons_own_type_error_not_serialization_error(
        self,
    ):
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        Point = namedtuple("Point", ["x", "y"])
        with pytest.raises(TypeError) as exc_info:
            OrjsonSerializer().dumps({"p": Point(x=1.0, y=float("nan"))})
        assert not isinstance(exc_info.value, SerializationError)

    def test_plain_tuple_with_nan_still_raises_serialization_error(self):
        """Regression pin: plain tuples (not subclasses) must still be
        walked and still reject a non-finite float."""
        if not _orjson_installed():
            pytest.skip("orjson not installed")
        from kibana.serializer import OrjsonSerializer

        with pytest.raises(SerializationError):
            OrjsonSerializer().dumps({"t": (1.0, float("nan"))})
