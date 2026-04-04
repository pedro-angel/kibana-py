"""Unit tests for AsyncSavedObjectsClient."""

from unittest.mock import AsyncMock

import pytest

from kibana.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class TestAsyncSavedObjectsClientInitialization:
    """Tests for AsyncSavedObjectsClient initialization."""

    @pytest.mark.asyncio
    async def test_init_with_base_client(self, mock_async_transport):
        """Test AsyncSavedObjectsClient initialization with AsyncBaseClient."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        assert saved_objects_client._client is base_client

    @pytest.mark.asyncio
    async def test_inherits_from_namespace_client(self, mock_async_transport):
        """Test that AsyncSavedObjectsClient inherits from AsyncNamespaceClient."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient
        from kibana._async.client.utils import AsyncNamespaceClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        assert isinstance(saved_objects_client, AsyncNamespaceClient)


class TestAsyncSavedObjectsClientCreate:
    """Tests for AsyncSavedObjectsClient.create() method."""

    @pytest.mark.asyncio
    async def test_create_with_required_params(
        self, mock_async_transport, mock_response
    ):
        """Test create() with required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-dashboard-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                    "references": [],
                    "version": "WzEsMV0=",
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        result = await saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
        )

        # Verify the request was made correctly
        mock_async_transport.perform_request.assert_called_once()
        call_args = mock_async_transport.perform_request.call_args

        assert call_args[1]["method"] == "POST"
        assert call_args[1]["target"] == "/api/saved_objects/dashboard"
        assert call_args[1]["body"] == {
            "attributes": {"title": "Test Dashboard"},
        }

        # Verify response
        assert result.body["id"] == "test-dashboard-id"
        assert result.body["type"] == "dashboard"

    @pytest.mark.asyncio
    async def test_create_with_id(self, mock_async_transport, mock_response):
        """Test create() with explicit ID."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "my-custom-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            id="my-custom-id",
        )

        # Verify the request includes id in the path
        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/api/saved_objects/dashboard/my-custom-id"

    @pytest.mark.asyncio
    async def test_create_with_overwrite(self, mock_async_transport, mock_response):
        """Test create() with overwrite parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            id="test-id",
            overwrite=True,
        )

        # Verify the request includes id in path and overwrite parameter in target
        call_args = mock_async_transport.perform_request.call_args
        assert "/api/saved_objects/dashboard/test-id" in call_args[1]["target"]
        assert "overwrite=true" in call_args[1]["target"]

    @pytest.mark.asyncio
    async def test_create_with_references(self, mock_async_transport, mock_response):
        """Test create() with references parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                    "references": [
                        {"type": "index-pattern", "id": "pattern-1", "name": "ref1"}
                    ],
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        references = [{"type": "index-pattern", "id": "pattern-1", "name": "ref1"}]
        await saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            references=references,
        )

        # Verify the request includes references
        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["body"]["references"] == references

    @pytest.mark.asyncio
    async def test_create_with_space_id(self, mock_async_transport, mock_response):
        """Test create() with space_id parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.create(
            type="dashboard",
            attributes={"title": "Test Dashboard"},
            space_id="marketing",
        )

        # Verify the request uses space-scoped target (no ID, so no ID in path)
        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard"

    @pytest.mark.asyncio
    async def test_create_validates_required_params(self, mock_async_transport):
        """Test that create() validates required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test missing type
        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await saved_objects_client.create(
                type="",
                attributes={"title": "Test"},
            )

        # Test missing attributes
        with pytest.raises(ValueError, match="Parameter 'attributes' is required"):
            await saved_objects_client.create(
                type="dashboard",
                attributes=None,
            )

    @pytest.mark.asyncio
    async def test_create_handles_400_error(self, mock_async_transport, mock_response):
        """Test create() handles 400 Bad Request error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Invalid attributes"}},
                status=400,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(BadRequestError) as exc_info:
            await saved_objects_client.create(
                type="dashboard",
                attributes={"invalid": "data"},
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_handles_409_conflict(
        self, mock_async_transport, mock_response
    ):
        """Test create() handles 409 Conflict error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Saved object already exists"}},
                status=409,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(ConflictError) as exc_info:
            await saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test"},
                id="existing-id",
            )

        assert exc_info.value.status_code == 409


class TestAsyncSavedObjectsClientGet:
    """Tests for AsyncSavedObjectsClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_by_type_and_id(self, mock_async_transport, mock_response):
        """Test get() retrieves saved object by type and ID."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-dashboard-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                    "version": "WzEsMV0=",
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        result = await saved_objects_client.get(
            type="dashboard",
            id="test-dashboard-id",
        )

        # Verify the request
        mock_async_transport.perform_request.assert_called_once()
        call_args = mock_async_transport.perform_request.call_args

        assert call_args[1]["method"] == "GET"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )

        # Verify response
        assert result.body["id"] == "test-dashboard-id"
        assert result.body["type"] == "dashboard"

    @pytest.mark.asyncio
    async def test_get_with_space_id(self, mock_async_transport, mock_response):
        """Test get() with space_id parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Test Dashboard"},
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.get(
            type="dashboard",
            id="test-id",
            space_id="marketing",
        )

        # Verify the request uses space-scoped target
        call_args = mock_async_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard/test-id"
        )

    @pytest.mark.asyncio
    async def test_get_validates_required_params(self, mock_async_transport):
        """Test that get() validates required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test missing type
        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await saved_objects_client.get(type="", id="test-id")

        # Test missing id
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await saved_objects_client.get(type="dashboard", id="")

    @pytest.mark.asyncio
    async def test_get_handles_404_error(self, mock_async_transport, mock_response):
        """Test get() handles 404 Not Found error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Saved object not found"}},
                status=404,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            await saved_objects_client.get(type="dashboard", id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncSavedObjectsClientUpdate:
    """Tests for AsyncSavedObjectsClient.update() method."""

    @pytest.mark.asyncio
    async def test_update_saved_object(self, mock_async_transport, mock_response):
        """Test update() modifies an existing saved object."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-dashboard-id",
                    "type": "dashboard",
                    "attributes": {"title": "Updated Dashboard"},
                    "version": "WzIsMV0=",
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        result = await saved_objects_client.update(
            type="dashboard",
            id="test-dashboard-id",
            attributes={"title": "Updated Dashboard"},
        )

        # Verify the request
        mock_async_transport.perform_request.assert_called_once()
        call_args = mock_async_transport.perform_request.call_args

        assert call_args[1]["method"] == "PUT"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )
        assert call_args[1]["body"] == {
            "attributes": {"title": "Updated Dashboard"},
        }

        # Verify response
        assert result.body["attributes"]["title"] == "Updated Dashboard"

    @pytest.mark.asyncio
    async def test_update_with_version(self, mock_async_transport, mock_response):
        """Test update() with version parameter for optimistic concurrency."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Updated Dashboard"},
                    "version": "WzIsMV0=",
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.update(
            type="dashboard",
            id="test-id",
            attributes={"title": "Updated Dashboard"},
            version="WzEsMV0=",
        )

        # Verify the request includes version
        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["body"]["version"] == "WzEsMV0="

    @pytest.mark.asyncio
    async def test_update_with_references(self, mock_async_transport, mock_response):
        """Test update() with references parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Updated Dashboard"},
                    "references": [
                        {"type": "index-pattern", "id": "pattern-1", "name": "ref1"}
                    ],
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        references = [{"type": "index-pattern", "id": "pattern-1", "name": "ref1"}]
        await saved_objects_client.update(
            type="dashboard",
            id="test-id",
            attributes={"title": "Updated Dashboard"},
            references=references,
        )

        # Verify the request includes references
        call_args = mock_async_transport.perform_request.call_args
        assert call_args[1]["body"]["references"] == references

    @pytest.mark.asyncio
    async def test_update_with_space_id(self, mock_async_transport, mock_response):
        """Test update() with space_id parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={
                    "id": "test-id",
                    "type": "dashboard",
                    "attributes": {"title": "Updated Dashboard"},
                },
                status=200,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.update(
            type="dashboard",
            id="test-id",
            attributes={"title": "Updated Dashboard"},
            space_id="marketing",
        )

        # Verify the request uses space-scoped target
        call_args = mock_async_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard/test-id"
        )

    @pytest.mark.asyncio
    async def test_update_validates_required_params(self, mock_async_transport):
        """Test that update() validates required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test missing type
        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await saved_objects_client.update(
                type="",
                id="test-id",
                attributes={"title": "Test"},
            )

        # Test missing id
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await saved_objects_client.update(
                type="dashboard",
                id="",
                attributes={"title": "Test"},
            )

        # Test missing attributes
        with pytest.raises(ValueError, match="Parameter 'attributes' is required"):
            await saved_objects_client.update(
                type="dashboard",
                id="test-id",
                attributes=None,
            )

    @pytest.mark.asyncio
    async def test_update_handles_404_error(self, mock_async_transport, mock_response):
        """Test update() handles 404 Not Found error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Saved object not found"}},
                status=404,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            await saved_objects_client.update(
                type="dashboard",
                id="nonexistent-id",
                attributes={"title": "New Title"},
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_handles_409_conflict(
        self, mock_async_transport, mock_response
    ):
        """Test update() handles 409 Conflict error (version mismatch)."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Version conflict"}},
                status=409,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(ConflictError) as exc_info:
            await saved_objects_client.update(
                type="dashboard",
                id="test-id",
                attributes={"title": "New Title"},
                version="WzEsMV0=",
            )

        assert exc_info.value.status_code == 409


class TestAsyncSavedObjectsClientDelete:
    """Tests for AsyncSavedObjectsClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_saved_object(self, mock_async_transport, mock_response):
        """Test delete() removes a saved object."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={}, status=200)
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        result = await saved_objects_client.delete(
            type="dashboard",
            id="test-dashboard-id",
        )

        # Verify the request
        mock_async_transport.perform_request.assert_called_once()
        call_args = mock_async_transport.perform_request.call_args

        assert call_args[1]["method"] == "DELETE"
        assert (
            call_args[1]["target"] == "/api/saved_objects/dashboard/test-dashboard-id"
        )

        # Verify response
        assert result.meta.status == 200

    @pytest.mark.asyncio
    async def test_delete_with_force(self, mock_async_transport, mock_response):
        """Test delete() with force parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={}, status=200)
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.delete(
            type="dashboard",
            id="test-id",
            force=True,
        )

        # Verify the request includes force parameter in target
        call_args = mock_async_transport.perform_request.call_args
        assert "force=true" in call_args[1]["target"]

    @pytest.mark.asyncio
    async def test_delete_with_space_id(self, mock_async_transport, mock_response):
        """Test delete() with space_id parameter."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(body={}, status=200)
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        await saved_objects_client.delete(
            type="dashboard",
            id="test-id",
            space_id="marketing",
        )

        # Verify the request uses space-scoped target
        call_args = mock_async_transport.perform_request.call_args
        assert (
            call_args[1]["target"] == "/s/marketing/api/saved_objects/dashboard/test-id"
        )

    @pytest.mark.asyncio
    async def test_delete_validates_required_params(self, mock_async_transport):
        """Test that delete() validates required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test missing type
        with pytest.raises(ValueError, match="Parameter 'type' is required"):
            await saved_objects_client.delete(type="", id="test-id")

        # Test missing id
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await saved_objects_client.delete(type="dashboard", id="")

    @pytest.mark.asyncio
    async def test_delete_handles_404_error(self, mock_async_transport, mock_response):
        """Test delete() handles 404 Not Found error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Saved object not found"}},
                status=404,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        with pytest.raises(NotFoundError) as exc_info:
            await saved_objects_client.delete(type="dashboard", id="nonexistent-id")

        assert exc_info.value.status_code == 404


class TestAsyncSavedObjectsClientErrorHandling:
    """Tests for error handling across all AsyncSavedObjectsClient methods."""

    @pytest.mark.asyncio
    async def test_handles_authentication_error(
        self, mock_async_transport, mock_response
    ):
        """Test that all methods handle 401 Authentication error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Unauthorized"}},
                status=401,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test create
        with pytest.raises(AuthenticationException):
            await saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test"},
            )

        # Test get
        with pytest.raises(AuthenticationException):
            await saved_objects_client.get(type="dashboard", id="test-id")

        # Test update
        with pytest.raises(AuthenticationException):
            await saved_objects_client.update(
                type="dashboard",
                id="test-id",
                attributes={"title": "Test"},
            )

        # Test delete
        with pytest.raises(AuthenticationException):
            await saved_objects_client.delete(type="dashboard", id="test-id")

    @pytest.mark.asyncio
    async def test_handles_authorization_error(
        self, mock_async_transport, mock_response
    ):
        """Test that all methods handle 403 Authorization error."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.saved_objects import AsyncSavedObjectsClient

        mock_async_transport.perform_request = AsyncMock(
            return_value=mock_response(
                body={"error": {"message": "Insufficient privileges"}},
                status=403,
            )
        )

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        saved_objects_client = AsyncSavedObjectsClient(base_client)

        # Test create
        with pytest.raises(AuthorizationException):
            await saved_objects_client.create(
                type="dashboard",
                attributes={"title": "Test"},
            )

        # Test get
        with pytest.raises(AuthorizationException):
            await saved_objects_client.get(type="dashboard", id="test-id")

        # Test update
        with pytest.raises(AuthorizationException):
            await saved_objects_client.update(
                type="dashboard",
                id="test-id",
                attributes={"title": "Test"},
            )

        # Test delete
        with pytest.raises(AuthorizationException):
            await saved_objects_client.delete(type="dashboard", id="test-id")
