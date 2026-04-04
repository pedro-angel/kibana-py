"""Tests for NamespaceClient space support functionality."""

import time
from unittest.mock import Mock, patch

import pytest

from kibana._sync.client.utils import NamespaceClient
from kibana.exceptions import InvalidSpaceIdError, SpaceNotFoundError


class TestNamespaceClientSpaceSupport:
    """Test space support functionality in NamespaceClient."""

    def test_init_with_default_space_id(self):
        """Test initialization with default space ID."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, default_space_id="marketing")

        assert client._default_space_id == "marketing"
        assert client._validate_spaces is True  # Default value

    def test_init_with_validation_disabled(self):
        """Test initialization with validation disabled."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        assert client._validate_spaces is False

    def test_build_space_path_without_space(self):
        """Test path building without space."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        path = client._build_space_path("/api/actions/connector")
        assert path == "/api/actions/connector"

    def test_build_space_path_with_space(self):
        """Test path building with space."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        path = client._build_space_path("/api/actions/connector", "marketing")
        assert path == "/s/marketing/api/actions/connector"

    def test_build_space_path_with_default_space(self):
        """Test path building with default space."""
        mock_client = Mock()
        client = NamespaceClient(
            mock_client, default_space_id="default-space", validate_spaces=False
        )

        path = client._build_space_path("/api/actions/connector")
        assert path == "/s/default-space/api/actions/connector"

    def test_build_space_path_override_default_space(self):
        """Test path building with space override."""
        mock_client = Mock()
        client = NamespaceClient(
            mock_client, default_space_id="default-space", validate_spaces=False
        )

        path = client._build_space_path("/api/actions/connector", "override-space")
        assert path == "/s/override-space/api/actions/connector"

    def test_build_space_path_invalid_space_id_raises_error(self):
        """Test that invalid space ID raises InvalidSpaceIdError."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        with pytest.raises(InvalidSpaceIdError) as exc_info:
            client._build_space_path("/api/actions/connector", "Invalid Space")

        assert exc_info.value.space_id == "Invalid Space"
        assert "Invalid space ID format" in str(exc_info.value)

    def test_validate_space_exists_success(self):
        """Test successful space validation."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Should not raise any exception
        client._validate_space_exists("marketing")

        # Verify API was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

    def test_validate_space_exists_not_found(self):
        """Test space validation when space doesn't exist."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("Space not found")

        client = NamespaceClient(mock_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            client._validate_space_exists("nonexistent")

        assert exc_info.value.space_id == "nonexistent"
        assert "Space not found" in str(exc_info.value)

    def test_validate_space_exists_404_error(self):
        """Test space validation with 404 error."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("404 Not Found")

        client = NamespaceClient(mock_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            client._validate_space_exists("nonexistent")

        assert exc_info.value.space_id == "nonexistent"

    def test_validate_space_exists_other_error_reraises(self):
        """Test that non-404 errors are re-raised."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("Authentication failed")

        client = NamespaceClient(mock_client, validate_spaces=True)

        with pytest.raises(Exception) as exc_info:
            client._validate_space_exists("marketing")

        assert "Authentication failed" in str(exc_info.value)

    def test_validate_space_exists_no_spaces_client(self):
        """Test space validation when no spaces client is available."""
        mock_client = Mock()
        mock_client.spaces = None

        client = NamespaceClient(mock_client, validate_spaces=True)

        # Should not raise any exception when no spaces client
        client._validate_space_exists("marketing")

    def test_space_validation_caching(self):
        """Test that space validation results are cached."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # First validation should hit the API
        client._validate_space_exists("marketing")

        # Second validation should use cache
        client._validate_space_exists("marketing")

        # API should only be called once
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify cache state
        assert client._space_cache["marketing"] is True
        assert "marketing" in client._cache_timestamps

    def test_space_validation_cache_negative_result(self):
        """Test that negative validation results are cached."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("Space not found")

        client = NamespaceClient(mock_client, validate_spaces=True)

        # First validation should fail and cache result
        with pytest.raises(SpaceNotFoundError):
            client._validate_space_exists("nonexistent")

        # Second validation should use cache and fail immediately
        with pytest.raises(SpaceNotFoundError):
            client._validate_space_exists("nonexistent")

        # API should only be called once
        mock_spaces_client.get.assert_called_once_with(id="nonexistent")

        # Verify cache state
        assert client._space_cache["nonexistent"] is False

    @patch("time.time")
    def test_space_validation_cache_expiry(self, mock_time):
        """Test that cache expires after TTL."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        # First validation at time 0
        mock_time.return_value = 0
        client._validate_space_exists("marketing")

        # Second validation at time 100 (within TTL)
        mock_time.return_value = 100
        client._validate_space_exists("marketing")

        # API should only be called once (cache hit)
        assert mock_spaces_client.get.call_count == 1

        # Third validation at time 400 (beyond TTL of 300)
        mock_time.return_value = 400
        client._validate_space_exists("marketing")

        # API should be called again (cache expired)
        assert mock_spaces_client.get.call_count == 2

    def test_clear_space_cache_specific_space(self):
        """Test clearing cache for specific space."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=True)

        # Set up cache
        client._space_cache["marketing"] = True
        client._space_cache["sales"] = True
        client._cache_timestamps["marketing"] = time.time()
        client._cache_timestamps["sales"] = time.time()

        # Clear specific space
        client._clear_space_cache("marketing")

        # Verify only marketing was cleared
        assert "marketing" not in client._space_cache
        assert "marketing" not in client._cache_timestamps
        assert "sales" in client._space_cache
        assert "sales" in client._cache_timestamps

    def test_clear_space_cache_all_spaces(self):
        """Test clearing all cache."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=True)

        # Set up cache
        client._space_cache["marketing"] = True
        client._space_cache["sales"] = True
        client._cache_timestamps["marketing"] = time.time()
        client._cache_timestamps["sales"] = time.time()

        # Clear all cache
        client._clear_space_cache()

        # Verify all cache was cleared
        assert len(client._space_cache) == 0
        assert len(client._cache_timestamps) == 0

    def test_build_space_path_with_validation_success(self):
        """Test path building with validation enabled and successful validation."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.return_value = {"id": "marketing", "name": "Marketing"}

        client = NamespaceClient(mock_client, validate_spaces=True)

        path = client._build_space_path("/api/actions/connector", "marketing")

        assert path == "/s/marketing/api/actions/connector"
        mock_spaces_client.get.assert_called_once_with(id="marketing")

    def test_build_space_path_with_validation_failure(self):
        """Test path building with validation enabled and validation failure."""
        mock_client = Mock()
        mock_spaces_client = Mock()
        mock_client.spaces = mock_spaces_client
        mock_spaces_client.get.side_effect = Exception("Space not found")

        client = NamespaceClient(mock_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            client._build_space_path("/api/actions/connector", "nonexistent")

        assert exc_info.value.space_id == "nonexistent"

    def test_build_space_path_validation_disabled(self):
        """Test path building with validation disabled."""
        mock_client = Mock()
        client = NamespaceClient(mock_client, validate_spaces=False)

        # Should work even with invalid space (no validation)
        path = client._build_space_path("/api/actions/connector", "any-space")

        assert path == "/s/any-space/api/actions/connector"
        # Verify no spaces client methods were called (validation was skipped)
        if hasattr(mock_client, "spaces") and mock_client.spaces:
            # If spaces client exists, verify it wasn't called
            assert not mock_client.spaces.get.called


class TestNamespaceClientBackwardCompatibility:
    """Test that existing functionality still works."""

    def test_init_without_space_parameters(self):
        """Test initialization without space parameters (backward compatibility)."""
        mock_client = Mock()
        client = NamespaceClient(mock_client)

        assert client._default_space_id is None
        assert client._validate_spaces is True
        assert isinstance(client._space_cache, dict)
        assert isinstance(client._cache_timestamps, dict)

    def test_perform_request_unchanged(self):
        """Test that perform_request method works unchanged."""
        mock_client = Mock()
        mock_response = Mock()
        mock_client.perform_request.return_value = mock_response

        client = NamespaceClient(mock_client)

        result = client.perform_request(
            method="GET",
            path="/api/test",
            params={"param": "value"},
            headers={"header": "value"},
            body={"body": "value"},
        )

        assert result == mock_response
        mock_client.perform_request.assert_called_once_with(
            method="GET",
            path="/api/test",
            params={"param": "value"},
            headers={"header": "value"},
            body={"body": "value"},
        )

    def test_perform_request_enhances_error_with_space_context(self):
        """Test that perform_request enhances errors with space context."""
        from elastic_transport import ApiResponseMeta

        from kibana.exceptions import ApiError

        mock_client = Mock()

        # Create a mock API error with message attribute
        original_error = ApiError(
            message="Resource not found",
            meta=ApiResponseMeta(
                status=404, headers={}, http_version="1.1", duration=0.1, node=None
            ),
            body={"error": "not found"},
        )
        mock_client.perform_request.side_effect = original_error

        client = NamespaceClient(mock_client)

        # Test with space-scoped path
        with pytest.raises(ApiError) as exc_info:
            client.perform_request(
                method="GET", path="/s/marketing/api/actions/connector/123"
            )

        # Verify error message was enhanced with space context
        enhanced_error = exc_info.value
        assert "[Space: marketing]" in enhanced_error.message
        assert "Resource not found" in enhanced_error.message
        assert enhanced_error.args[0].startswith("[Space: marketing]")

    def test_perform_request_no_enhancement_for_non_space_path(self):
        """Test that perform_request doesn't enhance errors for non-space paths."""
        from elastic_transport import ApiResponseMeta

        from kibana.exceptions import ApiError

        mock_client = Mock()

        # Create a mock API error
        original_error = ApiError(
            message="Resource not found",
            meta=ApiResponseMeta(
                status=404, headers={}, http_version="1.1", duration=0.1, node=None
            ),
            body={"error": "not found"},
        )
        mock_client.perform_request.side_effect = original_error

        client = NamespaceClient(mock_client)

        # Test with non-space path
        with pytest.raises(ApiError) as exc_info:
            client.perform_request(method="GET", path="/api/actions/connector/123")

        # Verify error message was not enhanced
        enhanced_error = exc_info.value
        assert "[Space:" not in enhanced_error.message
        assert enhanced_error.message == "Resource not found"

    def test_extract_space_id_from_path(self):
        """Test space ID extraction from API paths."""
        mock_client = Mock()
        client = NamespaceClient(mock_client)

        # Test space-scoped paths
        assert (
            client._extract_space_id_from_path("/s/marketing/api/actions/connector")
            == "marketing"
        )
        assert (
            client._extract_space_id_from_path(
                "/s/dev-team/api/saved_objects/dashboard"
            )
            == "dev-team"
        )
        assert (
            client._extract_space_id_from_path("/s/test_space/api/spaces/space")
            == "test_space"
        )

        # Test non-space paths
        assert client._extract_space_id_from_path("/api/actions/connector") is None
        assert (
            client._extract_space_id_from_path("/api/saved_objects/dashboard") is None
        )
        assert client._extract_space_id_from_path("/status") is None

        # Test edge cases
        assert client._extract_space_id_from_path("") is None
        assert client._extract_space_id_from_path("/s/") is None
        assert client._extract_space_id_from_path("/s") is None
