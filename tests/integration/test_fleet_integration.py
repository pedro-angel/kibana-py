"""Integration tests for FleetClient against a live Kibana instance."""

import uuid

import pytest

from kibana.exceptions import BadRequestError, NotFoundError

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


class TestFleetSetup:
    """Live tests for POST /api/fleet/setup."""

    def test_setup_is_initialized_and_idempotent(self, kibana_client):
        """Test that Fleet setup reports initialized and can be re-run."""
        first = kibana_client.fleet.setup()
        assert first.meta.status == 200
        assert first.body["isInitialized"] is True
        assert isinstance(first.body["nonFatalErrors"], list)

        # Idempotent: calling it again succeeds with the same shape
        second = kibana_client.fleet.setup()
        assert second.body["isInitialized"] is True


class TestFleetSettings:
    """Live tests for GET/PUT /api/fleet/settings."""

    def test_get_settings(self, kibana_client):
        """Test reading the global Fleet settings."""
        result = kibana_client.fleet.get_settings()
        assert result.meta.status == 200
        item = result.body["item"]
        assert item["id"] == "fleet-default-settings"
        assert "prerelease_integrations_enabled" in item

    def test_update_settings_round_trip(self, kibana_client):
        """Test flipping prerelease_integrations_enabled and restoring it."""
        original = kibana_client.fleet.get_settings().body["item"][
            "prerelease_integrations_enabled"
        ]
        try:
            updated = kibana_client.fleet.update_settings(
                prerelease_integrations_enabled=not original
            )
            assert (
                updated.body["item"]["prerelease_integrations_enabled"] is not original
            )

            # The change is visible in a subsequent GET
            fetched = kibana_client.fleet.get_settings()
            assert (
                fetched.body["item"]["prerelease_integrations_enabled"] is not original
            )
        finally:
            restored = kibana_client.fleet.update_settings(
                prerelease_integrations_enabled=original
            )
            assert restored.body["item"]["prerelease_integrations_enabled"] is original


class TestFleetSpaceSettings:
    """Live tests for GET/PUT /api/fleet/space_settings."""

    def test_get_space_settings(self, kibana_client):
        """Test reading the Fleet space settings for the default space."""
        result = kibana_client.fleet.get_space_settings()
        assert result.meta.status == 200
        assert isinstance(result.body["item"]["allowed_namespace_prefixes"], list)

    def test_update_space_settings_round_trip(self, kibana_client):
        """Test setting allowed_namespace_prefixes and restoring the value."""
        original = kibana_client.fleet.get_space_settings().body["item"][
            "allowed_namespace_prefixes"
        ]
        # Live 9.4.3 rejects prefixes containing "-", so use a plain prefix
        test_prefixes = ["kbnpyfleettest"]
        try:
            updated = kibana_client.fleet.update_space_settings(
                allowed_namespace_prefixes=test_prefixes
            )
            assert updated.body["item"]["allowed_namespace_prefixes"] == test_prefixes

            fetched = kibana_client.fleet.get_space_settings()
            assert fetched.body["item"]["allowed_namespace_prefixes"] == test_prefixes
        finally:
            restored = kibana_client.fleet.update_space_settings(
                allowed_namespace_prefixes=original
            )
            assert restored.body["item"]["allowed_namespace_prefixes"] == original

    def test_update_space_settings_rejects_hyphenated_prefix(self, kibana_client):
        """Test the live 9.4.3 quirk: prefixes must not contain a hyphen.

        The published OpenAPI schema allows arbitrary strings, but the live
        server validates them; this documents the discrepancy.
        """
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.fleet.update_space_settings(
                allowed_namespace_prefixes=["kbnpy-fleet-bad"]
            )
        assert "Must not contain -" in str(exc_info.value)

    def test_space_settings_are_space_scoped(self, kibana_client):
        """Test that space settings written in one space don't leak elsewhere."""
        space_id = f"kbnpy-fleet-{uuid.uuid4().hex[:8]}"
        kibana_client.spaces.create(id=space_id, name=space_id)
        try:
            # New space starts with no prefixes
            initial = kibana_client.fleet.get_space_settings(space_id=space_id)
            assert initial.body["item"]["allowed_namespace_prefixes"] == []

            # Set prefixes only in the new space
            kibana_client.fleet.update_space_settings(
                allowed_namespace_prefixes=["kbnpyfleetscoped"],
                space_id=space_id,
            )
            scoped = kibana_client.fleet.get_space_settings(space_id=space_id)
            assert scoped.body["item"]["allowed_namespace_prefixes"] == [
                "kbnpyfleetscoped"
            ]

            # The default space is unaffected
            default = kibana_client.fleet.get_space_settings()
            assert "kbnpyfleetscoped" not in (
                default.body["item"]["allowed_namespace_prefixes"]
            )
        finally:
            kibana_client.spaces.delete(id=space_id)


class TestFleetHealthCheck:
    """Live tests for POST /api/fleet/health_check.

    The dev stack has no Fleet Server hosts configured, so the happy path
    (status ONLINE) cannot run; the route is exercised via its semantic 404.
    """

    def test_health_check_unknown_host_semantic_404(self, kibana_client):
        """Test that an unknown host ID returns the server's semantic 404."""
        host_id = f"kbnpy-fleet-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.fleet.health_check(id=host_id)
        # Assert the server's message so a routing typo can't pass as a 404
        assert f"The requested host id {host_id} does not exist." in str(exc_info.value)


class TestFleetCheckPermissions:
    """Live tests for GET /api/fleet/check-permissions."""

    def test_check_permissions_success(self, kibana_client):
        """Test that the superuser has all Fleet permissions."""
        result = kibana_client.fleet.check_permissions()
        assert result.meta.status == 200
        assert result.body["success"] is True

    def test_check_permissions_with_fleet_server_setup(self, kibana_client):
        """Test the fleetServerSetup query param round-trips live."""
        result = kibana_client.fleet.check_permissions(fleet_server_setup=True)
        assert result.body["success"] is True

    def test_check_permissions_in_default_space(self, kibana_client):
        """Test the space-scoped path variant against the default space."""
        result = kibana_client.fleet.check_permissions(space_id="default")
        assert result.body["success"] is True


class TestAsyncFleet:
    """Async round-trip tests for the Fleet core API."""

    @pytest.mark.asyncio
    async def test_async_setup_and_reads(self, async_kibana_client):
        """Test setup, settings, space settings and permissions (async)."""
        setup = await async_kibana_client.fleet.setup()
        assert setup.body["isInitialized"] is True

        settings = await async_kibana_client.fleet.get_settings()
        assert settings.body["item"]["id"] == "fleet-default-settings"

        space_settings = await async_kibana_client.fleet.get_space_settings()
        assert isinstance(
            space_settings.body["item"]["allowed_namespace_prefixes"], list
        )

        perms = await async_kibana_client.fleet.check_permissions()
        assert perms.body["success"] is True

    @pytest.mark.asyncio
    async def test_async_update_settings_round_trip(self, async_kibana_client):
        """Test updating and restoring a global Fleet setting (async)."""
        current = await async_kibana_client.fleet.get_settings()
        original = current.body["item"]["prerelease_integrations_enabled"]
        try:
            updated = await async_kibana_client.fleet.update_settings(
                prerelease_integrations_enabled=not original
            )
            assert (
                updated.body["item"]["prerelease_integrations_enabled"] is not original
            )
        finally:
            restored = await async_kibana_client.fleet.update_settings(
                prerelease_integrations_enabled=original
            )
            assert restored.body["item"]["prerelease_integrations_enabled"] is original

    @pytest.mark.asyncio
    async def test_async_health_check_semantic_404(self, async_kibana_client):
        """Test the health check semantic 404 with the async client."""
        host_id = f"kbnpy-fleet-missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.fleet.health_check(id=host_id)
        assert f"The requested host id {host_id} does not exist." in str(exc_info.value)
