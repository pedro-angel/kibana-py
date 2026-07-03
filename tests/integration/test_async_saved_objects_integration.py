"""Integration tests for AsyncSavedObjectsClient."""

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
async def created_saved_objects():
    """Track saved objects created during tests for automatic cleanup."""
    saved_objects: list[tuple[str, str]] = []  # List of (type, id) tuples
    yield saved_objects

    # Cleanup: Delete all created saved objects
    if saved_objects:
        client = create_test_async_kibana_client()
        try:
            for obj_type, obj_id in saved_objects:
                try:
                    await client.saved_objects.delete(type=obj_type, id=obj_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(
                        f"Warning: Failed to cleanup saved object {obj_type}/{obj_id}: {e}"
                    )
        finally:
            await client.close()


@pytest.fixture
def unique_object_id():
    """Generate a unique saved object ID for testing."""
    return f"test-async-object-{uuid.uuid4().hex[:8]}"


async def create_test_saved_object(
    client, created_saved_objects, obj_type, obj_id, attributes, **kwargs
):
    """
    Helper to create a saved object and track it for cleanup.

    :param client: AsyncKibana client
    :param created_saved_objects: List to track created saved objects
    :param obj_type: Saved object type
    :param obj_id: Saved object ID
    :param attributes: Saved object attributes
    :param kwargs: Additional parameters
    :return: Created saved object data
    """
    response = await client.saved_objects.create(
        type=obj_type, id=obj_id, attributes=attributes, **kwargs
    )

    saved_object = response.body
    # Track for cleanup
    created_saved_objects.append((obj_type, saved_object["id"]))

    return saved_object


class TestAsyncSavedObjectsClientConnectivity:
    """Tests for basic AsyncSavedObjectsClient connectivity."""

    @pytest.mark.asyncio
    async def test_saved_objects_client_exists(self, async_kibana_client):
        """Test that AsyncSavedObjectsClient is accessible via the main client."""
        assert hasattr(async_kibana_client, "saved_objects")
        assert async_kibana_client.saved_objects is not None


class TestAsyncSavedObjectsClientCRUD:
    """Tests for CRUD operations on saved objects."""

    @pytest.mark.asyncio
    async def test_create_saved_object_with_id(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test creating a saved object with a specific ID."""
        attributes = {
            "title": "Test Async Config",
            "buildNum": 12345,
        }

        saved_object = await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        assert saved_object["id"] == unique_object_id
        assert saved_object["type"] == "config"
        assert saved_object["attributes"]["title"] == "Test Async Config"
        assert saved_object["attributes"]["buildNum"] == 12345

    @pytest.mark.asyncio
    async def test_create_saved_object_without_id(
        self, async_kibana_client, created_saved_objects
    ):
        """Test creating a saved object without specifying an ID (auto-generated)."""
        attributes = {
            "title": "Test Async Auto-ID Config",
            "buildNum": 54321,
        }

        response = await async_kibana_client.saved_objects.create(
            type="config", attributes=attributes
        )

        saved_object = response.body
        # Track for cleanup
        created_saved_objects.append(("config", saved_object["id"]))

        assert "id" in saved_object
        assert len(saved_object["id"]) > 0
        assert saved_object["type"] == "config"
        assert saved_object["attributes"]["title"] == "Test Async Auto-ID Config"

    @pytest.mark.asyncio
    async def test_get_saved_object(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test retrieving a saved object by type and ID."""
        # Create a saved object first
        attributes = {"title": "Test Async Get", "buildNum": 99999}
        created_object = await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        # Get the saved object
        response = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id
        )

        assert response.meta.status == 200
        retrieved_object = response.body

        assert retrieved_object["id"] == created_object["id"]
        assert retrieved_object["type"] == created_object["type"]
        assert retrieved_object["attributes"]["title"] == "Test Async Get"
        assert retrieved_object["attributes"]["buildNum"] == 99999

    @pytest.mark.asyncio
    async def test_update_saved_object(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test updating a saved object."""
        # Create a saved object first
        attributes = {"title": "Original Async Title", "buildNum": 11111}
        await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        # Update the saved object
        new_attributes = {"title": "Updated Async Title", "buildNum": 22222}

        response = await async_kibana_client.saved_objects.update(
            type="config", id=unique_object_id, attributes=new_attributes
        )

        assert response.meta.status == 200
        updated_object = response.body

        assert updated_object["id"] == unique_object_id
        assert updated_object["attributes"]["title"] == "Updated Async Title"
        assert updated_object["attributes"]["buildNum"] == 22222

        # Verify the update by getting the object
        get_response = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id
        )
        assert get_response.body["attributes"]["title"] == "Updated Async Title"
        assert get_response.body["attributes"]["buildNum"] == 22222

    @pytest.mark.asyncio
    async def test_delete_saved_object(self, async_kibana_client, unique_object_id):
        """Test deleting a saved object."""
        # Create a saved object first
        attributes = {"title": "Test Async Delete", "buildNum": 33333}
        await async_kibana_client.saved_objects.create(
            type="config", id=unique_object_id, attributes=attributes
        )

        # Delete the saved object
        response = await async_kibana_client.saved_objects.delete(
            type="config", id=unique_object_id
        )

        assert response.meta.status == 200

        # Verify it's deleted by trying to get it
        with pytest.raises(NotFoundError):
            await async_kibana_client.saved_objects.get(
                type="config", id=unique_object_id
            )


class TestAsyncSavedObjectsClientErrorHandling:
    """Tests for error handling in AsyncSavedObjectsClient."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_saved_object(self, async_kibana_client):
        """Test that getting a non-existent saved object raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.saved_objects.get(
                type="config", id="nonexistent-object-12345"
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.meta is not None
        assert exc_info.value.body is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_saved_object(self, async_kibana_client):
        """Test that updating a non-existent saved object raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.saved_objects.update(
                type="config",
                id="nonexistent-object-12345",
                attributes={"title": "Updated"},
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_saved_object(self, async_kibana_client):
        """Test that deleting a non-existent saved object raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await async_kibana_client.saved_objects.delete(
                type="config", id="nonexistent-object-12345"
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_saved_object_with_duplicate_id(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test that creating a saved object with duplicate ID raises ConflictError."""
        # Create a saved object first
        attributes = {"title": "First Async Object", "buildNum": 11111}
        await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        # Try to create another object with the same ID without overwrite
        with pytest.raises(ConflictError) as exc_info:
            await async_kibana_client.saved_objects.create(
                type="config",
                id=unique_object_id,
                attributes={"title": "Second Async Object", "buildNum": 22222},
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_saved_object_with_invalid_type(self, async_kibana_client):
        """Test that creating a saved object with invalid type raises BadRequestError."""
        with pytest.raises(BadRequestError) as exc_info:
            await async_kibana_client.saved_objects.create(
                type="invalid-type-that-does-not-exist",
                attributes={"title": "Test"},
            )

        assert exc_info.value.status_code == 400


class TestAsyncSavedObjectsClientOverwrite:
    """Tests for overwrite functionality."""

    @pytest.mark.asyncio
    async def test_create_saved_object_with_overwrite(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test creating a saved object with overwrite=True."""
        # Create a saved object first
        attributes1 = {"title": "First Async Version", "buildNum": 11111}
        await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes1,
        )

        # Create another object with the same ID and overwrite=True
        attributes2 = {"title": "Second Async Version", "buildNum": 22222}
        response = await async_kibana_client.saved_objects.create(
            type="config",
            id=unique_object_id,
            attributes=attributes2,
            overwrite=True,
        )

        assert response.meta.status == 200
        saved_object = response.body

        assert saved_object["id"] == unique_object_id
        assert saved_object["attributes"]["title"] == "Second Async Version"
        assert saved_object["attributes"]["buildNum"] == 22222

        # Verify by getting the object
        get_response = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id
        )
        assert get_response.body["attributes"]["title"] == "Second Async Version"


class TestAsyncSavedObjectsClientWithOptions:
    """Tests for AsyncSavedObjectsClient with client options."""

    @pytest.mark.asyncio
    async def test_saved_objects_with_custom_timeout(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test that AsyncSavedObjectsClient works with custom timeout options."""
        # Create client with custom timeout
        client_with_timeout = async_kibana_client.options(request_timeout=60.0)

        # Should still be able to create saved objects
        attributes = {"title": "Test Async Timeout", "buildNum": 99999}
        saved_object = await create_test_saved_object(
            client_with_timeout,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        assert saved_object["id"] == unique_object_id

    @pytest.mark.asyncio
    async def test_saved_objects_with_custom_headers(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test that AsyncSavedObjectsClient works with custom headers."""
        # Create client with custom headers
        client_with_headers = async_kibana_client.options(
            headers={"X-Custom-Header": "test-value"}
        )

        # Should still be able to create saved objects
        attributes = {"title": "Test Async Headers", "buildNum": 88888}
        saved_object = await create_test_saved_object(
            client_with_headers,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
        )

        assert saved_object["id"] == unique_object_id


class TestAsyncSavedObjectsClientComplexScenarios:
    """Tests for complex scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_saved_object_lifecycle_complete(
        self, async_kibana_client, unique_object_id
    ):
        """Test complete saved object lifecycle: create -> get -> update -> delete."""
        # 1. Create
        create_response = await async_kibana_client.saved_objects.create(
            type="config",
            id=unique_object_id,
            attributes={"title": "Async Lifecycle Test", "buildNum": 10000},
        )
        assert create_response.body["id"] == unique_object_id
        assert create_response.body["attributes"]["title"] == "Async Lifecycle Test"

        # 2. Get
        get_response = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id
        )
        assert get_response.body["id"] == unique_object_id
        assert get_response.body["attributes"]["title"] == "Async Lifecycle Test"

        # 3. Update
        update_response = await async_kibana_client.saved_objects.update(
            type="config",
            id=unique_object_id,
            attributes={"title": "Async Updated Lifecycle", "buildNum": 20000},
        )
        assert update_response.body["attributes"]["title"] == "Async Updated Lifecycle"

        # 4. Delete
        delete_response = await async_kibana_client.saved_objects.delete(
            type="config", id=unique_object_id
        )
        assert delete_response.meta.status == 200

        # 5. Verify deletion
        with pytest.raises(NotFoundError):
            await async_kibana_client.saved_objects.get(
                type="config", id=unique_object_id
            )

    @pytest.mark.asyncio
    async def test_saved_object_with_references(
        self, async_kibana_client, created_saved_objects, unique_object_id
    ):
        """Test creating a saved object with references."""
        # Create a saved object with references
        attributes = {"title": "Test Async References", "buildNum": 77777}
        references = [
            {"type": "index-pattern", "id": "test-pattern", "name": "testPattern"}
        ]

        saved_object = await create_test_saved_object(
            async_kibana_client,
            created_saved_objects,
            "config",
            unique_object_id,
            attributes,
            references=references,
        )

        assert saved_object["id"] == unique_object_id
        assert "references" in saved_object
        assert len(saved_object["references"]) == 1
        assert saved_object["references"][0]["type"] == "index-pattern"
        assert saved_object["references"][0]["id"] == "test-pattern"


class TestAsyncSavedObjectsClientSpaceSupport:
    """Tests for space support in AsyncSavedObjectsClient."""

    @pytest.fixture
    async def created_spaces(self):
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
    def unique_space_id(self):
        """Generate a unique space ID for testing."""
        return f"async-so-space-{uuid.uuid4().hex[:8]}"

    async def create_test_space(self, client, created_spaces, space_id, name, **kwargs):
        """
        Create a test space and track it for cleanup.

        :param client: AsyncKibana client
        :param created_spaces: List to track created spaces
        :param space_id: Space ID
        :param name: Space name
        :param kwargs: Additional space parameters
        :return: Created space data
        """
        response = await client.spaces.create(id=space_id, name=name, **kwargs)
        space = response.body
        created_spaces.append(space["id"])
        return space

    @pytest.mark.asyncio
    async def test_create_saved_object_in_space(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_object_id,
    ):
        """Test creating a saved object in a specific space."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async SO Test Space"
        )

        # Create saved object in the space
        attributes = {"title": "Test Async Space Object", "buildNum": 12345}
        response = await async_kibana_client.saved_objects.create(
            type="config",
            id=unique_object_id,
            attributes=attributes,
            space_id=unique_space_id,
        )

        saved_object = response.body
        assert saved_object["id"] == unique_object_id
        assert saved_object["attributes"]["title"] == "Test Async Space Object"

        # Verify object exists in the space
        retrieved = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id, space_id=unique_space_id
        )
        assert retrieved.body["id"] == unique_object_id

        # Verify object doesn't exist in default space
        with pytest.raises(NotFoundError):
            await async_kibana_client.saved_objects.get(
                type="config", id=unique_object_id
            )

        # Cleanup
        await async_kibana_client.saved_objects.delete(
            type="config", id=unique_object_id, space_id=unique_space_id
        )

    @pytest.mark.asyncio
    async def test_space_scoped_saved_objects_client(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_object_id,
    ):
        """Test async space-scoped saved objects client."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async SO Test Space"
        )

        # Create space-scoped client
        space_client = await async_kibana_client.space(unique_space_id)

        # Create saved object using space-scoped client
        attributes = {"title": "Test Async Space Scoped Object", "buildNum": 54321}
        response = await space_client.saved_objects.create(
            type="config", id=unique_object_id, attributes=attributes
        )

        saved_object = response.body
        assert saved_object["id"] == unique_object_id
        assert saved_object["attributes"]["title"] == "Test Async Space Scoped Object"

        # Verify object exists in the space
        retrieved = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id, space_id=unique_space_id
        )
        assert retrieved.body["id"] == unique_object_id

        # Cleanup using space-scoped client
        await space_client.saved_objects.delete(type="config", id=unique_object_id)

    @pytest.mark.asyncio
    async def test_saved_object_space_isolation(
        self,
        async_kibana_client,
        created_spaces,
        unique_object_id,
    ):
        """Test that saved objects in one space are not visible in another space."""
        # Create two test spaces
        space1_id = f"async-so-space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"async-so-space2-{uuid.uuid4().hex[:8]}"

        await self.create_test_space(
            async_kibana_client, created_spaces, space1_id, "Async SO Test Space 1"
        )
        await self.create_test_space(
            async_kibana_client, created_spaces, space2_id, "Async SO Test Space 2"
        )

        # Create saved object in space1
        attributes = {"title": "Test Async Space Isolation", "buildNum": 99999}
        response = await async_kibana_client.saved_objects.create(
            type="config",
            id=unique_object_id,
            attributes=attributes,
            space_id=space1_id,
        )

        saved_object = response.body
        assert saved_object["id"] == unique_object_id

        # Verify object exists in space1
        retrieved = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id, space_id=space1_id
        )
        assert retrieved.body["id"] == unique_object_id

        # Verify object doesn't exist in space2
        with pytest.raises(NotFoundError):
            await async_kibana_client.saved_objects.get(
                type="config", id=unique_object_id, space_id=space2_id
            )

        # Verify object doesn't exist in default space
        with pytest.raises(NotFoundError):
            await async_kibana_client.saved_objects.get(
                type="config", id=unique_object_id
            )

        # Cleanup
        await async_kibana_client.saved_objects.delete(
            type="config", id=unique_object_id, space_id=space1_id
        )

    @pytest.mark.asyncio
    async def test_update_saved_object_in_space(
        self,
        async_kibana_client,
        created_spaces,
        unique_space_id,
        unique_object_id,
    ):
        """Test updating a saved object in a specific space."""
        # Create test space
        await self.create_test_space(
            async_kibana_client, created_spaces, unique_space_id, "Async SO Test Space"
        )

        # Create saved object in the space
        attributes = {"title": "Original Async Space Title", "buildNum": 11111}
        await async_kibana_client.saved_objects.create(
            type="config",
            id=unique_object_id,
            attributes=attributes,
            space_id=unique_space_id,
        )

        # Update the saved object in the space
        new_attributes = {"title": "Updated Async Space Title", "buildNum": 22222}
        response = await async_kibana_client.saved_objects.update(
            type="config",
            id=unique_object_id,
            attributes=new_attributes,
            space_id=unique_space_id,
        )

        updated_object = response.body
        assert updated_object["id"] == unique_object_id
        assert updated_object["attributes"]["title"] == "Updated Async Space Title"

        # Verify update persisted
        retrieved = await async_kibana_client.saved_objects.get(
            type="config", id=unique_object_id, space_id=unique_space_id
        )
        assert retrieved.body["attributes"]["title"] == "Updated Async Space Title"

        # Cleanup
        await async_kibana_client.saved_objects.delete(
            type="config", id=unique_object_id, space_id=unique_space_id
        )
