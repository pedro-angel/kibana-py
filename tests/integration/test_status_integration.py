"""Integration tests for StatusClient against a live Kibana 9.x instance."""

import pytest

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing."""
    client = create_test_kibana_client()
    yield client
    client.close()


class TestStatusIntegration:
    """Integration tests for the Status API."""

    def test_get_status(self, kibana_client):
        """Test retrieving Kibana status (default v8 format) from a real instance."""
        response = kibana_client.status.get_status()
        status = response.body

        # Verify response structure
        assert "name" in status
        assert "uuid" in status
        assert "version" in status
        assert "status" in status

        # Verify version information
        assert "number" in status["version"]
        assert "build_hash" in status["version"]
        assert "build_number" in status["version"]

        # Verify status structure
        assert "overall" in status["status"]
        assert "level" in status["status"]["overall"]
        assert status["status"]["overall"]["level"] in [
            "available",
            "degraded",
            "unavailable",
            "critical",
        ]

        # 9.x v8 format: core + plugins dicts, no legacy "statuses" key
        assert "core" in status["status"]
        assert "elasticsearch" in status["status"]["core"]
        assert "savedObjects" in status["status"]["core"]
        assert "plugins" in status["status"]
        assert isinstance(status["status"]["plugins"], dict)
        assert "statuses" not in status["status"]

        print(f"\nKibana Status: {status['status']['overall']['level']}")
        print(f"   Version: {status['version']['number']}")
        print(f"   Name: {status['name']}")

    def test_get_status_v7format(self, kibana_client):
        """Test retrieving Kibana status in the legacy v7 format."""
        response = kibana_client.status.get_status(v7format=True)
        status = response.body

        # v7 format: overall has state/title; statuses is a LIST
        assert "overall" in status["status"]
        assert "state" in status["status"]["overall"]
        assert status["status"]["overall"]["state"] in ["green", "yellow", "red"]
        assert isinstance(status["status"]["statuses"], list)
        assert len(status["status"]["statuses"]) > 0
        first = status["status"]["statuses"][0]
        assert "id" in first
        assert "state" in first

        print(f"\nKibana v7 status state: {status['status']['overall']['state']}")

    def test_get_status_v8format_explicit(self, kibana_client):
        """Test that v8format=True returns the same shape as the default."""
        response = kibana_client.status.get_status(v8format=True)
        status = response.body

        assert "level" in status["status"]["overall"]
        assert "core" in status["status"]

    def test_get_status_conflicting_formats_rejected(self, kibana_client):
        """Test that passing both format params yields a 400 Bad Request."""
        from kibana.exceptions import BadRequestError

        with pytest.raises(BadRequestError):
            kibana_client.status.get_status(v7format=True, v8format=True)

    def test_get_stats(self, kibana_client):
        """Test retrieving Kibana statistics from a real instance."""
        response = kibana_client.status.get_stats()
        stats = response.body

        # Verify response structure
        assert "kibana" in stats
        assert "process" in stats
        assert "os" in stats

        # Verify Kibana info
        assert "uuid" in stats["kibana"]
        assert "name" in stats["kibana"]
        assert "version" in stats["kibana"]
        assert "status" in stats["kibana"]

        # Verify process info (9.x field names)
        assert "memory" in stats["process"]
        assert "uptime_ms" in stats["process"]

        # Verify OS info (9.x field names)
        assert "platform" in stats["os"]
        assert "platform_release" in stats["os"]
        assert "load" in stats["os"]

        # Verify heap memory information (9.x: *_bytes suffix)
        heap = stats["process"]["memory"]["heap"]
        assert "total_bytes" in heap
        assert "used_bytes" in heap

        print("\nKibana Stats Retrieved")
        print(f"   Platform: {stats['os']['platform']}")
        print(f"   Status: {stats['kibana']['status']}")

    def test_get_stats_extended(self, kibana_client):
        """Test that extended stats include the cluster_uuid."""
        response = kibana_client.status.get_stats(extended=True)
        stats = response.body

        assert "cluster_uuid" in stats
        # In 9.4.3 the usage object is present but empty (usage collection
        # moved out of /api/stats); the key remains even with exclude_usage.
        assert isinstance(stats.get("usage", {}), dict)

        # legacy=True formats the extended payload in camelCase
        response = kibana_client.status.get_stats(extended=True, legacy=True)
        assert "clusterUuid" in response.body

    def test_get_features(self, kibana_client):
        """Test retrieving the Kibana features registry (technical preview)."""
        response = kibana_client.status.get_features()
        features = response.body

        assert isinstance(features, list)
        assert len(features) > 0

        feature_ids = {feature["id"] for feature in features}
        # Core features that always exist on a default install
        # (dashboard/discover are versioned ids in 9.4.3, e.g. dashboard_v2)
        assert "advancedSettings" in feature_ids
        assert any(fid.startswith("dashboard") for fid in feature_ids)
        assert any(fid.startswith("discover") for fid in feature_ids)

        for feature in features:
            assert "id" in feature
            assert "name" in feature

        print(f"\nFeatures registered: {len(features)}")

    def test_status_available_when_healthy(self, kibana_client):
        """Test that status is 'available' when Kibana is healthy."""
        response = kibana_client.status.get_status()
        status = response.body

        # For a running test instance, we expect it to be available
        # (or at least not unavailable)
        overall_level = status["status"]["overall"]["level"]
        assert overall_level in ["available", "degraded"]

        print(f"\nKibana is {overall_level}")

    def test_stats_contains_metrics(self, kibana_client):
        """Test that stats contain expected metrics with sane values."""
        response = kibana_client.status.get_stats()
        stats = response.body

        heap = stats["process"]["memory"]["heap"]
        heap_used = heap["used_bytes"]
        heap_total = heap["total_bytes"]

        assert heap_used > 0, "Heap used should be positive"
        assert heap_total > 0, "Heap total should be positive"
        assert stats["process"]["uptime_ms"] > 0, "Uptime should be positive"

        print("\nMetrics validated")
        heap_used_mb = heap_used / (1024 * 1024)
        heap_total_mb = heap_total / (1024 * 1024)
        print(f"   Heap: {heap_used_mb:.2f} MB / {heap_total_mb:.2f} MB")


class TestAsyncStatusIntegration:
    """Async round-trip integration tests for the Status API."""

    async def test_async_get_status(self):
        """Test retrieving Kibana status with the async client."""
        client = create_test_async_kibana_client()
        try:
            response = await client.status.get_status()
            status = response.body

            assert status["status"]["overall"]["level"] in [
                "available",
                "degraded",
                "unavailable",
                "critical",
            ]
            assert "core" in status["status"]
            assert "elasticsearch" in status["status"]["core"]
        finally:
            await client.close()

    async def test_async_get_stats_and_features(self):
        """Test async stats and features round trips."""
        client = create_test_async_kibana_client()
        try:
            stats = (await client.status.get_stats()).body
            assert stats["process"]["uptime_ms"] > 0
            assert "total_bytes" in stats["process"]["memory"]["heap"]

            features = (await client.status.get_features()).body
            assert isinstance(features, list)
            assert len(features) > 0
        finally:
            await client.close()


class TestStatusClientProperties:
    """Test StatusClient integration with the main client."""

    def test_status_client_accessible(self, kibana_client):
        """Test that status client is accessible from main client."""
        from kibana._sync.client.status import StatusClient

        assert hasattr(kibana_client, "status")
        assert isinstance(kibana_client.status, StatusClient)

    def test_status_client_caching(self, kibana_client):
        """Test that status client is cached."""
        status1 = kibana_client.status
        status2 = kibana_client.status
        assert status1 is status2


if __name__ == "__main__":
    # Run tests manually for debugging
    from .utils import print_test_config_info

    print_test_config_info()

    if is_kibana_available():
        client = create_test_kibana_client()
        try:
            print("\n=== Testing Status API ===\n")

            # Test get_status
            print("Testing get_status()...")
            response = client.status.get_status()
            status = response.body
            print(f"Status: {status['status']['overall']['level']}")
            print(f"   Version: {status['version']['number']}")

            # Test get_stats (9.x field names)
            print("\nTesting get_stats()...")
            response = client.status.get_stats()
            stats = response.body
            print("Stats retrieved")
            print(f"   Uptime: {stats['process']['uptime_ms'] / 1000:.2f}s")
            print(f"   Platform: {stats['os']['platform']}")

            # Test get_features
            print("\nTesting get_features()...")
            response = client.status.get_features()
            print(f"Features registered: {len(response.body)}")

            print("\nAll manual tests passed!")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback

            traceback.print_exc()
        finally:
            client.close()
    else:
        print("\nKibana not available for testing")
        print("   Set KIBANA_URL or start elastic-start-local stack")
