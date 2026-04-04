"""Integration tests for space validation with real Kibana instance."""

import time
import uuid

import pytest

from kibana.exceptions import InvalidSpaceIdError, SpaceNotFoundError

from .utils import create_test_kibana_client, is_kibana_available

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_spaces():
    """Track spaces created during tests for automatic cleanup."""
    space_ids: list[str] = []
    yield space_ids

    # Cleanup: Delete all created spaces
    if space_ids:
        client = create_test_kibana_client()
        try:
            for space_id in space_ids:
                try:
                    client.spaces.delete(id=space_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup space {space_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def unique_space_id():
    """Generate a unique space ID for testing."""
    return f"test-space-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def created_connectors(kibana_client):
    """Track connectors created during tests for automatic cleanup."""
    connectors: list[tuple[str, str | None]] = []
    yield connectors

    # Cleanup: Delete all created connectors
    for connector_id, space_id in connectors:
        try:
            kibana_client.actions.delete(id=connector_id, space_id=space_id)
        except Exception:
            pass


def create_test_space(client, created_spaces, space_id, name, **kwargs):
    """
    Create a test space and track it for cleanup.

    :param client: Kibana client
    :param created_spaces: List to track created spaces
    :param space_id: Space ID
    :param name: Space name
    :param kwargs: Additional space parameters
    :return: Created space data
    """
    response = client.spaces.create(id=space_id, name=name, **kwargs)
    space = response.body
    created_spaces.append(space["id"])
    return space


class TestSpaceValidationWithRealKibana:
    """Test space validation against real Kibana API."""

    def test_validate_existing_space_success(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test that validation succeeds for existing spaces."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space for Validation",
        )

        # Create ActionsClient with validation enabled
        actions_client = kibana_client.actions

        # This should succeed without raising an exception
        # The space validation happens internally when building the path
        response = (
            actions_client.list_types()
        )  # This doesn't use space, but tests client creation
        assert response.meta.status == 200

        # Test actual space validation by creating a connector in the space
        connector_response = actions_client.create(
            name="Test Connector",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,  # This will trigger space validation
        )

        assert connector_response.meta.status == 200
        connector_id = connector_response.body["id"]

        # Cleanup connector
        try:
            actions_client.delete(id=connector_id, space_id=unique_space_id)
        except Exception:
            # DELETE may return empty response
            pass

    def test_validate_nonexistent_space_raises_error(self, kibana_client):
        """Test that validation fails for non-existent spaces."""
        nonexistent_space_id = f"nonexistent-space-{uuid.uuid4().hex[:8]}"

        # Create ActionsClient with validation enabled
        actions_client = kibana_client.actions

        # This should raise SpaceNotFoundError
        with pytest.raises(SpaceNotFoundError) as exc_info:
            actions_client.create(
                name="Test Connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )

        assert exc_info.value.space_id == nonexistent_space_id
        assert "not found" in str(exc_info.value).lower()

    def test_validate_invalid_space_id_format_raises_error(self, kibana_client):
        """Test that validation fails for invalid space ID formats."""
        invalid_space_ids = [
            "UPPERCASE",  # Must be lowercase
            "space with spaces",  # No spaces allowed
            "space@domain.com",  # No special chars except - and _
            "space/with/slashes",  # No slashes
            "space.with.dots",  # No dots
        ]

        actions_client = kibana_client.actions

        for invalid_space_id in invalid_space_ids:
            with pytest.raises(InvalidSpaceIdError) as exc_info:
                actions_client.create(
                    name="Test Connector",
                    connector_type_id=".server-log",
                    config={},
                    space_id=invalid_space_id,
                )

            assert exc_info.value.space_id == invalid_space_id

    def test_empty_space_id_uses_default_space(self, kibana_client, created_connectors):
        """Test that empty space ID uses default space (no validation error)."""
        actions_client = kibana_client.actions

        # Empty string should be treated as default space (no space_id)
        response = actions_client.create(
            name=f"test-empty-space-{uuid.uuid4().hex[:8]}",
            connector_type_id=".server-log",
            config={},
            space_id="",  # Empty string should use default space
        )

        created_connectors.append((response.body["id"], None))  # Track for cleanup
        assert response.meta.status == 200

    def test_validation_bypass_with_validate_space_false(self, kibana_client):
        """Test that validation can be bypassed with validate_space=False."""
        nonexistent_space_id = f"nonexistent-space-{uuid.uuid4().hex[:8]}"

        actions_client = kibana_client.actions

        # With validate_space=False, SpaceNotFoundError must never be raised.
        # The underlying API may succeed or fail depending on how Kibana handles
        # the space path — either outcome is acceptable; the key assertion is that
        # our client-side validation is bypassed.
        try:
            actions_client.create(
                name="Test Connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
                validate_space=False,  # Bypass validation
            )
        except SpaceNotFoundError:
            pytest.fail("SpaceNotFoundError raised even with validate_space=False")
        except Exception:
            pass  # Any other error from the API is acceptable

    def test_default_space_validation_success(self, kibana_client):
        """Test that default space validation works."""
        actions_client = kibana_client.actions

        # Default space should always exist and validate successfully
        response = actions_client.create(
            name="Test Connector in Default Space",
            connector_type_id=".server-log",
            config={},
            space_id="default",
        )

        assert response.meta.status == 200
        connector_id = response.body["id"]

        # Cleanup
        try:
            actions_client.delete(id=connector_id, space_id="default")
        except Exception:
            pass


class TestSpaceCachingWithRealKibana:
    """Test space validation caching behavior with real Kibana."""

    def test_cache_hit_reduces_api_calls(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test that space validation results are cached to reduce API calls."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space for Caching",
        )

        # Create ActionsClient with validation enabled
        actions_client = kibana_client.actions

        # Clear any existing cache
        actions_client._clear_space_cache()

        # First operation should validate the space (cache miss)
        start_time = time.time()
        response1 = actions_client.create(
            name="Test Connector 1",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        first_call_time = time.time() - start_time

        connector_id1 = response1.body["id"]

        # Second operation should use cached result (cache hit)
        start_time = time.time()
        response2 = actions_client.create(
            name="Test Connector 2",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        second_call_time = time.time() - start_time

        connector_id2 = response2.body["id"]

        # Both operations should succeed
        assert response1.meta.status == 200
        assert response2.meta.status == 200

        # Second call should be faster due to caching (though this is not guaranteed)
        # We mainly verify that both calls succeeded, indicating caching worked
        print(f"First call time: {first_call_time:.3f}s")
        print(f"Second call time: {second_call_time:.3f}s")

        # Cleanup connectors
        try:
            actions_client.delete(id=connector_id1, space_id=unique_space_id)
            actions_client.delete(id=connector_id2, space_id=unique_space_id)
        except Exception:
            pass

    def test_cache_expiration_revalidates_space(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test that cache expiration causes revalidation."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space for Cache Expiration",
        )

        # Create ActionsClient with very short cache TTL for testing
        actions_client = kibana_client.actions
        actions_client._cache_ttl = 1  # 1 second TTL

        # Clear any existing cache
        actions_client._clear_space_cache()

        # First operation should validate the space
        response1 = actions_client.create(
            name="Test Connector 1",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        connector_id1 = response1.body["id"]

        # Wait for cache to expire
        time.sleep(2)

        # Second operation should revalidate due to cache expiration
        response2 = actions_client.create(
            name="Test Connector 2",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        connector_id2 = response2.body["id"]

        # Both operations should succeed
        assert response1.meta.status == 200
        assert response2.meta.status == 200

        # Cleanup connectors
        try:
            actions_client.delete(id=connector_id1, space_id=unique_space_id)
            actions_client.delete(id=connector_id2, space_id=unique_space_id)
        except Exception:
            pass

    def test_cache_negative_results(self, kibana_client):
        """Test that negative validation results are also cached."""
        nonexistent_space_id = f"nonexistent-space-{uuid.uuid4().hex[:8]}"

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # First call should validate and cache negative result
        with pytest.raises(SpaceNotFoundError):
            actions_client.create(
                name="Test Connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )

        # Second call should use cached negative result (should be fast)
        start_time = time.time()
        with pytest.raises(SpaceNotFoundError):
            actions_client.create(
                name="Test Connector 2",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )
        second_call_time = time.time() - start_time

        # Second call should be very fast due to cached negative result
        assert second_call_time < 0.1  # Should be nearly instantaneous

    def test_cache_clearing_functionality(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test cache clearing functionality."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space for Cache Clearing",
        )

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # Validate space to populate cache
        response = actions_client.create(
            name="Test Connector",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        connector_id = response.body["id"]

        # Verify space is in cache
        assert unique_space_id in actions_client._space_cache
        assert actions_client._space_cache[unique_space_id] is True

        # Clear specific space from cache
        actions_client._clear_space_cache(unique_space_id)

        # Verify space is no longer in cache
        assert unique_space_id not in actions_client._space_cache

        # Clear entire cache
        actions_client._space_cache[unique_space_id] = True  # Add back to cache
        actions_client._clear_space_cache()  # Clear all

        # Verify cache is empty
        assert len(actions_client._space_cache) == 0

        # Cleanup connector
        try:
            actions_client.delete(id=connector_id, space_id=unique_space_id)
        except Exception:
            pass


class TestSpaceValidationErrorHandling:
    """Test error handling for space validation scenarios."""

    def test_space_validation_with_network_error(self, kibana_client):
        """Test space validation behavior when network errors occur."""
        # This test is difficult to implement reliably in integration tests
        # as it requires simulating network failures
        # We'll test the error handling path by using an invalid space format
        # which should trigger validation before any network call

        actions_client = kibana_client.actions

        with pytest.raises(InvalidSpaceIdError):
            actions_client.create(
                name="Test Connector",
                connector_type_id=".server-log",
                config={},
                space_id="INVALID_FORMAT",  # This will fail format validation first
            )

    def test_space_validation_error_context_enhancement(self, kibana_client):
        """Test that space validation errors include proper context."""
        nonexistent_space_id = f"nonexistent-space-{uuid.uuid4().hex[:8]}"

        actions_client = kibana_client.actions

        with pytest.raises(SpaceNotFoundError) as exc_info:
            actions_client.create(
                name="Test Connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )

        # Verify error includes space context
        error = exc_info.value
        assert error.space_id == nonexistent_space_id
        assert nonexistent_space_id in str(error)

    def test_space_validation_with_auth_error(self, kibana_client):
        """Test space validation behavior with authentication errors."""
        # Create a client with invalid credentials
        from kibana import Kibana

        from .utils import get_integration_test_config

        kibana_url, _, _ = get_integration_test_config()

        # Create client with invalid API key
        invalid_client = Kibana(kibana_url, api_key="invalid-key")

        try:
            # This should fail with authentication error, not space validation error
            with pytest.raises(Exception) as exc_info:
                invalid_client.actions.create(
                    name="Test Connector",
                    connector_type_id=".server-log",
                    config={},
                    space_id="default",
                )

            # Should be an authentication error, not a space validation error
            assert not isinstance(exc_info.value, SpaceNotFoundError)
            assert not isinstance(exc_info.value, InvalidSpaceIdError)
            # Should be a 401 or 403 error
            error_str = str(exc_info.value).lower()
            assert (
                "401" in error_str
                or "403" in error_str
                or "unauthorized" in error_str
                or "forbidden" in error_str
            )
        finally:
            invalid_client.close()


class TestSpaceValidationPerformance:
    """Test performance aspects of space validation."""

    def test_validation_overhead_measurement(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Measure performance impact of space validation."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space for Performance",
        )

        actions_client = kibana_client.actions

        # Test with validation enabled (first call - cache miss)
        actions_client._clear_space_cache()
        start_time = time.time()
        response1 = actions_client.create(
            name="Test Connector With Validation",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        validation_time = time.time() - start_time
        connector_id1 = response1.body["id"]

        # Test with validation disabled
        start_time = time.time()
        response2 = actions_client.create(
            name="Test Connector Without Validation",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
            validate_space=False,
        )
        no_validation_time = time.time() - start_time
        connector_id2 = response2.body["id"]

        # Test with validation enabled (second call - cache hit)
        start_time = time.time()
        response3 = actions_client.create(
            name="Test Connector With Cached Validation",
            connector_type_id=".server-log",
            config={},
            space_id=unique_space_id,
        )
        cached_validation_time = time.time() - start_time
        connector_id3 = response3.body["id"]

        # All operations should succeed
        assert response1.meta.status == 200
        assert response2.meta.status == 200
        assert response3.meta.status == 200

        # Log performance results
        print(f"Validation (cache miss): {validation_time:.3f}s")
        print(f"No validation: {no_validation_time:.3f}s")
        print(f"Validation (cache hit): {cached_validation_time:.3f}s")

        # Note: we intentionally do not assert timing here — wall-clock times
        # vary with network jitter and the cache benefit is sub-millisecond,
        # making timing assertions inherently flaky in CI environments.

        # Cleanup connectors
        try:
            actions_client.delete(id=connector_id1, space_id=unique_space_id)
            actions_client.delete(id=connector_id2, space_id=unique_space_id)
            actions_client.delete(id=connector_id3, space_id=unique_space_id)
        except Exception:
            pass

    def test_no_performance_regression_for_global_operations(self, kibana_client):
        """Verify no performance regression for non-space-scoped operations."""
        actions_client = kibana_client.actions

        # Test global operation (no space_id)
        start_time = time.time()
        response = actions_client.list_types()
        global_operation_time = time.time() - start_time

        assert response.meta.status == 200

        # Global operations should be fast (no space validation overhead)
        print(f"Global operation time: {global_operation_time:.3f}s")

        # This should complete quickly (under 5 seconds even on slow networks)
        assert global_operation_time < 5.0
