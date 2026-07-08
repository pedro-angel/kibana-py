"""Integration tests for the Upgrade Assistant API against a live Kibana."""

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


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing."""
    client = create_test_async_kibana_client()
    yield client
    await client.close()


class TestUpgradeAssistantIntegration:
    """Integration tests for the Upgrade Assistant status API (sync)."""

    def test_status_returns_readiness(self, kibana_client):
        """Test retrieving the upgrade readiness status from a live Kibana."""
        response = kibana_client.upgrade_assistant.status()

        assert response.meta.status == 200
        body = response.body
        assert isinstance(body, dict)

        # readyForUpgrade is the one field guaranteed by the API contract.
        assert "readyForUpgrade" in body
        assert isinstance(body["readyForUpgrade"], bool)

    def test_status_reports_deprecation_details(self, kibana_client):
        """Test that the live 9.4 response exposes deprecation detail sections."""
        body = kibana_client.upgrade_assistant.status().body

        # Live 9.4.3 returns these sections (the spec example shows an older
        # "cluster" shape; the live server wins).
        assert "recentEsDeprecationLogs" in body
        assert isinstance(body["recentEsDeprecationLogs"].get("count"), int)
        assert isinstance(body["recentEsDeprecationLogs"].get("logs"), list)
        assert isinstance(body.get("kibanaApiDeprecations", []), list)

        if body["readyForUpgrade"]:
            # When ready, a human-readable summary is included.
            assert isinstance(body.get("details", ""), str)

    def test_status_is_stable_across_calls(self, kibana_client):
        """Test that repeated read-only calls succeed and agree on the shape."""
        first = kibana_client.upgrade_assistant.status().body
        second = kibana_client.upgrade_assistant.status().body

        assert isinstance(first["readyForUpgrade"], bool)
        assert isinstance(second["readyForUpgrade"], bool)


class TestAsyncUpgradeAssistantIntegration:
    """Integration tests for the Upgrade Assistant status API (async)."""

    @pytest.mark.asyncio
    async def test_async_status_returns_readiness(self, async_kibana_client):
        """Test the async round-trip for the upgrade readiness status."""
        response = await async_kibana_client.upgrade_assistant.status()

        assert response.meta.status == 200
        body = response.body
        assert "readyForUpgrade" in body
        assert isinstance(body["readyForUpgrade"], bool)
        assert "recentEsDeprecationLogs" in body

    @pytest.mark.asyncio
    async def test_async_matches_sync_readiness(self, async_kibana_client):
        """Test that the async client reports the same readiness as the sync one."""
        sync_client = create_test_kibana_client()
        try:
            sync_body = sync_client.upgrade_assistant.status().body
            async_body = (await async_kibana_client.upgrade_assistant.status()).body
            assert sync_body["readyForUpgrade"] == async_body["readyForUpgrade"]
        finally:
            sync_client.close()
