"""Integration tests for SavedObjectsClient."""

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
def created_saved_objects():
    """Track saved objects created during tests for automatic cleanup."""
    saved_objects: list[tuple[str, str]] = []  # List of (type, id) tuples
    yield saved_objects

    # Cleanup: Delete all created saved objects
    if saved_objects:
        client = create_test_kibana_client()
        try:
            for obj_type, obj_id in saved_objects:
                try:
                    client.saved_objects.delete(type=obj_type, id=obj_id)
                    print(f"Cleaned up saved object: {obj_type}/{obj_id}")
                except NotFoundError:
                    # Object already deleted, that's fine
                    pass
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(
                        f"Warning: Failed to cleanup saved object {obj_type}/{obj_id}: {e}"
                    )
        finally:
            client.close()


@pytest.fixture
def unique_object_id():
    """Generate a unique object ID for testing."""
    return f"test-obj-{uuid.uuid4().hex[:8]}"


def get_test_visualization_attributes(title="Test Visualization"):
    """Get standard attributes for a test visualization."""
    return {
        "title": title,
        "visState": "{}",
        "uiStateJSON": "{}",
        "description": "",
        "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": "{}"},
    }


class TestSavedObjectsClientCRUD:
    """Test basic CRUD operations for saved objects."""

    def test_create_and_get_saved_object(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test creating and retrieving a saved object."""
        # Create a visualization saved object
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Test Viz"),
            id=unique_object_id,
        )
        created = response.body
        created_saved_objects.append((created["type"], created["id"]))

        # Verify creation
        assert created["id"] == unique_object_id
        assert created["type"] == "visualization"
        assert created["attributes"]["title"] == "Test Viz"
        assert "version" in created

        # Get the saved object
        response = kibana_client.saved_objects.get(
            type="visualization",
            id=unique_object_id,
        )
        retrieved = response.body

        # Verify retrieval
        assert retrieved["id"] == created["id"]
        assert retrieved["type"] == created["type"]
        assert retrieved["attributes"]["title"] == "Test Viz"

    def test_create_saved_object_auto_id(self, kibana_client, created_saved_objects):
        """Test creating a saved object with auto-generated ID."""
        # Create without specifying ID
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Auto ID Test"),
        )
        saved_object = response.body
        created_saved_objects.append((saved_object["type"], saved_object["id"]))

        # Verify the response has an auto-generated ID
        assert "id" in saved_object
        assert saved_object["type"] == "visualization"
        assert saved_object["attributes"]["title"] == "Auto ID Test"

    def test_create_with_overwrite(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test creating a saved object with overwrite."""
        # Create initial object
        response1 = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Initial"),
            id=unique_object_id,
        )
        obj1 = response1.body
        created_saved_objects.append((obj1["type"], obj1["id"]))

        # Create again with overwrite=True (should succeed)
        response2 = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Overwritten"),
            id=unique_object_id,
            overwrite=True,
        )
        obj2 = response2.body

        # Verify overwrite
        assert obj2["id"] == unique_object_id
        assert obj2["attributes"]["title"] == "Overwritten"
        assert obj2["version"] != obj1["version"]

    def test_create_conflict(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test that creating a duplicate raises ConflictError."""
        # Create initial object
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Initial"),
            id=unique_object_id,
        )
        obj = response.body
        created_saved_objects.append((obj["type"], obj["id"]))

        # Try to create again without overwrite (should fail)
        with pytest.raises(ConflictError):
            kibana_client.saved_objects.create(
                type="visualization",
                attributes=get_test_visualization_attributes("Duplicate"),
                id=unique_object_id,
                overwrite=False,
            )

    def test_update_saved_object(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test updating a saved object."""
        # Create object
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Original"),
            id=unique_object_id,
        )
        created = response.body
        created_saved_objects.append((created["type"], created["id"]))

        # Update the object
        response = kibana_client.saved_objects.update(
            type="visualization",
            id=unique_object_id,
            attributes=get_test_visualization_attributes("Updated"),
        )
        updated = response.body

        # Verify update
        assert updated["id"] == created["id"]
        assert updated["attributes"]["title"] == "Updated"
        assert updated["version"] != created["version"]

    def test_update_with_version(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test updating with version for optimistic concurrency."""
        # Create object
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Original"),
            id=unique_object_id,
        )
        created = response.body
        created_saved_objects.append((created["type"], created["id"]))

        # Update with correct version (should succeed)
        response = kibana_client.saved_objects.update(
            type="visualization",
            id=unique_object_id,
            attributes=get_test_visualization_attributes("Updated"),
            version=created["version"],
        )
        updated = response.body
        assert updated["attributes"]["title"] == "Updated"

        # Try to update with old version (should fail)
        with pytest.raises(ConflictError):
            kibana_client.saved_objects.update(
                type="visualization",
                id=unique_object_id,
                attributes=get_test_visualization_attributes("Failed Update"),
                version=created["version"],  # Old version
            )

    def test_delete_saved_object(
        self, kibana_client, created_saved_objects, unique_object_id
    ):
        """Test deleting a saved object."""
        # Create object
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("To Delete"),
            id=unique_object_id,
        )
        created = response.body
        created_saved_objects.append((created["type"], created["id"]))

        # Delete the object
        kibana_client.saved_objects.delete(
            type="visualization",
            id=unique_object_id,
        )

        # Verify deletion
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(
                type="visualization",
                id=unique_object_id,
            )

        # Remove from cleanup list
        created_saved_objects.remove(("visualization", unique_object_id))

    def test_get_not_found(self, kibana_client):
        """Test that getting a non-existent object raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(
                type="visualization",
                id="nonexistent-id",
            )

    def test_update_not_found(self, kibana_client):
        """Test that updating a non-existent object raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.update(
                type="visualization",
                id="nonexistent-id",
                attributes=get_test_visualization_attributes("Update"),
            )

    def test_delete_not_found(self, kibana_client):
        """Test that deleting a non-existent object raises NotFoundError."""
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.delete(
                type="visualization",
                id="nonexistent-id",
            )


class TestSavedObjectsClientSpaceScoped:
    """Test space-scoped saved object operations."""

    @pytest.fixture
    def test_space_id(self):
        """Generate a unique space ID for testing."""
        return f"test-space-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def test_space(self, kibana_client, test_space_id):
        """Create a test space for space-scoped operations."""
        # Create the space
        response = kibana_client.spaces.create(
            id=test_space_id,
            name=f"Test Space {test_space_id}",
            description="Space for saved objects integration tests",
        )
        space = response.body

        yield space

        # Cleanup: Delete the space
        try:
            kibana_client.spaces.delete(id=test_space_id)
            print(f"Cleaned up test space: {test_space_id}")
        except NotFoundError:
            pass
        except Exception as e:
            print(f"Warning: Failed to cleanup space {test_space_id}: {e}")

    def test_create_in_space(self, kibana_client, test_space, unique_object_id):
        """Test creating a saved object in a specific space."""
        space_id = test_space["id"]

        # Create object in the test space
        response = kibana_client.saved_objects.create(
            type="visualization",
            attributes=get_test_visualization_attributes("Space Test"),
            id=unique_object_id,
            space_id=space_id,
        )
        created = response.body

        # Verify creation
        assert created["id"] == unique_object_id

        # Verify we can retrieve it from the same space
        response = kibana_client.saved_objects.get(
            type="visualization",
            id=unique_object_id,
            space_id=space_id,
        )
        retrieved = response.body
        assert retrieved["id"] == unique_object_id

        # Verify it's NOT in the default space
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(
                type="visualization",
                id=unique_object_id,
            )

        # Cleanup
        kibana_client.saved_objects.delete(
            type="visualization",
            id=unique_object_id,
            space_id=space_id,
        )
