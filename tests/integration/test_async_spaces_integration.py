"""Integration tests for AsyncSpacesClient."""

import uuid

import pytest

from kibana.exceptions import BadRequestError, ConflictError, NotFoundError

from .utils import create_test_async_kibana_client, is_kibana_available

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
async def async_kibana_client():
    """Create an AsyncKibana client for testing with automatic configuration."""
    client = create_test_async_kibana_client(auth_method="auto")
    yield client
    await client.close()


@pytest.fixture
async def created_spaces():
    """Track spaces created during tests for automatic cleanup."""
    space_ids: list[str] = []
    yield space_ids

    # Cleanup: Delete all created spaces
    if space_ids:
        client = create_test_async_kibana_client()
        try:
            for space_id in space_ids:
                try:
                    await client.spaces.delete(id=space_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup space {space_id}: {e}")
        finally:
            await client.close()


@pytest.fixture
def unique_space_id():
    """Generate a unique space ID for testing."""
    return f"test-async-space-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_space_name():
    """Generate a unique space name for testing."""
    return f"Test Async Space {uuid.uuid4().hex[:8]}"


async def create_test_space(client, created_spaces, space_id, name, **kwargs):
    """
    Helper to create a space and track it for cleanup.

    :param client: AsyncKibana client
    :param created_spaces: List to track created space IDs
    :param space_id: Space ID
    :param name: Space name
    :param kwargs: Additional space properties
    :return: Created space data
    """
    response = await client.spaces.create(id=space_id, name=name, **kwargs)

    space = response.body
    # Track for cleanup
    created_spaces.append(space["id"])

    return space


class TestAsyncSpacesClientConnectivity:
    """Tests for basic AsyncSpacesClient connectivity."""

    @pytest.mark.asyncio
    async def test_spaces_client_exists(self, async_kibana_client):
        """Test that AsyncSpacesClient is accessible via the main client."""
        assert hasattr(async_kibana_client, "spaces")
        assert async_kibana_client.spaces is not None

    @pytest.mark.asyncio
    async def test_get_all_spaces(self, async_kibana_client):
        """Test getting all spaces."""
        response = await async_kibana_client.spaces.get_all()

        assert response.meta.status == 200
        assert isinstance(response.body, list)
        assert len(response.body) > 0

        # Default space should always exist
        default_space = next((s for s in response.body if s["id"] == "default"), None)
        assert default_space is not None
        assert default_space["name"] == "Default"

    @pytest.mark.asyncio
    async def test_get_default_space(self, async_kibana_client):
        """Test getting the default space."""
        response = await async_kibana_client.spaces.get(id="default")

        assert response.meta.status == 200
        space = response.body

        assert space["id"] == "default"
        assert space["name"] == "Default"
        assert "disabledFeatures" in space


class TestAsyncSpacesClientCRUD:
    """Tests for CRUD operations on spaces."""

    @pytest.mark.asyncio
    async def test_create_space_minimal(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test creating a space with minimal required fields."""
        space = await create_test_space(
            async_kibana_client, created_spaces, unique_space_id, unique_space_name
        )

        assert space["id"] == unique_space_id
        assert space["name"] == unique_space_name
        assert "disabledFeatures" in space
        assert isinstance(space["disabledFeatures"], list)

    @pytest.mark.asyncio
    async def test_create_space_with_all_fields(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test creating a space with all optional fields."""
        space = await create_test_space(
            async_kibana_client,
            created_spaces,
            unique_space_id,
            unique_space_name,
            description="Test async space description",
            color="#FF0000",
            initials="TA",
            disabled_features=["dev_tools"],
        )

        assert space["id"] == unique_space_id
        assert space["name"] == unique_space_name
        assert space["description"] == "Test async space description"
        assert space["color"] == "#FF0000"
        assert space["initials"] == "TA"
        assert "dev_tools" in space["disabledFeatures"]

    @pytest.mark.asyncio
    async def test_get_space_by_id(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test retrieving a space by ID."""
        # Create a space first
        created_space = await create_test_space(
            async_kibana_client, created_spaces, unique_space_id, unique_space_name
        )

        # Get the space
        response = await async_kibana_client.spaces.get(id=unique_space_id)

        assert response.meta.status == 200
        retrieved_space = response.body

        assert retrieved_space["id"] == created_space["id"]
        assert retrieved_space["name"] == created_space["name"]

    @pytest.mark.asyncio
    async def test_get_all_spaces_with_custom_space(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test getting all spaces when custom spaces exist."""
        # Create a space first
        await create_test_space(
            async_kibana_client, created_spaces, unique_space_id, unique_space_name
        )

        # Get all spaces
        response = await async_kibana_client.spaces.get_all()

        assert response.meta.status == 200
        spaces = response.body
        assert isinstance(spaces, list)
        assert len(spaces) > 1  # At least default + our space

        # Find our space in the list
        our_space = next((s for s in spaces if s["id"] == unique_space_id), None)
        assert our_space is not None
        assert our_space["name"] == unique_space_name

    @pytest.mark.asyncio
    async def test_update_space(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test updating a space."""
        # Create a space first
        await create_test_space(
            async_kibana_client, created_spaces, unique_space_id, unique_space_name
        )

        # Update the space
        new_name = f"{unique_space_name} Updated"
        new_description = "Updated async description"
        new_color = "#00FF00"

        response = await async_kibana_client.spaces.update(
            id=unique_space_id,
            name=new_name,
            description=new_description,
            color=new_color,
        )

        assert response.meta.status == 200
        updated_space = response.body

        assert updated_space["id"] == unique_space_id
        assert updated_space["name"] == new_name
        assert updated_space["description"] == new_description
        assert updated_space["color"] == new_color

        # Verify the update by getting the space
        get_response = await async_kibana_client.spaces.get(id=unique_space_id)
        assert get_response.body["name"] == new_name
        assert get_response.body["description"] == new_description
        assert get_response.body["color"] == new_color

    @pytest.mark.asyncio
    async def test_update_space_partial(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test partially updating a space (only name)."""
        # Create a space first
        original_space = await create_test_space(
            async_kibana_client,
            created_spaces,
            unique_space_id,
            unique_space_name,
            description="Original async description",
            color="#FF0000",
        )

        # Update only the name
        new_name = f"{unique_space_name} Partial Update"

        response = await async_kibana_client.spaces.update(
            id=unique_space_id, name=new_name
        )

        assert response.meta.status == 200
        updated_space = response.body

        assert updated_space["id"] == unique_space_id
        assert updated_space["name"] == new_name
        # Other fields should remain unchanged
        assert updated_space["description"] == original_space["description"]
        assert updated_space["color"] == original_space["color"]

    @pytest.mark.asyncio
    async def test_delete_space(
        self, async_kibana_client, unique_space_id, unique_space_name
    ):
        """Test deleting a space."""
        # Create a space first
        await async_kibana_client.spaces.create(
            id=unique_space_id, name=unique_space_name
        )

        # Delete the space
        response = await async_kibana_client.spaces.delete(id=unique_space_id)

        assert response.meta.status == 204

        # Verify it's deleted by trying to get it
        with pytest.raises(NotFoundError):
            await async_kibana_client.spaces.get(id=unique_space_id)


class TestAsyncSpacesClientErrorHandling:
    """Tests for error handling in AsyncSpacesClient."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_space(self, async_kibana_client):
        """Test that getting a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.spaces.get(id="nonexistent-space-12345")

        assert exc_info.value.status_code == 404
        assert exc_info.value.meta is not None
        assert exc_info.value.body is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_space(self, async_kibana_client):
        """Test that updating a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.spaces.update(
                id="nonexistent-space-12345", name="Updated Name"
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_space(self, async_kibana_client):
        """Test that deleting a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.spaces.delete(id="nonexistent-space-12345")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_space_with_duplicate_id(
        self, async_kibana_client, created_spaces, unique_space_id, unique_space_name
    ):
        """Test that creating a space with duplicate ID raises ConflictError."""
        # Create a space first
        await create_test_space(
            async_kibana_client, created_spaces, unique_space_id, unique_space_name
        )

        # Try to create another space with the same ID
        with pytest.raises(ConflictError) as exc_info:
            await async_kibana_client.spaces.create(
                id=unique_space_id, name="Different Name"
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_space_with_invalid_id(self, async_kibana_client):
        """Test that creating a space with invalid ID raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            await async_kibana_client.spaces.create(
                id="Invalid Space ID!",  # Spaces with special chars are invalid
                name="Test Space",
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_default_space(self, async_kibana_client):
        """Test that deleting the default space raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            await async_kibana_client.spaces.delete(id="default")

        assert exc_info.value.status_code == 400


class TestAsyncSpacesClientWithOptions:
    """Tests for AsyncSpacesClient with client options."""

    @pytest.mark.asyncio
    async def test_spaces_with_custom_timeout(self, async_kibana_client):
        """Test that AsyncSpacesClient works with custom timeout options."""
        # Create client with custom timeout
        client_with_timeout = async_kibana_client.options(request_timeout=60.0)

        # Should still be able to use spaces
        response = await client_with_timeout.spaces.get_all()
        assert response.meta.status == 200

    @pytest.mark.asyncio
    async def test_spaces_with_custom_headers(self, async_kibana_client):
        """Test that AsyncSpacesClient works with custom headers."""
        # Create client with custom headers
        client_with_headers = async_kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to use spaces
        response = await client_with_headers.spaces.get_all()
        assert response.meta.status == 200


class TestAsyncSpacesClientComplexScenarios:
    """Tests for complex scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_space_lifecycle_complete(
        self, async_kibana_client, unique_space_id, unique_space_name
    ):
        """Test complete space lifecycle: create -> get -> update -> delete."""
        # 1. Create
        create_response = await async_kibana_client.spaces.create(
            id=unique_space_id,
            name=unique_space_name,
            description="Async lifecycle test",
            color="#0000FF",
        )
        assert create_response.body["id"] == unique_space_id
        assert create_response.body["name"] == unique_space_name

        # 2. Get
        get_response = await async_kibana_client.spaces.get(id=unique_space_id)
        assert get_response.body["id"] == unique_space_id
        assert get_response.body["name"] == unique_space_name

        # 3. Update
        new_name = f"{unique_space_name} Updated"
        update_response = await async_kibana_client.spaces.update(
            id=unique_space_id, name=new_name, description="Updated async description"
        )
        assert update_response.body["name"] == new_name

        # 4. Delete
        delete_response = await async_kibana_client.spaces.delete(id=unique_space_id)
        assert delete_response.meta.status == 204

        # 5. Verify deletion
        with pytest.raises(NotFoundError):
            await async_kibana_client.spaces.get(id=unique_space_id)

    @pytest.mark.asyncio
    async def test_get_all_spaces_structure_validation(self, async_kibana_client):
        """Test that get_all returns properly structured data."""
        response = await async_kibana_client.spaces.get_all()

        assert response.meta.status == 200
        spaces = response.body
        assert isinstance(spaces, list)
        assert len(spaces) > 0

        # Validate structure of each space
        for space in spaces:
            assert isinstance(space, dict)
            assert "id" in space
            assert "name" in space
            assert "disabledFeatures" in space

            # ID should be a non-empty string
            assert isinstance(space["id"], str)
            assert len(space["id"]) > 0

            # Name should be a non-empty string
            assert isinstance(space["name"], str)
            assert len(space["name"]) > 0

            # disabledFeatures should be a list
            assert isinstance(space["disabledFeatures"], list)
