"""Unit tests for AsyncSpacesClient."""

from unittest.mock import AsyncMock

import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from kibana.exceptions import ConflictError, NotFoundError


class TestAsyncSpacesClientInitialization:
    """Test AsyncSpacesClient initialization."""

    @pytest.mark.asyncio
    async def test_spaces_client_initialization(self, mock_async_transport):
        """Test that AsyncSpacesClient can be initialized with a parent client."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)
        assert spaces_client._client == base_client


class TestAsyncSpacesClientCreate:
    """Test AsyncSpacesClient create method."""

    @pytest.mark.asyncio
    async def test_create_space_minimal(self, mock_async_transport):
        """Test creating a space with minimal required parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={
                "id": "marketing",
                "name": "Marketing",
                "disabledFeatures": [],
            },
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.create(
            id="marketing",
            name="Marketing",
        )

        assert result.body["id"] == "marketing"
        assert result.body["name"] == "Marketing"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["path"] == "/api/spaces/space"
        assert call_args[1]["body"] == {
            "id": "marketing",
            "name": "Marketing",
        }

    @pytest.mark.asyncio
    async def test_create_space_with_all_parameters(self, mock_async_transport):
        """Test creating a space with all optional parameters."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={
                "id": "marketing",
                "name": "Marketing Team",
                "description": "Marketing department space",
                "color": "#FF0000",
                "initials": "MK",
                "disabledFeatures": ["dev_tools", "advancedSettings"],
            },
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.create(
            id="marketing",
            name="Marketing Team",
            description="Marketing department space",
            color="#FF0000",
            initials="MK",
            disabled_features=["dev_tools", "advancedSettings"],
        )

        assert result.body["id"] == "marketing"
        assert result.body["description"] == "Marketing department space"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["path"] == "/api/spaces/space"
        assert call_args[1]["body"] == {
            "id": "marketing",
            "name": "Marketing Team",
            "description": "Marketing department space",
            "color": "#FF0000",
            "initials": "MK",
            "disabledFeatures": ["dev_tools", "advancedSettings"],
        }

    @pytest.mark.asyncio
    async def test_create_space_missing_id(self, mock_async_transport):
        """Test that creating a space without id raises ValueError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await spaces_client.create(id="", name="Marketing")

    @pytest.mark.asyncio
    async def test_create_space_missing_name(self, mock_async_transport):
        """Test that creating a space without name raises ValueError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            await spaces_client.create(id="marketing", name="")

    @pytest.mark.asyncio
    async def test_create_space_conflict(self, mock_async_transport):
        """Test that creating a duplicate space raises ConflictError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        base_client.perform_request = AsyncMock(
            side_effect=ConflictError(
                message="Space already exists",
                meta=ApiResponseMeta(
                    status=409,
                    headers={},
                    http_version="1.1",
                    duration=0.1,
                    node=None,
                ),
                body={"error": "Conflict"},
            )
        )

        with pytest.raises(ConflictError):
            await spaces_client.create(id="marketing", name="Marketing")


class TestAsyncSpacesClientGet:
    """Test AsyncSpacesClient get method."""

    @pytest.mark.asyncio
    async def test_get_space(self, mock_async_transport):
        """Test getting a space by ID."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={
                "id": "marketing",
                "name": "Marketing",
                "description": "Marketing space",
                "disabledFeatures": [],
            },
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.get(id="marketing")

        assert result.body["id"] == "marketing"
        assert result.body["name"] == "Marketing"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"

    @pytest.mark.asyncio
    async def test_get_space_not_found(self, mock_async_transport):
        """Test that getting a non-existent space raises NotFoundError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        base_client.perform_request = AsyncMock(
            side_effect=NotFoundError(
                message="Space not found",
                meta=ApiResponseMeta(
                    status=404,
                    headers={},
                    http_version="1.1",
                    duration=0.1,
                    node=None,
                ),
                body={"error": "Not Found"},
            )
        )

        with pytest.raises(NotFoundError):
            await spaces_client.get(id="nonexistent")

    @pytest.mark.asyncio
    async def test_get_space_missing_id(self, mock_async_transport):
        """Test that getting a space without id raises ValueError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await spaces_client.get(id="")


class TestAsyncSpacesClientGetAll:
    """Test AsyncSpacesClient get_all method."""

    @pytest.mark.asyncio
    async def test_get_all_spaces(self, mock_async_transport):
        """Test getting all spaces."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body=[
                {"id": "default", "name": "Default", "disabledFeatures": []},
                {"id": "marketing", "name": "Marketing", "disabledFeatures": []},
            ],
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.get_all()

        assert len(result.body) == 2
        assert result.body[0]["id"] == "default"
        assert result.body[1]["id"] == "marketing"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space"

    @pytest.mark.asyncio
    async def test_get_all_spaces_empty(self, mock_async_transport):
        """Test getting all spaces when none exist."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body=[],
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.get_all()

        assert len(result.body) == 0

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space"


class TestAsyncSpacesClientUpdate:
    """Test AsyncSpacesClient update method."""

    @pytest.mark.asyncio
    async def test_update_space_name(self, mock_async_transport):
        """Test updating a space's name."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={
                "id": "marketing",
                "name": "Marketing Team",
                "disabledFeatures": [],
            },
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.update(
            id="marketing",
            name="Marketing Team",
        )

        assert result.body["name"] == "Marketing Team"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"
        assert call_args[1]["body"] == {"id": "marketing", "name": "Marketing Team"}

    @pytest.mark.asyncio
    async def test_update_space_all_fields(self, mock_async_transport):
        """Test updating all fields of a space."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={
                "id": "marketing",
                "name": "Marketing Team",
                "description": "Updated description",
                "color": "#00FF00",
                "initials": "MT",
                "disabledFeatures": ["dev_tools"],
            },
            meta=ApiResponseMeta(
                status=200,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.update(
            id="marketing",
            name="Marketing Team",
            description="Updated description",
            color="#00FF00",
            initials="MT",
            disabled_features=["dev_tools"],
        )

        assert result.body["name"] == "Marketing Team"
        assert result.body["description"] == "Updated description"

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"
        assert call_args[1]["body"] == {
            "id": "marketing",
            "name": "Marketing Team",
            "description": "Updated description",
            "color": "#00FF00",
            "initials": "MT",
            "disabledFeatures": ["dev_tools"],
        }

    @pytest.mark.asyncio
    async def test_update_space_missing_id(self, mock_async_transport):
        """Test that updating a space without id raises ValueError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await spaces_client.update(id="", name="Marketing")

    @pytest.mark.asyncio
    async def test_update_space_not_found(self, mock_async_transport):
        """Test that updating a non-existent space raises NotFoundError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        base_client.perform_request = AsyncMock(
            side_effect=NotFoundError(
                message="Space not found",
                meta=ApiResponseMeta(
                    status=404,
                    headers={},
                    http_version="1.1",
                    duration=0.1,
                    node=None,
                ),
                body={"error": "Not Found"},
            )
        )

        with pytest.raises(NotFoundError):
            await spaces_client.update(id="nonexistent", name="New Name")


class TestAsyncSpacesClientDelete:
    """Test AsyncSpacesClient delete method."""

    @pytest.mark.asyncio
    async def test_delete_space(self, mock_async_transport):
        """Test deleting a space."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        mock_response = ObjectApiResponse(
            body={},
            meta=ApiResponseMeta(
                status=204,
                headers={},
                http_version="1.1",
                duration=0.1,
                node=None,
            ),
        )
        base_client.perform_request = AsyncMock(return_value=mock_response)

        result = await spaces_client.delete(id="marketing")

        assert result.meta.status == 204

        # Verify the request was made correctly
        base_client.perform_request.assert_called_once()
        call_args = base_client.perform_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"

    @pytest.mark.asyncio
    async def test_delete_space_missing_id(self, mock_async_transport):
        """Test that deleting a space without id raises ValueError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            await spaces_client.delete(id="")

    @pytest.mark.asyncio
    async def test_delete_space_not_found(self, mock_async_transport):
        """Test that deleting a non-existent space raises NotFoundError."""
        from kibana._async.client._base import AsyncBaseClient
        from kibana._async.client.spaces import AsyncSpacesClient

        base_client = AsyncBaseClient(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(base_client)

        base_client.perform_request = AsyncMock(
            side_effect=NotFoundError(
                message="Space not found",
                meta=ApiResponseMeta(
                    status=404,
                    headers={},
                    http_version="1.1",
                    duration=0.1,
                    node=None,
                ),
                body={"error": "Not Found"},
            )
        )

        with pytest.raises(NotFoundError):
            await spaces_client.delete(id="nonexistent")
