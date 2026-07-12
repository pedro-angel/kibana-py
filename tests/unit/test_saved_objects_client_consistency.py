"""Comprehensive tests for SavedObjectsClient consistency with ActionsClient space patterns."""

from unittest.mock import Mock

import pytest
from elastic_transport import ApiResponseMeta

from kibana._sync.client._base import BaseClient
from kibana._sync.client.saved_objects import SavedObjectsClient
from kibana.exceptions import NotFoundError, SpaceNotFoundError


def _not_found(message: str = "Not Found") -> NotFoundError:
    """Build a real 404 NotFoundError, as the spaces client raises for a missing space."""
    meta = ApiResponseMeta(
        status=404, headers={}, http_version="1.1", duration=0.0, node=None
    )
    return NotFoundError(message, meta, {})


class TestSavedObjectsClientSpaceConsistency:
    """Test SavedObjectsClient space support consistency with ActionsClient."""

    def test_saved_objects_client_init_with_space_context(self, mock_transport):
        """Test SavedObjectsClient initialization with space context (consistent with ActionsClient)."""
        base_client = BaseClient(_transport=mock_transport)

        # Test with default space ID and validation enabled
        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="marketing", validate_spaces=True
        )

        assert saved_objects_client._default_space_id == "marketing"
        assert saved_objects_client._validate_spaces is True
        assert saved_objects_client._client is base_client

    def test_saved_objects_client_init_with_validation_disabled(self, mock_transport):
        """Test SavedObjectsClient initialization with validation disabled (consistent with ActionsClient)."""
        base_client = BaseClient(_transport=mock_transport)

        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="sales", validate_spaces=False
        )

        assert saved_objects_client._default_space_id == "sales"
        assert saved_objects_client._validate_spaces is False

    def test_saved_objects_client_init_without_space_context(self, mock_transport):
        """Test SavedObjectsClient initialization without space context (backward compatibility)."""
        base_client = BaseClient(_transport=mock_transport)

        saved_objects_client = SavedObjectsClient(base_client)

        assert saved_objects_client._default_space_id is None
        assert saved_objects_client._validate_spaces is True  # Default value


class TestSavedObjectsClientCreateSpaceConsistency:
    """Test SavedObjectsClient.create() method space support consistency."""

    def test_create_with_space_id_parameter(self, mock_transport, mock_response):
        """Test create() with space_id parameter (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Test Dashboard"},
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

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        mock_transport.perform_request.assert_called_once()
        call_args = mock_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard"
        assert call_args[1]["body"] == {"attributes": {"title": "Test Dashboard"}}

    def test_create_with_default_space_id(self, mock_transport, mock_response):
        """Test create() using default space ID (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        saved_objects_client.create(
            type="dashboard", attributes={"title": "Test Dashboard"}
        )

        # Verify space validation was called for default space
        mock_spaces_client.get.assert_called_once_with(id="sales")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/sales/api/saved_objects/dashboard"

    def test_create_space_id_overrides_default(self, mock_transport, mock_response):
        """Test that space_id parameter overrides default space ID (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(body={"id": "test", "name": "Test"})
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",  # Override default
        )

        # Verify space validation was called for override space
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with override space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard"

    def test_create_with_validation_override_enabled(
        self, mock_transport, mock_response
    ):
        """Test create() with validation override enabled (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=False)

        saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
            validate_space=True,  # Override to enable validation
        )

        # Verify space validation was called despite default being False
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify validation setting is restored
        assert saved_objects_client._validate_spaces is False

    def test_create_with_validation_override_disabled(
        self, mock_transport, mock_response
    ):
        """Test create() with validation override disabled (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client (should not be called)
        mock_spaces_client = Mock()
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
            validate_space=False,  # Override to disable validation
        )

        # Verify space validation was NOT called
        mock_spaces_client.get.assert_not_called()

        # Verify validation setting is restored
        assert saved_objects_client._validate_spaces is True

    def test_create_with_explicit_id_and_space(self, mock_transport, mock_response):
        """Test create() with explicit ID and space (path construction consistency)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "my-dashboard", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.create(
            type="dashboard",
            id="my-dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
        )

        # Verify the request was made with space-scoped path including ID
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/saved_objects/dashboard/my-dashboard"
        )

    def test_create_with_space_validation_failure(self, mock_transport):
        """Test create() with space validation failure (consistent with ActionsClient)."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to return not found error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = _not_found("Space not found")
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test Dashboard"},
                space_id="nonexistent",
            )

        assert exc_info.value.space_id == "nonexistent"

        # Verify transport was not called due to validation failure
        mock_transport.perform_request.assert_not_called()


class TestSavedObjectsClientGetSpaceConsistency:
    """Test SavedObjectsClient.get() method space support consistency."""

    def test_get_with_space_id_parameter(self, mock_transport, mock_response):
        """Test get() with space_id parameter (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Test Dashboard"},
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

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.get(
            type="dashboard", id="test-dashboard-id", space_id="marketing"
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/saved_objects/dashboard/test-dashboard-id"
        )

    def test_get_with_default_space_id(self, mock_transport, mock_response):
        """Test get() using default space ID (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "sales", "name": "Sales"}
        )
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        saved_objects_client.get(type="dashboard", id="test-dashboard-id")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"]
            == "/s/sales/api/saved_objects/dashboard/test-dashboard-id"
        )

    def test_get_without_space_uses_global_path(self, mock_transport, mock_response):
        """Test get() without space uses global path (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=False)

        saved_objects_client.get(type="dashboard", id="test-dashboard-id")

        # Verify the request was made with global path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )


class TestSavedObjectsClientUpdateSpaceConsistency:
    """Test SavedObjectsClient.update() method space support consistency."""

    def test_update_with_space_id_parameter(self, mock_transport, mock_response):
        """Test update() with space_id parameter (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "id": "test-dashboard-id",
                "type": "dashboard",
                "attributes": {"title": "Updated Dashboard"},
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

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.update(
            type="dashboard",
            id="test-dashboard-id",
            attributes={"title": "Updated Dashboard"},
            space_id="marketing",
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/saved_objects/dashboard/test-dashboard-id"
        )
        assert call_args[1]["body"] == {"attributes": {"title": "Updated Dashboard"}}

    def test_update_with_all_parameters_and_space(self, mock_transport, mock_response):
        """Test update() with all parameters and space (consistent with ActionsClient)."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client for validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.return_value = Mock(
            body={"id": "marketing", "name": "Marketing"}
        )
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.update(
            type="dashboard",
            id="test-dashboard-id",
            attributes={"title": "Updated Dashboard"},
            version="WzEsMV0=",
            references=[{"type": "index-pattern", "id": "pattern-1", "name": "ref1"}],
            space_id="marketing",
        )

        # Verify the request body includes all parameters
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["body"] == {
            "attributes": {"title": "Updated Dashboard"},
            "version": "WzEsMV0=",
            "references": [
                {"type": "index-pattern", "id": "pattern-1", "name": "ref1"}
            ],
        }


class TestSavedObjectsClientDeleteSpaceConsistency:
    """Test SavedObjectsClient.delete() method space support consistency."""

    def test_delete_with_space_id_parameter(self, mock_transport, mock_response):
        """Test delete() with space_id parameter (consistent with ActionsClient)."""
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

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.delete(
            type="dashboard", id="test-dashboard-id", space_id="marketing"
        )

        # Verify space validation was called
        mock_spaces_client.get.assert_called_once_with(id="marketing")

        # Verify the request was made with space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert (
            call_args[1]["target"]
            == "/s/marketing/api/saved_objects/dashboard/test-dashboard-id"
        )

    def test_delete_with_default_space_id(self, mock_transport, mock_response):
        """Test delete() using default space ID (consistent with ActionsClient)."""
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

        saved_objects_client = SavedObjectsClient(
            base_client, default_space_id="sales", validate_spaces=True
        )

        saved_objects_client.delete(type="dashboard", id="test-dashboard-id")

        # Verify the request was made with default space-scoped path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"]
            == "/s/sales/api/saved_objects/dashboard/test-dashboard-id"
        )

    def test_delete_with_force_parameter_and_space(self, mock_transport, mock_response):
        """Test delete() with force parameter and space (parameter handling consistency)."""
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

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        saved_objects_client.delete(
            type="dashboard", id="test-dashboard-id", force=True, space_id="marketing"
        )

        # Verify the request includes force parameter in the URL
        call_args = mock_transport.perform_request.call_args
        target = call_args[1]["target"]
        assert "force=true" in target


class TestSavedObjectsClientSpaceErrorConsistency:
    """Test SavedObjectsClient error scenarios with space context (consistent with ActionsClient)."""

    def test_space_validation_error_includes_space_context(self, mock_transport):
        """Test that space validation errors include space context (consistent with ActionsClient)."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to return not found error
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = _not_found("Space not found")
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=True)

        with pytest.raises(SpaceNotFoundError) as exc_info:
            saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test Dashboard"},
                space_id="nonexistent",
            )

        # Verify error includes space context
        assert exc_info.value.space_id == "nonexistent"
        assert "Space not found" in str(exc_info.value)

    def test_api_error_enhanced_with_space_context(self, mock_transport):
        """Test that API errors are enhanced with space context (consistent with ActionsClient)."""
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
        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=False)

        with pytest.raises(ApiError) as exc_info:
            saved_objects_client.get(
                type="dashboard", id="nonexistent-dashboard", space_id="marketing"
            )

        # Verify error message was enhanced with space context
        enhanced_error = exc_info.value
        assert "[Space: marketing]" in enhanced_error.message
        assert "Resource not found" in enhanced_error.message

    def test_validation_setting_restoration_after_exception(self, mock_transport):
        """Test that validation setting is restored even after exception (consistent with ActionsClient)."""
        base_client = BaseClient(_transport=mock_transport)

        # Mock spaces client to raise error during validation
        mock_spaces_client = Mock()
        mock_spaces_client.get.side_effect = Exception("Network error")
        base_client.spaces = mock_spaces_client

        saved_objects_client = SavedObjectsClient(base_client, validate_spaces=False)

        # Verify initial validation setting
        assert saved_objects_client._validate_spaces is False

        # Call method with validation override that will fail
        with pytest.raises(Exception):
            saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test Dashboard"},
                space_id="marketing",
                validate_space=True,  # Override to enable validation
            )

        # Verify validation setting was restored despite exception
        assert saved_objects_client._validate_spaces is False


class TestSavedObjectsClientBackwardCompatibility:
    """Test that SavedObjectsClient maintains existing functionality."""

    def test_existing_functionality_without_space_parameters(
        self, mock_transport, mock_response
    ):
        """Test that existing code without space parameters continues to work."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        saved_objects_client = SavedObjectsClient(base_client)

        # Test create without space parameters (existing usage)
        saved_objects_client.create(
            type="dashboard", attributes={"title": "Test Dashboard"}
        )

        # Verify request uses global path
        call_args = mock_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/dashboard"

        # Test get without space parameters (existing usage)
        saved_objects_client.get(type="dashboard", id="test-dashboard-id")

        # Verify request uses global path
        call_args = mock_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )

    def test_parameter_validation_unchanged(self, mock_transport):
        """Test that parameter validation behavior is unchanged."""
        base_client = BaseClient(_transport=mock_transport)
        saved_objects_client = SavedObjectsClient(base_client)

        # Test required parameter validation (existing behavior)
        with pytest.raises(ValueError) as exc_info:
            saved_objects_client.create(type="", attributes={"title": "Test"})
        assert "Parameter 'type' is required" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            saved_objects_client.create(type="dashboard", attributes=None)
        assert "Parameter 'attributes' is required" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            saved_objects_client.get(type="", id="test-id")
        assert "Parameter 'type' is required" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            saved_objects_client.get(type="dashboard", id="")
        assert "Parameter 'id' is required" in str(exc_info.value)

    def test_optional_parameters_handling_unchanged(
        self, mock_transport, mock_response
    ):
        """Test that optional parameter handling is unchanged."""
        mock_transport.perform_request.return_value = mock_response(
            body={"id": "test-dashboard-id", "type": "dashboard"},
            status=200,
        )

        base_client = BaseClient(_transport=mock_transport)
        saved_objects_client = SavedObjectsClient(base_client)

        # Test create with optional parameters (existing behavior)
        saved_objects_client.create(
            type="dashboard",
            id="my-dashboard",
            attributes={"title": "Test Dashboard"},
            overwrite=True,
            references=[{"type": "index-pattern", "id": "pattern-1", "name": "ref1"}],
        )

        call_args = mock_transport.perform_request.call_args
        # The target may include query parameters, so check if it starts with the expected path
        target = call_args[1]["target"]
        assert target.startswith("/api/saved_objects/dashboard/my-dashboard")
        assert "overwrite=true" in target
        assert call_args[1]["body"] == {
            "attributes": {"title": "Test Dashboard"},
            "references": [
                {"type": "index-pattern", "id": "pattern-1", "name": "ref1"}
            ],
        }
