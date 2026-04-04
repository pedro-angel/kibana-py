"""Integration tests for StatusClient."""

import pytest

from .utils import create_test_kibana_client, is_kibana_available

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
    """Integration tests for Status API."""

    def test_get_status(self, kibana_client):
        """Test retrieving Kibana status from real instance."""
        # Get status
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
        ]

        # Verify core services status
        if "core" in status["status"]:
            assert "elasticsearch" in status["status"]["core"]
            assert "savedObjects" in status["status"]["core"]

        print(f"\n✅ Kibana Status: {status['status']['overall']['level']}")
        print(f"   Version: {status['version']['number']}")
        print(f"   Name: {status['name']}")

    def test_get_stats(self, kibana_client):
        """Test retrieving Kibana statistics from real instance."""
        # Get stats
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

        # Verify process info
        assert "memory" in stats["process"]

        # Verify OS info
        assert "platform" in stats["os"]
        assert "load" in stats["os"]

        # Verify memory information (heap structure may vary by Kibana version)
        assert "memory" in stats["process"]
        memory = stats["process"]["memory"]
        if "heap" in memory:
            assert "total_bytes" in memory["heap"] or "total_in_bytes" in memory["heap"]
            assert "used_bytes" in memory["heap"] or "used_in_bytes" in memory["heap"]

        print("\n✅ Kibana Stats Retrieved")
        print(f"   Platform: {stats['os']['platform']}")
        print(f"   Status: {stats['kibana']['status']}")

    def test_status_available_when_healthy(self, kibana_client):
        """Test that status is 'available' when Kibana is healthy."""
        response = kibana_client.status.get_status()
        status = response.body

        # For a running test instance, we expect it to be available
        # (or at least not unavailable)
        overall_level = status["status"]["overall"]["level"]
        assert overall_level in ["available", "degraded"]

        print(f"\n✅ Kibana is {overall_level}")

    def test_stats_contains_metrics(self, kibana_client):
        """Test that stats contain expected metrics."""
        response = kibana_client.status.get_stats()
        stats = response.body

        # Verify memory metrics exist and are reasonable
        assert "memory" in stats["process"]
        memory = stats["process"]["memory"]

        if "heap" in memory:
            # Handle both naming conventions (with/without _in_bytes suffix)
            heap = memory["heap"]
            heap_used = heap.get("used_bytes") or heap.get("used_in_bytes")
            heap_total = heap.get("total_bytes") or heap.get("total_in_bytes")

            assert heap_used is not None, "Heap used should be present"
            assert heap_total is not None, "Heap total should be present"
            assert heap_used > 0, "Heap used should be positive"
            assert heap_total > 0, "Heap total should be positive"
            assert heap_used <= heap_total, "Heap used should not exceed total"

            print("\n✅ Metrics validated")
            heap_used_mb = heap_used / (1024 * 1024)
            heap_total_mb = heap_total / (1024 * 1024)
            print(f"   Heap: {heap_used_mb:.2f} MB / {heap_total_mb:.2f} MB")
        else:
            # If heap info not available, just verify memory structure exists
            print(
                "\n✅ Metrics validated (heap info not available in this Kibana version)"
            )


class TestStatusClientProperties:
    """Test StatusClient integration with main client."""

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
            print(f"✅ Status: {status['status']['overall']['level']}")
            print(f"   Version: {status['version']['number']}")

            # Test get_stats
            print("\nTesting get_stats()...")
            response = client.status.get_stats()
            stats = response.body
            print("✅ Stats retrieved")
            print(f"   Uptime: {stats['process']['uptime_in_millis'] / 1000:.2f}s")
            print(f"   Platform: {stats['os']['platform']}")

            print("\n✅ All manual tests passed!")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            client.close()
    else:
        print("\n❌ Kibana not available for testing")
        print("   Set KIBANA_URL or start elastic-start-local stack")
