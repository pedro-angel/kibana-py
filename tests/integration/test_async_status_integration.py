"""Integration tests for AsyncStatusClient."""

import pytest

from .utils import create_test_async_kibana_client, is_kibana_available

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


class TestAsyncStatusClientConnectivity:
    """Tests for basic AsyncStatusClient connectivity."""

    @pytest.mark.asyncio
    async def test_status_client_exists(self, async_kibana_client):
        """Test that AsyncStatusClient is accessible via the main client."""
        assert hasattr(async_kibana_client, "status")
        assert async_kibana_client.status is not None

    @pytest.mark.asyncio
    async def test_get_status(self, async_kibana_client):
        """Test getting Kibana status."""
        response = await async_kibana_client.status.get_status()

        assert response.meta.status == 200
        status = response.body

        # Validate status structure
        assert isinstance(status, dict)
        assert "status" in status
        assert "version" in status

        # Status should have overall state
        assert "overall" in status["status"]
        assert "level" in status["status"]["overall"]

        # Version should have number and build info
        assert "number" in status["version"]
        assert "build_hash" in status["version"]
        assert "build_number" in status["version"]

    @pytest.mark.asyncio
    async def test_get_stats(self, async_kibana_client):
        """Test getting Kibana stats."""
        response = await async_kibana_client.status.get_stats()

        assert response.meta.status == 200
        stats = response.body

        # Validate stats structure
        assert isinstance(stats, dict)
        assert "kibana" in stats or "process" in stats or "os" in stats


class TestAsyncStatusClientResponseStructure:
    """Tests for validating response structure."""

    @pytest.mark.asyncio
    async def test_status_overall_state(self, async_kibana_client):
        """Test that status includes overall state information."""
        response = await async_kibana_client.status.get_status()
        status = response.body

        overall = status["status"]["overall"]
        assert "level" in overall
        assert overall["level"] in ["available", "degraded", "unavailable"]

        # Should have summary if available
        if "summary" in overall:
            assert isinstance(overall["summary"], str)

    @pytest.mark.asyncio
    async def test_status_version_info(self, async_kibana_client):
        """Test that status includes version information."""
        response = await async_kibana_client.status.get_status()
        status = response.body

        version = status["version"]
        assert isinstance(version["number"], str)
        assert isinstance(version["build_hash"], str)
        assert isinstance(version["build_number"], int)
        assert isinstance(version["build_snapshot"], bool)

    @pytest.mark.asyncio
    async def test_status_metrics(self, async_kibana_client):
        """Test that status includes metrics information."""
        response = await async_kibana_client.status.get_status()
        status = response.body

        # Metrics should be present
        if "metrics" in status:
            metrics = status["metrics"]
            assert isinstance(metrics, dict)

            # Common metrics
            if "last_updated" in metrics:
                assert isinstance(metrics["last_updated"], str)

            if "collection_interval_in_millis" in metrics:
                assert isinstance(metrics["collection_interval_in_millis"], int)


class TestAsyncStatusClientWithOptions:
    """Tests for AsyncStatusClient with client options."""

    @pytest.mark.asyncio
    async def test_status_with_custom_timeout(self, async_kibana_client):
        """Test that AsyncStatusClient works with custom timeout options."""
        # Create client with custom timeout
        client_with_timeout = async_kibana_client.options(request_timeout=60.0)

        # Should still be able to get status
        response = await client_with_timeout.status.get_status()
        assert response.meta.status == 200

    @pytest.mark.asyncio
    async def test_status_with_custom_headers(self, async_kibana_client):
        """Test that AsyncStatusClient works with custom headers."""
        # Create client with custom headers
        client_with_headers = async_kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to get status
        response = await client_with_headers.status.get_status()
        assert response.meta.status == 200


class TestAsyncStatusClientMultipleCalls:
    """Tests for making multiple status calls."""

    @pytest.mark.asyncio
    async def test_multiple_status_calls(self, async_kibana_client):
        """Test making multiple status calls in sequence."""
        # First call
        response1 = await async_kibana_client.status.get_status()
        assert response1.meta.status == 200

        # Second call
        response2 = await async_kibana_client.status.get_status()
        assert response2.meta.status == 200

        # Both should return valid status
        assert "status" in response1.body
        assert "status" in response2.body

    @pytest.mark.asyncio
    async def test_status_and_stats_calls(self, async_kibana_client):
        """Test calling both status and stats endpoints."""
        # Get status
        status_response = await async_kibana_client.status.get_status()
        assert status_response.meta.status == 200
        assert "status" in status_response.body

        # Get stats
        stats_response = await async_kibana_client.status.get_stats()
        assert stats_response.meta.status == 200
        assert isinstance(stats_response.body, dict)
