"""Unit tests for AsyncConnectorsClient (and the deprecated AsyncActionsClient alias)."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client._base import AsyncBaseClient
from kibana._async.client.actions import AsyncActionsClient
from kibana._async.client.connectors import AsyncConnectorsClient
from kibana._async.client.utils import AsyncNamespaceClient
from kibana.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    InvalidSpaceIdError,
    NotFoundError,
)


@pytest.fixture
def connectors_client(mock_async_transport):
    """AsyncConnectorsClient wired to a mock transport (no space validation)."""
    base_client = AsyncBaseClient(_transport=mock_async_transport)
    return AsyncConnectorsClient(base_client, validate_spaces=False)


class TestAsyncConnectorsClientInitialization:
    """Tests for AsyncConnectorsClient initialization and wiring."""

    async def test_init_with_base_client(self, mock_async_transport):
        """Test AsyncConnectorsClient initialization with AsyncBaseClient."""
        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(base_client)

        assert client._client is base_client

    async def test_inherits_from_namespace_client(self, mock_async_transport):
        """Test that AsyncConnectorsClient inherits from AsyncNamespaceClient."""
        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(base_client)

        assert isinstance(client, AsyncNamespaceClient)

    async def test_init_with_space_context(self, mock_async_transport):
        """Test initialization with a default space and validation flag."""
        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(
            base_client, default_space_id="marketing", validate_spaces=False
        )

        assert client._default_space_id == "marketing"
        assert client._validate_spaces is False

    async def test_kibana_connectors_property(self, mock_async_transport):
        """Test that client.connectors returns an AsyncConnectorsClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.connectors, AsyncConnectorsClient)


class TestAsyncConnectorsClientCreate:
    """Tests for AsyncConnectorsClient.create() method."""

    async def test_create_with_required_params(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() with only the required parameters (no config)."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "generated-id",
                "name": "Server Log",
                "connector_type_id": ".server-log",
                "config": {},
            },
            status=200,
        )

        result = await connectors_client.create(
            name="Server Log", connector_type_id=".server-log"
        )

        mock_async_transport.perform_request.assert_called_once()
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/actions/connector"
        # config/secrets are omitted from the body when not provided
        assert call_kwargs["body"] == {
            "name": "Server Log",
            "connector_type_id": ".server-log",
        }
        assert result.body["id"] == "generated-id"

    async def test_create_with_config_and_secrets(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() passes config and secrets in the body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id"}, status=200
        )

        await connectors_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
            secrets={"user": "admin", "password": "secret"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "Test Webhook",
            "connector_type_id": ".webhook",
            "config": {"url": "https://example.com/webhook"},
            "secrets": {"user": "admin", "password": "secret"},
        }

    async def test_create_with_caller_specified_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() with a caller-specified connector ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "my fixed id"}, status=200
        )

        await connectors_client.create(
            id="my fixed id",
            name="Fixed",
            connector_type_id=".server-log",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        # id is URL-encoded into the path
        assert call_kwargs["target"] == "/api/actions/connector/my%20fixed%20id"

    async def test_create_with_space_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id"}, status=200
        )

        await connectors_client.create(
            name="Test",
            connector_type_id=".server-log",
            space_id="marketing",
            validate_space=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/actions/connector"

    async def test_create_validates_required_params(self, connectors_client):
        """Test that create() validates required parameters."""
        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            await connectors_client.create(name="", connector_type_id=".webhook")

        with pytest.raises(
            ValueError, match="Parameter 'connector_type_id' is required"
        ):
            await connectors_client.create(name="Test", connector_type_id="")

        with pytest.raises(ValueError, match="Parameter 'id' must be non-empty"):
            await connectors_client.create(
                id="", name="Test", connector_type_id=".server-log"
            )

    async def test_create_handles_400_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() handles 400 Bad Request error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Invalid connector configuration"},
            status=400,
        )

        with pytest.raises(BadRequestError) as exc_info:
            await connectors_client.create(
                name="Test",
                connector_type_id=".webhook",
                config={"invalid": "config"},
            )

        assert exc_info.value.status_code == 400

    async def test_create_handles_409_conflict(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test create() handles 409 Conflict error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Connector already exists"},
            status=409,
        )

        with pytest.raises(ConflictError) as exc_info:
            await connectors_client.create(
                id="already-there",
                name="Existing Connector",
                connector_type_id=".server-log",
            )

        assert exc_info.value.status_code == 409


class TestAsyncConnectorsClientGet:
    """Tests for AsyncConnectorsClient.get() method."""

    async def test_get_by_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get() retrieves connector by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Test Webhook",
                "connector_type_id": ".webhook",
            },
            status=200,
        )

        result = await connectors_client.get(id="test-connector-id")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connector/test-connector-id"
        assert result.body["id"] == "test-connector-id"

    async def test_get_quotes_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get() URL-encodes the connector ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "a/b c"}, status=200
        )

        await connectors_client.get(id="a/b c")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/actions/connector/a%2Fb%20c"

    async def test_get_with_default_space_id(self, mock_async_transport, mock_response):
        """Test get() applies the client-level default space ID."""
        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(
            base_client, default_space_id="marketing", validate_spaces=False
        )
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "x"}, status=200
        )

        await client.get(id="x")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/actions/connector/x"

    async def test_get_space_id_overrides_default(
        self, mock_async_transport, mock_response
    ):
        """Test that an explicit space_id overrides the default space."""
        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(
            base_client, default_space_id="marketing", validate_spaces=False
        )
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "x"}, status=200
        )

        await client.get(id="x", space_id="engineering")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/engineering/api/actions/connector/x"

    async def test_get_invalid_space_id_format(self, connectors_client):
        """Test that an invalid space ID format raises InvalidSpaceIdError."""
        with pytest.raises(InvalidSpaceIdError):
            await connectors_client.get(id="x", space_id="Invalid Space!")

    async def test_get_validates_required_id(self, connectors_client):
        """Test that get() validates required id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await connectors_client.get(id="")

    async def test_get_handles_404_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get() handles 404 Not Found error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Connector not found"},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await connectors_client.get(id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncConnectorsClientGetAll:
    """Tests for AsyncConnectorsClient.get_all() method."""

    async def test_get_all_connectors(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get_all() retrieves all connectors."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[
                {"id": "connector-1", "connector_type_id": ".webhook"},
                {"id": "connector-2", "connector_type_id": ".slack"},
            ],
            status=200,
        )

        result = await connectors_client.get_all()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connectors"
        assert len(result.body) == 2

    async def test_get_all_with_space_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get_all() builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[], status=200
        )

        await connectors_client.get_all(space_id="marketing", validate_space=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/actions/connectors"

    async def test_get_all_handles_auth_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get_all() handles authentication error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Unauthorized"},
            status=401,
        )

        with pytest.raises(AuthenticationException) as exc_info:
            await connectors_client.get_all()

        assert exc_info.value.status_code == 401


class TestAsyncConnectorsClientListTypes:
    """Tests for AsyncConnectorsClient.list_types() method."""

    async def test_list_types(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test list_types() retrieves available connector types."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[
                {"id": ".webhook", "name": "Webhook", "enabled": True},
                {"id": ".slack", "name": "Slack", "enabled": True},
            ],
            status=200,
        )

        result = await connectors_client.list_types()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connector_types"
        assert len(result.body) == 2

    async def test_list_types_with_feature_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test list_types() sends the feature_id query parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[], status=200
        )

        await connectors_client.list_types(feature_id="alerting")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"] == "/api/actions/connector_types?feature_id=alerting"
        )

    async def test_list_types_with_space_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test list_types() supports space scoping."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[], status=200
        )

        await connectors_client.list_types(space_id="marketing", validate_space=False)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/actions/connector_types"


class TestAsyncConnectorsClientUpdate:
    """Tests for AsyncConnectorsClient.update() method."""

    async def test_update_connector(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test update() sends a full-replace PUT with name and config."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Updated Webhook",
                "config": {"url": "https://updated.example.com/webhook"},
            },
            status=200,
        )

        result = await connectors_client.update(
            id="test-connector-id",
            name="Updated Webhook",
            config={"url": "https://updated.example.com/webhook"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/actions/connector/test-connector-id"
        assert call_kwargs["body"] == {
            "name": "Updated Webhook",
            "config": {"url": "https://updated.example.com/webhook"},
        }
        assert result.body["name"] == "Updated Webhook"

    async def test_update_name_only_body(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test update() with only name sends just the name (config resets to {})."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id", "name": "New Name"}, status=200
        )

        await connectors_client.update(id="test-id", name="New Name")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {"name": "New Name"}

    async def test_update_with_secrets(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test update() with secrets parameter."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"id": "test-id"}, status=200
        )

        await connectors_client.update(
            id="test-id",
            name="Updated Slack",
            secrets={"webhookUrl": "https://hooks.slack.com/services/new"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "name": "Updated Slack",
            "secrets": {"webhookUrl": "https://hooks.slack.com/services/new"},
        }

    async def test_update_requires_name_keyword(self, connectors_client):
        """Test that update() requires the name keyword argument (API contract)."""
        with pytest.raises(TypeError):
            await connectors_client.update(id="test-id")

    async def test_update_validates_required_params(self, connectors_client):
        """Test that update() rejects empty id and name."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await connectors_client.update(id="", name="New Name")

        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            await connectors_client.update(id="test-id", name="")

    async def test_update_handles_404_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test update() handles 404 Not Found error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Connector not found"},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await connectors_client.update(id="nonexistent-id", name="New Name")

        assert exc_info.value.status_code == 404


class TestAsyncConnectorsClientDelete:
    """Tests for AsyncConnectorsClient.delete() method."""

    async def test_delete_connector(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test delete() removes a connector."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        result = await connectors_client.delete(id="test-connector-id")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/actions/connector/test-connector-id"
        assert result.meta.status == 204

    async def test_delete_validates_required_id(self, connectors_client):
        """Test that delete() validates required id parameter."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await connectors_client.delete(id="")

    async def test_delete_handles_404_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test delete() handles 404 Not Found error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Connector not found"},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await connectors_client.delete(id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncConnectorsClientExecute:
    """Tests for AsyncConnectorsClient.execute() method."""

    async def test_execute_connector(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test execute() runs a connector with parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"connector_id": "test-connector-id", "status": "ok"},
            status=200,
        )

        result = await connectors_client.execute(
            id="test-connector-id",
            params={"message": "Test alert", "level": "info"},
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert (
            call_kwargs["target"] == "/api/actions/connector/test-connector-id/_execute"
        )
        assert call_kwargs["body"] == {
            "params": {"message": "Test alert", "level": "info"}
        }
        assert result.body["status"] == "ok"

    async def test_execute_with_space_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test execute() builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"status": "ok"}, status=200
        )

        await connectors_client.execute(
            id="x", params={"message": "hi"}, space_id="marketing", validate_space=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/s/marketing/api/actions/connector/x/_execute"

    async def test_execute_validates_required_params(self, connectors_client):
        """Test that execute() validates required parameters."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await connectors_client.execute(id="", params={"message": "test"})

        with pytest.raises(ValueError, match="Parameter 'params' is required"):
            await connectors_client.execute(id="test-id", params=None)

    async def test_execute_handles_400_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test execute() handles 400 Bad Request error."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Invalid execution parameters"},
            status=400,
        )

        with pytest.raises(BadRequestError) as exc_info:
            await connectors_client.execute(
                id="test-connector-id", params={"invalid": "params"}
            )

        assert exc_info.value.status_code == 400


class TestAsyncConnectorsClientOAuthCallback:
    """Tests for AsyncConnectorsClient.oauth_callback() method."""

    async def test_oauth_callback_without_params(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test oauth_callback() sends no query string when no params given."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        await connectors_client.oauth_callback()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connector/_oauth_callback"

    async def test_oauth_callback_with_params(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test oauth_callback() encodes only the provided query parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        await connectors_client.oauth_callback(
            code="auth-code",
            state="csrf-state",
            session_state="ms-session",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        path, _, query = target.partition("?")
        assert path == "/api/actions/connector/_oauth_callback"
        assert set(query.split("&")) == {
            "code=auth-code",
            "state=csrf-state",
            "session_state=ms-session",
        }

    async def test_oauth_callback_with_error_params(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test oauth_callback() forwards provider error parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        await connectors_client.oauth_callback(
            error="access_denied", error_description="user denied"
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        target = call_kwargs["target"]
        assert "error=access_denied" in target
        assert "error_description=user+denied" in target or (
            "error_description=user%20denied" in target
        )

    async def test_oauth_callback_with_space_id(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test oauth_callback() builds a space-scoped path."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        await connectors_client.oauth_callback(
            space_id="marketing", validate_space=False
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/s/marketing/api/actions/connector/_oauth_callback"
        )


class TestAsyncConnectorsClientOAuthCallbackScript:
    """Tests for AsyncConnectorsClient.get_oauth_callback_script() method."""

    async def test_get_oauth_callback_script(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test get_oauth_callback_script() targets the script endpoint."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        await connectors_client.get_oauth_callback_script()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connector/_oauth_callback_script"

    async def test_script_serializer_registration(
        self, mock_async_transport, mock_response
    ):
        """Test that a JavaScript text serializer is registered on the transport."""
        from elastic_transport import TextSerializer

        # Give the mock transport a real serializer registry
        class FakeCollection:
            serializers: dict = {}

        collection = FakeCollection()
        collection.serializers = {}
        mock_async_transport.serializers = collection
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=200
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        client = AsyncConnectorsClient(base_client, validate_spaces=False)
        await client.get_oauth_callback_script()

        assert isinstance(
            collection.serializers.get("application/javascript"), TextSerializer
        )
        assert isinstance(collection.serializers.get("text/javascript"), TextSerializer)


class TestAsyncConnectorsClientErrorHandling:
    """Tests for error handling across AsyncConnectorsClient methods."""

    async def test_handles_authorization_error(
        self, mock_async_transport, mock_response, connectors_client
    ):
        """Test that all methods map 403 to AuthorizationException."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"message": "Insufficient privileges"},
            status=403,
        )

        with pytest.raises(AuthorizationException):
            await connectors_client.create(name="Test", connector_type_id=".server-log")

        with pytest.raises(AuthorizationException):
            await connectors_client.get(id="test-id")

        with pytest.raises(AuthorizationException):
            await connectors_client.get_all()

        with pytest.raises(AuthorizationException):
            await connectors_client.list_types()

        with pytest.raises(AuthorizationException):
            await connectors_client.update(id="test-id", name="New Name")

        with pytest.raises(AuthorizationException):
            await connectors_client.delete(id="test-id")

        with pytest.raises(AuthorizationException):
            await connectors_client.execute(id="test-id", params={"message": "test"})

        with pytest.raises(AuthorizationException):
            await connectors_client.oauth_callback()

        with pytest.raises(AuthorizationException):
            await connectors_client.get_oauth_callback_script()


class TestAsyncActionsClientAlias:
    """Tests for the deprecated AsyncActionsClient alias."""

    async def test_actions_client_is_connectors_subclass(self):
        """Test that AsyncActionsClient is a subclass of AsyncConnectorsClient."""
        assert issubclass(AsyncActionsClient, AsyncConnectorsClient)

    async def test_kibana_actions_property_is_connectors_instance(
        self, mock_async_transport
    ):
        """Test that client.actions is an AsyncActionsClient (and AsyncConnectorsClient)."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.actions, AsyncActionsClient)
        assert isinstance(client.actions, AsyncConnectorsClient)

    async def test_actions_alias_methods_still_work(
        self, mock_async_transport, mock_response
    ):
        """Test that client.actions methods hit the same endpoints."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[{"id": ".server-log"}], status=200
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.actions.list_types()

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/actions/connector_types"
        assert result.body[0]["id"] == ".server-log"

    async def test_actions_alias_has_deprecation_note(self):
        """Test that the alias docstring carries a deprecation note."""
        assert AsyncActionsClient.__doc__ is not None
        assert "deprecated" in AsyncActionsClient.__doc__.lower()
        assert "client.connectors" in AsyncActionsClient.__doc__
