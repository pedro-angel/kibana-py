"""Unit tests for SpacesClient."""

import pytest

from kibana._sync.client import Kibana
from kibana._sync.client.spaces import SpacesClient
from kibana.exceptions import ConflictError, NotFoundError


def _space_body(**overrides) -> dict:
    """A Kibana 9.4.3 space object response body."""
    body = {
        "id": "marketing",
        "name": "Marketing Team",
        "description": "Space for marketing analytics",
        "color": "#FF6B6B",
        "initials": "MK",
        "disabledFeatures": [],
        "solution": "classic",
    }
    body.update(overrides)
    return body


class TestSpacesClientInitialization:
    """Test SpacesClient initialization and wiring."""

    def test_spaces_client_initialization(self, mock_transport):
        """Test that SpacesClient can be initialized with a parent client."""
        client = Kibana(_transport=mock_transport)
        spaces_client = SpacesClient(client)
        assert spaces_client._client is client

    def test_spaces_property_returns_spaces_client(self, mock_transport):
        """Test that client.spaces returns a SpacesClient instance."""
        client = Kibana(_transport=mock_transport)
        assert isinstance(client.spaces, SpacesClient)


class TestSpacesClientCreate:
    """Test SpacesClient.create() method."""

    def test_create_space_minimal(self, mock_transport, mock_response):
        """Test creating a space with only required parameters."""
        mock_transport.perform_request.return_value = mock_response(
            body=_space_body(id="kbnpy-spaces-a", name="Test")
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.create(id="kbnpy-spaces-a", name="Test")

        assert result.body["id"] == "kbnpy-spaces-a"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/space"
        assert call_kwargs["body"] == {"id": "kbnpy-spaces-a", "name": "Test"}
        # Kibana CSRF + JSON content-type headers are injected automatically
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    def test_create_space_with_all_parameters(self, mock_transport, mock_response):
        """Test creating a space with the full 9.4.3 body surface."""
        mock_transport.perform_request.return_value = mock_response(body=_space_body())

        client = Kibana(_transport=mock_transport)
        client.spaces.create(
            id="marketing",
            name="Marketing Team",
            description="Space for marketing analytics",
            color="#FF6B6B",
            initials="MK",
            image_url="data:image/png;base64,iVBOR",
            disabled_features=["ml", "apm"],
            solution="oblt",
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "id": "marketing",
            "name": "Marketing Team",
            "description": "Space for marketing analytics",
            "color": "#FF6B6B",
            "initials": "MK",
            "imageUrl": "data:image/png;base64,iVBOR",
            "disabledFeatures": ["ml", "apm"],
            "solution": "oblt",
        }

    def test_create_space_missing_id(self, mock_transport):
        """Test that an empty id raises ValueError before any request."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.spaces.create(id="", name="Test")
        mock_transport.perform_request.assert_not_called()

    def test_create_space_missing_name(self, mock_transport):
        """Test that an empty name raises ValueError before any request."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'name' is required"):
            client.spaces.create(id="test", name="")
        mock_transport.perform_request.assert_not_called()

    def test_create_space_conflict(self, mock_transport, mock_response):
        """Test that a 409 response maps to ConflictError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 409,
                "error": "Conflict",
                "message": "A space with the identifier marketing already exists.",
            },
            status=409,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(ConflictError):
            client.spaces.create(id="marketing", name="Marketing")


class TestSpacesClientGet:
    """Test SpacesClient.get() method."""

    def test_get_space(self, mock_transport, mock_response):
        """Test retrieving a space by ID."""
        mock_transport.perform_request.return_value = mock_response(body=_space_body())

        client = Kibana(_transport=mock_transport)
        result = client.spaces.get(id="marketing")

        assert result.body["name"] == "Marketing Team"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"

    def test_get_space_id_is_url_quoted(self, mock_transport, mock_response):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.spaces.get(id="odd id?#/x")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%20id%3F%23%2Fx"

    def test_get_space_not_found(self, mock_transport, mock_response):
        """Test that a 404 response maps to NotFoundError."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [space/nope] not found",
            },
            status=404,
        )

        client = Kibana(_transport=mock_transport)
        with pytest.raises(NotFoundError):
            client.spaces.get(id="nope")

    def test_get_space_missing_id(self, mock_transport):
        """Test that an empty id raises ValueError."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.spaces.get(id="")


class TestSpacesClientGetAll:
    """Test SpacesClient.get_all() method."""

    def test_get_all_spaces(self, mock_transport, mock_response):
        """Test retrieving all spaces without filters."""
        mock_transport.perform_request.return_value = mock_response(
            body=[_space_body(), _space_body(id="default", name="Default")]
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.get_all()

        assert len(result.body) == 2
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/spaces/space"

    def test_get_all_spaces_with_purpose(self, mock_transport, mock_response):
        """Test the purpose query parameter is encoded."""
        mock_transport.perform_request.return_value = mock_response(body=[])

        client = Kibana(_transport=mock_transport)
        client.spaces.get_all(purpose="copySavedObjectsIntoSpace")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/spaces/space?purpose=copySavedObjectsIntoSpace"
        )

    def test_get_all_spaces_with_include_authorized_purposes(
        self, mock_transport, mock_response
    ):
        """Test the include_authorized_purposes bool encodes as true/false."""
        mock_transport.perform_request.return_value = mock_response(body=[])

        client = Kibana(_transport=mock_transport)
        client.spaces.get_all(include_authorized_purposes=True)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/spaces/space?include_authorized_purposes=true"
        )


class TestSpacesClientUpdate:
    """Test SpacesClient.update() method."""

    def test_update_space(self, mock_transport, mock_response):
        """Test a full-replace update sends id and name in the PUT body."""
        mock_transport.perform_request.return_value = mock_response(
            body=_space_body(name="Marketing & Sales")
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.update(
            id="marketing",
            name="Marketing & Sales",
            color="#00FF00",
            solution="es",
        )

        assert result.body["name"] == "Marketing & Sales"
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"
        assert call_kwargs["body"] == {
            "id": "marketing",
            "name": "Marketing & Sales",
            "color": "#00FF00",
            "solution": "es",
        }

    def test_update_space_name_is_required(self, mock_transport):
        """Test that update() cannot be called without name (PUT is full replace)."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(TypeError):
            client.spaces.update(id="marketing")  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="'name' is required"):
            client.spaces.update(id="marketing", name="")
        mock_transport.perform_request.assert_not_called()

    def test_update_space_id_is_url_quoted(self, mock_transport, mock_response):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.spaces.update(id="odd id", name="Odd")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%20id"

    def test_update_space_missing_id(self, mock_transport):
        """Test that an empty id raises ValueError."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.spaces.update(id="", name="X")


class TestSpacesClientDelete:
    """Test SpacesClient.delete() method."""

    def test_delete_space(self, mock_transport, mock_response):
        """Test deleting a space."""
        mock_transport.perform_request.return_value = mock_response(body={}, status=204)

        client = Kibana(_transport=mock_transport)
        client.spaces.delete(id="marketing")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"

    def test_delete_space_id_is_url_quoted(self, mock_transport, mock_response):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_transport.perform_request.return_value = mock_response(body={}, status=204)

        client = Kibana(_transport=mock_transport)
        client.spaces.delete(id="odd/id")

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%2Fid"

    def test_delete_space_missing_id(self, mock_transport):
        """Test that an empty id raises ValueError."""
        client = Kibana(_transport=mock_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            client.spaces.delete(id="")


class TestSpacesClientCopySavedObjects:
    """Test SpacesClient.copy_saved_objects() method."""

    def test_copy_saved_objects_minimal(self, mock_transport, mock_response):
        """Test copy with only the required body fields."""
        mock_transport.perform_request.return_value = mock_response(
            body={"target": {"success": True, "successCount": 1}}
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.copy_saved_objects(
            spaces=["target"],
            objects=[{"type": "dashboard", "id": "dash-1"}],
        )

        assert result.body["target"]["success"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_copy_saved_objects"
        assert call_kwargs["body"] == {
            "spaces": ["target"],
            "objects": [{"type": "dashboard", "id": "dash-1"}],
        }

    def test_copy_saved_objects_with_options(self, mock_transport, mock_response):
        """Test option kwargs map to the camelCase body fields."""
        mock_transport.perform_request.return_value = mock_response(body={})

        client = Kibana(_transport=mock_transport)
        client.spaces.copy_saved_objects(
            spaces=["a", "b"],
            objects=[{"type": "index-pattern", "id": "ip-1"}],
            include_references=True,
            create_new_copies=False,
            overwrite=True,
            compatibility_mode=False,
        )

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "spaces": ["a", "b"],
            "objects": [{"type": "index-pattern", "id": "ip-1"}],
            "includeReferences": True,
            "createNewCopies": False,
            "overwrite": True,
            "compatibilityMode": False,
        }


class TestSpacesClientResolveCopySavedObjectsErrors:
    """Test SpacesClient.resolve_copy_saved_objects_errors() method."""

    def test_resolve_copy_errors(self, mock_transport, mock_response):
        """Test the retries/objects body and camelCase options."""
        mock_transport.perform_request.return_value = mock_response(
            body={"target": {"success": True, "successCount": 1}}
        )

        client = Kibana(_transport=mock_transport)
        retries = {"target": [{"type": "dashboard", "id": "dash-1", "overwrite": True}]}
        result = client.spaces.resolve_copy_saved_objects_errors(
            retries=retries,
            objects=[{"type": "dashboard", "id": "dash-1"}],
            include_references=True,
            create_new_copies=False,
        )

        assert result.body["target"]["success"] is True
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_resolve_copy_saved_objects_errors"
        assert call_kwargs["body"] == {
            "retries": retries,
            "objects": [{"type": "dashboard", "id": "dash-1"}],
            "includeReferences": True,
            "createNewCopies": False,
        }


class TestSpacesClientDisableLegacyUrlAliases:
    """Test SpacesClient.disable_legacy_url_aliases() method."""

    def test_disable_legacy_url_aliases(self, mock_transport, mock_response):
        """Test the aliases body is sent as-is."""
        mock_transport.perform_request.return_value = mock_response(body={}, status=204)

        client = Kibana(_transport=mock_transport)
        aliases = [
            {
                "targetSpace": "marketing",
                "targetType": "dashboard",
                "sourceId": "legacy-id",
            }
        ]
        client.spaces.disable_legacy_url_aliases(aliases=aliases)

        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_disable_legacy_url_aliases"
        assert call_kwargs["body"] == {"aliases": aliases}


class TestSpacesClientGetShareableReferences:
    """Test SpacesClient.get_shareable_references() method."""

    def test_get_shareable_references(self, mock_transport, mock_response):
        """Test the objects body and response passthrough."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "objects": [
                    {"type": "dashboard", "id": "dash-1", "spaces": ["default"]}
                ]
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.get_shareable_references(
            objects=[{"type": "dashboard", "id": "dash-1"}]
        )

        assert result.body["objects"][0]["spaces"] == ["default"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_get_shareable_references"
        assert call_kwargs["body"] == {
            "objects": [{"type": "dashboard", "id": "dash-1"}]
        }


class TestSpacesClientUpdateObjectsSpaces:
    """Test SpacesClient.update_objects_spaces() method."""

    def test_update_objects_spaces(self, mock_transport, mock_response):
        """Test the objects/spacesToAdd/spacesToRemove body mapping."""
        mock_transport.perform_request.return_value = mock_response(
            body={
                "objects": [
                    {
                        "type": "dashboard",
                        "id": "dash-1",
                        "spaces": ["default", "marketing"],
                    }
                ]
            }
        )

        client = Kibana(_transport=mock_transport)
        result = client.spaces.update_objects_spaces(
            objects=[{"type": "dashboard", "id": "dash-1"}],
            spaces_to_add=["marketing"],
            spaces_to_remove=[],
        )

        assert result.body["objects"][0]["spaces"] == ["default", "marketing"]
        call_kwargs = mock_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_update_objects_spaces"
        assert call_kwargs["body"] == {
            "objects": [{"type": "dashboard", "id": "dash-1"}],
            "spacesToAdd": ["marketing"],
            "spacesToRemove": [],
        }
