"""Integration tests for SpacesClient."""

import uuid

import pytest

from kibana.exceptions import ConflictError, NotFoundError

from .utils import create_test_kibana_client, is_kibana_available

# Skip all integration tests if Kibana is not available
pytestmark = pytest.mark.skipif(
    not is_kibana_available(),
    reason="Kibana not available. Set KIBANA_URL or start elastic-start-local stack.",
)


@pytest.fixture
def kibana_client():
    """Create a Kibana client for testing with automatic configuration."""
    client = create_test_kibana_client(auth_method="auto")
    yield client
    client.close()


@pytest.fixture
def created_spaces():
    """Track spaces created during tests for automatic cleanup."""
    space_ids: list[str] = []
    yield space_ids

    # Cleanup: Delete all created spaces
    if space_ids:
        client = create_test_kibana_client()
        try:
            for space_id in space_ids:
                try:
                    safe_delete_space(client, space_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup space {space_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def unique_space_id():
    """Generate a unique space ID for testing."""
    return f"test-space-{uuid.uuid4().hex[:8]}"


def safe_delete_space(client, space_id: str) -> None:
    """
    Safely delete a space, handling errors.

    :param client: Kibana client
    :param space_id: ID of space to delete
    """
    try:
        client.spaces.delete(id=space_id)
    except NotFoundError:
        # Space already deleted or doesn't exist
        pass
    except Exception:
        # DELETE may return empty response, verify deletion by trying to get
        try:
            client.spaces.get(id=space_id)
            # If get succeeds, deletion failed
            raise AssertionError(f"Space {space_id} was not deleted")
        except NotFoundError:
            # Expected - space was deleted successfully
            pass


def create_test_space(client, created_spaces, space_id, name, **kwargs):
    """
    Create a test space and track it for cleanup.

    :param client: Kibana client
    :param created_spaces: List to track created spaces
    :param space_id: Space ID
    :param name: Space name
    :param kwargs: Additional space parameters
    :return: Created space data
    """
    response = client.spaces.create(id=space_id, name=name, **kwargs)
    space = response.body
    created_spaces.append(space["id"])
    return space


class TestSpacesClientCRUD:
    """Test basic CRUD operations for spaces."""

    def test_create_space_minimal(self, kibana_client, created_spaces, unique_space_id):
        """Test creating a space with minimal parameters."""
        space = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space",
        )

        assert space["id"] == unique_space_id
        assert space["name"] == "Test Space"
        assert "disabledFeatures" in space

    def test_create_space_with_all_parameters(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test creating a space with all optional parameters."""
        space = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Marketing Team",
            description="Space for marketing department",
            color="#FF0000",
            initials="MK",
            disabled_features=["dev_tools", "advancedSettings"],
        )

        assert space["id"] == unique_space_id
        assert space["name"] == "Marketing Team"
        assert space["description"] == "Space for marketing department"
        assert space["color"] == "#FF0000"
        assert space["initials"] == "MK"
        assert "dev_tools" in space["disabledFeatures"]
        assert "advancedSettings" in space["disabledFeatures"]

    def test_create_duplicate_space_raises_conflict(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test that creating a duplicate space raises ConflictError."""
        # Create first space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space",
        )

        # Try to create duplicate
        with pytest.raises(ConflictError):
            kibana_client.spaces.create(id=unique_space_id, name="Duplicate Space")

    def test_get_space(self, kibana_client, created_spaces, unique_space_id):
        """Test getting a space by ID."""
        # Create space
        created = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space",
            description="Test description",
        )

        # Get space
        response = kibana_client.spaces.get(id=unique_space_id)
        space = response.body

        assert space["id"] == created["id"]
        assert space["name"] == created["name"]
        assert space["description"] == created["description"]

    def test_get_nonexistent_space_raises_not_found(self, kibana_client):
        """Test that getting a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.spaces.get(id="nonexistent-space-id")

    def test_get_all_spaces(self, kibana_client, created_spaces, unique_space_id):
        """Test getting all spaces."""
        # Create a test space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space",
        )

        # Get all spaces
        response = kibana_client.spaces.get_all()
        spaces = response.body

        assert isinstance(spaces, list)
        assert len(spaces) > 0

        # Verify our test space is in the list
        space_ids = [space["id"] for space in spaces]
        assert unique_space_id in space_ids

        # Verify default space exists
        assert "default" in space_ids

    def test_update_space_name(self, kibana_client, created_spaces, unique_space_id):
        """Test updating a space's name."""
        # Create space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Original Name",
        )

        # Update name
        response = kibana_client.spaces.update(
            id=unique_space_id,
            name="Updated Name",
        )
        updated = response.body

        assert updated["id"] == unique_space_id
        assert updated["name"] == "Updated Name"

        # Verify update persisted
        response = kibana_client.spaces.get(id=unique_space_id)
        space = response.body
        assert space["name"] == "Updated Name"

    def test_update_space_all_fields(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test updating all fields of a space."""
        # Create space
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Original Name",
            description="Original description",
            color="#FF0000",
        )

        # Update all fields
        response = kibana_client.spaces.update(
            id=unique_space_id,
            name="Updated Name",
            description="Updated description",
            color="#00FF00",
            initials="UP",
            disabled_features=["dev_tools"],
        )
        updated = response.body

        assert updated["name"] == "Updated Name"
        assert updated["description"] == "Updated description"
        assert updated["color"] == "#00FF00"
        assert updated["initials"] == "UP"
        assert "dev_tools" in updated["disabledFeatures"]

    def test_update_nonexistent_space_raises_not_found(self, kibana_client):
        """Test that updating a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.spaces.update(
                id="nonexistent-space-id",
                name="New Name",
            )

    def test_delete_space(self, kibana_client, unique_space_id):
        """Test deleting a space."""
        # Create space (don't track for cleanup since we're testing deletion)
        kibana_client.spaces.create(id=unique_space_id, name="Test Space")

        # Delete space
        response = kibana_client.spaces.delete(id=unique_space_id)

        # Verify deletion (status code should be 204 or similar)
        assert response.meta.status in [200, 204]

        # Verify space no longer exists
        with pytest.raises(NotFoundError):
            kibana_client.spaces.get(id=unique_space_id)

    def test_delete_nonexistent_space_raises_not_found(self, kibana_client):
        """Test that deleting a non-existent space raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.spaces.delete(id="nonexistent-space-id")


class TestSpacesClientValidation:
    """Test parameter validation for SpacesClient."""

    def test_create_without_id_raises_error(self, kibana_client):
        """Test that creating a space without ID raises ValueError."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.spaces.create(id="", name="Test Space")

    def test_create_without_name_raises_error(self, kibana_client):
        """Test that creating a space without name raises ValueError."""
        with pytest.raises(ValueError, match="Parameter 'name' is required"):
            kibana_client.spaces.create(id="test-space", name="")

    def test_get_without_id_raises_error(self, kibana_client):
        """Test that getting a space without ID raises ValueError."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.spaces.get(id="")

    def test_update_without_id_raises_error(self, kibana_client):
        """Test that updating a space without ID raises ValueError."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.spaces.update(id="", name="Test")

    def test_delete_without_id_raises_error(self, kibana_client):
        """Test that deleting a space without ID raises ValueError."""
        with pytest.raises(ValueError, match="Parameter 'id' is required"):
            kibana_client.spaces.delete(id="")


class TestSpacesClientComplexScenarios:
    """Test complex scenarios and edge cases."""

    def test_create_update_delete_workflow(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test complete workflow: create, update, delete."""
        # Create
        space = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Initial Name",
            description="Initial description",
        )
        assert space["name"] == "Initial Name"

        # Update
        response = kibana_client.spaces.update(
            id=unique_space_id,
            name="Updated Name",
            description="Updated description",
        )
        updated = response.body
        assert updated["name"] == "Updated Name"

        # Delete
        kibana_client.spaces.delete(id=unique_space_id)
        created_spaces.remove(unique_space_id)  # Remove from cleanup list

        # Verify deletion
        with pytest.raises(NotFoundError):
            kibana_client.spaces.get(id=unique_space_id)

    def test_multiple_spaces_creation(self, kibana_client, created_spaces):
        """Test creating multiple spaces."""
        space_ids = [f"test-space-{uuid.uuid4().hex[:8]}" for _ in range(3)]

        # Create multiple spaces
        for i, space_id in enumerate(space_ids):
            create_test_space(
                kibana_client,
                created_spaces,
                space_id=space_id,
                name=f"Test Space {i + 1}",
            )

        # Verify all spaces exist
        response = kibana_client.spaces.get_all()
        all_spaces = response.body
        all_space_ids = [space["id"] for space in all_spaces]

        for space_id in space_ids:
            assert space_id in all_space_ids

    def test_space_with_special_characters_in_name(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test creating a space with special characters in name."""
        space = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space: Marketing & Sales (2024)",
            description="Space with special chars: @#$%",
        )

        assert space["name"] == "Test Space: Marketing & Sales (2024)"
        assert space["description"] == "Space with special chars: @#$%"

    def test_space_with_long_description(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test creating a space with a long description."""
        long_description = "A" * 500  # 500 character description

        space = create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Test Space",
            description=long_description,
        )

        assert space["description"] == long_description

    def test_update_space_partial_fields(
        self, kibana_client, created_spaces, unique_space_id
    ):
        """Test updating only some fields of a space."""
        # Create space with multiple fields
        create_test_space(
            kibana_client,
            created_spaces,
            space_id=unique_space_id,
            name="Original Name",
            description="Original description",
            color="#FF0000",
        )

        # Update only name
        response = kibana_client.spaces.update(
            id=unique_space_id,
            name="Updated Name",
        )
        updated = response.body

        assert updated["name"] == "Updated Name"
        # Other fields should remain unchanged
        assert updated["description"] == "Original description"
        assert updated["color"] == "#FF0000"
