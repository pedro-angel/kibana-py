"""Integration tests for space-scoped operations end-to-end with real Kibana."""

import uuid

import pytest

from kibana.exceptions import NotFoundError

from .utils import create_test_kibana_client, is_kibana_available, safe_delete_connector

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
                    client.spaces.delete(id=space_id)
                except Exception as e:
                    # Log but don't fail the test due to cleanup issues
                    print(f"Warning: Failed to cleanup space {space_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def created_connectors():
    """Track connectors created during tests for automatic cleanup."""
    connector_data: list[tuple[str, str | None]] = []  # (connector_id, space_id)
    yield connector_data

    # Cleanup: Delete all created connectors
    if connector_data:
        client = create_test_kibana_client()
        try:
            for connector_id, space_id in connector_data:
                try:
                    if space_id:
                        safe_delete_connector(client, connector_id)
                        # Also try space-scoped deletion
                        try:
                            client.actions.delete(id=connector_id, space_id=space_id)
                        except Exception:
                            pass
                    else:
                        safe_delete_connector(client, connector_id)
                except Exception as e:
                    print(f"Warning: Failed to cleanup connector {connector_id}: {e}")
        finally:
            client.close()


@pytest.fixture
def unique_space_id():
    """Generate a unique space ID for testing."""
    return f"test-space-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_connector_name():
    """Generate a unique connector name for testing."""
    return f"test-connector-{uuid.uuid4().hex[:8]}"


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


def create_test_connector(
    client,
    created_connectors,
    name,
    connector_type_id,
    config,
    secrets=None,
    space_id=None,
):
    """
    Create a test connector and track it for cleanup.

    :param client: Kibana client
    :param created_connectors: List to track created connectors
    :param name: Connector name
    :param connector_type_id: Connector type ID
    :param config: Connector configuration
    :param secrets: Connector secrets (optional)
    :param space_id: Space ID (optional)
    :return: Created connector data
    """
    response = client.actions.create(
        name=name,
        connector_type_id=connector_type_id,
        config=config,
        secrets=secrets,
        space_id=space_id,
    )
    connector = response.body
    created_connectors.append((connector["id"], space_id))
    return connector


class TestSpaceScopedConnectorOperations:
    """Test connector operations in different spaces."""

    def test_create_connectors_in_different_spaces(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test creating connectors in different spaces."""
        # Create two test spaces
        space1_id = f"space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"space2-{uuid.uuid4().hex[:8]}"

        create_test_space(kibana_client, created_spaces, space1_id, "Test Space 1")
        create_test_space(kibana_client, created_spaces, space2_id, "Test Space 2")

        # Create connector in space1
        connector1 = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-space1",
            connector_type_id=".server-log",
            config={},
            space_id=space1_id,
        )

        # Create connector in space2
        connector2 = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-space2",
            connector_type_id=".server-log",
            config={},
            space_id=space2_id,
        )

        # Create connector in default space
        connector3 = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-default",
            connector_type_id=".server-log",
            config={},
            # No space_id = default space
        )

        # Verify all connectors were created successfully
        assert connector1["name"] == f"{unique_connector_name}-space1"
        assert connector2["name"] == f"{unique_connector_name}-space2"
        assert connector3["name"] == f"{unique_connector_name}-default"

        # Verify connectors have different IDs
        assert connector1["id"] != connector2["id"]
        assert connector1["id"] != connector3["id"]
        assert connector2["id"] != connector3["id"]

    def test_space_isolation_connectors_not_visible_across_spaces(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test that connectors in one space are not visible in another space."""
        # Create two test spaces
        space1_id = f"space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"space2-{uuid.uuid4().hex[:8]}"

        create_test_space(kibana_client, created_spaces, space1_id, "Test Space 1")
        create_test_space(kibana_client, created_spaces, space2_id, "Test Space 2")

        # Create connector in space1
        connector1 = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-space1",
            connector_type_id=".server-log",
            config={},
            space_id=space1_id,
        )

        # Create connector in space2
        connector2 = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-space2",
            connector_type_id=".server-log",
            config={},
            space_id=space2_id,
        )

        # Verify connector1 exists in space1
        retrieved1 = kibana_client.actions.get(id=connector1["id"], space_id=space1_id)
        assert retrieved1.body["id"] == connector1["id"]
        assert retrieved1.body["name"] == f"{unique_connector_name}-space1"

        # Verify connector2 exists in space2
        retrieved2 = kibana_client.actions.get(id=connector2["id"], space_id=space2_id)
        assert retrieved2.body["id"] == connector2["id"]
        assert retrieved2.body["name"] == f"{unique_connector_name}-space2"

        # Verify connector1 is NOT visible in space2
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector1["id"], space_id=space2_id)

        # Verify connector2 is NOT visible in space1
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector2["id"], space_id=space1_id)

        # Verify connectors are NOT visible in default space
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(
                id=connector1["id"]
            )  # No space_id = default space

        with pytest.raises(NotFoundError):
            kibana_client.actions.get(
                id=connector2["id"]
            )  # No space_id = default space

    def test_get_all_connectors_space_scoped(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test that get_all returns only connectors from the specified space."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create connector in the space
        connector_in_space = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-in-space",
            connector_type_id=".server-log",
            config={},
            space_id=space_id,
        )

        # Create connector in default space
        connector_in_default = create_test_connector(
            kibana_client,
            created_connectors,
            name=f"{unique_connector_name}-in-default",
            connector_type_id=".server-log",
            config={},
        )

        # Get all connectors from the space
        space_connectors = kibana_client.actions.get_all(space_id=space_id)
        space_connector_ids = [c["id"] for c in space_connectors.body]

        # Get all connectors from default space
        default_connectors = kibana_client.actions.get_all()
        default_connector_ids = [c["id"] for c in default_connectors.body]

        # Verify space connector is only in space list
        assert connector_in_space["id"] in space_connector_ids
        assert connector_in_space["id"] not in default_connector_ids

        # Verify default connector is only in default list
        assert connector_in_default["id"] in default_connector_ids
        assert connector_in_default["id"] not in space_connector_ids

    def test_update_connector_in_space(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test updating a connector in a specific space."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create connector in the space
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            name=unique_connector_name,
            connector_type_id=".server-log",
            config={},
            space_id=space_id,
        )

        # Update the connector
        new_name = f"{unique_connector_name}-updated"
        updated = kibana_client.actions.update(
            id=connector["id"], name=new_name, space_id=space_id
        )

        assert updated.body["name"] == new_name
        assert updated.body["id"] == connector["id"]

        # Verify update persisted
        retrieved = kibana_client.actions.get(id=connector["id"], space_id=space_id)
        assert retrieved.body["name"] == new_name

    def test_execute_connector_in_space(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test executing a connector in a specific space."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create server-log connector in the space
        connector = create_test_connector(
            kibana_client,
            created_connectors,
            name=unique_connector_name,
            connector_type_id=".server-log",
            config={},
            space_id=space_id,
        )

        # Execute the connector
        execution_params = {
            "message": f"Test execution from space {space_id}",
            "level": "info",
        }

        result = kibana_client.actions.execute(
            id=connector["id"], params=execution_params, space_id=space_id
        )

        assert result.meta.status == 200
        assert result.body["status"] == "ok"

    def test_delete_connector_in_space(
        self, kibana_client, created_spaces, unique_connector_name
    ):
        """Test deleting a connector in a specific space."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create connector in the space (don't track for cleanup since we're testing deletion)
        connector_response = kibana_client.actions.create(
            name=unique_connector_name,
            connector_type_id=".server-log",
            config={},
            space_id=space_id,
        )
        connector_id = connector_response.body["id"]

        # Verify connector exists
        retrieved = kibana_client.actions.get(id=connector_id, space_id=space_id)
        assert retrieved.body["id"] == connector_id

        # Delete the connector
        try:
            delete_response = kibana_client.actions.delete(
                id=connector_id, space_id=space_id
            )
            # If we get a response, it should be successful
            if hasattr(delete_response, "meta"):
                assert delete_response.meta.status in [200, 204]
        except Exception:
            # DELETE may return empty response, which is acceptable
            pass

        # Verify connector is deleted
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector_id, space_id=space_id)


class TestSpaceScopedSavedObjectOperations:
    """Test saved object operations in different spaces."""

    def test_create_saved_objects_in_different_spaces(
        self, kibana_client, created_spaces
    ):
        """Test creating saved objects in different spaces."""
        # Create two test spaces
        space1_id = f"space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"space2-{uuid.uuid4().hex[:8]}"

        create_test_space(kibana_client, created_spaces, space1_id, "Test Space 1")
        create_test_space(kibana_client, created_spaces, space2_id, "Test Space 2")

        # Create saved object in space1
        obj1_response = kibana_client.saved_objects.create(
            type="config",
            attributes={"title": "Test Config 1", "description": "Config in space 1"},
            space_id=space1_id,
        )
        obj1 = obj1_response.body

        # Create saved object in space2
        obj2_response = kibana_client.saved_objects.create(
            type="config",
            attributes={"title": "Test Config 2", "description": "Config in space 2"},
            space_id=space2_id,
        )
        obj2 = obj2_response.body

        # Verify objects were created successfully
        assert obj1["attributes"]["title"] == "Test Config 1"
        assert obj2["attributes"]["title"] == "Test Config 2"
        assert obj1["id"] != obj2["id"]

        # Cleanup
        try:
            kibana_client.saved_objects.delete(
                type="config", id=obj1["id"], space_id=space1_id
            )
            kibana_client.saved_objects.delete(
                type="config", id=obj2["id"], space_id=space2_id
            )
        except Exception:
            pass

    def test_saved_object_space_isolation(self, kibana_client, created_spaces):
        """Test that saved objects in one space are not visible in another space."""
        # Create two test spaces
        space1_id = f"space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"space2-{uuid.uuid4().hex[:8]}"

        create_test_space(kibana_client, created_spaces, space1_id, "Test Space 1")
        create_test_space(kibana_client, created_spaces, space2_id, "Test Space 2")

        # Create saved object in space1
        obj_response = kibana_client.saved_objects.create(
            type="config",
            attributes={"title": "Test Config", "description": "Config in space 1"},
            space_id=space1_id,
        )
        obj = obj_response.body

        # Verify object exists in space1
        retrieved = kibana_client.saved_objects.get(
            type="config", id=obj["id"], space_id=space1_id
        )
        assert retrieved.body["id"] == obj["id"]

        # Verify object is NOT visible in space2
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(
                type="config", id=obj["id"], space_id=space2_id
            )

        # Verify object is NOT visible in default space
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(type="config", id=obj["id"])

        # Cleanup
        try:
            kibana_client.saved_objects.delete(
                type="config", id=obj["id"], space_id=space1_id
            )
        except Exception:
            pass


class TestSpaceScopedClientBehavior:
    """Test space-scoped client behavior with real operations."""

    def test_space_scoped_client_factory(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test space-scoped client factory and behavior."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create space-scoped client
        space_client = kibana_client.space(space_id)

        # Verify space-scoped client has correct context
        assert hasattr(space_client, "_space_id")
        assert space_client._space_id == space_id

        # Create connector using space-scoped client (no space_id parameter needed)
        connector = space_client.actions.create(
            name=unique_connector_name, connector_type_id=".server-log", config={}
        )
        created_connectors.append((connector.body["id"], space_id))

        # Verify connector was created in the correct space
        retrieved = kibana_client.actions.get(
            id=connector.body["id"], space_id=space_id
        )
        assert retrieved.body["id"] == connector.body["id"]

        # Verify connector is not visible in default space
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector.body["id"])

    def test_space_scoped_client_validation_on_creation(self, kibana_client):
        """Test that space-scoped client validates space exists on creation."""
        nonexistent_space_id = f"nonexistent-space-{uuid.uuid4().hex[:8]}"

        # This should raise SpaceNotFoundError during client creation
        with pytest.raises(Exception) as exc_info:
            kibana_client.space(nonexistent_space_id)

        # Should be a space-related error
        error_str = str(exc_info.value).lower()
        assert "not found" in error_str or "404" in error_str

    def test_space_scoped_client_validation_bypass(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test space-scoped client with validation disabled."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create space-scoped client with validation disabled
        space_client = kibana_client.space(space_id, validate=False)

        # Should work without validation
        connector = space_client.actions.create(
            name=unique_connector_name, connector_type_id=".server-log", config={}
        )
        created_connectors.append((connector.body["id"], space_id))

        # Verify connector was created successfully
        assert connector.body["name"] == unique_connector_name

    def test_space_scoped_client_override_space_id(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Test that space-scoped client can override space_id for individual operations."""
        # Create two test spaces
        space1_id = f"space1-{uuid.uuid4().hex[:8]}"
        space2_id = f"space2-{uuid.uuid4().hex[:8]}"

        create_test_space(kibana_client, created_spaces, space1_id, "Test Space 1")
        create_test_space(kibana_client, created_spaces, space2_id, "Test Space 2")

        # Create space-scoped client for space1
        space1_client = kibana_client.space(space1_id)

        # Create connector in space1 (using default space context)
        connector1 = space1_client.actions.create(
            name=f"{unique_connector_name}-space1",
            connector_type_id=".server-log",
            config={},
        )
        created_connectors.append((connector1.body["id"], space1_id))

        # Create connector in space2 (overriding space context)
        connector2 = space1_client.actions.create(
            name=f"{unique_connector_name}-space2",
            connector_type_id=".server-log",
            config={},
            space_id=space2_id,  # Override default space
        )
        created_connectors.append((connector2.body["id"], space2_id))

        # Verify connector1 is in space1
        retrieved1 = kibana_client.actions.get(
            id=connector1.body["id"], space_id=space1_id
        )
        assert retrieved1.body["id"] == connector1.body["id"]

        # Verify connector2 is in space2
        retrieved2 = kibana_client.actions.get(
            id=connector2.body["id"], space_id=space2_id
        )
        assert retrieved2.body["id"] == connector2.body["id"]

        # Verify cross-space isolation
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector1.body["id"], space_id=space2_id)

        with pytest.raises(NotFoundError):
            kibana_client.actions.get(id=connector2.body["id"], space_id=space1_id)

    def test_space_scoped_client_saved_objects(self, kibana_client, created_spaces):
        """Test space-scoped client with saved objects."""
        # Create test space
        space_id = f"test-space-{uuid.uuid4().hex[:8]}"
        create_test_space(kibana_client, created_spaces, space_id, "Test Space")

        # Create space-scoped client
        space_client = kibana_client.space(space_id)

        # Create saved object using space-scoped client
        obj_response = space_client.saved_objects.create(
            type="config",
            attributes={"title": "Test Config", "description": "Config in space"},
        )
        obj = obj_response.body

        # Verify object exists in the space
        retrieved = kibana_client.saved_objects.get(
            type="config", id=obj["id"], space_id=space_id
        )
        assert retrieved.body["id"] == obj["id"]

        # Verify object is not in default space
        with pytest.raises(NotFoundError):
            kibana_client.saved_objects.get(type="config", id=obj["id"])

        # Cleanup
        try:
            space_client.saved_objects.delete(type="config", id=obj["id"])
        except Exception:
            pass


class TestComplexSpaceScenarios:
    """Test complex scenarios involving multiple spaces and operations."""

    def test_multi_space_workflow(
        self, kibana_client, created_spaces, created_connectors
    ):
        """Test complex workflow involving multiple spaces."""
        # Create multiple spaces
        spaces = []
        for i in range(3):
            space_id = f"workflow-space-{i}-{uuid.uuid4().hex[:8]}"
            space = create_test_space(
                kibana_client, created_spaces, space_id, f"Workflow Space {i+1}"
            )
            spaces.append(space)

        # Create connectors in each space
        connectors = []
        for i, space in enumerate(spaces):
            connector = create_test_connector(
                kibana_client,
                created_connectors,
                name=f"workflow-connector-{i}",
                connector_type_id=".server-log",
                config={},
                space_id=space["id"],
            )
            connectors.append(connector)

        # Verify each connector exists only in its own space
        for i, (space, connector) in enumerate(zip(spaces, connectors)):
            # Verify connector exists in its space
            retrieved = kibana_client.actions.get(
                id=connector["id"], space_id=space["id"]
            )
            assert retrieved.body["id"] == connector["id"]

            # Verify connector doesn't exist in other spaces
            for j, other_space in enumerate(spaces):
                if i != j:
                    with pytest.raises(NotFoundError):
                        kibana_client.actions.get(
                            id=connector["id"], space_id=other_space["id"]
                        )

        # Execute connectors in their respective spaces
        for space, connector in zip(spaces, connectors):
            result = kibana_client.actions.execute(
                id=connector["id"],
                params={"message": f"Test from {space['name']}", "level": "info"},
                space_id=space["id"],
            )
            assert result.body["status"] == "ok"

    def test_space_migration_simulation(
        self, kibana_client, created_spaces, created_connectors, unique_connector_name
    ):
        """Simulate migrating resources between spaces."""
        # Create two spaces
        source_space_id = f"source-space-{uuid.uuid4().hex[:8]}"
        target_space_id = f"target-space-{uuid.uuid4().hex[:8]}"

        create_test_space(
            kibana_client, created_spaces, source_space_id, "Source Space"
        )
        create_test_space(
            kibana_client, created_spaces, target_space_id, "Target Space"
        )

        # Create connector in source space
        original_connector = create_test_connector(
            kibana_client,
            created_connectors,
            name=unique_connector_name,
            connector_type_id=".server-log",
            config={},  # Use empty config for server-log connector
            space_id=source_space_id,
        )

        # "Migrate" by creating equivalent connector in target space
        migrated_connector = create_test_connector(
            kibana_client,
            created_connectors,
            name=unique_connector_name,  # Same name
            connector_type_id=".server-log",
            config={},  # Use empty config for server-log connector
            space_id=target_space_id,
        )

        # Verify both connectors exist in their respective spaces
        source_retrieved = kibana_client.actions.get(
            id=original_connector["id"], space_id=source_space_id
        )
        target_retrieved = kibana_client.actions.get(
            id=migrated_connector["id"], space_id=target_space_id
        )

        assert source_retrieved.body["name"] == unique_connector_name
        assert target_retrieved.body["name"] == unique_connector_name
        assert source_retrieved.body["id"] != target_retrieved.body["id"]

        # Verify isolation is maintained
        with pytest.raises(NotFoundError):
            kibana_client.actions.get(
                id=original_connector["id"], space_id=target_space_id
            )

        with pytest.raises(NotFoundError):
            kibana_client.actions.get(
                id=migrated_connector["id"], space_id=source_space_id
            )
