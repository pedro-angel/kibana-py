#!/usr/bin/env python3
"""
Saved Objects Management Example

This comprehensive example demonstrates:
1. Creating saved objects with and without IDs
2. Retrieving saved objects
3. Updating saved objects with version control
4. Deleting saved objects
5. Working with saved objects in different spaces
6. Error handling and best practices

Run this example:
    python examples/saved_objects_management.py
"""

import json
import uuid

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_cleanup,
    should_enable_telemetry,
)

from kibana.exceptions import ConflictError, NotFoundError


class SavedObjectsManager:
    """Manager class for saved objects operations."""

    def __init__(self, client):
        """Initialize with a Kibana client."""
        self.client = client
        self.created_objects = []  # Track for cleanup

    def create_visualization(self, title, obj_id=None, space_id=None):
        """
        Create a visualization saved object.

        :param title: Title for the visualization
        :param obj_id: Optional ID (auto-generated if not provided)
        :param space_id: Optional space ID for space-scoped creation
        :return: Created saved object
        """
        import logging

        logger = logging.getLogger(__name__)

        print(f"\n📝 Creating visualization: {title}")

        attributes = {
            "title": title,
            "visState": json.dumps({"type": "line", "params": {}}),
            "uiStateJSON": "{}",
            "description": f"Visualization created via API: {title}",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": "", "filter": []})
            },
        }

        try:
            logger.info(
                "Creating visualization saved object",
                extra={
                    "title": title,
                    "object_id": obj_id,
                    "space_id": space_id,
                    "object_type": "visualization",
                    "operation": "create_saved_object",
                },
            )

            response = self.client.saved_objects.create(
                type="visualization",
                attributes=attributes,
                id=obj_id,
                space_id=space_id,
            )
            saved_object = response.body
            self.created_objects.append(
                (saved_object["type"], saved_object["id"], space_id)
            )

            print(f"✓ Created: {saved_object['id']}")
            if space_id:
                print(f"  Space: {space_id}")

            logger.info(
                "Visualization created successfully",
                extra={
                    "object_id": saved_object["id"],
                    "title": title,
                    "space_id": space_id,
                    "object_type": "visualization",
                    "operation": "create_saved_object",
                    "status": "success",
                },
            )

            return saved_object

        except ConflictError:
            print(f"❌ Object with ID '{obj_id}' already exists")
            logger.error(
                f"Object with ID '{obj_id}' already exists",
                extra={
                    "object_id": obj_id,
                    "title": title,
                    "space_id": space_id,
                    "object_type": "visualization",
                    "operation": "create_saved_object",
                    "status": "error",
                    "error_type": "ConflictError",
                },
            )
            raise
        except Exception as e:
            print(f"❌ Failed to create: {e}")
            logger.error(
                f"Failed to create visualization: {e}",
                extra={
                    "title": title,
                    "object_id": obj_id,
                    "space_id": space_id,
                    "object_type": "visualization",
                    "operation": "create_saved_object",
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            raise

    def get_visualization(self, obj_id, space_id=None):
        """
        Retrieve a visualization by ID.

        :param obj_id: Object ID
        :param space_id: Optional space ID
        :return: Retrieved saved object
        """
        print(f"\n🔍 Retrieving visualization: {obj_id}")

        try:
            response = self.client.saved_objects.get(
                type="visualization",
                id=obj_id,
                space_id=space_id,
            )
            saved_object = response.body

            print(f"✓ Retrieved: {saved_object['attributes']['title']}")
            print(f"  Version: {saved_object.get('version', 'N/A')}")
            return saved_object

        except NotFoundError:
            print(f"❌ Visualization not found: {obj_id}")
            raise
        except Exception as e:
            print(f"❌ Failed to retrieve: {e}")
            raise

    def update_visualization(self, obj_id, new_title, version=None, space_id=None):
        """
        Update a visualization's title.

        :param obj_id: Object ID
        :param new_title: New title
        :param version: Optional version for optimistic concurrency
        :param space_id: Optional space ID
        :return: Updated saved object
        """
        print(f"\n✏️  Updating visualization: {obj_id}")

        # Get current object to preserve other attributes
        current = self.get_visualization(obj_id, space_id)
        attributes = current["attributes"].copy()
        attributes["title"] = new_title

        try:
            response = self.client.saved_objects.update(
                type="visualization",
                id=obj_id,
                attributes=attributes,
                version=version,
                space_id=space_id,
            )
            updated = response.body

            print(f"✓ Updated: {updated['attributes']['title']}")
            print(f"  New version: {updated.get('version', 'N/A')}")
            return updated

        except ConflictError:
            print("❌ Version conflict - object was modified by another process")
            raise
        except NotFoundError:
            print(f"❌ Visualization not found: {obj_id}")
            raise
        except Exception as e:
            print(f"❌ Failed to update: {e}")
            raise

    def delete_visualization(self, obj_id, space_id=None):
        """
        Delete a visualization.

        :param obj_id: Object ID
        :param space_id: Optional space ID
        """
        print(f"\n🗑️  Deleting visualization: {obj_id}")

        try:
            self.client.saved_objects.delete(
                type="visualization",
                id=obj_id,
                space_id=space_id,
            )

            # Remove from tracking
            self.created_objects = [
                obj
                for obj in self.created_objects
                if not (obj[1] == obj_id and obj[2] == space_id)
            ]

            print(f"✓ Deleted: {obj_id}")

        except NotFoundError:
            print(f"❌ Visualization not found: {obj_id}")
            raise
        except Exception as e:
            print(f"❌ Failed to delete: {e}")
            raise

    def cleanup(self):
        """Clean up all created objects."""
        if not self.created_objects:
            return

        print(f"\n🧹 Cleaning up {len(self.created_objects)} object(s)...")
        for obj_type, obj_id, space_id in self.created_objects[:]:
            try:
                self.client.saved_objects.delete(
                    type=obj_type,
                    id=obj_id,
                    space_id=space_id,
                )
                print(f"✓ Deleted: {obj_id}")
            except Exception as e:
                print(f"⚠️  Failed to delete {obj_id}: {e}")


def main():
    # Print configuration information
    print_config_info()

    # Configure telemetry with production-ready error handling
    import logging

    logger = logging.getLogger(__name__)

    try:
        telemetry_enabled = should_enable_telemetry()
        traces_configured, logs_configured = configure_example_telemetry(
            enabled=telemetry_enabled,
            logs_enabled=telemetry_enabled,  # Enable log forwarding when telemetry is enabled
        )
        print_telemetry_info()

        # Set up automatic telemetry cleanup
        setup_telemetry_cleanup()

        if traces_configured or logs_configured:
            logger.info(
                "Saved objects management example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "saved_objects_management",
                },
            )
    except Exception as e:
        print(f"⚠️  Telemetry configuration failed: {e}")
        print("   Continuing without telemetry...")
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={
                "error_type": "telemetry_config_error",
                "example": "saved_objects_management",
            },
        )

    # Initialize Kibana client
    client = create_kibana_client()
    manager = SavedObjectsManager(client)

    try:
        print("=" * 80)
        print("SAVED OBJECTS MANAGEMENT DEMO")
        print("=" * 80)

        # 1. Create with auto-generated ID
        print("\n" + "=" * 80)
        print("1. CREATE WITH AUTO-GENERATED ID")
        print("=" * 80)
        viz1 = manager.create_visualization("Auto-Generated ID Visualization")

        # 2. Create with specific ID
        print("\n" + "=" * 80)
        print("2. CREATE WITH SPECIFIC ID")
        print("=" * 80)
        custom_id = f"custom-viz-{uuid.uuid4().hex[:8]}"
        viz2 = manager.create_visualization(
            "Custom ID Visualization",
            obj_id=custom_id,
        )

        # 3. Retrieve objects
        print("\n" + "=" * 80)
        print("3. RETRIEVE OBJECTS")
        print("=" * 80)
        manager.get_visualization(viz1["id"])
        manager.get_visualization(viz2["id"])

        # 4. Update without version (simple update)
        print("\n" + "=" * 80)
        print("4. UPDATE WITHOUT VERSION")
        print("=" * 80)
        manager.update_visualization(
            viz1["id"],
            "Updated Auto-Generated Visualization",
        )

        # 5. Update with version (optimistic concurrency)
        print("\n" + "=" * 80)
        print("5. UPDATE WITH VERSION (OPTIMISTIC CONCURRENCY)")
        print("=" * 80)
        current = manager.get_visualization(viz2["id"])
        manager.update_visualization(
            viz2["id"],
            "Updated Custom Visualization",
            version=current["version"],
        )

        # 6. Demonstrate version conflict
        print("\n" + "=" * 80)
        print("6. DEMONSTRATE VERSION CONFLICT")
        print("=" * 80)
        print("Attempting update with old version...")
        try:
            manager.update_visualization(
                viz2["id"],
                "This should fail",
                version=current["version"],  # Old version
            )
        except ConflictError:
            print("✓ Conflict detected as expected")

        # 7. Delete an object
        print("\n" + "=" * 80)
        print("7. DELETE OBJECT")
        print("=" * 80)
        manager.delete_visualization(viz1["id"])

        # 8. Verify deletion
        print("\n" + "=" * 80)
        print("8. VERIFY DELETION")
        print("=" * 80)
        print("Attempting to retrieve deleted object...")
        try:
            manager.get_visualization(viz1["id"])
        except NotFoundError:
            print("✓ Object not found as expected")

        # 9. Space-scoped operations (if space exists)
        print("\n" + "=" * 80)
        print("9. SPACE-SCOPED OPERATIONS (OPTIONAL)")
        print("=" * 80)
        print("Creating a test space...")
        try:
            space_id = f"test-space-{uuid.uuid4().hex[:8]}"
            client.spaces.create(
                id=space_id,
                name=f"Test Space {space_id}",
                description="Temporary space for saved objects demo",
            )
            print(f"✓ Created space: {space_id}")

            # Create object in space
            viz3 = manager.create_visualization(
                "Space-Scoped Visualization",
                space_id=space_id,
            )

            # Retrieve from space
            manager.get_visualization(viz3["id"], space_id=space_id)

            # Verify it's not in default space
            print("\nVerifying object is not in default space...")
            try:
                manager.get_visualization(viz3["id"])
            except NotFoundError:
                print("✓ Object not found in default space (as expected)")

            # Cleanup space
            print("\nCleaning up test space...")
            client.spaces.delete(id=space_id)
            print(f"✓ Deleted space: {space_id}")

        except Exception as e:
            print(f"⚠️  Space operations skipped: {e}")

        print("\n" + "=" * 80)
        print("DEMO COMPLETE")
        print("=" * 80)
        print("\n🎉 All operations completed successfully!")

        # Ask about cleanup
        print(
            f"\n{len(manager.created_objects)} object(s) were created during this demo."
        )
        if should_cleanup("Delete all created objects? (y/N): "):
            manager.cleanup()
            print("✓ Cleanup complete")
        else:
            print("✓ Objects kept")
            print("\nCreated objects:")
            for obj_type, obj_id, space_id in manager.created_objects:
                space_info = f" (space: {space_id})" if space_id else ""
                print(f"  - {obj_type}/{obj_id}{space_info}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
