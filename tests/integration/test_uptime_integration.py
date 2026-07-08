"""Integration tests for the Uptime API clients.

These tests run against a live Kibana instance. The stack is shared with
other test runs, so every test that updates the uptime settings reads the
current values first and restores them in a ``finally`` block. The
space-scoped tests create (and always delete) a dedicated space prefixed
with ``kbnpy-uptime-``.
"""

import uuid

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

SETTINGS_KEYS = (
    "heartbeatIndices",
    "certExpirationThreshold",
    "certAgeThreshold",
    "defaultConnectors",
    "defaultEmail",
)


def _restore_kwargs(original: dict) -> dict:
    """Map an uptime settings body to update_settings() keyword arguments."""
    return {
        "heartbeat_indices": original.get("heartbeatIndices"),
        "cert_expiration_threshold": original.get("certExpirationThreshold"),
        "cert_age_threshold": original.get("certAgeThreshold"),
        "default_connectors": original.get("defaultConnectors"),
        "default_email": original.get("defaultEmail"),
    }


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


class TestUptimeSettingsGet:
    """Live tests for UptimeClient.get_settings()."""

    def test_uptime_client_exists(self, kibana_client):
        """Test that UptimeClient is accessible via the main client."""
        assert hasattr(kibana_client, "uptime")
        assert kibana_client.uptime is not None

    def test_get_settings(self, kibana_client):
        """Test reading the uptime settings from the default space."""
        response = kibana_client.uptime.get_settings()

        assert response.meta.status == 200
        settings = response.body
        assert isinstance(settings, dict)
        for key in SETTINGS_KEYS:
            assert key in settings, f"missing settings key: {key}"

        assert isinstance(settings["heartbeatIndices"], str)
        assert isinstance(settings["certExpirationThreshold"], (int, float))
        assert isinstance(settings["certAgeThreshold"], (int, float))
        assert isinstance(settings["defaultConnectors"], list)
        assert isinstance(settings["defaultEmail"], dict)


class TestUptimeSettingsUpdate:
    """Live tests for UptimeClient.update_settings()."""

    def test_update_settings_partial_and_restore(self, kibana_client):
        """Test a partial update merges with existing settings; then restore."""
        original = kibana_client.uptime.get_settings().body
        new_cert_age = int(original["certAgeThreshold"]) + 1

        try:
            updated = kibana_client.uptime.update_settings(
                cert_age_threshold=new_cert_age
            )

            assert updated.meta.status == 200
            assert updated.body["certAgeThreshold"] == new_cert_age
            # Partial update: untouched keys are preserved (merge semantics)
            assert updated.body["heartbeatIndices"] == original["heartbeatIndices"]
            assert (
                updated.body["certExpirationThreshold"]
                == original["certExpirationThreshold"]
            )

            # The change is visible on a subsequent read
            reread = kibana_client.uptime.get_settings().body
            assert reread["certAgeThreshold"] == new_cert_age
        finally:
            kibana_client.uptime.update_settings(**_restore_kwargs(original))

        restored = kibana_client.uptime.get_settings().body
        assert restored["certAgeThreshold"] == original["certAgeThreshold"]

    def test_update_settings_multiple_fields_and_restore(self, kibana_client):
        """Test updating several settings at once; then restore."""
        original = kibana_client.uptime.get_settings().body

        try:
            updated = kibana_client.uptime.update_settings(
                heartbeat_indices="kbnpy-uptime-heartbeat-*",
                cert_expiration_threshold=14,
                default_email={"to": ["kbnpy-uptime@example.com"], "cc": [], "bcc": []},
            )

            assert updated.meta.status == 200
            assert updated.body["heartbeatIndices"] == "kbnpy-uptime-heartbeat-*"
            assert updated.body["certExpirationThreshold"] == 14
            assert updated.body["defaultEmail"]["to"] == ["kbnpy-uptime@example.com"]
            # Untouched key preserved
            assert updated.body["certAgeThreshold"] == original["certAgeThreshold"]
        finally:
            kibana_client.uptime.update_settings(**_restore_kwargs(original))

        restored = kibana_client.uptime.get_settings().body
        for key in SETTINGS_KEYS:
            assert restored[key] == original[key], f"key not restored: {key}"


class TestUptimeSettingsSpaceScoped:
    """Live tests for space-scoped uptime settings."""

    @pytest.fixture
    def test_space(self, kibana_client):
        """Create a dedicated space and delete it (and its settings) afterwards."""
        space_id = f"kbnpy-uptime-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        yield space_id
        kibana_client.spaces.delete(id=space_id)

    def test_settings_are_per_space(self, kibana_client, test_space):
        """Test that updating settings in one space does not leak to another."""
        default_before = kibana_client.uptime.get_settings().body

        updated = kibana_client.uptime.update_settings(
            cert_age_threshold=123,
            space_id=test_space,
        )
        assert updated.body["certAgeThreshold"] == 123

        in_space = kibana_client.uptime.get_settings(space_id=test_space).body
        assert in_space["certAgeThreshold"] == 123

        # The default space settings are unaffected
        default_after = kibana_client.uptime.get_settings().body
        assert default_after["certAgeThreshold"] == default_before["certAgeThreshold"]


class TestAsyncUptimeSettings:
    """Live tests for AsyncUptimeClient."""

    async def test_async_get_settings(self, async_kibana_client):
        """Test reading the uptime settings asynchronously."""
        response = await async_kibana_client.uptime.get_settings()

        assert response.meta.status == 200
        for key in SETTINGS_KEYS:
            assert key in response.body, f"missing settings key: {key}"

    async def test_async_update_settings_and_restore(self, async_kibana_client):
        """Test an async partial update round-trip; then restore."""
        original = (await async_kibana_client.uptime.get_settings()).body
        new_threshold = int(original["certExpirationThreshold"]) + 1

        try:
            updated = await async_kibana_client.uptime.update_settings(
                cert_expiration_threshold=new_threshold
            )

            assert updated.meta.status == 200
            assert updated.body["certExpirationThreshold"] == new_threshold
            assert updated.body["heartbeatIndices"] == original["heartbeatIndices"]
        finally:
            await async_kibana_client.uptime.update_settings(
                **_restore_kwargs(original)
            )

        restored = (await async_kibana_client.uptime.get_settings()).body
        assert (
            restored["certExpirationThreshold"] == original["certExpirationThreshold"]
        )
