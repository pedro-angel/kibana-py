"""Unit tests for serializer classes."""

import json
from datetime import UTC, datetime

import pytest

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

        # Temporarily hide orjson from imports
        orjson_module = sys.modules.get("orjson")
        if orjson_module:
            sys.modules["orjson"] = None

        try:
            # Reload the serializer module to trigger the import logic
            import kibana.serializer

            importlib.reload(kibana.serializer)

            # Check that the default serializer is JSONSerializer
            from kibana.serializer import DEFAULT_SERIALIZERS, JSONSerializer

            serializer = DEFAULT_SERIALIZERS["application/json"]
            assert isinstance(serializer, JSONSerializer)

        finally:
            # Restore orjson module
            if orjson_module:
                sys.modules["orjson"] = orjson_module
            # Reload again to restore original state
            import kibana.serializer

            importlib.reload(kibana.serializer)
