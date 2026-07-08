"""Unit tests for AsyncSpacesClient."""

import pytest

from kibana._async.client import AsyncKibana
from kibana._async.client.spaces import AsyncSpacesClient
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


class TestAsyncSpacesClientInitialization:
    """Test AsyncSpacesClient initialization and wiring."""

    @pytest.mark.asyncio
    async def test_spaces_client_initialization(self, mock_async_transport):
        """Test that AsyncSpacesClient can be initialized with a parent client."""
        client = AsyncKibana(_transport=mock_async_transport)
        spaces_client = AsyncSpacesClient(client)
        assert spaces_client._client is client

    @pytest.mark.asyncio
    async def test_spaces_property_returns_spaces_client(self, mock_async_transport):
        """Test that client.spaces returns an AsyncSpacesClient instance."""
        client = AsyncKibana(_transport=mock_async_transport)
        assert isinstance(client.spaces, AsyncSpacesClient)


class TestAsyncSpacesClientCreate:
    """Test AsyncSpacesClient.create() method."""

    @pytest.mark.asyncio
    async def test_create_space_minimal(self, mock_async_transport, mock_response):
        """Test creating a space with only required parameters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_body(id="kbnpy-spaces-a", name="Test")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.create(id="kbnpy-spaces-a", name="Test")

        assert result.body["id"] == "kbnpy-spaces-a"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/space"
        assert call_kwargs["body"] == {"id": "kbnpy-spaces-a", "name": "Test"}
        # Kibana CSRF + JSON content-type headers are injected automatically
        assert call_kwargs["headers"]["kbn-xsrf"] == "true"
        assert call_kwargs["headers"]["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_space_with_all_parameters(
        self, mock_async_transport, mock_response
    ):
        """Test creating a space with the full 9.4.3 body surface."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.create(
            id="marketing",
            name="Marketing Team",
            description="Space for marketing analytics",
            color="#FF6B6B",
            initials="MK",
            image_url="data:image/png;base64,iVBOR",
            disabled_features=["ml", "apm"],
            solution="oblt",
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
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

    @pytest.mark.asyncio
    async def test_create_space_missing_id(self, mock_async_transport):
        """Test that an empty id raises ValueError before any request."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.spaces.create(id="", name="Test")
        mock_async_transport.perform_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_space_missing_name(self, mock_async_transport):
        """Test that an empty name raises ValueError before any request."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'name' is required"):
            await client.spaces.create(id="test", name="")
        mock_async_transport.perform_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_space_conflict(self, mock_async_transport, mock_response):
        """Test that a 409 response maps to ConflictError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 409,
                "error": "Conflict",
                "message": "A space with the identifier marketing already exists.",
            },
            status=409,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ConflictError):
            await client.spaces.create(id="marketing", name="Marketing")


class TestAsyncSpacesClientGet:
    """Test AsyncSpacesClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_space(self, mock_async_transport, mock_response):
        """Test retrieving a space by ID."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_body()
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.get(id="marketing")

        assert result.body["name"] == "Marketing Team"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"

    @pytest.mark.asyncio
    async def test_get_space_id_is_url_quoted(
        self, mock_async_transport, mock_response
    ):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.get(id="odd id?#/x")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%20id%3F%23%2Fx"

    @pytest.mark.asyncio
    async def test_get_space_not_found(self, mock_async_transport, mock_response):
        """Test that a 404 response maps to NotFoundError."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "statusCode": 404,
                "error": "Not Found",
                "message": "Saved object [space/nope] not found",
            },
            status=404,
        )

        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(NotFoundError):
            await client.spaces.get(id="nope")

    @pytest.mark.asyncio
    async def test_get_space_missing_id(self, mock_async_transport):
        """Test that an empty id raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.spaces.get(id="")


class TestAsyncSpacesClientGetAll:
    """Test AsyncSpacesClient.get_all() method."""

    @pytest.mark.asyncio
    async def test_get_all_spaces(self, mock_async_transport, mock_response):
        """Test retrieving all spaces without filters."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=[_space_body(), _space_body(id="default", name="Default")]
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.get_all()

        assert len(result.body) == 2
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["target"] == "/api/spaces/space"

    @pytest.mark.asyncio
    async def test_get_all_spaces_with_purpose(
        self, mock_async_transport, mock_response
    ):
        """Test the purpose query parameter is encoded."""
        mock_async_transport.perform_request.return_value = mock_response(body=[])

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.get_all(purpose="copySavedObjectsIntoSpace")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/spaces/space?purpose=copySavedObjectsIntoSpace"
        )

    @pytest.mark.asyncio
    async def test_get_all_spaces_with_include_authorized_purposes(
        self, mock_async_transport, mock_response
    ):
        """Test the include_authorized_purposes bool encodes as true/false."""
        mock_async_transport.perform_request.return_value = mock_response(body=[])

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.get_all(include_authorized_purposes=True)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert (
            call_kwargs["target"]
            == "/api/spaces/space?include_authorized_purposes=true"
        )


class TestAsyncSpacesClientUpdate:
    """Test AsyncSpacesClient.update() method."""

    @pytest.mark.asyncio
    async def test_update_space(self, mock_async_transport, mock_response):
        """Test a full-replace update sends id and name in the PUT body."""
        mock_async_transport.perform_request.return_value = mock_response(
            body=_space_body(name="Marketing & Sales")
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.update(
            id="marketing",
            name="Marketing & Sales",
            color="#00FF00",
            solution="es",
        )

        assert result.body["name"] == "Marketing & Sales"
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"
        assert call_kwargs["body"] == {
            "id": "marketing",
            "name": "Marketing & Sales",
            "color": "#00FF00",
            "solution": "es",
        }

    @pytest.mark.asyncio
    async def test_update_space_name_is_required(self, mock_async_transport):
        """Test that update() cannot be called without name (PUT is full replace)."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(TypeError):
            await client.spaces.update(id="marketing")  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="'name' is required"):
            await client.spaces.update(id="marketing", name="")
        mock_async_transport.perform_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_space_id_is_url_quoted(
        self, mock_async_transport, mock_response
    ):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.update(id="odd id", name="Odd")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%20id"

    @pytest.mark.asyncio
    async def test_update_space_missing_id(self, mock_async_transport):
        """Test that an empty id raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.spaces.update(id="", name="X")


class TestAsyncSpacesClientDelete:
    """Test AsyncSpacesClient.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_space(self, mock_async_transport, mock_response):
        """Test deleting a space."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.delete(id="marketing")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "DELETE"
        assert call_kwargs["target"] == "/api/spaces/space/marketing"

    @pytest.mark.asyncio
    async def test_delete_space_id_is_url_quoted(
        self, mock_async_transport, mock_response
    ):
        """Test that unsafe characters in the space id are percent-encoded."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.delete(id="odd/id")

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["target"] == "/api/spaces/space/odd%2Fid"

    @pytest.mark.asyncio
    async def test_delete_space_missing_id(self, mock_async_transport):
        """Test that an empty id raises ValueError."""
        client = AsyncKibana(_transport=mock_async_transport)
        with pytest.raises(ValueError, match="'id' is required"):
            await client.spaces.delete(id="")


class TestAsyncSpacesClientCopySavedObjects:
    """Test AsyncSpacesClient.copy_saved_objects() method."""

    @pytest.mark.asyncio
    async def test_copy_saved_objects_minimal(
        self, mock_async_transport, mock_response
    ):
        """Test copy with only the required body fields."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"target": {"success": True, "successCount": 1}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.copy_saved_objects(
            spaces=["target"],
            objects=[{"type": "dashboard", "id": "dash-1"}],
        )

        assert result.body["target"]["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_copy_saved_objects"
        assert call_kwargs["body"] == {
            "spaces": ["target"],
            "objects": [{"type": "dashboard", "id": "dash-1"}],
        }

    @pytest.mark.asyncio
    async def test_copy_saved_objects_with_options(
        self, mock_async_transport, mock_response
    ):
        """Test option kwargs map to the camelCase body fields."""
        mock_async_transport.perform_request.return_value = mock_response(body={})

        client = AsyncKibana(_transport=mock_async_transport)
        await client.spaces.copy_saved_objects(
            spaces=["a", "b"],
            objects=[{"type": "index-pattern", "id": "ip-1"}],
            include_references=True,
            create_new_copies=False,
            overwrite=True,
            compatibility_mode=False,
        )

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["body"] == {
            "spaces": ["a", "b"],
            "objects": [{"type": "index-pattern", "id": "ip-1"}],
            "includeReferences": True,
            "createNewCopies": False,
            "overwrite": True,
            "compatibilityMode": False,
        }


class TestAsyncSpacesClientResolveCopySavedObjectsErrors:
    """Test AsyncSpacesClient.resolve_copy_saved_objects_errors() method."""

    @pytest.mark.asyncio
    async def test_resolve_copy_errors(self, mock_async_transport, mock_response):
        """Test the retries/objects body and camelCase options."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={"target": {"success": True, "successCount": 1}}
        )

        client = AsyncKibana(_transport=mock_async_transport)
        retries = {"target": [{"type": "dashboard", "id": "dash-1", "overwrite": True}]}
        result = await client.spaces.resolve_copy_saved_objects_errors(
            retries=retries,
            objects=[{"type": "dashboard", "id": "dash-1"}],
            include_references=True,
            create_new_copies=False,
        )

        assert result.body["target"]["success"] is True
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_resolve_copy_saved_objects_errors"
        assert call_kwargs["body"] == {
            "retries": retries,
            "objects": [{"type": "dashboard", "id": "dash-1"}],
            "includeReferences": True,
            "createNewCopies": False,
        }


class TestAsyncSpacesClientDisableLegacyUrlAliases:
    """Test AsyncSpacesClient.disable_legacy_url_aliases() method."""

    @pytest.mark.asyncio
    async def test_disable_legacy_url_aliases(
        self, mock_async_transport, mock_response
    ):
        """Test the aliases body is sent as-is."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={}, status=204
        )

        client = AsyncKibana(_transport=mock_async_transport)
        aliases = [
            {
                "targetSpace": "marketing",
                "targetType": "dashboard",
                "sourceId": "legacy-id",
            }
        ]
        await client.spaces.disable_legacy_url_aliases(aliases=aliases)

        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_disable_legacy_url_aliases"
        assert call_kwargs["body"] == {"aliases": aliases}


class TestAsyncSpacesClientGetShareableReferences:
    """Test AsyncSpacesClient.get_shareable_references() method."""

    @pytest.mark.asyncio
    async def test_get_shareable_references(self, mock_async_transport, mock_response):
        """Test the objects body and response passthrough."""
        mock_async_transport.perform_request.return_value = mock_response(
            body={
                "objects": [
                    {"type": "dashboard", "id": "dash-1", "spaces": ["default"]}
                ]
            }
        )

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.get_shareable_references(
            objects=[{"type": "dashboard", "id": "dash-1"}]
        )

        assert result.body["objects"][0]["spaces"] == ["default"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_get_shareable_references"
        assert call_kwargs["body"] == {
            "objects": [{"type": "dashboard", "id": "dash-1"}]
        }


class TestAsyncSpacesClientUpdateObjectsSpaces:
    """Test AsyncSpacesClient.update_objects_spaces() method."""

    @pytest.mark.asyncio
    async def test_update_objects_spaces(self, mock_async_transport, mock_response):
        """Test the objects/spacesToAdd/spacesToRemove body mapping."""
        mock_async_transport.perform_request.return_value = mock_response(
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

        client = AsyncKibana(_transport=mock_async_transport)
        result = await client.spaces.update_objects_spaces(
            objects=[{"type": "dashboard", "id": "dash-1"}],
            spaces_to_add=["marketing"],
            spaces_to_remove=[],
        )

        assert result.body["objects"][0]["spaces"] == ["default", "marketing"]
        call_kwargs = mock_async_transport.perform_request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["target"] == "/api/spaces/_update_objects_spaces"
        assert call_kwargs["body"] == {
            "objects": [{"type": "dashboard", "id": "dash-1"}],
            "spacesToAdd": ["marketing"],
            "spacesToRemove": [],
        }
