"""Integration tests for the Task Manager API clients.

These tests run against a live Kibana instance. The task manager health
endpoint is read-only, so no resources are created and no cleanup is needed.
"""

import pytest

from .utils import (
    create_test_async_kibana_client,
    create_test_kibana_client,
    is_kibana_available,
)

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)

MONITORED_STATS_SECTIONS = (
    "configuration",
    "runtime",
    "workload",
    "capacity_estimation",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


class TestTaskManagerHealth:
    """Live tests for TaskManagerClient.health()."""

    def test_task_manager_client_exists(self, kibana_client):
        """Test that TaskManagerClient is accessible via the main client."""
        assert hasattr(kibana_client, "task_manager")
        assert kibana_client.task_manager is not None

    def test_health(self, kibana_client):
        """Test getting the task manager health report."""
        response = kibana_client.task_manager.health()

        assert response.meta.status == 200
        health = response.body
        assert isinstance(health, dict)

        # Top-level report structure
        assert "id" in health
        assert "timestamp" in health
        assert "last_update" in health
        assert health["status"] in ("OK", "warn", "error")

        # Monitored stats sections
        assert "stats" in health
        for section in MONITORED_STATS_SECTIONS:
            assert section in health["stats"], f"missing stats section: {section}"
            section_stats = health["stats"][section]
            assert "timestamp" in section_stats
            assert "status" in section_stats
            assert "value" in section_stats

    def test_health_configuration_section(self, kibana_client):
        """Test that the configuration section exposes task manager settings."""
        response = kibana_client.task_manager.health()
        configuration = response.body["stats"]["configuration"]["value"]

        assert "poll_interval" in configuration
        assert isinstance(configuration["poll_interval"], int)
        assert "capacity" in configuration

    def test_health_runtime_polling_section(self, kibana_client):
        """Test that the runtime section exposes polling statistics."""
        response = kibana_client.task_manager.health()
        runtime = response.body["stats"]["runtime"]["value"]

        assert "polling" in runtime
        assert "drift" in runtime

    def test_health_repeated_calls(self, kibana_client):
        """Test that repeated health calls report the same Kibana instance."""
        first = kibana_client.task_manager.health()
        second = kibana_client.task_manager.health()

        assert first.meta.status == 200
        assert second.meta.status == 200
        assert first.body["id"] == second.body["id"]


class TestAsyncTaskManagerHealth:
    """Live tests for AsyncTaskManagerClient.health()."""

    @pytest.mark.asyncio
    async def test_health_async(self, async_kibana_client):
        """Test getting the task manager health report asynchronously."""
        response = await async_kibana_client.task_manager.health()

        assert response.meta.status == 200
        health = response.body
        assert health["status"] in ("OK", "warn", "error")
        for section in MONITORED_STATS_SECTIONS:
            assert section in health["stats"], f"missing stats section: {section}"
