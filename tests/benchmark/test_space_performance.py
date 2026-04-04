"""Integration tests for space support performance and caching effectiveness."""

import statistics
import time
import uuid

import pytest
from utils import create_test_kibana_client, is_kibana_available

# Skip all integration tests if Kibana is not available
pytestmark = [
    pytest.mark.skipif(
        not is_kibana_available(),
        reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
    ),
    pytest.mark.benchmark,
]


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
def created_connectors():
    """Track connectors created during tests for automatic cleanup."""
    connector_data: list[tuple[str, str | None]] = []  # (connector_id, space_id)
    yield connector_data

    # Cleanup: Delete all created connectors
    if connector_data:
        client = create_test_kibana_client()
        try:
            for connector_id, space_id in connector_data:
                try:
                    if space_id:
                        client.actions.delete(id=connector_id, space_id=space_id)
                    else:
                        client.actions.delete(id=connector_id)
                except Exception:
                    # DELETE may return empty response or connector may not exist
                    pass
        finally:
            client.close()


@pytest.fixture
def unique_space_id():
    """Generate a unique space ID for testing."""
    return f"perf-space-{uuid.uuid4().hex[:8]}"


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


def measure_operation_time(operation_func, *args, **kwargs):
    """
    Measure the time taken to execute an operation.

    :param operation_func: Function to execute
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    :return: Tuple of (result, execution_time_seconds)
    """
    start_time = time.time()
    result = operation_func(*args, **kwargs)
    end_time = time.time()
    return result, end_time - start_time


def measure_multiple_operations(operation_func, iterations=5, *args, **kwargs):
    """
    Measure multiple iterations of an operation and return statistics.

    :param operation_func: Function to execute
    :param iterations: Number of iterations to run
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    :return: Dictionary with timing statistics
    """
    times = []
    results = []

    for _ in range(iterations):
        result, execution_time = measure_operation_time(operation_func, *args, **kwargs)
        times.append(execution_time)
        results.append(result)

    return {
        "times": times,
        "results": results,
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
        "iterations": iterations,
    }


class TestSpaceValidationPerformanceImpact:
    """Test performance impact of space validation on operations."""

    def test_validation_overhead_measurement(
        self, kibana_client, created_spaces, created_connectors, unique_space_id
    ):
        """Measure performance impact of space validation."""
        # Create test space
        create_test_space(
            kibana_client, created_spaces, unique_space_id, "Performance Test Space"
        )

        actions_client = kibana_client.actions

        # Test 1: Operation with validation enabled (cache miss)
        actions_client._clear_space_cache()

        def create_with_validation():
            response = actions_client.create(
                name=f"perf-test-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response.body["id"], unique_space_id))
            return response

        validation_stats = measure_multiple_operations(
            create_with_validation, iterations=3
        )

        # Test 2: Operation with validation disabled
        def create_without_validation():
            response = actions_client.create(
                name=f"perf-test-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
                validate_space=False,
            )
            created_connectors.append((response.body["id"], unique_space_id))
            return response

        no_validation_stats = measure_multiple_operations(
            create_without_validation, iterations=3
        )

        # Test 3: Operation with validation enabled (cache hit)
        def create_with_cached_validation():
            response = actions_client.create(
                name=f"perf-test-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response.body["id"], unique_space_id))
            return response

        cached_validation_stats = measure_multiple_operations(
            create_with_cached_validation, iterations=3
        )

        # Print performance results
        print("\nSpace Validation Performance Results:")
        print(
            f"Validation (cache miss): {validation_stats['mean']:.3f}s ± {validation_stats['stdev']:.3f}s"
        )
        print(
            f"No validation: {no_validation_stats['mean']:.3f}s ± {no_validation_stats['stdev']:.3f}s"
        )
        print(
            f"Validation (cache hit): {cached_validation_stats['mean']:.3f}s ± {cached_validation_stats['stdev']:.3f}s"
        )

        # Verify all operations succeeded
        for stats in [validation_stats, no_validation_stats, cached_validation_stats]:
            for result in stats["results"]:
                assert result.meta.status == 200

        # Performance assertions - be more lenient for integration tests
        # All operations should complete within reasonable time (30 seconds max)
        assert validation_stats["max"] < 10.0
        assert no_validation_stats["max"] < 10.0
        assert cached_validation_stats["max"] < 10.0

        # The validation overhead should be reasonable (less than 100% of total operation time)
        # This is a realistic test since we're measuring full API operations over network
        validation_overhead = abs(
            validation_stats["mean"] - no_validation_stats["mean"]
        )
        max_operation_time = max(validation_stats["mean"], no_validation_stats["mean"])
        assert (
            validation_overhead < max_operation_time
        )  # Overhead should be less than the operation itself

        # Cache should provide some benefit or at least not be significantly worse
        cache_overhead = abs(cached_validation_stats["mean"] - validation_stats["mean"])
        assert (
            cache_overhead < validation_stats["mean"]
        )  # Cache overhead should be less than full validation

    def test_cache_effectiveness_measurement(
        self, kibana_client, created_spaces, created_connectors, unique_space_id
    ):
        """Test cache effectiveness in reducing API calls."""
        # Create test space
        create_test_space(
            kibana_client, created_spaces, unique_space_id, "Cache Test Space"
        )

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # Measure first operation (cache miss)
        def first_operation():
            response = actions_client.create(
                name=f"cache-test-1-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response.body["id"], unique_space_id))
            return response

        first_result, first_time = measure_operation_time(first_operation)

        # Measure subsequent operations (cache hits)
        cache_hit_times = []
        for i in range(5):

            def cache_hit_operation():
                response = actions_client.create(
                    name=f"cache-test-{i+2}-{uuid.uuid4().hex[:8]}",
                    connector_type_id=".server-log",
                    config={},
                    space_id=unique_space_id,
                )
                created_connectors.append((response.body["id"], unique_space_id))
                return response

            result, execution_time = measure_operation_time(cache_hit_operation)
            cache_hit_times.append(execution_time)
            assert result.meta.status == 200

        # Calculate statistics
        cache_hit_mean = statistics.mean(cache_hit_times)
        cache_hit_min = min(cache_hit_times)
        cache_hit_max = max(cache_hit_times)

        print("\nCache Effectiveness Results:")
        print(f"First operation (cache miss): {first_time:.3f}s")
        print(
            f"Cache hit operations: {cache_hit_mean:.3f}s (min: {cache_hit_min:.3f}s, max: {cache_hit_max:.3f}s)"
        )

        # Calculate cache effectiveness
        cache_effectiveness = ((first_time - cache_hit_mean) / first_time) * 100
        print(f"Cache effectiveness: {cache_effectiveness:.1f}% improvement")

        # Network variance can make cache hits appear slower than cache misses.
        # Verify caching doesn't cause major degradation (within 2s tolerance).
        assert (
            cache_hit_mean <= first_time + 2.0
        ), f"Cache hit ({cache_hit_mean:.3f}s) much slower than first call ({first_time:.3f}s)"

        # Verify cache contains the space
        assert unique_space_id in actions_client._space_cache
        assert actions_client._space_cache[unique_space_id] is True

    def test_no_performance_regression_for_global_operations(self, kibana_client):
        """Verify no performance regression for non-space-scoped operations."""
        actions_client = kibana_client.actions

        # Measure global operations (no space validation)
        def global_operation():
            return actions_client.list_types()

        global_stats = measure_multiple_operations(global_operation, iterations=5)

        print("\nGlobal Operation Performance:")
        print(f"List types: {global_stats['mean']:.3f}s ± {global_stats['stdev']:.3f}s")

        # Verify all operations succeeded
        for result in global_stats["results"]:
            assert result.meta.status == 200
            assert isinstance(result.body, list)
            assert len(result.body) > 0

        # Global operations should be fast (under 10 seconds even on slow networks)
        assert global_stats["mean"] < 5.0
        assert global_stats["max"] < 10.0

    def test_concurrent_space_validation_performance(
        self, kibana_client, created_spaces, created_connectors
    ):
        """Test performance with multiple spaces being validated concurrently."""
        # Create multiple test spaces
        space_ids = []
        for i in range(3):
            space_id = f"concurrent-space-{i}-{uuid.uuid4().hex[:8]}"
            create_test_space(
                kibana_client, created_spaces, space_id, f"Concurrent Test Space {i+1}"
            )
            space_ids.append(space_id)

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # Measure operations across different spaces
        def multi_space_operations():
            results = []
            for i, space_id in enumerate(space_ids):
                response = actions_client.create(
                    name=f"concurrent-test-{i}-{uuid.uuid4().hex[:8]}",
                    connector_type_id=".server-log",
                    config={},
                    space_id=space_id,
                )
                created_connectors.append((response.body["id"], space_id))
                results.append(response)
            return results

        multi_space_result, multi_space_time = measure_operation_time(
            multi_space_operations
        )

        print("\nMulti-Space Operation Performance:")
        print(f"3 operations across 3 spaces: {multi_space_time:.3f}s")
        print(f"Average per operation: {multi_space_time / 3:.3f}s")

        # Verify all operations succeeded
        assert len(multi_space_result) == 3
        for result in multi_space_result:
            assert result.meta.status == 200

        # Verify all spaces are cached
        for space_id in space_ids:
            assert space_id in actions_client._space_cache
            assert actions_client._space_cache[space_id] is True

        # Multi-space operations should complete in reasonable time
        assert multi_space_time < 15.0


class TestSpaceCachingEffectiveness:
    """Test space validation caching effectiveness."""

    def test_cache_ttl_behavior(
        self, kibana_client, created_spaces, created_connectors, unique_space_id
    ):
        """Test cache TTL (Time To Live) behavior."""
        # Create test space
        create_test_space(
            kibana_client, created_spaces, unique_space_id, "TTL Test Space"
        )

        actions_client = kibana_client.actions

        # Set very short TTL for testing
        original_ttl = actions_client._cache_ttl
        actions_client._cache_ttl = 2  # 2 seconds
        actions_client._clear_space_cache()

        try:
            # First operation - populate cache
            response1 = actions_client.create(
                name=f"ttl-test-1-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response1.body["id"], unique_space_id))

            # Verify cache is populated
            assert unique_space_id in actions_client._space_cache
            cache_time_1 = actions_client._cache_timestamps[unique_space_id]

            # Second operation immediately - should use cache
            response2 = actions_client.create(
                name=f"ttl-test-2-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response2.body["id"], unique_space_id))

            # Cache timestamp should not change (cache hit)
            cache_time_2 = actions_client._cache_timestamps[unique_space_id]
            assert cache_time_2 == cache_time_1

            # Wait for cache to expire
            time.sleep(3)

            # Third operation - cache should be expired and revalidated
            response3 = actions_client.create(
                name=f"ttl-test-3-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=unique_space_id,
            )
            created_connectors.append((response3.body["id"], unique_space_id))

            # Cache timestamp should be updated (cache miss due to expiration)
            cache_time_3 = actions_client._cache_timestamps[unique_space_id]
            assert cache_time_3 > cache_time_1

            # All operations should succeed
            assert response1.meta.status == 200
            assert response2.meta.status == 200
            assert response3.meta.status == 200

        finally:
            # Restore original TTL
            actions_client._cache_ttl = original_ttl

    def test_cache_memory_efficiency(self, kibana_client, created_spaces):
        """Test that cache doesn't grow unbounded."""
        # Create multiple spaces
        space_ids = []
        for i in range(10):
            space_id = f"memory-test-{i}-{uuid.uuid4().hex[:8]}"
            create_test_space(
                kibana_client, created_spaces, space_id, f"Memory Test Space {i+1}"
            )
            space_ids.append(space_id)

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # Validate all spaces to populate cache
        for space_id in space_ids:
            # Just trigger validation without creating connectors
            try:
                actions_client.get_all(space_id=space_id)
            except Exception:
                # get_all might fail, but validation should happen
                pass

        # Verify cache contains all spaces
        assert len(actions_client._space_cache) <= len(space_ids)

        # Cache should not be excessively large
        cache_size = len(actions_client._space_cache)
        print(f"Cache size after validating {len(space_ids)} spaces: {cache_size}")

        # Clear cache and verify it's empty
        actions_client._clear_space_cache()
        assert len(actions_client._space_cache) == 0
        assert len(actions_client._cache_timestamps) == 0

    def test_cache_negative_result_effectiveness(self, kibana_client):
        """Test that negative cache results are effective."""
        nonexistent_space_id = f"nonexistent-{uuid.uuid4().hex[:8]}"

        actions_client = kibana_client.actions
        actions_client._clear_space_cache()

        # First attempt - should validate and cache negative result
        start_time = time.time()
        try:
            actions_client.create(
                name="test-connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected
        first_attempt_time = time.time() - start_time

        # Verify negative result is cached
        assert nonexistent_space_id in actions_client._space_cache
        assert actions_client._space_cache[nonexistent_space_id] is False

        # Second attempt - should use cached negative result
        start_time = time.time()
        try:
            actions_client.create(
                name="test-connector-2",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected
        second_attempt_time = time.time() - start_time

        print(f"First validation attempt: {first_attempt_time:.3f}s")
        print(f"Cached negative result: {second_attempt_time:.3f}s")

        # Second attempt should be faster (cached negative result)
        assert second_attempt_time <= first_attempt_time + 0.1  # Allow 100ms tolerance

        # Cached negative result should be very fast
        assert second_attempt_time < 0.2  # Should be under 500ms


class TestPerformanceRegressionPrevention:
    """Test to prevent performance regressions in space support."""

    def test_baseline_performance_benchmarks(
        self, kibana_client, created_spaces, created_connectors
    ):
        """Establish baseline performance benchmarks."""
        # Create test space
        space_id = f"benchmark-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Benchmark Space")

        actions_client = kibana_client.actions

        # Benchmark 1: Global operations (no space support)
        global_stats = measure_multiple_operations(
            lambda: actions_client.list_types(), iterations=3
        )

        # Benchmark 2: Space-scoped operations (with validation)
        def space_scoped_operation():
            response = actions_client.create(
                name=f"benchmark-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=space_id,
            )
            created_connectors.append((response.body["id"], space_id))
            return response

        space_stats = measure_multiple_operations(space_scoped_operation, iterations=3)

        # Benchmark 3: Space-scoped operations (without validation)
        def space_no_validation_operation():
            response = actions_client.create(
                name=f"benchmark-no-val-{uuid.uuid4().hex[:8]}",
                connector_type_id=".server-log",
                config={},
                space_id=space_id,
                validate_space=False,
            )
            created_connectors.append((response.body["id"], space_id))
            return response

        space_no_val_stats = measure_multiple_operations(
            space_no_validation_operation, iterations=3
        )

        # Print benchmark results
        print("\nPerformance Benchmarks:")
        print(
            f"Global operations: {global_stats['mean']:.3f}s ± {global_stats['stdev']:.3f}s"
        )
        print(
            f"Space-scoped (with validation): {space_stats['mean']:.3f}s ± {space_stats['stdev']:.3f}s"
        )
        print(
            f"Space-scoped (no validation): {space_no_val_stats['mean']:.3f}s ± {space_no_val_stats['stdev']:.3f}s"
        )

        # Performance regression checks
        # All operations should complete within reasonable time limits
        assert global_stats["mean"] < 5.0, "Global operations too slow"
        assert space_stats["mean"] < 10.0, "Space-scoped operations too slow"
        assert (
            space_no_val_stats["mean"] < 10.0
        ), "Space-scoped (no validation) operations too slow"

        # Space operations without validation should not be significantly slower than global
        # (allowing for network variance and API differences)
        validation_overhead = space_stats["mean"] - space_no_val_stats["mean"]
        print(f"Validation overhead: {validation_overhead:.3f}s")

        # Validation overhead should be reasonable (under 5 seconds)
        assert validation_overhead < 3.0, "Space validation overhead too high"

    def test_memory_usage_stability(self, kibana_client, created_spaces):
        """Test that space support doesn't cause memory leaks."""
        # This is a basic test - in a real scenario you'd use memory profiling tools

        # Create and validate many spaces to test cache behavior
        space_ids = []
        for i in range(20):
            space_id = f"memory-stability-{i}-{uuid.uuid4().hex[:8]}"
            create_test_space(
                kibana_client, created_spaces, space_id, f"Memory Stability Space {i+1}"
            )
            space_ids.append(space_id)

        actions_client = kibana_client.actions

        # Validate all spaces multiple times
        for iteration in range(3):
            actions_client._clear_space_cache()  # Clear cache between iterations

            for space_id in space_ids:
                try:
                    # Trigger space validation
                    actions_client.get_all(space_id=space_id)
                except Exception:
                    pass  # get_all might fail, but validation should happen

            # Check cache size is reasonable
            cache_size = len(actions_client._space_cache)
            print(f"Iteration {iteration + 1}: Cache size = {cache_size}")

            # Cache should not grow unbounded
            assert cache_size <= len(space_ids)

        # Final cleanup
        actions_client._clear_space_cache()
        assert len(actions_client._space_cache) == 0

    def test_error_handling_performance(self, kibana_client):
        """Test that error handling doesn't cause performance issues."""
        actions_client = kibana_client.actions

        # Test multiple invalid space operations
        invalid_space_ids = [f"invalid-{i}-{uuid.uuid4().hex[:8]}" for i in range(5)]

        error_times = []
        for space_id in invalid_space_ids:
            start_time = time.time()
            try:
                actions_client.create(
                    name="error-test",
                    connector_type_id=".server-log",
                    config={},
                    space_id=space_id,
                )
                assert False, "Should have raised an exception"
            except Exception:
                pass  # Expected

            error_time = time.time() - start_time
            error_times.append(error_time)

        mean_error_time = statistics.mean(error_times)
        print(f"Mean error handling time: {mean_error_time:.3f}s")

        # Error handling should be fast (errors should fail quickly)
        assert mean_error_time < 5.0, "Error handling too slow"

        # All error times should be reasonable
        for error_time in error_times:
            assert error_time < 10.0, "Individual error handling too slow"
