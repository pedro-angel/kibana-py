"""Comprehensive tests for space validation and caching functionality."""

import time
from unittest.mock import Mock, patch

import pytest

from kibana._sync.client.utils import NamespaceClient
from kibana.exceptions import InvalidSpaceIdError, SpaceNotFoundError


class TestSpaceValidationComprehensive:
    """Comprehensive tests for space validation functionality."""

    def test_validation_bypass_scenarios(self):
        """Test validation bypass scenarios."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        # Should not validate space existence when validation disabled, but format validation still applies
        path = client._build_space_path("/api/actions/connector", "valid-space")
        assert path == "/s/valid-space/api/actions/connector"

        # Should not call spaces client when validation disabled
        assert (
            not hasattr(mock_client, "spaces")
            or not getattr(mock_client.spaces, "get", Mock()).called
        )

    def test_validation_with_no_spaces_client_attribute(self):
        """Test validation when client has no spaces attribute."""
        mock_client = Mock()
        # Explicitly remove spaces attribute
        if hasattr(mock_client, "spaces"):
            delattr(mock_client, "spaces")

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Should not raise exception when no spaces client available
        client._validate_space_exists("marketing")

    def test_validation_with_spaces_client_none(self):
        """Test validation when spaces client is None."""
        mock_client = Mock()
        mock_client.spaces = None

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Should not raise exception when spaces client is None
        client._validate_space_exists("marketing")

    def test_cache_behavior_with_concurrent_access(self):
        """Test cache behavior with concurrent access patterns."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Simulate concurrent access to same space
        client._validate_space_exists("marketing")
        client._validate_space_exists("marketing")
        client._validate_space_exists("marketing")

        # Should only call API once due to caching
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify cache state is consistent
        assert client._space_cache["marketing"] is True
        assert "marketing" in client._cache_timestamps

    def test_cache_ttl_edge_cases(self):
        """Test cache TTL edge cases."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Test with custom TTL
        client._cache_ttl = 60  # 1 minute

        with patch("time.time") as mock_time:
            # First validation at time 0
            mock_time.return_value = 0
            client._validate_space_exists("marketing")

            # Validation at exactly TTL boundary (should still use cache)
            mock_time.return_value = 59.9
            client._validate_space_exists("marketing")

            # Should only be called once (cache hit)
            assert mock_spaces_client.get.call_count == 1

            # Validation just past TTL (should refresh cache)
            mock_time.return_value = 60.1
            client._validate_space_exists("marketing")

            # Should be called again (cache expired)
            assert mock_spaces_client.get.call_count == 2

    def test_cache_negative_result_persistence(self):
        """Test that negative cache results persist correctly."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("Space not found")

        client = NamespaceClient(mock_client, validate_spaces=True)

        # First validation should fail and cache negative result
        with pytest.raises(SpaceNotFoundError):
            client._validate_space_exists("nonexistent")

        # Multiple subsequent validations should use cached negative result
        for _ in range(3):
            with pytest.raises(SpaceNotFoundError):
                client._validate_space_exists("nonexistent")

        # API should only be called once
        mock_spaces_client.get.assert_called_once_with(id="nonexistent")

        # Verify negative cache state
        assert client._space_cache["nonexistent"] is False

    def test_cache_mixed_positive_negative_results(self):
        """Test cache with mixed positive and negative results."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client

        def mock_get(id):
            if id == "existing":
                return {"id": "existing", "name": "Existing Space"}
            else:
                raise Exception("Space not found")

        mock_spaces_client.get.side_effect = mock_get

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Validate existing space (should succeed and cache)
        client._validate_space_exists("existing")

        # Validate non-existing space (should fail and cache)
        with pytest.raises(SpaceNotFoundError):
            client._validate_space_exists("nonexistent")

        # Verify both are cached correctly
        assert client._space_cache["existing"] is True
        assert client._space_cache["nonexistent"] is False

        # Subsequent calls should use cache
        client._validate_space_exists("existing")
        with pytest.raises(SpaceNotFoundError):
            client._validate_space_exists("nonexistent")

        # Each space should only be validated once
        assert mock_spaces_client.get.call_count == 2

    def test_cache_clearing_specific_space_edge_cases(self):
        """Test cache clearing for specific spaces with edge cases."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=True)

        # Set up cache with multiple spaces
        client._space_cache.update({"marketing": True, "sales": False, "dev": True})
        client._cache_timestamps.update(
            {"marketing": time.time(), "sales": time.time(), "dev": time.time()}
        )

        # Clear non-existent space (should not error)
        client._clear_space_cache("nonexistent")

        # Verify other spaces remain
        assert len(client._space_cache) == 3
        assert len(client._cache_timestamps) == 3

        # Clear existing space
        client._clear_space_cache("sales")

        # Verify only sales was cleared
        assert "sales" not in client._space_cache
        assert "sales" not in client._cache_timestamps
        assert "marketing" in client._space_cache
        assert "dev" in client._space_cache

    def test_cache_clearing_all_spaces_when_empty(self):
        """Test clearing all spaces when cache is already empty."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=True)

        # Ensure cache is empty
        client._space_cache.clear()
        client._cache_timestamps.clear()

        # Clear all (should not error)
        client._clear_space_cache()

        # Verify still empty
        assert len(client._space_cache) == 0
        assert len(client._cache_timestamps) == 0

    def test_validation_error_types_comprehensive(self):
        """Test comprehensive error type handling in validation."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Test various "not found" error messages
        not_found_messages = [
            "Space not found",
            "404 Not Found",
            "Resource not found",
            "NOT FOUND",
            "space 'test' not found",
        ]

        for message in not_found_messages:
            mock_spaces_client.get.side_effect = Exception(message)

            with pytest.raises(SpaceNotFoundError) as exc_info:
                client._validate_space_exists("test")

            assert exc_info.value.space_id == "test"

            # Clear cache for next test
            client._clear_space_cache("test")

    def test_validation_non_404_errors_reraise(self):
        """Test that non-404 errors are properly re-raised."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Test various non-404 errors that should be re-raised
        other_errors = [
            "Authentication failed",
            "Forbidden",
            "Internal server error",
            "Connection timeout",
            "Invalid request",
        ]

        for error_message in other_errors:
            mock_spaces_client.get.side_effect = Exception(error_message)

            with pytest.raises(Exception) as exc_info:
                client._validate_space_exists("test")

            # Should re-raise original exception, not SpaceNotFoundError
            assert not isinstance(exc_info.value, SpaceNotFoundError)
            assert error_message in str(exc_info.value)

            # Clear cache for next test
            client._clear_space_cache("test")

    def test_space_id_format_validation_comprehensive(self):
        """Test comprehensive space ID format validation."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        # Test edge cases for valid space IDs
        valid_edge_cases = [
            "a",  # Single character
            "1",  # Single digit
            "a-b",  # Hyphen
            "a_b",  # Underscore
            "123",  # All digits
            "a1b2c3",  # Mixed alphanumeric
            "very-long-space-name-with-many-hyphens",  # Long name
            "space_with_many_underscores_here",  # Many underscores
            "a1-b2_c3-d4_e5",  # Mixed separators
        ]

        for space_id in valid_edge_cases:
            # Should not raise exception
            path = client._build_space_path("/api/test", space_id)
            assert path == f"/s/{space_id}/api/test"

    def test_space_id_format_validation_invalid_comprehensive(self):
        """Test comprehensive invalid space ID format validation."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        # Test edge cases for invalid space IDs
        invalid_edge_cases = [
            "",  # Empty string
            " ",  # Whitespace only
            "  ",  # Multiple whitespaces
            "\t",  # Tab
            "\n",  # Newline
            "Space With Spaces",  # Spaces
            "UPPERCASE",  # Uppercase
            "Mixed-Case",  # Mixed case
            "space.with.dots",  # Dots
            "space:with:colons",  # Colons
            "space/with/slashes",  # Forward slashes
            "space\\with\\backslashes",  # Backslashes
            "space@with@symbols",  # At symbols
            "space#with#hash",  # Hash symbols
            "space%with%percent",  # Percent symbols
            "space+with+plus",  # Plus symbols
            "space=with=equals",  # Equals symbols
            "space?with?question",  # Question marks
            "space&with&ampersand",  # Ampersands
            "space|with|pipe",  # Pipe symbols
            "space<with<less",  # Less than
            "space>with>greater",  # Greater than
            "space[with]brackets",  # Square brackets
            "space{with}braces",  # Curly braces
            "space(with)parens",  # Parentheses
            'space"with"quotes',  # Double quotes
            "space'with'quotes",  # Single quotes
            "space`with`backticks",  # Backticks
            "space~with~tilde",  # Tilde
            "space!with!exclamation",  # Exclamation
            "space,with,comma",  # Comma
            "space;with;semicolon",  # Semicolon
        ]

        for space_id in invalid_edge_cases:
            with pytest.raises(InvalidSpaceIdError) as exc_info:
                client._validate_space_id_format(space_id)

            assert exc_info.value.space_id == space_id
            assert "Invalid space ID format" in str(exc_info.value)

    def test_space_id_format_validation_non_string_types(self):
        """Test space ID format validation with non-string types."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        # Test non-string types
        non_string_types = [
            None,
            123,
            123.45,
            True,
            False,
            [],
            {},
            set(),
            object(),
        ]

        for space_id in non_string_types:
            with pytest.raises(InvalidSpaceIdError) as exc_info:
                client._validate_space_id_format(space_id)

            assert exc_info.value.space_id == space_id
            assert "Invalid space ID format" in str(exc_info.value)


class TestSpaceCachingPerformance:
    """Tests for space caching performance characteristics."""

    def test_cache_performance_with_many_spaces(self):
        """Test cache performance with many spaces."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "test", "name": "Test"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Validate many different spaces
        space_count = 100
        for i in range(space_count):
            space_id = f"space-{i}"
            client._validate_space_exists(space_id)

        # Each space should be validated exactly once
        assert mock_spaces_client.get.call_count == space_count

        # Cache should contain all spaces
        assert len(client._space_cache) == space_count
        assert len(client._cache_timestamps) == space_count

        # Subsequent validations should use cache
        for i in range(space_count):
            space_id = f"space-{i}"
            client._validate_space_exists(space_id)

        # No additional API calls should be made
        assert mock_spaces_client.get.call_count == space_count

    def test_cache_memory_cleanup_on_clear(self):
        """Test that cache memory is properly cleaned up."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=True)

        # Fill cache with many entries
        space_count = 1000
        current_time = time.time()

        for i in range(space_count):
            space_id = f"space-{i}"
            client._space_cache[space_id] = True
            client._cache_timestamps[space_id] = current_time

        # Verify cache is full
        assert len(client._space_cache) == space_count
        assert len(client._cache_timestamps) == space_count

        # Clear all cache
        client._clear_space_cache()

        # Verify complete cleanup
        assert len(client._space_cache) == 0
        assert len(client._cache_timestamps) == 0

        # Verify cache objects are still usable
        client._space_cache["test"] = True
        client._cache_timestamps["test"] = current_time

        assert len(client._space_cache) == 1
        assert len(client._cache_timestamps) == 1

    @patch("time.time")
    def test_cache_expiry_with_mixed_ages(self, mock_time):
        """Test cache expiry with entries of different ages."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "test", "name": "Test"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Create entries at different times
        mock_time.return_value = 0
        client._validate_space_exists("old-space")

        mock_time.return_value = 150  # 2.5 minutes later
        client._validate_space_exists("medium-space")

        mock_time.return_value = 250  # 4.17 minutes later
        client._validate_space_exists("recent-space")

        # All should be cached
        assert mock_spaces_client.get.call_count == 3

        # Move to time when old entry expires but others don't
        mock_time.return_value = 350  # 5.83 minutes from start

        # Old space should be revalidated (expired)
        client._validate_space_exists("old-space")
        assert mock_spaces_client.get.call_count == 4

        # Medium and recent should still use cache
        client._validate_space_exists("medium-space")
        client._validate_space_exists("recent-space")
        assert mock_spaces_client.get.call_count == 4

        # Move to time when medium entry also expires
        mock_time.return_value = 500  # 8.33 minutes from start

        # Medium space should be revalidated (expired)
        client._validate_space_exists("medium-space")
        assert mock_spaces_client.get.call_count == 5

        # Recent should still use cache
        client._validate_space_exists("recent-space")
        assert mock_spaces_client.get.call_count == 5
