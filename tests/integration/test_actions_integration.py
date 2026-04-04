"""Integration tests for ActionsClient."""

import uuid

import pytest

from kibana.exceptions import AuthorizationException, BadRequestError, NotFoundError

from .utils import (
    create_test_kibana_client,
    get_integration_test_config,
    is_kibana_available,
    safe_delete_connector,
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
def kibana_client_basic_auth():
    """Create a Kibana client for testing with basic auth."""
    client = create_test_kibana_client(auth_method="basic")
    yield client
    client.close()


@pytest.fixture
def kibana_client_api_key():
    """Create a Kibana client for testing with API key."""
    client = create_test_kibana_client(auth_method="api_key")
    yield client
    client.close()


@pytest.fixture
def created_connectors():
    """Track connectors created during tests for automatic cleanup."""
    connector_ids: list[str] = []
    yield connector_ids

    # Cleanup: Delete all created connectors
    if connector_ids:
        client = create_test_kibana_client()
        try:
            for connector_id in connector_ids:
                try:
                    safe_delete_connector(client, connector_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup connector {connector_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def unique_connector_name():
    """Generate a unique connector name for testing."""
    return f"test-connector-{uuid.uuid4().hex[:8]}"


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


def create_test_connector(
    client, created_connectors, name, connector_type_id, config, secrets=None
):
    """
    Helper to create a connector and track it for cleanup.

    :param client: Kibana client
    :param created_connectors: List to track created connector IDs
    :param name: Connector name
    :param connector_type_id: Connector type ID
    :param config: Connector configuration
    :param secrets: Connector secrets (optional)
    :return: Created connector data
    """
    try:
        response = client.actions.create(
            name=name,
            connector_type_id=connector_type_id,
            config=config,
            secrets=secrets,
        )
    except AuthorizationException as e:
        # Check for license error or just general forbidden for webhook
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


class TestActionsClientConnectivity:
    """Tests for basic ActionsClient connectivity and authentication."""

    def test_actions_client_exists(self, kibana_client):
        """Test that ActionsClient is accessible via the main client."""
        assert hasattr(kibana_client, "actions")
        assert kibana_client.actions is not None

    def test_list_connector_types(self, kibana_client):
        """Test listing available connector types."""
        response = kibana_client.actions.list_types()

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

    def test_get_all_connectors_empty_initially(self, kibana_client):
        """Test getting all connectors when none exist."""
        response = kibana_client.actions.get_all()

        assert response.meta.status == 200
        assert isinstance(response.body, list)
        # May or may not be empty depending on test environment

    def test_authentication_with_api_key(self, kibana_client_api_key):
        """Test that ActionsClient works with API key authentication."""
        response = kibana_client_api_key.actions.list_types()
        assert response.meta.status == 200
        assert isinstance(response.body, list)

    def test_authentication_with_basic_auth(self, kibana_client_basic_auth):
        """Test that ActionsClient works with basic authentication."""
        response = kibana_client_basic_auth.actions.list_types()
        assert response.meta.status == 200
        assert isinstance(response.body, list)


class TestActionsClientCRUD:
    """Tests for CRUD operations on action connectors."""

    def test_create_webhook_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test creating a webhook connector."""
        connector = create_test_connector(
            kibana_client,
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
        # Check that our original config fields are present
        for key, value in webhook_connector_config.items():
            assert connector["config"][key] == value

        # Secrets should not be returned in response
        assert "secrets" not in connector

        # Cleanup is handled automatically by the created_connectors fixture

    def test_create_server_log_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test creating a server-log connector (no secrets required)."""
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".server-log",
            server_log_connector_config,
        )

        assert "id" in connector
        assert connector["name"] == unique_connector_name
        assert connector["connector_type_id"] == ".server-log"

        # Cleanup is handled automatically by the created_connectors fixture

    def test_get_connector_by_id(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test retrieving a connector by ID."""
        # Create a connector first
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Get the connector
        response = kibana_client.actions.get(id=connector_id)

        assert response.meta.status == 200
        retrieved_connector = response.body

        assert retrieved_connector["id"] == connector_id
        assert retrieved_connector["name"] == unique_connector_name
        assert retrieved_connector["connector_type_id"] == ".webhook"

        # Check that our original config fields are present (Kibana may add additional fields)
        for key, value in webhook_connector_config.items():
            assert retrieved_connector["config"][key] == value

        # Cleanup is handled automatically by the created_connectors fixture

    def test_get_all_connectors_with_data(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test getting all connectors when connectors exist."""
        # Create a connector first
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Get all connectors
        response = kibana_client.actions.get_all()

        assert response.meta.status == 200
        connectors = response.body
        assert isinstance(connectors, list)
        assert len(connectors) > 0

        # Find our connector in the list
        our_connector = next((c for c in connectors if c["id"] == connector_id), None)
        assert our_connector is not None
        assert our_connector["name"] == unique_connector_name

        # Cleanup is handled automatically by the created_connectors fixture

    def test_update_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test updating a connector."""
        # Create a connector first
        connector = create_test_connector(
            kibana_client,
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

        response = kibana_client.actions.update(
            id=connector_id, name=new_name, config=new_config, secrets=new_secrets
        )

        assert response.meta.status == 200
        updated_connector = response.body

        assert updated_connector["id"] == connector_id
        assert updated_connector["name"] == new_name

        # Check that our updated config fields are present (Kibana may add additional fields)
        for key, value in new_config.items():
            assert updated_connector["config"][key] == value

        # Verify the update by getting the connector
        get_response = kibana_client.actions.get(id=connector_id)
        assert get_response.body["name"] == new_name
        for key, value in new_config.items():
            assert get_response.body["config"][key] == value

        # Clean up
        safe_delete_connector(kibana_client, connector_id)

    def test_update_connector_partial(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test partially updating a connector (only name)."""
        # Create a connector first
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Update only the name - for webhook connectors, we need to provide config too
        new_name = f"{unique_connector_name}-partial-update"

        response = kibana_client.actions.update(
            id=connector_id,
            name=new_name,
            config=webhook_connector_config,  # Webhook connectors require config on update
        )

        assert response.meta.status == 200
        updated_connector = response.body

        assert updated_connector["id"] == connector_id
        assert updated_connector["name"] == new_name

        # Config should contain our original fields (Kibana may add additional fields)
        for key, value in webhook_connector_config.items():
            assert updated_connector["config"][key] == value

        # Clean up
        safe_delete_connector(kibana_client, connector_id)

    def test_delete_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test deleting a connector."""
        # Create a connector first
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Delete the connector - may return empty response
        try:
            response = kibana_client.actions.delete(id=connector_id)
            # If we get a response, it should be 200
            assert response.meta.status == 200
        except Exception:
            # DELETE may return empty response, which is acceptable
            pass

        # Verify it's deleted by trying to get it
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector_id)


class TestActionsClientExecution:
    """Tests for executing action connectors."""

    def test_execute_server_log_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        server_log_connector_config,
    ):
        """Test executing a server-log connector."""
        # Create a server-log connector
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".server-log",
            server_log_connector_config,
        )
        connector_id = connector["id"]

        # Execute the connector
        execution_params = {
            "message": "Test log message from integration test",
            "level": "info",
        }

        response = kibana_client.actions.execute(
            id=connector_id, params=execution_params
        )

        assert response.meta.status == 200
        result = response.body

        # Server-log connector should return success status
        assert "status" in result
        assert result["status"] == "ok"

        # Cleanup is handled automatically by the created_connectors fixture

    def test_execute_webhook_connector(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test executing a webhook connector."""
        # Create a webhook connector
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]

        # Execute the connector
        execution_params = {
            "body": '{"message": "Test webhook execution", "timestamp": "2024-01-01T12:00:00Z"}'
        }

        response = kibana_client.actions.execute(
            id=connector_id, params=execution_params
        )

        assert response.meta.status == 200
        result = response.body

        # Webhook connector should return execution details
        assert "status" in result
        # httpbin.org should return success
        assert result["status"] == "ok"

        # Clean up
        safe_delete_connector(kibana_client, connector_id)


class TestActionsClientErrorHandling:
    """Tests for error handling in ActionsClient."""

    def test_get_nonexistent_connector(self, kibana_client):
        """Test that getting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.actions.get(id="nonexistent-connector-12345")

        assert exc_info.value.status_code == 404
        assert exc_info.value.meta is not None
        assert exc_info.value.body is not None

    def test_update_nonexistent_connector(self, kibana_client):
        """Test that updating a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.actions.update(
                id="nonexistent-connector-12345", name="Updated Name"
            )

        assert exc_info.value.status_code == 404

    def test_delete_nonexistent_connector(self, kibana_client):
        """Test that deleting a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.actions.delete(id="nonexistent-connector-12345")

        assert exc_info.value.status_code == 404

    def test_execute_nonexistent_connector(self, kibana_client):
        """Test that executing a non-existent connector raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            kibana_client.actions.execute(
                id="nonexistent-connector-12345", params={"message": "test"}
            )

        assert exc_info.value.status_code == 404

    def test_create_connector_with_invalid_type(
        self, kibana_client, unique_connector_name
    ):
        """Test that creating a connector with invalid type raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.actions.create(
                name=unique_connector_name,
                connector_type_id=".nonexistent-type",
                config={},
            )

        assert exc_info.value.status_code == 400

    def test_create_connector_with_invalid_config(
        self, kibana_client, unique_connector_name
    ):
        """Test that creating a connector with invalid config raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            kibana_client.actions.create(
                name=unique_connector_name,
                connector_type_id=".webhook",
                config={
                    "invalid_field": "invalid_value"
                },  # Missing required 'url' field
            )

        assert exc_info.value.status_code == 400

    def test_execute_connector_with_invalid_params(
        self, kibana_client, unique_connector_name, server_log_connector_config
    ):
        """Test that executing a connector with invalid params may succeed (server-log is flexible)."""
        # Create a server-log connector
        create_response = kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
        )
        connector_id = create_response.body["id"]

        try:
            # Execute with non-standard parameters - server-log is flexible and may accept this
            response = kibana_client.actions.execute(
                id=connector_id, params={"custom_message": "test message"}
            )
            # If it succeeds, that's fine - server-log is flexible
            assert response.meta.status == 200
        except BadRequestError:
            # If it fails with BadRequestError, that's also acceptable
            pass
        finally:
            # Clean up
            safe_delete_connector(kibana_client, connector_id)


class TestActionsClientParameterValidation:
    """Tests for parameter validation in ActionsClient methods."""

    def test_create_requires_name(self, kibana_client):
        """Test that create() requires name parameter."""
        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            kibana_client.actions.create(
                name="", connector_type_id=".webhook", config={}
            )

    def test_create_requires_connector_type_id(self, kibana_client):
        """Test that create() requires connector_type_id parameter."""
        with pytest.raises(
            ValueError, match="Parameter 'connector_type_id' is required"
        ):
            kibana_client.actions.create(
                name="Test Connector", connector_type_id="", config={}
            )

    def test_create_requires_config(self, kibana_client):
        """Test that create() requires config parameter."""
        with pytest.raises(ValueError, match="Parameter 'config' is required"):
            kibana_client.actions.create(
                name="Test Connector", connector_type_id=".webhook", config=None
            )

    def test_get_requires_id(self, kibana_client):
        """Test that get() requires id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.actions.get(id="")

    def test_update_requires_id(self, kibana_client):
        """Test that update() requires id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.actions.update(id="", name="Test")

    def test_delete_requires_id(self, kibana_client):
        """Test that delete() requires id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.actions.delete(id="")

    def test_execute_requires_id(self, kibana_client):
        """Test that execute() requires id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.actions.execute(id="", params={})

    def test_execute_requires_params(self, kibana_client):
        """Test that execute() requires params parameter."""
        with pytest.raises(ValueError, match="Parameter 'params' is required"):
            kibana_client.actions.execute(id="test-id", params=None)


class TestActionsClientWithOptions:
    """Tests for ActionsClient with client options."""

    def test_actions_with_custom_timeout(
        self, kibana_client, unique_connector_name, server_log_connector_config
    ):
        """Test that ActionsClient works with custom timeout options."""
        # Create client with custom timeout
        client_with_timeout = kibana_client.options(request_timeout=60.0)

        # Should still be able to use actions
        response = client_with_timeout.actions.list_types()
        assert response.meta.status == 200

    def test_actions_with_custom_headers(self, kibana_client):
        """Test that ActionsClient works with custom headers."""
        # Create client with custom headers
        client_with_headers = kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to use actions
        response = client_with_headers.actions.list_types()
        assert response.meta.status == 200

    def test_actions_with_different_auth(self, kibana_client):
        """Test that ActionsClient works when switching authentication methods."""
        # Get API key from configuration
        _, _, api_key = get_integration_test_config()

        if api_key:
            # Switch to API key authentication
            client_with_api_key = kibana_client.options(api_key=api_key)

            # Should still be able to use actions
            response = client_with_api_key.actions.list_types()
            assert response.meta.status == 200
        else:
            # Skip test if no API key available
            pytest.skip("API key not available for authentication switching test")


class TestActionsClientComplexScenarios:
    """Tests for complex scenarios and edge cases."""

    def test_create_multiple_connectors_same_name(
        self, kibana_client, unique_connector_name, server_log_connector_config
    ):
        """Test creating multiple connectors with the same name (should be allowed)."""
        # Create first connector
        response1 = kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
        )
        connector_id1 = response1.body["id"]

        # Create second connector with same name (should be allowed)
        response2 = kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
        )
        connector_id2 = response2.body["id"]

        assert connector_id1 != connector_id2
        assert response1.body["name"] == response2.body["name"]

        # Clean up
        safe_delete_connector(kibana_client, connector_id1)
        safe_delete_connector(kibana_client, connector_id2)

    def test_connector_lifecycle_complete(
        self,
        kibana_client,
        created_connectors,
        unique_connector_name,
        webhook_connector_config,
        webhook_connector_secrets,
    ):
        """Test complete connector lifecycle: create -> get -> update -> execute -> delete."""
        # 1. Create
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            unique_connector_name,
            ".webhook",
            webhook_connector_config,
            webhook_connector_secrets,
        )
        connector_id = connector["id"]
        assert connector["name"] == unique_connector_name

        # 2. Get
        get_response = kibana_client.actions.get(id=connector_id)
        assert get_response.body["id"] == connector_id
        assert get_response.body["name"] == unique_connector_name

        # 3. Update
        new_name = f"{unique_connector_name}-updated"
        new_config = {
            "url": "https://httpbin.org/put",
            "method": "put",
            "headers": {"Content-Type": "application/json"},
        }
        update_response = kibana_client.actions.update(
            id=connector_id, name=new_name, config=new_config
        )
        assert update_response.body["name"] == new_name

        # 4. Execute
        execute_response = kibana_client.actions.execute(
            id=connector_id, params={"body": '{"test": "execution"}'}
        )
        assert execute_response.meta.status == 200

        # 5. Delete
        try:
            delete_response = kibana_client.actions.delete(id=connector_id)
            # If we get a response, it should be 200
            if hasattr(delete_response, "meta"):
                assert delete_response.meta.status == 200
        except Exception:
            # DELETE may return empty response, which is acceptable
            pass

        # 6. Verify deletion
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector_id)

    def test_list_types_structure_validation(self, kibana_client):
        """Test that list_types returns properly structured data."""
        response = kibana_client.actions.list_types()

        assert response.meta.status == 200
        connector_types = response.body
        assert isinstance(connector_types, list)
        assert len(connector_types) > 0

        # Validate structure of each connector type
        for connector_type in connector_types:
            assert isinstance(connector_type, dict)
            assert "id" in connector_type
            assert "name" in connector_type
            assert "enabled" in connector_type
            assert "enabled_in_config" in connector_type

            # ID should start with a dot
            assert connector_type["id"].startswith(".")

            # Name should be a non-empty string
            assert isinstance(connector_type["name"], str)
            assert len(connector_type["name"]) > 0

            # Enabled fields should be boolean
            assert isinstance(connector_type["enabled"], bool)
            assert isinstance(connector_type["enabled_in_config"], bool)

    def test_get_all_connectors_structure_validation(
        self, kibana_client, unique_connector_name, server_log_connector_config
    ):
        """Test that get_all returns properly structured data."""
        # Create a connector to ensure we have data
        create_response = kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config=server_log_connector_config,
        )
        connector_id = create_response.body["id"]

        try:
            response = kibana_client.actions.get_all()

            assert response.meta.status == 200
            connectors = response.body
            assert isinstance(connectors, list)
            assert len(connectors) > 0

            # Find our connector and validate its structure
            our_connector = next(
                (c for c in connectors if c["id"] == connector_id), None
            )
            assert our_connector is not None

            # Validate connector structure
            assert "id" in our_connector
            assert "name" in our_connector
            assert "connector_type_id" in our_connector
            assert "config" in our_connector
            assert "is_preconfigured" in our_connector
            assert "is_deprecated" in our_connector

            # Validate data types
            assert isinstance(our_connector["id"], str)
            assert isinstance(our_connector["name"], str)
            assert isinstance(our_connector["connector_type_id"], str)
            assert isinstance(our_connector["config"], dict)
            assert isinstance(our_connector["is_preconfigured"], bool)
            assert isinstance(our_connector["is_deprecated"], bool)

        finally:
            # Clean up
            safe_delete_connector(kibana_client, connector_id)
