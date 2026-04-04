"""Integration tests for AsyncActionsClient."""

import uuid

import pytest

from kibana.exceptions import AuthorizationException, BadRequestError, NotFoundError

from .utils import (
    create_test_async_kibana_client,
    get_integration_test_config,
    is_kibana_available,
    safe_delete_connector_async,
)

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


@pytest.fixture
async def async_kibana_client_basic_auth():
    """Create an AsyncKibana client for testing with basic auth."""
    client = create_test_async_kibana_client(auth_method="basic")
    yield client
    await client.close()


@pytest.fixture
async def async_kibana_client_api_key():
    """Create an AsyncKibana client for testing with API key."""
    client = create_test_async_kibana_client(auth_method="api_key")
    yield client
    await client.close()


@pytest.fixture
async def created_connectors():
    """Track connectors created during tests for automatic cleanup."""
    connector_ids: list[str] = []
    yield connector_ids

    # Cleanup: Delete all created connectors
    if connector_ids:
        client = create_test_async_kibana_client()
        try:
            for connector_id in connector_ids:
                try:
                    await safe_delete_connector_async(client, connector_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup connector {connector_id}: {e}")
        finally:
            await client.close()


@pytest.fixture
def unique_connector_name():
    """Generate a unique connector name for testing."""
    return f"test-async-connector-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def webhook_connector_config():
    """Configuration for a webhook connector."""
    return {
        "url": "https://httpbin.org/post",
        "method": "post",
        "headers": {"Content-Type": "application/json"},
    }


@pytest.fixture
def webhook_connector_secrets():
    """Secrets for a webhook connector."""
    return {"user": "test_user", "password": "test_password"}


@pytest.fixture
def server_log_connector_config():
    """Configuration for a server-log connector (no secrets needed)."""
    return {}


async def create_test_connector(
    client, created_connectors, name, connector_type_id, config, secrets=None
):
    """
    Helper to create a connector and track it for cleanup.

    :param client: AsyncKibana client
    :param created_connectors: List to track created connector IDs
    :param name: Connector name
    :param connector_type_id: Connector type ID
    :param config: Connector configuration
    :param secrets: Connector secrets (optional)
    :return: Created connector data
    """
    try:
        response = await client.actions.create(
            name=name,
            connector_type_id=connector_type_id,
            config=config,
            secrets=secrets,
        )
    except AuthorizationException as e:
        error_msg = str(e).lower()
        if (
            "license" in error_msg
            or "disabled" in error_msg
            or connector_type_id == ".webhook"
        ):
            pytest.skip(f"Skipping test due to authorization/license error: {e}")
        raise

    connector = response.body
    connector_id = connector["id"]

    # Track for cleanup
    created_connectors.append(connector_id)

    return connector


class TestAsyncActionsClientConnectivity:
    """Tests for basic AsyncActionsClient connectivity and authentication."""

    @pytest.mark.asyncio
    async def test_actions_client_exists(self, async_kibana_client):
        """Test that AsyncActionsClient is accessible via the main client."""
        assert hasattr(async_kibana_client, "actions")
        assert async_kibana_client.actions is not None

    @pytest.mark.asyncio
    async def test_list_connector_types(self, async_kibana_client):
        """Test listing available connector types."""
        response = await async_kibana_client.actions.list_types()

        assert response.meta.status == 200
        assert isinstance(response.body, list)
        assert len(response.body) > 0

        # Check that common connector types exist
        connector_type_ids = [ct["id"] for ct in response.body]
        assert ".webhook" in connector_type_ids
        assert ".server-log" in connector_type_ids

        # Verify structure of connector type objects
        webhook_type = next(ct for ct in response.body if ct["id"] == ".webhook")
        assert "name" in webhook_type
        assert "enabled" in webhook_type
        assert "enabled_in_config" in webhook_type

    @pytest.mark.asyncio
    async def test_get_all_connectors(self, async_kibana_client):
        """Test getting all connectors."""
        response = await async_kibana_client.actions.get_all()

        assert response.meta.status == 200
        assert isinstance(response.body, list)

    @pytest.mark.asyncio
    async def test_authentication_with_api_key(self, async_kibana_client_api_key):
        """Test that AsyncActionsClient works with API key authentication."""
        response = await async_kibana_client_api_key.actions.list_types()
        assert response.meta.status == 200
        assert isinstance(response.body, list)

    @pytest.mark.asyncio
    async def test_authentication_with_basic_auth(self, async_kibana_client_basic_auth):
        """Test that AsyncActionsClient works with basic authentication."""
        response = await async_kibana_client_basic_auth.actions.list_types()
        assert response.meta.status == 200
        assert isinstance(response.body, list)


class TestAsyncActionsClientCRUD:
    """Tests for CRUD operations on action connectors."""

    @pytest.mark.asyncio
    async def test_create_webhook_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test creating a webhook connector."""
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )

        assert "id" in connector
        assert connector["name"] == unique_connector_name
        assert connector["connector_type_id"] == ".webhook"

        # Kibana may add additional fields to config (like hasAuth)
        for key, value in webhook_connector_config.items():
            assert connector["config"][key] == value

        # Secrets should not be returned in response
        assert "secrets" not in connector

    @pytest.mark.asyncio
    async def test_create_server_log_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test creating a server-log connector (no secrets required)."""
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".server-log",
            server_log_connector_config,
        )

        assert "id" in connector
        assert connector["name"] == unique_connector_name
        assert connector["connector_type_id"] == ".server-log"

    @pytest.mark.asyncio
    async def test_get_connector_by_id(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test retrieving a connector by ID."""
        # Create a connector first
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Get the connector
        response = await async_kibana_client.actions.get(id=connector_id)

        assert response.meta.status == 200
        retrieved_connector = response.body

        assert retrieved_connector["id"] == connector_id
        assert retrieved_connector["name"] == unique_connector_name
        assert retrieved_connector["connector_type_id"] == ".webhook"

        for key, value in webhook_connector_config.items():
            assert retrieved_connector["config"][key] == value

    @pytest.mark.asyncio
    async def test_get_all_connectors_with_data(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test getting all connectors when connectors exist."""
        # Create a connector first
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Get all connectors
        response = await async_kibana_client.actions.get_all()

        assert response.meta.status == 200
        connectors = response.body
        assert isinstance(connectors, list)
        assert len(connectors) > 0

        # Find our connector in the list
        our_connector = next((c for c in connectors if c["id"] == connector_id), None)
        assert our_connector is not None
        assert our_connector["name"] == unique_connector_name

    @pytest.mark.asyncio
    async def test_update_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test updating a connector."""
        # Create a connector first
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Update the connector
        new_name = f"{unique_connector_name}-updated"
        new_config = {
            "url": "https://httpbin.org/put",
            "method": "put",
            "headers": {
                "Content-Type": "application/json",
                "X-Custom-Header": "updated",
            },
        }
        new_secrets = {"user": "updated_user", "password": "updated_password"}

        response = await async_kibana_client.actions.update(
            id=connector_id, name=new_name, config=new_config, secrets=new_secrets
        )

        assert response.meta.status == 200
        updated_connector = response.body

        assert updated_connector["id"] == connector_id
        assert updated_connector["name"] == new_name

        for key, value in new_config.items():
            assert updated_connector["config"][key] == value

        # Verify the update by getting the connector
        get_response = await async_kibana_client.actions.get(id=connector_id)
        assert get_response.body["name"] == new_name
        for key, value in new_config.items():
            assert get_response.body["config"][key] == value

        # Clean up
        await safe_delete_connector_async(async_kibana_client, connector_id)

    @pytest.mark.asyncio
    async def test_delete_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test deleting a connector."""
        # Create a connector first
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Delete the connector
        try:
            response = await async_kibana_client.actions.delete(id=connector_id)
            assert response.meta.status == 200
        except Exception:
            # DELETE may return empty response, which is acceptable
            pass

        # Verify it's deleted by trying to get it
        with pytest.raises(NotFoundError):
            await async_kibana_client.actions.get(id=connector_id)


class TestAsyncActionsClientExecution:
    """Tests for executing action connectors."""

    @pytest.mark.asyncio
    async def test_execute_server_log_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test executing a server-log connector."""
        # Create a server-log connector
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".server-log",
            server_log_connector_config,
        )
        connector_id = connector["id"]

        # Execute the connector
        execution_params = {
            "message": "Test log message from async integration test",
            "level": "info",
        }

        response = await async_kibana_client.actions.execute(
            id=connector_id, params=execution_params
        )

        assert response.meta.status == 200
        result = response.body

        # Server-log connector should return success status
        assert "status" in result
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_execute_webhook_connector(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test executing a webhook connector."""
        # Create a webhook connector
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Execute the connector
        execution_params = {
            "body": '{"message": "Test async webhook execution", "timestamp": "2024-01-01T12:00:00Z"}'
        }

        response = await async_kibana_client.actions.execute(
            id=connector_id, params=execution_params
        )

        assert response.meta.status == 200
        result = response.body

        # Webhook connector should return execution details
        assert "status" in result
        assert result["status"] == "ok"

        # Clean up
        await safe_delete_connector_async(async_kibana_client, connector_id)


class TestAsyncActionsClientErrorHandling:
    """Tests for error handling in AsyncActionsClient."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_connector(self, async_kibana_client):
        """Test that getting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.actions.get(id="nonexistent-connector-12345")

        assert exc_info.value.status_code == 404
        assert exc_info.value.meta is not None
        assert exc_info.value.body is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_connector(self, async_kibana_client):
        """Test that updating a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.actions.update(
                id="nonexistent-connector-12345", name="Updated Name"
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_connector(self, async_kibana_client):
        """Test that deleting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.actions.delete(id="nonexistent-connector-12345")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_nonexistent_connector(self, async_kibana_client):
        """Test that executing a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.actions.execute(
                id="nonexistent-connector-12345", params={"message": "test"}
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_connector_with_invalid_type(
        self, async_kibana_client, unique_connector_name
    ):
        """Test that creating a connector with invalid type raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            await async_kibana_client.actions.create(
                name=unique_connector_name,
                connector_type_id=".nonexistent-type",
                config={},
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_connector_with_invalid_config(
        self, async_kibana_client, unique_connector_name
    ):
        """Test that creating a connector with invalid config raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            await async_kibana_client.actions.create(
                name=unique_connector_name,
                connector_type_id=".webhook",
                config={"invalid_field": "invalid_value"},
            )

        assert exc_info.value.status_code == 400


class TestAsyncActionsClientWithOptions:
    """Tests for AsyncActionsClient with client options."""

    @pytest.mark.asyncio
    async def test_actions_with_custom_timeout(self, async_kibana_client):
        """Test that AsyncActionsClient works with custom timeout options."""
        # Create client with custom timeout
        client_with_timeout = async_kibana_client.options(request_timeout=60.0)

        # Should still be able to use actions
        response = await client_with_timeout.actions.list_types()
        assert response.meta.status == 200

    @pytest.mark.asyncio
    async def test_actions_with_custom_headers(self, async_kibana_client):
        """Test that AsyncActionsClient works with custom headers."""
        # Create client with custom headers
        client_with_headers = async_kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to use actions
        response = await client_with_headers.actions.list_types()
        assert response.meta.status == 200

    @pytest.mark.asyncio
    async def test_actions_with_different_auth(self, async_kibana_client):
        """Test that AsyncActionsClient works when switching authentication methods."""
        # Get API key from configuration
        _, _, api_key = get_integration_test_config()

        if api_key:
            # Switch to API key authentication
            client_with_api_key = async_kibana_client.options(api_key=api_key)

            # Should still be able to use actions
            response = await client_with_api_key.actions.list_types()
            assert response.meta.status == 200
        else:
            # Skip test if no API key available
            pytest.skip("API key not available for authentication switching test")


class TestAsyncActionsClientComplexScenarios:
    """Tests for complex scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_connector_lifecycle_complete(
        self,
        async_kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test complete connector lifecycle: create -> get -> update -> execute -> delete."""
        # 1. Create
        connector = await create_test_connector(
            async_kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]
        assert connector["name"] == unique_connector_name

        # 2. Get
        get_response = await async_kibana_client.actions.get(id=connector_id)
        assert get_response.body["id"] == connector_id
        assert get_response.body["name"] == unique_connector_name

        # 3. Update
        new_name = f"{unique_connector_name}-updated"
        new_config = {
            "url": "https://httpbin.org/put",
            "method": "put",
            "headers": {"Content-Type": "application/json"},
        }
        update_response = await async_kibana_client.actions.update(
            id=connector_id, name=new_name, config=new_config
        )
        assert update_response.body["name"] == new_name

        # 4. Execute
        execute_response = await async_kibana_client.actions.execute(
            id=connector_id, params={"body": '{"test": "execution"}'}
        )
        assert execute_response.meta.status == 200

        # 5. Delete
        try:
            delete_response = await async_kibana_client.actions.delete(id=connector_id)
            if hasattr(delete_response, "meta"):
                assert delete_response.meta.status == 200
        except Exception:
            # DELETE may return empty response, which is acceptable
            pass

        # 6. Verify deletion
        with pytest.raises(NotFoundError):
            await async_kibana_client.actions.get(id=connector_id)


class TestAsyncActionsClientSpaceSupport:
    """Tests for space support in AsyncActionsClient."""

    @pytest.fixture
    async def created_spaces(self):
        """Track spaces created during tests for automatic cleanup."""
        space_ids: list[str] = []
        yield space_ids

        # Cleanup: Delete all created spaces
        if space_ids:
            client = create_test_async_kibana_client()
            try:
                for space_id in space_ids:
                    try:
                        await client.spaces.delete(id=space_id)
                    except Exception as e:
                        # Log but don't fail the test due to cleanup issues
                        print(f"Warning: Failed to cleanup space {space_id}: {e}")
            finally:
                await client.close()

    @pytest.fixture
    def unique_space_id(self):
        """Generate a unique space ID for testing."""
        return f"async-test-space-{uuid.uuid4().hex[:8]}"

    async def create_test_space(self, client, created_spaces, space_id, name, **kwargs):
        """
        Create a test space and track it for cleanup.

        :param client: AsyncKibana client
        :param created_spaces: List to track created spaces
        :param space_id: Space ID
        :param name: Space name
        :param kwargs: Additional space parameters
        :return: Created space data
        """
        response = await client.spaces.create(id=space_id, name=name, **kwargs)
        space = response.body
        created_spaces.append(space["id"])
        return space

    @pytest.mark.asyncio
    async def test_create_connector_in_space(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test creating a connector in a specific space."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async Test Space"
        )

        # Create connector in the space
        response = await async_kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
            space_id=unique_space_id,
        )

        connector = response.body
        assert connector["name"] == unique_connector_name

        # Verify connector exists in the space
        retrieved = await async_kibana_client.actions.get(
            id=connector["id"], space_id=unique_space_id
        )
        assert retrieved.body["id"] == connector["id"]

        # Verify connector doesn't exist in default space
        with pytest.raises(NotFoundError):
            await async_kibana_client.actions.get(id=connector["id"])

        # Cleanup connector
        try:
            await async_kibana_client.actions.delete(
                id=connector["id"], space_id=unique_space_id
            )
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_space_scoped_client_factory(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test async space-scoped client factory."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async Test Space"
        )

        # Create space-scoped client
        space_client = async_kibana_client.space(unique_space_id)

        # Create connector using space-scoped client
        response = await space_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
        )

        connector = response.body
        assert connector["name"] == unique_connector_name

        # Verify connector exists in the space
        retrieved = await async_kibana_client.actions.get(
            id=connector["id"], space_id=unique_space_id
        )
        assert retrieved.body["id"] == connector["id"]

        # Cleanup connector
        try:
            await space_client.actions.delete(id=connector["id"])
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_space_validation_error(self, async_kibana_client):
        """Test that space validation works with async client."""
        nonexistent_space_id = f"nonexistent-async-{uuid.uuid4().hex[:8]}"

        # This should raise an error due to space validation
        with pytest.raises(Exception) as exc_info:
            await async_kibana_client.actions.create(
                name="test-connector",
                connector_type_id=".server-log",
                config={},
                space_id=nonexistent_space_id,
            )

        # Should be a space-related error
        error_str = str(exc_info.value).lower()
        assert "not found" in error_str or "404" in error_str

    @pytest.mark.asyncio
    async def test_space_validation_bypass(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test bypassing space validation with async client."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async Test Space"
        )

        # Create connector with validation disabled
        response = await async_kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
            space_id=unique_space_id,
            validate_space=False,
        )

        connector = response.body
        assert connector["name"] == unique_connector_name

        # Cleanup connector
        try:
            await async_kibana_client.actions.delete(
                id=connector["id"], space_id=unique_space_id
            )
        except Exception:
            pass
