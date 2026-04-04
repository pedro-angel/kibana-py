"""Comprehensive tests for ActionsClient space support."""

from unittest.mock import Mock

import pytest

from kibana._sync.client._base import BaseClient
from kibana._sync.client.actions import ActionsClient
from kibana.exceptions import SpaceNotFoundError


class TestActionsClientSpaceSupport:
    """Test ActionsClient space support functionality."""

    def test_actions_client_init_with_space_context(self, mock_transport):
        """Test ActionsClient initialization with space context."""
        base_client = BaseClient(_transport=mock_transport)

        # Test with default space ID and validation enabled
        actions_client = ActionsClient(
            base_client, default_space_id="marketing", validate_spaces=True
        )

        assert actions_client._default_space_id == "marketing"
        assert actions_client._validate_spaces is True
        assert actions_client._client is base_client

    def test_actions_client_init_with_validation_disabled(self, mock_transport):
        """Test ActionsClient initialization with validation disabled."""
        base_client = BaseClient(_transport=mock_transport)

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=False
        )

        assert actions_client._default_space_id == "sales"
        assert actions_client._validate_spaces is False

    def test_actions_client_init_without_space_context(self, mock_transport):
        """Test ActionsClient initialization without space context (backward compatibility)."""
        base_client = BaseClient(_transport=mock_transport)

        actions_client = ActionsClient(base_client)

        assert actions_client._default_space_id is None
        assert actions_client._validate_spaces is True  # Default value


class TestActionsClientCreateSpaceSupport:
    """Test ActionsClient.create() method with space support."""

    def test_create_with_space_id_parameter(self, mock_transport, mock_response):
        """Test create() with space_id parameter."""
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

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
            space_id="marketing",
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/s/marketing/api/actions/connector"
        assert call_args[1]["body"] == {
            "name": "Test Webhook",
            "connector_type_id": ".webhook",
            "config": {"url": "https://example.com/webhook"},
        }

    def test_create_with_default_space_id(self, mock_transport, mock_response):
        """Test create() using default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
        )

        # Verify space validation was called for default space
        mock_spaces_client.get.assert_called_once_with(id="sales")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/sales/api/actions/connector"

    def test_create_space_id_overrides_default(self, mock_transport, mock_response):
        """Test that space_id parameter overrides default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(body={"id": "test", "name": "Test"})
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
            space_id="marketing",  # Override default
        )

        # Verify space validation was called for override space
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with override space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/marketing/api/actions/connector"

    def test_create_with_validation_override_enabled(
        self, mock_transport, mock_response
    ):
        """Test create() with validation override enabled."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=False)

        actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
            space_id="marketing",
            validate_space=True,  # Override to enable validation
        )

        # Verify space validation was called despite default being False
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify validation setting is restored
        assert actions_client._validate_spaces is False

    def test_create_with_validation_override_disabled(
        self, mock_transport, mock_response
    ):
        """Test create() with validation override disabled."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client (should not be called)
        mock_spaces_client = Mock()
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.create(
            name="Test Webhook",
            connector_type_id=".webhook",
            config={"url": "https://example.com/webhook"},
            space_id="marketing",
            validate_space=False,  # Override to disable validation
        )

        # Verify space validation was NOT called
        mock_spaces_client.get.assert_not_called()

        # Verify validation setting is restored
        assert actions_client._validate_spaces is True

    def test_create_with_space_validation_failure(self, mock_transport):
        """Test create() with space validation failure."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to return not found error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Space not found")
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            actions_client.create(
                name="Test Webhook",
                connector_type_id=".webhook",
                config={"url": "https://example.com/webhook"},
                space_id="nonexistent",
            )

        assert exc_info.value.space_id == "nonexistent"

        # Verify transport was not called due to validation failure
        mock_transport.perform_request.assert_not_called()


class TestActionsClientGetSpaceSupport:
    """Test ActionsClient.get() method with space support."""

    def test_get_with_space_id_parameter(self, mock_transport, mock_response):
        """Test get() with space_id parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Test Webhook",
                "connector_type_id": ".webhook",
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.get(id="test-connector-id", space_id="marketing")

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/actions/connector/test-connector-id"
        )

    def test_get_with_default_space_id(self, mock_transport, mock_response):
        """Test get() using default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.get(id="test-connector-id")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/sales/api/actions/connector/test-connector-id"
        )

    def test_get_without_space_uses_global_path(self, mock_transport, mock_response):
        """Test get() without space uses global path."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Test Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client, validate_spaces=False)

        actions_client.get(id="test-connector-id")

        # Verify the request was made with global path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/actions/connector/test-connector-id"


class TestActionsClientGetAllSpaceSupport:
    """Test ActionsClient.get_all() method with space support."""

    def test_get_all_with_space_id_parameter(self, mock_transport, mock_response):
        """Test get_all() with space_id parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body=[
                {"id": "connector-1", "name": "Webhook 1"},
                {"id": "connector-2", "name": "Webhook 2"},
            ],
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.get_all(space_id="marketing")

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/s/marketing/api/actions/connectors"

    def test_get_all_with_default_space_id(self, mock_transport, mock_response):
        """Test get_all() using default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body=[{"id": "connector-1", "name": "Webhook 1"}],
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.get_all()

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/sales/api/actions/connectors"


class TestActionsClientUpdateSpaceSupport:
    """Test ActionsClient.update() method with space support."""

    def test_update_with_space_id_parameter(self, mock_transport, mock_response):
        """Test update() with space_id parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-connector-id",
                "name": "Updated Webhook",
                "connector_type_id": ".webhook",
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.update(
            id="test-connector-id", name="Updated Webhook", space_id="marketing"
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/actions/connector/test-connector-id"
        )
        assert call_args[1]["body"] == {"name": "Updated Webhook"}

    def test_update_with_all_parameters_and_space(self, mock_transport, mock_response):
        """Test update() with all parameters and space."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector-id", "name": "Updated Webhook"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.update(
            id="test-connector-id",
            name="Updated Webhook",
            config={"url": "https://new-url.com"},
            secrets={"token": "new-token"},
            space_id="marketing",
        )

        # Verify the request body includes all parameters
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["body"] == {
            "name": "Updated Webhook",
            "config": {"url": "https://new-url.com"},
            "secrets": {"token": "new-token"},
        }


class TestActionsClientDeleteSpaceSupport:
    """Test ActionsClient.delete() method with space support."""

    def test_delete_with_space_id_parameter(self, mock_transport, mock_response):
        """Test delete() with space_id parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={},
            status=204,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.delete(id="test-connector-id", space_id="marketing")

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/actions/connector/test-connector-id"
        )

    def test_delete_with_default_space_id(self, mock_transport, mock_response):
        """Test delete() using default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={},
            status=204,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.delete(id="test-connector-id")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/sales/api/actions/connector/test-connector-id"
        )


class TestActionsClientExecuteSpaceSupport:
    """Test ActionsClient.execute() method with space support."""

    def test_execute_with_space_id_parameter(self, mock_transport, mock_response):
        """Test execute() with space_id parameter."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "connector_id": "test-connector-id",
                "status": "ok",
                "data": {"message": "Success"},
            },
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        actions_client.execute(
            id="test-connector-id",
            params={"message": "Test alert"},
            space_id="marketing",
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/actions/connector/test-connector-id/_execute"
        )
        assert call_args[1]["body"] == {"params": {"message": "Test alert"}}

    def test_execute_with_default_space_id(self, mock_transport, mock_response):
        """Test execute() using default space ID."""
        mock_transport.perform_request.return_value = mock_response(
            body={"connector_id": "test-connector-id", "status": "ok"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        actions_client.execute(id="test-connector-id", params={"message": "Test alert"})

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"]
            == "/s/sales/api/actions/connector/test-connector-id/_execute"
        )


class TestActionsClientListTypesNoSpaceSupport:
    """Test ActionsClient.list_types() method (no space support)."""

    def test_list_types_ignores_space_context(self, mock_transport, mock_response):
        """Test list_types() ignores space context (global operation)."""
        mock_transport.perform_request.return_value = mock_response(
            body=[
                {"id": ".webhook", "name": "Webhook"},
                {"id": ".slack", "name": "Slack"},
            ],
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Create client with default space ID
        actions_client = ActionsClient(
            base_client, default_space_id="marketing", validate_spaces=False
        )

        actions_client.list_types()

        # Verify the request was made with global path (no space scoping)
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["target"] == "/api/actions/connector_types"


class TestActionsClientSpaceErrorScenarios:
    """Test ActionsClient error scenarios with space context."""

    def test_space_validation_error_includes_space_context(self, mock_transport):
        """Test that space validation errors include space context."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to return not found error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Space not found")
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            actions_client.create(
                name="Test Webhook",
                connector_type_id=".webhook",
                config={"url": "https://example.com/webhook"},
                space_id="nonexistent",
            )

        # Verify error includes space context
        assert exc_info.value.space_id == "nonexistent"
        assert "Space not found" in str(exc_info.value)

    def test_api_error_enhanced_with_space_context(self, mock_transport):
        """Test that API errors are enhanced with space context."""
        from elastic_transport import ApiResponseMeta

        from kibana.exceptions import ApiError

        # Mock transport to raise API error
        api_error = ApiError(
            message="Resource not found",
            meta=ApiResponseMeta(
                status=404, headers={}, http_version="1.1", duration=0.1, node=None
            ),
            body={"error": "not found"},
        )
        mock_transport.perform_request.side_effect = api_error

        base_client = BaseClient(_transport=mock_transport)
        actions_client = ActionsClient(base_client, validate_spaces=False)

        with pytest.raises(ApiError) as exc_info:
            actions_client.get(id="nonexistent-connector", space_id="marketing")

        # Verify error message was enhanced with space context
        enhanced_error = exc_info.value
        assert "[Space: marketing]" in enhanced_error.message
        assert "Resource not found" in enhanced_error.message

    def test_validation_setting_restoration_after_exception(self, mock_transport):
        """Test that validation setting is restored even after exception."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to raise error during validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Network error")
        base_client.spaces = mock_spaces_client

        actions_client = ActionsClient(base_client, validate_spaces=False)

        # Verify initial validation setting
        assert actions_client._validate_spaces is False

        # Call method with validation override that will fail
        with pytest.raises(Exception):
            actions_client.create(
                name="Test Webhook",
                connector_type_id=".webhook",
                config={"url": "https://example.com/webhook"},
                space_id="marketing",
                validate_space=True,  # Override to enable validation
            )

        # Verify validation setting was restored despite exception
        assert actions_client._validate_spaces is False
