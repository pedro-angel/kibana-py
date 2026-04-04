"""Comprehensive tests for space-scoped client creation and behavior."""

from unittest.mock import Mock

import pytest

from kibana._sync.client import Kibana, SpaceScopedKibana
from kibana.exceptions import SpaceNotFoundError


class TestSpaceScopedKibanaCreation:
    """Test SpaceScopedKibana creation with various scenarios."""

    def test_space_scoped_client_creation_with_valid_space(self, mock_transport):
        """Test creating space-scoped client with valid space."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to return valid space
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        client._spaces_client = mock_spaces_client

        # Create space-scoped client
        space_client = client.space("marketing")

        # Verify space-scoped client properties
        assert isinstance(space_client, SpaceScopedKibana)
        assert space_client._space_id == "marketing"
        assert space_client._validate is True
        assert space_client._client is client

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

    def test_space_scoped_client_creation_with_invalid_space(self, mock_transport):
        """Test creating space-scoped client with invalid space."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to return not found error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Space not found")
        client._spaces_client = mock_spaces_client

        # Creating space-scoped client should raise SpaceNotFoundError
        with pytest.raises(SpaceNotFoundError) as exc_info:
            client.space("nonexistent")

        assert exc_info.value.space_id == "nonexistent"
        mock_spaces_client.get.assert_called_once_with(id="nonexistent")

    def test_space_scoped_client_creation_with_404_error(self, mock_transport):
        """Test creating space-scoped client with 404 error."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to return 404 error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("404 Not Found")
        client._spaces_client = mock_spaces_client

        # Creating space-scoped client should raise SpaceNotFoundError
        with pytest.raises(SpaceNotFoundError) as exc_info:
            client.space("nonexistent")

        assert exc_info.value.space_id == "nonexistent"

    def test_space_scoped_client_creation_with_other_error(self, mock_transport):
        """Test creating space-scoped client with non-404 error."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to return auth error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Authentication failed")
        client._spaces_client = mock_spaces_client

        # Creating space-scoped client should re-raise original error
        with pytest.raises(Exception) as exc_info:
            client.space("marketing")

        assert "Authentication failed" in str(exc_info.value)
        assert not isinstance(exc_info.value, SpaceNotFoundError)

    def test_space_scoped_client_creation_without_validation(self, mock_transport):
        """Test creating space-scoped client without validation."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client (should not be called)
        mock_spaces_client = Mock()
        client._spaces_client = mock_spaces_client

        # Create space-scoped client without validation
        space_client = client.space("marketing", validate=False)

        # Verify space-scoped client properties
        assert isinstance(space_client, SpaceScopedKibana)
        assert space_client._space_id == "marketing"
        assert space_client._validate is False
        assert space_client._client is client

        # Verify space validation was NOT called
        mock_spaces_client.get.assert_not_called()

    def test_space_scoped_client_creation_validation_parameter_types(
        self, mock_transport
    ):
        """Test space-scoped client creation with different validation parameter types."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        client._spaces_client = mock_spaces_client

        # Test with explicit True
        space_client = client.space("marketing", validate=True)
        assert space_client._validate is True

        # Test with explicit False
        space_client = client.space("marketing", validate=False)
        assert space_client._validate is False

        # Test with default (should be True)
        space_client = client.space("marketing")
        assert space_client._validate is True


class TestSpaceScopedKibanaChildClients:
    """Test space context propagation to child clients."""

    def test_actions_client_space_context_propagation(self, mock_transport):
        """Test that ActionsClient inherits space context."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client without validation for simplicity
        space_client = client.space("marketing", validate=False)

        # Get actions client
        actions_client = space_client.actions

        # Verify space context propagation
        assert actions_client._default_space_id == "marketing"
        assert actions_client._validate_spaces is False
        assert actions_client._client is client

    def test_saved_objects_client_space_context_propagation(self, mock_transport):
        """Test that SavedObjectsClient inherits space context."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client without validation for simplicity
        space_client = client.space("marketing", validate=False)

        # Get saved objects client
        saved_objects_client = space_client.saved_objects

        # Verify space context propagation
        assert saved_objects_client._default_space_id == "marketing"
        assert saved_objects_client._validate_spaces is False
        assert saved_objects_client._client is client

    def test_spaces_client_not_space_scoped(self, mock_transport):
        """Test that SpacesClient is not space-scoped."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Get spaces client
        spaces_client = space_client.spaces

        # Verify it's the same as the main client's spaces client
        assert spaces_client is client.spaces

    def test_status_client_not_space_scoped(self, mock_transport):
        """Test that StatusClient is not space-scoped."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Get status client
        status_client = space_client.status

        # Verify it's the same as the main client's status client
        assert status_client is client.status

    def test_child_client_lazy_initialization(self, mock_transport):
        """Test that child clients are lazily initialized."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Verify child clients are not initialized yet
        assert not hasattr(space_client, "_actions_client")
        assert not hasattr(space_client, "_saved_objects_client")

        # Access actions client
        actions_client = space_client.actions

        # Verify actions client is now initialized but saved objects is not
        assert hasattr(space_client, "_actions_client")
        assert not hasattr(space_client, "_saved_objects_client")

        # Verify subsequent access returns same instance
        assert space_client.actions is actions_client

    def test_multiple_child_clients_independent(self, mock_transport):
        """Test that multiple child clients are independent."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Get both child clients
        actions_client = space_client.actions
        saved_objects_client = space_client.saved_objects

        # Verify they are different instances
        assert actions_client is not saved_objects_client

        # Verify they both have correct space context
        assert actions_client._default_space_id == "marketing"
        assert saved_objects_client._default_space_id == "marketing"

        # Verify they both reference the same main client
        assert actions_client._client is client
        assert saved_objects_client._client is client


class TestSpaceScopedKibanaValidationSettings:
    """Test validation setting inheritance and override."""

    def test_validation_setting_inheritance_enabled(self, mock_transport):
        """Test validation setting inheritance when enabled."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        client._spaces_client = mock_spaces_client

        # Create space-scoped client with validation enabled
        space_client = client.space("marketing", validate=True)

        # Get child clients
        actions_client = space_client.actions
        saved_objects_client = space_client.saved_objects

        # Verify validation is enabled for child clients
        assert actions_client._validate_spaces is True
        assert saved_objects_client._validate_spaces is True

    def test_validation_setting_inheritance_disabled(self, mock_transport):
        """Test validation setting inheritance when disabled."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client with validation disabled
        space_client = client.space("marketing", validate=False)

        # Get child clients
        actions_client = space_client.actions
        saved_objects_client = space_client.saved_objects

        # Verify validation is disabled for child clients
        assert actions_client._validate_spaces is False
        assert saved_objects_client._validate_spaces is False

    def test_validation_override_in_child_client_methods(
        self, mock_transport, mock_response
    ):
        """Test that child client methods can override validation settings."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock transport for API calls
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-connector", "name": "Test"}, status=200
        )

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = mock_response(
            body={"id": "marketing", "name": "Marketing"}, status=200
        )
        client._spaces_client = mock_spaces_client

        # Create space-scoped client with validation disabled
        space_client = client.space("marketing", validate=False)
        actions_client = space_client.actions

        # Verify base validation setting
        assert actions_client._validate_spaces is False

        # Call method with validation override
        actions_client.create(
            name="Test Connector",
            connector_type_id=".webhook",
            config={"url": "https://example.com"},
            validate_space=True,  # Override to enable validation
        )

        # Verify validation setting is restored after method call
        assert actions_client._validate_spaces is False

    def test_multiple_space_scoped_clients_independent_validation(self, mock_transport):
        """Test that multiple space-scoped clients have independent validation settings."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(body={"id": "test", "name": "Test"})
        client._spaces_client = mock_spaces_client

        # Create space-scoped clients with different validation settings
        space_client_validated = client.space("marketing", validate=True)
        space_client_unvalidated = client.space("sales", validate=False)

        # Get child clients
        actions_validated = space_client_validated.actions
        actions_unvalidated = space_client_unvalidated.actions

        # Verify independent validation settings
        assert actions_validated._validate_spaces is True
        assert actions_unvalidated._validate_spaces is False

        # Verify independent space contexts
        assert actions_validated._default_space_id == "marketing"
        assert actions_unvalidated._default_space_id == "sales"


class TestSpaceScopedKibanaErrorHandling:
    """Test error handling for space-related failures."""

    def test_space_validation_error_during_creation(self, mock_transport):
        """Test error handling during space-scoped client creation."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to raise various errors
        mock_spaces_client = Mock()
        client._spaces_client = mock_spaces_client

        # Test network error
        mock_spaces_client.get.side_effect = Exception("Connection timeout")
        with pytest.raises(Exception) as exc_info:
            client.space("marketing")
        assert "Connection timeout" in str(exc_info.value)

        # Test authentication error
        mock_spaces_client.get.side_effect = Exception("Unauthorized")
        with pytest.raises(Exception) as exc_info:
            client.space("marketing")
        assert "Unauthorized" in str(exc_info.value)

        # Test space not found error
        mock_spaces_client.get.side_effect = Exception("Space not found")
        with pytest.raises(SpaceNotFoundError) as exc_info:
            client.space("marketing")
        assert exc_info.value.space_id == "marketing"

    def test_child_client_error_handling_with_space_context(self, mock_transport):
        """Test that child client errors include space context."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock transport to raise error
        from elastic_transport import ApiResponseMeta

        from kibana.exceptions import ApiError

        api_error = ApiError(
            message="Resource not found",
            meta=ApiResponseMeta(
                status=404, headers={}, http_version="1.1", duration=0.1, node=None
            ),
            body={"error": "not found"},
        )
        mock_transport.perform_request.side_effect = api_error

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)
        actions_client = space_client.actions

        # Call method that should include space context in error
        with pytest.raises(ApiError) as exc_info:
            actions_client.get(id="nonexistent-connector")

        # Verify error includes space context
        enhanced_error = exc_info.value
        assert "[Space: marketing]" in enhanced_error.message
        assert "Resource not found" in enhanced_error.message

    def test_space_scoped_client_close_delegation(self, mock_transport):
        """Test that space-scoped client close() delegates to main client."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Mock main client close method
        client.close = Mock()

        # Call close on space-scoped client
        space_client.close()

        # Verify delegation
        client.close.assert_called_once()

    def test_space_scoped_client_context_manager(self, mock_transport):
        """Test space-scoped client as context manager."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock main client close method
        client.close = Mock()

        # Use space-scoped client as context manager
        with client.space("marketing", validate=False) as space_client:
            assert isinstance(space_client, SpaceScopedKibana)
            assert space_client._space_id == "marketing"

        # Verify close was called
        client.close.assert_called_once()

    def test_space_scoped_client_repr(self, mock_transport):
        """Test space-scoped client string representation."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped clients with different settings
        space_client_validated = client.space("marketing", validate=False)
        space_client_unvalidated = client.space("sales", validate=False)

        # Test string representations
        repr_validated = repr(space_client_validated)
        repr_unvalidated = repr(space_client_unvalidated)

        assert "SpaceScopedKibana" in repr_validated
        assert "marketing" in repr_validated
        assert "validate=False" in repr_validated

        assert "SpaceScopedKibana" in repr_unvalidated
        assert "sales" in repr_unvalidated
        assert "validate=False" in repr_unvalidated


class TestSpaceScopedKibanaEdgeCases:
    """Test edge cases for space-scoped client behavior."""

    def test_space_scoped_client_with_empty_space_id(self, mock_transport):
        """Test space-scoped client creation with empty space ID."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Invalid space ID")
        client._spaces_client = mock_spaces_client

        # Creating space-scoped client with empty space ID should fail
        with pytest.raises(Exception):
            client.space("")

    def test_space_scoped_client_with_none_space_id(self, mock_transport):
        """Test space-scoped client creation with None space ID."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Creating space-scoped client with None space ID should fail
        with pytest.raises(Exception):
            client.space(None)

    def test_space_scoped_client_multiple_access_same_child(self, mock_transport):
        """Test multiple access to same child client returns same instance."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create space-scoped client
        space_client = client.space("marketing", validate=False)

        # Access actions client multiple times
        actions1 = space_client.actions
        actions2 = space_client.actions
        actions3 = space_client.actions

        # Verify all references point to same instance
        assert actions1 is actions2
        assert actions2 is actions3
        assert actions1 is actions3

    def test_space_scoped_client_child_client_independence(self, mock_transport):
        """Test that child clients from different space-scoped clients are independent."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Create different space-scoped clients
        marketing_client = client.space("marketing", validate=False)
        sales_client = client.space("sales", validate=False)

        # Get actions clients from both
        marketing_actions = marketing_client.actions
        sales_actions = sales_client.actions

        # Verify they are different instances
        assert marketing_actions is not sales_actions

        # Verify they have different space contexts
        assert marketing_actions._default_space_id == "marketing"
        assert sales_actions._default_space_id == "sales"

        # Verify they both reference the same main client
        assert marketing_actions._client is client
        assert sales_actions._client is client

    def test_space_scoped_client_validation_with_no_spaces_client(self, mock_transport):
        """Test space-scoped client validation when main client has no spaces client."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Mock spaces client to not exist (return None)
        client._spaces_client = None

        # Creating space-scoped client should fail when trying to validate
        with pytest.raises(AttributeError):
            client.space("marketing", validate=True)

    def test_space_scoped_client_validation_with_spaces_client_none(
        self, mock_transport
    ):
        """Test space-scoped client validation when spaces client is None."""
        # Create main client
        client = Kibana(_transport=mock_transport)

        # Set spaces client to None
        client._spaces_client = None

        # Creating space-scoped client should fail when trying to validate
        with pytest.raises(AttributeError):
            client.space("marketing", validate=True)
