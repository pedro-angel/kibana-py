"""Unit tests for SpacesClient."""

from unittest.mock import Mock

import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from kibana._sync.client.spaces import SpacesClient
from kibana.exceptions import ConflictError, NotFoundError


class TestSpacesClientInitialization:
    """Test SpacesClient initialization."""

    def test_spaces_client_initialization(self):
        """Test that SpacesClient can be initialized with a parent client."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)
        assert spaces_client._client == mock_client


class TestSpacesClientCreate:
    """Test SpacesClient create method."""

    def test_create_space_minimal(self):
        """Test creating a space with minimal required parameters."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.create(
            id="marketing",
            name="Marketing",
        )

        assert result.body["id"] == "marketing"
        assert result.body["name"] == "Marketing"

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["path"] == "/api/spaces/space"
        assert call_args[1]["body"] == {
            "id": "marketing",
            "name": "Marketing",
        }

    def test_create_space_with_all_parameters(self):
        """Test creating a space with all optional parameters."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.create(
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
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
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

    def test_create_space_missing_id(self):
        """Test that creating a space without id raises ValueError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            spaces_client.create(id="", name="Marketing")

    def test_create_space_missing_name(self):
        """Test that creating a space without name raises ValueError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            spaces_client.create(id="marketing", name="")

    def test_create_space_conflict(self):
        """Test that creating a duplicate space raises ConflictError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        mock_client.perform_request.side_effect = ConflictError(
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

        with pytest.raises(ConflictError):
            spaces_client.create(id="marketing", name="Marketing")


class TestSpacesClientGet:
    """Test SpacesClient get method."""

    def test_get_space(self):
        """Test getting a space by ID."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.get(id="marketing")

        assert result.body["id"] == "marketing"
        assert result.body["name"] == "Marketing"

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"

    def test_get_space_not_found(self):
        """Test that getting a non-existent space raises NotFoundError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        mock_client.perform_request.side_effect = NotFoundError(
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

        with pytest.raises(NotFoundError):
            spaces_client.get(id="nonexistent")

    def test_get_space_missing_id(self):
        """Test that getting a space without id raises ValueError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            spaces_client.get(id="")


class TestSpacesClientGetAll:
    """Test SpacesClient get_all method."""

    def test_get_all_spaces(self):
        """Test getting all spaces."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.get_all()

        assert len(result.body) == 2
        assert result.body[0]["id"] == "default"
        assert result.body[1]["id"] == "marketing"

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space"

    def test_get_all_spaces_empty(self):
        """Test getting all spaces when none exist."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.get_all()

        assert len(result.body) == 0

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/spaces/space"


class TestSpacesClientUpdate:
    """Test SpacesClient update method."""

    def test_update_space_name(self):
        """Test updating a space's name."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.update(
            id="marketing",
            name="Marketing Team",
        )

        assert result.body["name"] == "Marketing Team"

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "PUT"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"
        assert call_args[1]["body"] == {"id": "marketing", "name": "Marketing Team"}

    def test_update_space_all_fields(self):
        """Test updating all fields of a space."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.update(
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
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
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

    def test_update_space_missing_id(self):
        """Test that updating a space without id raises ValueError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            spaces_client.update(id="", name="Marketing")

    def test_update_space_not_found(self):
        """Test that updating a non-existent space raises NotFoundError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        mock_client.perform_request.side_effect = NotFoundError(
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

        with pytest.raises(NotFoundError):
            spaces_client.update(id="nonexistent", name="New Name")


class TestSpacesClientDelete:
    """Test SpacesClient delete method."""

    def test_delete_space(self):
        """Test deleting a space."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

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
        mock_client.perform_request.return_value = mock_response

        result = spaces_client.delete(id="marketing")

        assert result.meta.status == 204

        # Verify the request was made correctly
        mock_client.perform_request.assert_called_once()
        call_args = mock_client.perform_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert call_args[1]["path"] == "/api/spaces/space/marketing"

    def test_delete_space_missing_id(self):
        """Test that deleting a space without id raises ValueError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            spaces_client.delete(id="")

    def test_delete_space_not_found(self):
        """Test that deleting a non-existent space raises NotFoundError."""
        mock_client = Mock()
        spaces_client = SpacesClient(mock_client)

        mock_client.perform_request.side_effect = NotFoundError(
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

        with pytest.raises(NotFoundError):
            spaces_client.delete(id="nonexistent")
