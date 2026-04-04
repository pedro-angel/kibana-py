"""Unit tests for ActionsClient."""

import pytest

from kibana.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class TestActionsClientInitialization:
    """Tests for ActionsClient initialization."""

    def test_init_with_base_client(self, mock_transport):
        """Test ActionsClient initialization with BaseClient."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        assert actions_client._client is base_client

    def test_inherits_from_namespace_client(self, mock_transport):
        """Test that ActionsClient inherits from NamespaceClient."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient
        from kibana._sync.client.utils import NamespaceClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        assert isinstance(actions_client, NamespaceClient)


class TestActionsClientCreate:
    """Tests for ActionsClient.create() method."""

    def test_create_with_required_params(self, mock_transport, mock_response):
        """Test create() with required parameters."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Test Webhook",
                "connector_type_id": ".webhook",
                "config": {"url": "https://example.com/webhook"},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
        )

        # Verify the request was made correctly
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/actions/connector"
        assert call_args[1]["body"] == {
            "name": "Test Webhook",
            "connector_type_id": ".webhook",
            "config": {"url": "https://example.com/webhook"},
        }

        # Verify response
        assert result.body["id"] == "test-connector-id"
        assert result.body["name"] == "Test Webhook"

    def test_create_with_secrets(self, mock_transport, mock_response):
        """Test create() with secrets parameter."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Test Slack",
                "connector_type_id": ".slack",
                "config": {},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        _ = actions_client.create(
            name="Test Slack",
            connector_type_id=".slack",
            config={},
            secrets={"webhookUrl": "https://hooks.slack.com/services/..."},
        )

        # Verify the request includes secrets
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["body"]["secrets"] == {
            "webhookUrl": "https://hooks.slack.com/services/..."
        }

    def test_create_validates_required_params(self, mock_transport):
        """Test that create() validates required parameters."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        # Test missing name
        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            actions_client.create(
                name="",
                connector_type_id=".webhook",
                config={"url": "https://example.com"},
            )

        # Test missing connector_type_id
        with pytest.raises(
            ValueError, match="Parameter 'connector_type_id' is required"
        ):
            actions_client.create(
                name="Test",
                connector_type_id="",
                config={"url": "https://example.com"},
            )

        # Test missing config
        with pytest.raises(ValueError, match="Parameter 'config' is required"):
            actions_client.create(
                name="Test",
                connector_type_id=".webhook",
                config=None,
            )

    def test_create_handles_400_error(self, mock_transport, mock_response):
        """Test create() handles 400 Bad Request error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Invalid connector configuration"}},
            status=400,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(BadRequestError) as exc_info:
            actions_client.create(
                name="Test",
                connector_type_id=".webhook",
                config={"invalid": "config"},
            )

        assert exc_info.value.status_code == 400

    def test_create_handles_409_conflict(self, mock_transport, mock_response):
        """Test create() handles 409 Conflict error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Connector already exists"}},
            status=409,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(ConflictError) as exc_info:
            actions_client.create(
                name="Existing Connector",
                connector_type_id=".webhook",
                config={"url": "https://example.com"},
            )

        assert exc_info.value.status_code == 409


class TestActionsClientGet:
    """Tests for ActionsClient.get() method."""

    def test_get_by_id(self, mock_transport, mock_response):
        """Test get() retrieves connector by ID."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Test Webhook",
                "connector_type_id": ".webhook",
                "config": {"url": "https://example.com/webhook"},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.get(id="test-connector-id")

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/api/actions/connector/test-connector-id"

        # Verify response
        assert result.body["id"] == "test-connector-id"

    def test_get_validates_required_id(self, mock_transport):
        """Test that get() validates required id parameter."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            actions_client.get(id="")

    def test_get_handles_404_error(self, mock_transport, mock_response):
        """Test get() handles 404 Not Found error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Connector not found"}},
            status=404,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            actions_client.get(id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestActionsClientGetAll:
    """Tests for ActionsClient.get_all() method."""

    def test_get_all_connectors(self, mock_transport, mock_response):
        """Test get_all() retrieves all connectors."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body=[
                {
                    "id": "connector-1",
                    "name": "Webhook 1",
                    "connector_type_id": ".webhook",
                },
                {
                    "id": "connector-2",
                    "name": "Slack 1",
                    "connector_type_id": ".slack",
                },
            ],
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.get_all()

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/api/actions/connectors"

        # Verify response
        assert len(result.body) == 2
        assert result.body[0]["id"] == "connector-1"
        assert result.body[1]["id"] == "connector-2"

    def test_get_all_handles_auth_error(self, mock_transport, mock_response):
        """Test get_all() handles authentication error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Unauthorized"}},
            status=401,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(AuthenticationException) as exc_info:
            actions_client.get_all()

        assert exc_info.value.status_code == 401


class TestActionsClientListTypes:
    """Tests for ActionsClient.list_types() method."""

    def test_list_types(self, mock_transport, mock_response):
        """Test list_types() retrieves available connector types."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body=[
                {
                    "id": ".webhook",
                    "name": "Webhook",
                    "enabled": True,
                },
                {
                    "id": ".slack",
                    "name": "Slack",
                    "enabled": True,
                },
                {
                    "id": ".email",
                    "name": "Email",
                    "enabled": True,
                },
            ],
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.list_types()

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/api/actions/connector_types"

        # Verify response
        assert len(result.body) == 3
        assert result.body[0]["id"] == ".webhook"
        assert result.body[1]["id"] == ".slack"
        assert result.body[2]["id"] == ".email"


class TestActionsClientUpdate:
    """Tests for ActionsClient.update() method."""

    def test_update_connector(self, mock_transport, mock_response):
        """Test update() modifies an existing connector."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Updated Webhook",
                "connector_type_id": ".webhook",
                "config": {"url": "https://updated.example.com/webhook"},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.update(
            id="test-connector-id",
            name="Updated Webhook",
            config={"url": "https://updated.example.com/webhook"},
        )

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "PUT"
        assert call_args[1]["target"] == "/api/actions/connector/test-connector-id"
        assert call_args[1]["body"] == {
            "name": "Updated Webhook",
            "config": {"url": "https://updated.example.com/webhook"},
        }

        # Verify response
        assert result.body["name"] == "Updated Webhook"

    def test_update_with_secrets(self, mock_transport, mock_response):
        """Test update() with secrets parameter."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Updated Slack",
                "connector_type_id": ".slack",
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        actions_client.update(
            id="test-connector-id",
            name="Updated Slack",
            secrets={"webhookUrl": "https://hooks.slack.com/services/new..."},
        )

        # Verify the request includes secrets
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["body"]["secrets"] == {
            "webhookUrl": "https://hooks.slack.com/services/new..."
        }

    def test_update_validates_required_id(self, mock_transport):
        """Test that update() validates required id parameter."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            actions_client.update(id="", name="Updated Name")

    def test_update_handles_404_error(self, mock_transport, mock_response):
        """Test update() handles 404 Not Found error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Connector not found"}},
            status=404,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            actions_client.update(id="nonexistent-id", name="New Name")

        assert exc_info.value.status_code == 404


class TestActionsClientDelete:
    """Tests for ActionsClient.delete() method."""

    def test_delete_connector(self, mock_transport, mock_response):
        """Test delete() removes a connector."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(body={}, status=204)

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.delete(id="test-connector-id")

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "DELETE"
        assert call_args[1]["target"] == "/api/actions/connector/test-connector-id"

        # Verify response
        assert result.meta.status == 204

    def test_delete_validates_required_id(self, mock_transport):
        """Test that delete() validates required id parameter."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            actions_client.delete(id="")

    def test_delete_handles_404_error(self, mock_transport, mock_response):
        """Test delete() handles 404 Not Found error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Connector not found"}},
            status=404,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            actions_client.delete(id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestActionsClientExecute:
    """Tests for ActionsClient.execute() method."""

    def test_execute_connector(self, mock_transport, mock_response):
        """Test execute() runs a connector with parameters."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={
                "connector_id": "test-connector-id",
                "status": "ok",
                "data": {"message": "Webhook executed successfully"},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        result = actions_client.execute(
            id="test-connector-id",
            params={"message": "Test alert", "severity": "high"},
        )

        # Verify the request
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert (
            call_args[1]["target"]
            == "/api/actions/connector/test-connector-id/_execute"
        )
        assert call_args[1]["body"] == {
            "params": {"message": "Test alert", "severity": "high"}
        }

        # Verify response
        assert result.body["status"] == "ok"
        assert result.body["connector_id"] == "test-connector-id"

    def test_execute_validates_required_params(self, mock_transport):
        """Test that execute() validates required parameters."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        # Test missing id
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            actions_client.execute(id="", params={"message": "test"})

        # Test missing params
        with pytest.raises(ValueError, match="Parameter 'params' is required"):
            actions_client.execute(id="test-id", params=None)

    def test_execute_handles_400_error(self, mock_transport, mock_response):
        """Test execute() handles 400 Bad Request error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Invalid execution parameters"}},
            status=400,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(BadRequestError) as exc_info:
            actions_client.execute(
                id="test-connector-id",
                params={"invalid": "params"},
            )

        assert exc_info.value.status_code == 400

    def test_execute_handles_404_error(self, mock_transport, mock_response):
        """Test execute() handles 404 Not Found error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Connector not found"}},
            status=404,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            actions_client.execute(
                id="nonexistent-id",
                params={"message": "test"},
            )

        assert exc_info.value.status_code == 404


class TestActionsClientErrorHandling:
    """Tests for error handling across all ActionsClient methods."""

    def test_handles_authorization_error(self, mock_transport, mock_response):
        """Test that all methods handle 403 Authorization error."""
        from kibana._sync.client._base import BaseClient
        from kibana._sync.client.actions import ActionsClient

        mock_transport.perform_request.return_value = mock_response(
            body={"error": {"message": "Insufficient privileges"}},
            status=403,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client)

        # Test create
        with pytest.raises(AuthorizationException):
            actions_client.create(
                name="Test",
                connector_type_id=".webhook",
                config={"url": "https://example.com"},
            )

        # Test get
        with pytest.raises(AuthorizationException):
            actions_client.get(id="test-id")

        # Test get_all
        with pytest.raises(AuthorizationException):
            actions_client.get_all()

        # Test list_types
        with pytest.raises(AuthorizationException):
            actions_client.list_types()

        # Test update
        with pytest.raises(AuthorizationException):
            actions_client.update(id="test-id", name="New Name")

        # Test delete
        with pytest.raises(AuthorizationException):
            actions_client.delete(id="test-id")

        # Test execute
        with pytest.raises(AuthorizationException):
            actions_client.execute(id="test-id", params={"message": "test"})
